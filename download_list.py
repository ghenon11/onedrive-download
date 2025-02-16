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
from contextlib import closing

import config,utils

log = logging.getLogger(__name__)
lock_download = threading.Lock()

# TO DO check item_download_errors and add lock


def load_file_list(perror) -> list:
    if perror==1:
        filelist="item_download_errors.json"
    else:
        filelist="file_list.json"
    log.info(f"Loading {filelist}")
    for attempt in range(config.MAX_RETRIES):
        try:
            with open(filelist, "r", encoding='utf8') as f:
                config.file_list=json.load(f)
                log.debug(f"config.file_list length is {len(config.file_list)}")
                return config.file_list
        except Exception as e:
            log.warning(f"Error loading file list, attempt {attempt + 1}")
            time.sleep( 3 * attempt) 
    log.error(f"Error loading file list")
    return None

def refresh_url_from_fileid(fileid):
    download_url=None
    try:
        headers = {"Authorization": "Bearer " + config.accesstoken}
        url=f"https://graph.microsoft.com/v1.0/me/drive/items/{fileid}"
        response = requests.get(url, headers=headers)
        data = response.json()
        download_url=data.get('@microsoft.graph.downloadUrl')
    except Exception as e:
        log.error(f"Error checking {fileid}")
        log.error("Traceback: %s", traceback.format_exc())
    return download_url

def download_file_by_url(url, local_file_path, item):
    access_token = config.accesstoken
    headers = {"Authorization": "Bearer " + access_token}
    
    if not url:
        return None
    
    filesize = item["size"]
    fileid = item["id"]
    
    try:
        if filesize < 100*1024*1024:  # Small files (<100MB) downloaded in one go
            r = requests.get(url, headers=headers, allow_redirects=True, timeout=3)
            r.raise_for_status()
            with open(local_file_path, 'wb') as f:
                f.write(r.content)
        else:
            log.info("Big file identified, downloading in chunks")
                        
            downloaded_size = 0
            chunk_size = 10*1024 * 1024  # 10MB
            log_interval = filesize / 100  # Log every 1% of the total size
            next_log_threshold = log_interval  # First log threshold
            
            response=requests.get(url, stream=True, headers=headers, allow_redirects=True, timeout=10)
            response.raise_for_status()
            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Log progress at every 1% increment
                        if downloaded_size >= next_log_threshold:
                            with lock_download:
                                index=next((i for i, entry in enumerate(config.downloadinprogress) if entry["id"] == fileid), None)
                                config.downloadinprogress[index]["downloaded"]=downloaded_size
                            next_log_threshold += log_interval  # Update next threshold

        return local_file_path

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 404:
            log.warning(f"HTTP error {http_err.response.status_code}: {http_err}")
            new_url = refresh_download_url(url)
            if new_url and new_url != url:
                log.info(f"Trying refreshed URL {new_url}")
                return download_file_by_url(new_url, local_file_path, item)
        else:
            log.error(f"HTTP Error {http_err}")
    
    except requests.exceptions.RequestException as e:
        log.error(f"Request failed for {url}: {e}")
    
    except Exception as e:
        log.error(f"Error processing {local_file_path.encode('utf-8')}")
        log.error("Traceback: %s", traceback.format_exc())
        config.num_error += 1

    return None

def ensure_local_path_exists(local_path):
    Path(local_path).mkdir(parents=True, exist_ok=True)

def get_local_download_folder_by_item(item) -> str:
    master_parent_folder_name = "/drive/root:"
    local_folder_path = item["parentReference"]["path"].replace(master_parent_folder_name, "")
    local_folder_path = urllib.parse.unquote(local_folder_path)  # Decode URL-encoded characters
    return f"{config.OFFLINEBACKUP_PATH}{local_folder_path}"

def get_onedrive_path_by_item(item) -> str:
    master_parent_folder_name = "/drive/root:"
    onedrive_folder_path = item["parentReference"]["path"].replace(master_parent_folder_name, "")
    onedrive_folder_path = urllib.parse.unquote(onedrive_folder_path)  # Decode URL-encoded characters
    return f"{onedrive_folder_path}"

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

def is_file_excluded(exclusion_list,filepath):
    if not exclusion_list:
        return False
    filepath=filepath.lower()
    return any(substring.lower() in filepath for substring in exclusion_list)

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
        filename = "To Be Set"
        config.status_str = f"Files processed: {config.progress_num} of {config.progress_tot}"
        if config.progress_num % 100 == 0:  # Only update every 100 files
            log.info(config.status_str)
        
        filetype=item.get('file',{}).get('mimeType','Unknown type')
        filecreatedby=item["createdBy"]["application"]["displayName"]
        fileid = item["id"]
        download_url = item.get('@microsoft.graph.downloadUrl')
        filename = urllib.parse.unquote(item["name"], encoding='utf-8')
        filename_enc = filename.encode('utf-8')
        onedrivefilepath = item["parentReference"]["path"]
        filepath = os.path.join(get_onedrive_path_by_item(item), filename)
        filepath = os.path.normpath(filepath)
        
        log.info(f"Processing {filename_enc}({fileid}) of type {filetype} in {onedrivefilepath}")
        
        if filecreatedby=="Office.OneNote":
            log.warning(f"Office OneNote files cannot be downloaded !")
        else:
            if is_file_excluded(config.exclusion_list, filepath):
                log.info(f"{filename_enc} excluded")
            else:
                local_folder_path = get_local_download_folder_by_item(item)
                local_file_path = os.path.join(local_folder_path, filename)
                ensure_local_path_exists(local_folder_path)
                
                if is_file_changed(item, local_file_path):
                    log.debug(f"Downloading {filename.encode('utf-8')}")
                    
                    with lock_download:  # Ensuring thread safety
                        config.downloadinprogress.append(item)
                    
                    filesizemb = item["size"] / 1024 / 1024
                    if filesizemb > 100:
                        log.info(f"Processing file {filename_enc} of {int(filesizemb)}Mb")
                    
                    downloaded_file = download_file_by_url(download_url, local_file_path,item)
                    
                    with lock_download:  # Ensuring thread safety
                        config.downloadinprogress = [entry for entry in config.downloadinprogress if entry["id"] != fileid]
                    
                    if downloaded_file:
                        update_file_dates(local_file_path, item)
                        local_file_path = os.path.normpath(local_file_path)
                        log.info(f"Downloaded: {local_file_path.encode('utf-8')}")
                    else:
                        with lock_download:  # Ensuring thread safety
                            config.item_download_errors.append(item)
                            config.num_error += 1
                else:
                    log.info(f"Unchanged: {filename_enc}")
                
        config.progress_num += 1
    
    except Exception as e:
        log.error(f"Error processing {filename_enc if 'filename_enc' in locals() else 'unknown'}")
        log.error("Traceback: %s", traceback.format_exc())
        
        with lock_download:  # Ensuring thread safety
            config.downloadinprogress = [entry for entry in config.downloadinprogress if entry["id"] != fileid]
            config.item_download_errors.append(item)
            config.num_error += 1
        

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

def download_the_list_of_files(perror):
    log.info("Download process Started.")
    config.status_str = "Loading files list"
    items = load_file_list(perror)
    config.status_str = "Downloads start"
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
                try:
                    future.result()
                    if config.stop_flag:
                        log.warning("Stop flag detected. Cancelling remaining downloads.")
                        executor.shutdown(wait=True, cancel_futures=True)
                except Exception as e:
                    log.error(f"Error in download executor: {e}")
                    log.error("Traceback: %s", traceback.format_exc())
        except Exception as e:
            log.error(f"Unexpected error during download process: {e}")
    
    if config.item_download_errors:
        with open('item_download_errors.json', 'w', encoding="utf8") as f:
            json.dump(config.item_download_errors, f, indent=2)
        log.info("Errors logged in item_download_errors.json.")
    
    log.info("Download process completed.")
    if config.stop_flag:
        config.status_str = "Downloads ended due to stop_flag"
    else:
        config.status_str = "Downloads completed"
    config.progress_num = 0
    config.isprocessing=False
    config.stop_flag=False
        

if __name__ == "__main__":
    download_the_list_of_files()
