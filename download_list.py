import requests
import json
import logging
import traceback
import sys
import os
import time
import urllib.parse
import threading
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from dateutil import parser as datetimeparser
from onedrive_authorization_utils import load_access_token_from_file,load_refresh_token_from_file,get_new_access_token_using_refresh_token,save_access_token
from generate_list import refresh_download_url
from filedate import File

import config,utils

log = logging.getLogger(__name__)
lock = utils.TimeoutLock()
item_download_errors = []

def load_file_list() -> list:
    for attempt in range(config.MAX_RETRIES):
        try:
            with open("file_list.json", "r", encoding='utf8') as f:
                config.file_list=json.load(f)
                return config.file_list
        except Exception as e:
            log.warning(f"Error loading file list, attempt {attempt + 1}")
            time.sleep(2 ** attempt) 
    log.error(f"Error loading file list")
    return None


def download_file_by_url(url, local_file_path):
    access_token = config.accesstoken
    headers = {"Authorization": "Bearer " + access_token}
    #for attempt in range(config.MAX_RETRIES):
    try:
        r = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        r.raise_for_status()
        with open(local_file_path, 'wb') as f:
            f.write(r.content)
        return local_file_path
    except requests.exceptions.HTTPError as http_err:
        log.warning(f"HTTP error {http_err.response.status_code}: {http_err}")
        if http_err.response.status_code==401:
            with lock.acquire_timeout(3) as lockresult:
                if lockresult:
                    refresh_access_token=load_access_token_from_file()
                    if not refresh_access_token==access_token:
                        access_token=refresh_access_token
                        headers["Authorization"] = f"Bearer {access_token}"
                    else:
                        log.warning("Access token expired, refreshing...")
                        access_token = get_new_access_token_using_refresh_token(load_refresh_token_from_file())
                        save_access_token(access_token)
                        config.accesstoken=access_token
                        headers["Authorization"] = f"Bearer {access_token}"  # Update header with new token
                else:
                    raise Exception("Unable to acquire lock!")
        if http_err.response.status_code==404:
            new_url=refresh_download_url(url)
            log.info(f"Trying refreshed url {new_url}")
            if not new_url==url:
                result=download_file_by_url(new_url,local_file_path)
                if result:
                    return result
        log.error(f"HTTP Error {http_err} for url {url}")                             
    except requests.exceptions.RequestException as e:
        log.error(f"Request attempt {attempt + 1} failed for {url}: {e}")
    except Exception as e:
        log.error(f"Error processing {filename.encode('utf-8')}")
        log.error("Traceback: %s", traceback.format_exc())
    config.num_error+=1
    if config.num_error > config.MAX_ERRORS:
        config.stop_flag=True
    return None

def ensure_local_path_exists(local_path):
    Path(local_path).mkdir(parents=True, exist_ok=True)

def get_local_download_folder_by_item(item) -> str:
    master_parent_folder_name = "/drive/root:"
    local_folder_path = item["parentReference"]["path"].replace(master_parent_folder_name, "")
    local_folder_path = urllib.parse.unquote(local_folder_path)  # Decode URL-encoded characters
    return f"{config.OFFLINEBACKUP_PATH}{local_folder_path}"


def to_utc_aware(dt):
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        local_timestamp = time.mktime(dt.timetuple())
        return datetime.fromtimestamp(local_timestamp, tz=timezone.utc)
    return dt.astimezone(timezone.utc)


def update_file_dates(file_path, item):
    iso_modifieddate=item["lastModifiedDateTime"]
    dt_md = to_utc_aware(datetimeparser.isoparse(iso_modifieddate))
    #timestamp = dt.timestamp()
    iso_creationdate=item["createdDateTime"]
    dt_cd=to_utc_aware(datetimeparser.isoparse(iso_creationdate))
    try:
        file = File(file_path)
        file.set(created=dt_cd, modified=dt_md)
    except Exception as e:
        log.error(f"Failed to update creation date : {e}")
    log.debug(f"File {file_path.encode('utf-8')} dates set to {iso_modifieddate}")

def is_file_changed(item, local_file_path):
    file_path = Path(local_file_path)
    if not file_path.exists():
        return True
    item_last_modified = to_utc_aware(datetime.fromisoformat(item["lastModifiedDateTime"]))
    file_size = file_path.stat().st_size
    file_last_modified = to_utc_aware(datetime.fromtimestamp(file_path.stat().st_mtime))
    delta_sec = (file_last_modified - item_last_modified).total_seconds()
    return not (item["size"] == file_size and abs(delta_sec) < 60)


def process_item(item):
    try:
        
        config.status_str="Downloading in progress\nFile "+str(config.progress_num)+"/"+str(config.progress_tot)
        download_url = item["@microsoft.graph.downloadUrl"]
        filename = urllib.parse.unquote(item["name"],encoding='utf-8')  # Decode URL-encoded filename
       # filename = filename.encode('utf-8')
        log.debug(f"Processing {filename.encode('utf-8')}")
        local_folder_path = get_local_download_folder_by_item(item)
        local_file_path = os.path.join(local_folder_path, filename)
        ensure_local_path_exists(local_folder_path)
        if is_file_changed(item, local_file_path):
            downloaded_file = download_file_by_url(download_url, local_file_path)
            if downloaded_file:
                update_file_dates(local_file_path, item)
                log.info(f"Downloaded: {local_file_path.encode('utf-8')}")
            else:
                item_download_errors.append(item)
        else:
            log.info(f"Unchanged: {filename.encode('utf-8')}")
        config.progress_num += 1

    except Exception as e:
        #log.error(f"Error processing {item['name']}: {e}")
        log.error(f"Error processing {filename.encode('utf-8')}")
        log.error("Traceback: %s", traceback.format_exc())
        item_download_errors.append(item)

def safe_submit(executor, func, item):
    """Submit a task only if there is enough disk space and stop_flag is False."""
    if config.stop_flag:
        log.warning("Stop flag is set. Skipping new downloads.")
        return None  # Prevent new tasks from being submitted
    
    if not utils.has_enough_space(get_local_download_folder_by_item(item)):
        log.error("Low disk space. Stopping downloads...")
        config.stop_flag = True  # Set the stop flag to prevent further submissions
        return None
    
    return executor.submit(func, item)

def download_the_list_of_files():
    log.info("Download process Started.")
    config.status_str = "Downloads start"
    items = load_file_list()

    if not items or len(items) == 0:
        log.error("No items in file")
        return

    config.progress_tot = len(items)
    config.progress_num = 0
    log.info("Starting download of %s file(s).", len(items))
    log.debug("First one is %s", get_local_download_folder_by_item(items[0]))

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        try:
            futures = {}
            index = 0
            while index < len(items) and not config.stop_flag:
                item = items[index]
                future = safe_submit(executor, process_item, item)
                if future:
                    futures[future] = item
                index += 1
            for future in as_completed(futures):
                if config.stop_flag:
                    log.warning("Stop flag detected. Cancelling remaining downloads.")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    future.result()
                except Exception as e:
                    log.error(f"Error in download executor: {e}")
                    log.error("Traceback: %s", traceback.format_exc())
        except Exception as e:
            log.error(f"Unexpected error during download process: {e}")
    
    if item_download_errors:
        with open('item_download_errors.json', 'w', encoding="utf8") as f:
            json.dump(item_download_errors, f, indent=2)
        log.info("Errors logged in item_download_errors.json.")
    
    log.debug(f"config.restart {config.restart}") 
    
    log.info("Download process completed.")
    if config.stop_flag:
        config.status_str = "Downloads ended due to stop_flag"
    else:
        config.status_str = "Downloads completed"
    config.progress_num = 0
        

if __name__ == "__main__":
    download_the_list_of_files()
