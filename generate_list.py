import requests 
import json
from coloring import *
import logging
from tabulate import tabulate 
from onedrive_authorization_utils import procure_new_tokens_from_user, load_access_token_from_file, save_access_token, BASE_URL

log = logging.getLogger(__name__)

# You'll want to change this to the folder YOU want to start with.
# In my OneDrive, I've created top-level folders for A, B, C... Z
# In the "P" folder, I have what I really wanted to download: Pictures

root_folder = "/me/drive/root:/Numérisations"


# 1) Get Access Token
# 2) When Access Token expires, get a new one. 
# 3) We want to first build a list of all the names and files to fetch. 
#    Don't download anything at first, just traverse the folders and build up a task list. 

#    Build a list of folders to traverse, by: 
#    folders = [] 

#    def process_folder_url(url:str):
#          get pageful of items in folder
#                if the item in list is a folder, append it to work queue
#          if there's a next_link, process_folder_url(next_link) 
#                else return
#          for each folder in the list of items:
#                process_folder 
# 


# Go to Portal / App Registrations to create one.




def get_next_link_from_response_dictionary(dict) -> str:
    if (dict.__contains__("@odata.nextLink")):
        return dict["@odata.nextLink"]
    return None 


########### Access token ############
# access_token = load_access_token_from_file()

# if (access_token is None):
#     access_token = procure_new_tokens_from_user()
#     save_access_token(access_token)
#####################################################
# log.info("token: %s" % access_token)




current_folder = root_folder 

def get_current_endpoint() -> str:
    return BASE_URL + current_folder + ":/children"

# Given an item dictionary of a folder object, construct its ms opengraph "children" inspector endpoint
def get_folder_endpoint_by_folder_item(item) -> str:
    return BASE_URL + "/me" + item["parentReference"]["path"] + "/" + item["name"] + ":/children"

# examples: 
# endpoint = base_url + "/me/drive/special/photos/children"
#endpoint = base_url + "/me/drive/special/cameraroll/children"
#endpoint = base_url + "/me/drive/root/P/Pictures/Camera Roll/children"

folder_list = []
file_list = []

# To list what's in a folder, append :/children to the folder name 
def process_folder_pagefull(endpoint:str, access_token:str):
    headers = {"Authorization":"Bearer "+access_token}
    log.info("getting "+endpoint)
    try: 
        response = requests.get(endpoint, headers = headers)
        
    except:
        log.info(response.json()["error"]["code"])
        error_code = response.json()["error"]["code"]
        if (error_code=="InvalidAuthenticationToken"):
            access_token = procure_new_tokens_from_user()
            save_access_token(access_token)
            log.info("New access token saved, which is good for 1 hour. Please re-run program.")
            exit()

    log.debug(json.dumps(response.json(), indent=2))
    content = response.json()
    item_count = len(content["value"])
    log.info("There are %s item(s) in this folder." % item_count)

    try:
    # Items are going to either be folders or files. 
        for item in content["value"]:
            is_folder = item.__contains__("folder") 
            msg = "%s %s" % (item["name"] , ("[FOLDER]" if is_folder else "[FILE]"))
            log.info(msg)
            if not is_folder:
                log.debug("DOWNLOAD %s" % item["@microsoft.graph.downloadUrl"])
                file_list.append(item)
            else:
                folder_list.append(item)
                # process the folder 
                endpoint = get_folder_endpoint_by_folder_item(item)
                process_folder_pagefull(endpoint, access_token=access_token)

        next_link = get_next_link_from_response_dictionary(content)
        log.info("Next link: %s", next_link)
        if (next_link is not None):
            return process_folder_pagefull(next_link, access_token=access_token)
            
    except Exception as e:
        log.error(f"Error finding loopback devices: {e}")
        
    return len(folder_list)


# START

def generate_list_of_all_files_and_folders(access_token:str):
    
    endpoint = get_current_endpoint()

    result_count = process_folder_pagefull(endpoint, access_token=access_token)
    log.info("%s folder item(s) found" % result_count)

    #log.info(file_list[1])
 
   

    log.info("Writing list of files and folders to process:")
    # save file_list to file
    if file_list:
        log.info("file list 0 %s: ",file_list[0])
        json_file_list = json.dumps(file_list)
    else:
        json_file_list=""
    f = open('file_list.json', 'w', encoding="utf8")
    f.write(json_file_list)

    # save folder_list to file 
    if folder_list:
        log.info("folder list 0 %s: ", folder_list[0])
        json_folder_list = json.dumps(folder_list)
    else:
        json_folder_list=""
    f = open('folder_list.json', 'w', encoding="utf8")
    f.write(json_folder_list)
    log.info("")
    log.info("file_list.json and folder_list.json have been saved to the current folder.")
    log.info("OneDrive Folder: %s " % root_folder.replace("/me/drive/root:",""))
    log.info("Files %i, Folders %i",len(file_list),len(folder_list))
    log.info("Done.")


