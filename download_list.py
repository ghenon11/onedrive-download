# Assumes you've got file_list.json 

from coloring import *
import logging,traceback
import json
import requests 
import sys,os,time
from dateutil import parser as datetimeparser
from pathlib import Path
from onedrive_authorization_utils import load_access_token_from_file

from datetime import datetime, timezone

from progress.bar import Bar

log = logging.getLogger(__name__)

item_download_errors = []
OFFLINEBACKUP_PATH="D:\OneDriveOfflineBackup"

def load_file_list() -> list:
    with open("file_list.json", "r") as f:
        str = f.read()
        file_items = json.loads(str)
    return file_items

def download_file_by_url(url, local_file_path) -> str:
    try: 
        access_token = load_access_token_from_file()
        headers = {"Authorization":"Bearer " + access_token}
        r = requests.get(url, headers=headers, allow_redirects=True)
        if (r.status_code != 200):
            log.info("ERROR COULD NOT GET FILE -- REFRESH YOUR ACCESS TOKEN")
            log.error(r.status_code)
            exit()
        open(local_file_path, 'wb').write(r.content)
        return local_file_path
    except KeyboardInterrupt as ke:
        log.info("Keyboard pressed. Goodbye")
        return "EXIT"
    except:
        log.info("ERROR IN download_file_by_url %s" % url)
        return None 

def ensure_local_path_exists(local_path):
    Path(local_path).mkdir(parents=True, exist_ok=True)

# from file item, get the local folder path
# can't save it all to one flat directory, 
# or else files with same name in different folders will collide
# also ensures folder path exists  
def get_local_download_folder_by_item(item) -> str:
    master_parent_folder_name = "/drive/root:"
    local_folder_path = item["parentReference"]["path"].replace(master_parent_folder_name, "")
    #cwd = Path.cwd()
    return "%s%s" % (OFFLINEBACKUP_PATH, local_folder_path)

def to_utc_aware(dt):
    #Ensure datetime is UTC-aware. Converts naive datetimes from local time.
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        # Convert from local time to UTC
        local_timestamp = time.mktime(dt.timetuple())  # Get local timestamp
        return datetime.fromtimestamp(local_timestamp, tz=timezone.utc)
    else:
        # Convert any timezone-aware datetime to UTC
        return dt.astimezone(timezone.utc)
        
def update_last_modified(file_path, iso_date):
    # Parse the ISO 8601 date
    dt = datetimeparser.isoparse(iso_date)
    # Ensure it's explicitly in UTC
    dt=to_utc_aware(dt)
    # Convert to Unix timestamp
    timestamp = dt.timestamp()
    # Update file modification time
    os.utime(file_path, (timestamp, timestamp))
    log.debug("File %s LastModified time set to %s",file_path,iso_date)
    
def is_file_changed(item,local_file_path):
    
    itemlastModifiedDateTime=item["lastModifiedDateTime"] #already in iso format
    itemlastModifiedDateTime=to_utc_aware(datetime.fromisoformat(itemlastModifiedDateTime))
    itemsize=item["size"]
    filename=item["name"]
    file_path = Path(local_file_path)
    if not file_path.exists():
        return True
        
    filesize=file_path.stat().st_size
    filelastModified= file_path.stat().st_mtime
    filelastModified= to_utc_aware(datetime.fromtimestamp(filelastModified))
    
    delta_sec = (filelastModified - itemlastModifiedDateTime).total_seconds()
    
    log.debug("Item date %s, File date %s (%d seconds delta), Item size %d, File size %d", itemlastModifiedDateTime,filelastModified,delta_sec,itemsize,filesize) 
    if itemsize==filesize and delta_sec<60:
        return False
    else:
        return True


def download_the_list_of_files(access_token:str):
    items = load_file_list()
    total = len(items)
    log.info("There are %s file(s) in file_list.json." % total)
    log.info("")
    #bar = Bar('Processing', max=total)

    index = 0
    for item in items:
        index = index+1 
 
    #    bar.next()
        download_url = item["@microsoft.graph.downloadUrl"]
        item_type = "unknown"
        if (item.__contains__("photo")):
            item_type = "photo/video"
        elif (item.__contains__("file")):
            item_type = "file"
        log.debug("Item %i is type %s",index,item_type)
  
        
        try: 
            lastModifiedDateTime=item["lastModifiedDateTime"]
            size=item["size"]
            filename=item["name"]
            log.info("[%s of %s] %s: (%s) LastModified %s Size %d" % (index, total, filename, item_type,lastModifiedDateTime,size))
                        
            local_folder_path = get_local_download_folder_by_item(item)
            log.debug("Saving to: %s" % local_folder_path)
            local_file_path = local_folder_path + "/"+item["name"]
            ensure_local_path_exists(local_folder_path)
                
            if is_file_changed(item, local_file_path):
                
                file_on_disk = download_file_by_url(download_url, local_file_path)
                if (file_on_disk == "EXIT"):
                    log.info("Exiting.")
                    sys.exit(2) 

                if (file_on_disk is not None):
                    log.debug("File %s downloaded",file_on_disk)
                    update_last_modified(local_file_path,lastModifiedDateTime)
                    #cwd = Path.cwd()
                    json_formatted_str = json.dumps(item, indent=2)
                else:
                    item_download_errors.append(item)
            else:
                log.info("File %s unchanged, pass",filename)
        except SystemExit:
            sys.exit(2)
        except Exception as e:
            log.error(f"Error processing item {filename}: {e}")
            log.error("Traceback: %s", traceback.format_exc())
            item_download_errors.append(item)

    #bar.finish()
    
    total_errors = len(item_download_errors)
    json_error_list = json.dumps(item_download_errors)
    f = open('item_download_errors.json', 'w', encoding="utf8")
    f.write(json_error_list)

    log.info("There were %s total error(s) in download. Often that's due to network errors." % total_errors)
    log.info("Rather than interrupt the loop, I've saved them in 'item_download_errors.json', so you can try manually.")
