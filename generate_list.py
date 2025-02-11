import requests
import json
import shutil,time
import logging,traceback
import threading
from queue import Queue,Empty
import urllib.parse
from urllib.parse import quote,urlparse,urlunparse

import concurrent.futures
from onedrive_authorization_utils import (
    procure_new_tokens_from_user, load_access_token_from_file, save_access_token,
    load_refresh_token_from_file, BASE_URL, get_new_access_token_using_refresh_token
)

import config,utils

log = logging.getLogger(__name__)

# Thread-safe lock for shared resources
lock = utils.TimeoutLock()


def get_next_link(response_dict) -> str:
    return response_dict.get("@odata.nextLink")


def get_folder_endpoint(folder: str) -> str:
    if folder == "/me/drive/root:/":
        log.debug("Starting at OneDrive root folder")
        return f"{BASE_URL}/me/drive/root/children"
    return f"{BASE_URL}{quote(folder)}:/children"


def format_endpoint(endpoint: str) -> str:
    """Normalize and validate the endpoint URL to prevent 404 errors."""
    log.debug("endpoint in %s",endpoint)
    endpoint = endpoint.strip()  # Remove leading/trailing spaces
    decoded_url = urllib.parse.unquote(endpoint)  # Decode once
    attempts=0
    while decoded_url != endpoint and attempts<5:  # Check if further decoding is needed
        endpoint = decoded_url
        decoded_url = urllib.parse.unquote(endpoint)
        attempts += 1
    #Since # is a fragment identifier and isn't sent in HTTP requests, you need to encode it as %23 if you want it to be treated as part of the query string.   
    endpoint = endpoint.replace("#","%23")
    log.debug("endpoint out %s",endpoint)
    
    return endpoint

def fetch_folder_contents(endpoint: str, access_token: str):
    """Fetch folder contents with automatic endpoint validation and retry logic."""
    endpoint = format_endpoint(endpoint)  # Format the endpoint to avoid 404
    headers = {"Authorization": f"Bearer {access_token}"}
    attempts = 0

    while attempts < 3 and not config.stop_flag:
        try:
            response = requests.get(endpoint, headers=headers)
            response.encoding = "utf-8"
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if response is not None and response.status_code == 401:
                log.warning("Access token expired, refreshing...")
                access_token = get_new_access_token_using_refresh_token(load_refresh_token_from_file())
                save_access_token(access_token)
                config.accesstoken=access_token
                headers["Authorization"] = f"Bearer {access_token}"  # Update header with new token
            elif response is not None and response.status_code == 404:
                log.error(f"Error 404: The endpoint {endpoint} was not found. Check if the path is correct.")
                break  # Don't retry if the endpoint is invalid
            else:
                if attempts<2:
                    log.error(f"HTTP error {response.status_code}: {e}, attempt {attempts + 1}")
                else:
                    log.warning(f"HTTP error {response.status_code}: {e}, attempt {attempts + 1}")
               # break  # Stop retrying for non-recoverable HTTP errors (e.g., 403, 404)

        except requests.exceptions.RequestException as e:
            log.error(f"Request error: {e}, attempt {attempts + 1}")
        
        except Exception as e:
            log.error(f"Unexpected error: {e}, attempt {attempts + 1}")

        attempts += 1

    return None



def process_one_folder(access_token: str):
    try:
        folder_list = []
        file_list = []
        current_folder = config.folder_queue.get(True,3)
        endpoint = get_folder_endpoint(current_folder)
        log.debug(f"Processing folder: {current_folder}")  
        
        while endpoint and not config.stop_flag:
            content = fetch_folder_contents(endpoint, access_token)
            if not content:
                break
            
            for item in content.get("value", []):
                is_folder = "folder" in item
               # log.info(f"Adding {item['name']} from {current_folder} {'[FOLDER]' if is_folder else '[FILE]'}")
                try:
                    log.info(f"Adding %s from %s {'[FOLDER]' if is_folder else '[FILE]'}",item['name'].encode("utf-8"),current_folder)
                except Exception as exc:
                    log.error(f"Error when processing folder: {exc}")
                    break
                if is_folder:
                    folder_list.append(item)
                    config.folder_queue.put(item["parentReference"]["path"] + "/" + item["name"])
                else:
                    file_list.append(item)
                    log.debug(f"Adding file URL: {item.get('@microsoft.graph.downloadUrl', 'No URL')}")
            
            endpoint = get_next_link(content)
            
    except Empty:
        log.warning(f"Queue is empty")
        current_folder="No more folder to process"
        pass
            
    except Exception as exc:
        log.error(f"Error when processing folder: {exc}")
        
        
    return current_folder, folder_list, file_list


def process_folders(access_token: str):
    root_folder = f"/me/drive/root:{config.ONEDRIVEDIR_PATH}"
    config.folder_queue.put(root_folder)

    folder_list = []
    file_list = []

    log.debug(f"Starting from root folder: {root_folder}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS_GEN) as executor:
        futures = set()

        while (not config.folder_queue.empty() or futures) and not config.stop_flag:
            
            log.debug(f"Queue length %s",config.folder_queue.qsize())
            # Submit new folder tasks while workers are available
            while len(futures) < config.MAX_WORKERS_GEN and not config.folder_queue.empty() and not config.stop_flag:
                try:
                    log.debug(f"Submit new executor,len(futures) %s",len(futures))
                    future = executor.submit(process_one_folder, access_token)
                    futures.add(future)  # Track running futures
                except TimeoutError:
                    log.error('Time out submitting')
            try:
                # Process completed tasks (wait with timeout to avoid deadlock)
                done, futures = concurrent.futures.wait(futures, timeout=config.TIMEOUT, return_when=concurrent.futures.FIRST_COMPLETED)

                for future in done:
                        with lock.acquire_timeout(10) as lockresult:
                            if lockresult:
                                current_folder, new_folders, new_files = future.result()
                                folder_list.extend(new_folders)
                                file_list.extend(new_files)
                                config.status_str = f"Identifying files: \n{len(file_list)} files found so far,\n{config.folder_queue.qsize()} folders remaining"
                                log.debug(f"Processed folder: {current_folder}")
                            else:
                                raise Exception("Unable to acquire lock!")
                # Remove completed future
                futures.discard(future)
            except TimeoutError:
                log.error('Time out submitting')
            except Exception as exc:
                log.error(f"Error processing folder: {exc}")
                    
        # Final cleanup
        executor.shutdown(wait=True)

    config.status_str = f"Identification complete: {len(file_list)} files found."
    config.progress_num=0
    return file_list, folder_list



def generate_list_of_all_files_and_folders(access_token):
    
    
    file_list, folder_list = process_folders(access_token)
    
    log.info("Saving files")
    with open("file_list.json", "w", encoding="utf-8") as f:
        json.dump(file_list, f, indent=2)
    
    with open("folder_list.json", "w", encoding="utf-8") as f:
        json.dump(folder_list, f, indent=2)
    
    config.progress_num=0
    log.info("File and folder lists have been saved.")
    log.info(f"Total Files: {len(file_list)}, Total Folders: {len(folder_list)}")
    config.status_str = f"Identification complete: {len(file_list)} files found."
    config.progress_num=0
    log.info("Done.")

    
def find_folder_and_file_from_url(url):
    try:
        for item in config.file_list:
            if item["@microsoft.graph.downloadUrl"]==url:
                folder="/me"+item["parentReference"]["path"]
                file=item["name"]
                return get_folder_endpoint(folder),file,item["id"]
    except Exception as exc:
        log.error(f"Error finding endpoint: {exc}")
    return None,None
    
def refresh_download_url(url):
    access_token = config.accesstoken
    endpoint,file,fileid = find_folder_and_file_from_url(url)
    log.debug(f"{url} is file {file} ({fileid}) in folder {endpoint}")
    try:
        content=fetch_folder_contents(endpoint,access_token)
        for item in content.get("value", []):
            is_folder = "folder" in item
            if not is_folder and item["id"]==fileid:
                good_url=item["@microsoft.graph.downloadUrl"]
                return good_url     
    except Exception as exc:
        log.error(f"Error refreshing download url: {exc}")
        log.error("Traceback: %s", traceback.format_exc())
    return None