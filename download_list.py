import requests
import json
import logging
import traceback
import sys
import os
import time
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dateutil import parser as datetimeparser
from onedrive_authorization_utils import load_access_token_from_file,load_refresh_token_from_file,get_new_access_token_using_refresh_token
from filedate import File

import config

log = logging.getLogger(__name__)
item_download_errors = []

def load_file_list() -> list:
    with open("file_list.json", "r", encoding='utf8') as f:
        return json.load(f)


def download_file_by_url(url, local_file_path):
    access_token = load_access_token_from_file()
    headers = {"Authorization": "Bearer " + access_token}
    for attempt in range(config.MAX_RETRIES):
        try:
            r = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
            r.raise_for_status()
            with open(local_file_path, 'wb') as f:
                f.write(r.content)
            return local_file_path
        except requests.exceptions.HTTPError as http_err:
            log.error(f"Attempt {attempt + 1} failed for {url}: HTTP ERROR {http_err}")
            if http_err.response.status_code == 404:
                access_token=get_new_access_token_using_refresh_token(load_refresh_token_from_file())
                logging.info("Access Token refreshed, retrying...")
        except requests.exceptions.RequestException as e:
            log.error(f"Attempt {attempt + 1} failed for {url}: {e}")
            time.sleep(2 ** attempt)
    log.error(f"Failed to download {url} after {config.MAX_RETRIES} attempts.")
    return None


def ensure_local_path_exists(local_path):
    Path(local_path).mkdir(parents=True, exist_ok=True)

def stop_download():
    global stop_flag
    stop_flag = True
    log.info("Stopping new downloads...")
    messagebox.showinfo("Stopping", "New downloads have been stopped.")

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
        log.error(f"Failed to update creation date for {file_path}: {e}")
    log.debug("File %s dates set to %s", file_path, iso_modifieddate)


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
        download_url = item["@microsoft.graph.downloadUrl"]
        filename = urllib.parse.unquote(item["name"])  # Decode URL-encoded filename
        local_folder_path = get_local_download_folder_by_item(item)
        local_file_path = os.path.join(local_folder_path, filename)
        ensure_local_path_exists(local_folder_path)
        if is_file_changed(item, local_file_path):
            downloaded_file = download_file_by_url(download_url, local_file_path)
            if downloaded_file:
                update_file_dates(local_file_path, item)
                log.info("Downloaded: %s", filename)
            else:
                item_download_errors.append(item)
        else:
            log.info("Unchanged: %s", filename)
    except Exception as e:
        log.error(f"Error processing {item['name']}: {e}")
        log.error("Traceback: %s", traceback.format_exc())
        item_download_errors.append(item)


def download_the_list_of_files():
    items = load_file_list()
    log.info("Starting download of %s file(s).", len(items))
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        futures = {executor.submit(process_item, item): item for item in items}
        for future in as_completed(futures):
            future.result()
    if item_download_errors:
        with open('item_download_errors.json', 'w', encoding="utf8") as f:
            json.dump(item_download_errors, f, indent=2)
        log.info("Errors logged in item_download_errors.json.")
    log.info("Download process completed.")


if __name__ == "__main__":
    download_the_list_of_files()
