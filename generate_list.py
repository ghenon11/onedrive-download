import requests
import json
import logging
from queue import Queue
from onedrive_authorization_utils import procure_new_tokens_from_user, load_access_token_from_file, save_access_token, load_refresh_token_from_file,BASE_URL,get_new_access_token_using_refresh_token
import config

log = logging.getLogger(__name__)


#root_folder = "/me/drive/root:\Pictures\bestof\bestof_2018_08_venise_croatie"

def get_next_link_from_response_dictionary(dict) -> str:
    return dict.get("@odata.nextLink", None)

def get_current_endpoint(folder: str) -> str:
    return BASE_URL + folder + ":/children"

def get_folder_endpoint_by_folder_item(item) -> str:
    return BASE_URL + "/me" + item["parentReference"]["path"] + "/" + item["name"] + ":/children"

def process_folder_queue(access_token: str):
    folder_queue = Queue()
    root_folder="/me/drive/root:"+config.ONEDRIVEDIR_PATH
    folder_queue.put(root_folder)
    folder_list = []
    file_list = []
    
    headers = {"Authorization": "Bearer " + access_token}
    
    while not folder_queue.empty() and config.stop_flag==False:
        current_folder = folder_queue.get()
        endpoint = get_current_endpoint(current_folder)
                
        while endpoint and config.stop_flag==False:
            try:
                response = requests.get(endpoint, headers=headers)
                response.encoding = 'utf-8'  # Ensure UTF-8 encoding
                
                response.raise_for_status()
                                
                content = response.json()
                
                for item in content.get("value", []):
                    is_folder = "folder" in item
                    msg = f"{item['name']} {'[FOLDER]' if is_folder else '[FILE]'}"
                    log.info(msg)
                    
                    if is_folder:
                        folder_list.append(item)
                        folder_queue.put(item["parentReference"]["path"] + "/" + item["name"])
                    else:
                        file_list.append(item)
                        log.debug("Adding %s" % item.get("@microsoft.graph.downloadUrl", "No URL"))
                
                endpoint = get_next_link_from_response_dictionary(content)
                config.status_str="Identification in progress\n"+str(len(file_list))+" files identified so far"
               
            except requests.exceptions.RequestException as e:
                log.error(f"HTTP error: {e}")
                log.error("Try getting a new access Token and try again") 
                break
            except Exception as e:
                log.error(f"Unexpected error: {e}")
                break
    
    config.status_str="Identification complete\n"+str(len(file_list))+" files identified"
    return file_list, folder_list

def generate_list_of_all_files_and_folders(access_token):
    
    if access_token is None:
        access_token = procure_new_tokens_from_user()
        save_access_token(access_token)
    
    file_list, folder_list = process_folder_queue(access_token)
    
    with open('file_list.json', 'w', encoding='utf8') as f:
        json.dump(file_list, f, indent=2)
    
    with open('folder_list.json', 'w', encoding='utf8') as f:
        json.dump(folder_list, f, indent=2)
    
    log.info("file_list.json and folder_list.json have been saved.")
    log.info("Files: %i, Folders: %i", len(file_list), len(folder_list))
    log.info("Done.")