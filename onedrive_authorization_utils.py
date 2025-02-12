import msal
import webbrowser
import requests 
import json
import os 
import logging

import config

log = logging.getLogger(__name__)

# Set these environment variables:
# MS_OPENGRAPH_APP_ID
# MS_OPENGRAPH_CLIENT_SECRET 

# TODO check variable exists !!
APP_ID=os.environ.get("MS_OPENGRAPH_APP_ID")
CLIENT_SECRET=os.environ.get("MS_OPENGRAPH_CLIENT_SECRET")
APP_CODE=os.environ.get("MS_OPENGRAPH_APP_CODE")
SCOPES=["Files.ReadWrite.All"]

# This will expire in 24 months -- i.e., January 2, 2025.
# You can generate a new one in Azure Portal under app registrations > client secrets

AUTHORITY_URL = "https://login.microsoftonline.com/consumers/"
BASE_URL = "https://graph.microsoft.com/v1.0/"

def procure_new_tokens_from_user() -> tuple:
    endpoint = BASE_URL + "me"
    SCOPES = ["User.Read", "User.Export.All, Files.ReadWrite.All"]
    log.debug("APP_ID %s CLIENT_SECRET %s",APP_ID,CLIENT_SECRET)
    client_instance = msal.ConfidentialClientApplication(
            client_id = APP_ID,
       #     client_credential = CLIENT_SECRET, seems not needed for desktop app
            authority = AUTHORITY_URL)
    if not APP_CODE:      
        authorization_request_url = client_instance.get_authorization_request_url(SCOPES)
        webbrowser.open(authorization_request_url)
        log.debug(authorization_request_url)
        log.info("Please use the code you see in the URL on the web browser to set environment variable MS_OPENGRAPH_CODE ")
        config.status_str="Please use the code you see in the URL on the web browser to set environment variable MS_OPENGRAPH_APP_CODE"
        # example: authorization_code = "M.R3_BAY.ec1e0d91-e035-0065-f757-494a9c206744"
        access_token = ""
        refresh_token =""
        name = "Set APP CODE"
    else:
        tokenDictionary = client_instance.acquire_token_by_authorization_code(code=APP_CODE, scopes=SCOPES)
        log.info("TokenDirectory %s",tokenDictionary)
        access_token = tokenDictionary["access_token"]
        refresh_token = tokenDictionary["refresh_token"]
        name = tokenDictionary["id_token_claims"]["name"]
    return (access_token, refresh_token, name)

def load_access_token_from_file() -> str:
    try: 
        with open("access_token.txt") as f:
            line = f.readline()
        return line
    except Exception as e:
        log.error(f"Unexpected error during load access token: {e}")
        return None 

def load_refresh_token_from_file() -> str:
    try: 
        with open("refresh_token.txt") as f:
            line = f.readline()
        return line
    except Exception as e:
        log.error(f"Unexpected error during load refresh token: {e}")
    return None

def save_access_token(token:str):
    with open("access_token.txt", "w") as f:
         f.write(token)
    return 

def save_refresh_token(token:str):
    with open("refresh_token.txt", "w") as f:
         f.write(token)
    return 

# see https://learn.microsoft.com/en-us/graph/auth-v2-user?view=graph-rest-1.0#5-use-the-refresh-token-to-get-a-new-access-token
def get_new_access_token_using_refresh_token(refresh_token:str):
    # POST /{tenant}/oauth2/v2.0/token HTTP/1.1
    # Host: https://login.microsoftonline.com
    # Content-Type: application/x-www-form-urlencoded
    #client_id=11111111-1111-1111-1111-111111111111
    #&scope=user.read%20mail.read
    #&refresh_token=OAAABAAAAiL9Kn2Z27UubvWFPbm0gLWQJVzCTE9UkP3pSx1aXxUjq...
    #&grant_type=refresh_token
    #&client_secret=jXoM3iz...      // NOTE: Only required for web apps

    request_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    scope_list = ["https://graph.microsoft.com/Files.ReadWrite.All"]
    scope = "%20".join(scope_list)
    redirect_uri = (
        #f"https://someuri.com/login"
        f"https://login.microsoftonline.com/common/oauth2/nativeclient"
    )

    payload = {
        "client_id": APP_ID,
        #"client_secret": CLIENT_SECRET, #removed
        "scope": scope,
        "tenantID": 'consumers', #added AADSTS9002331: Application is configured for use by Microsoft Account users only. Please use the /consumers endpoint to serve this request. 
        "redirect_uri": redirect_uri,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    response = requests.post(url=request_url, headers=headers, data=payload)
    log.debug(response.content)
    responseText = response.text
    log.debug(responseText)
    j = json.loads(responseText)

    return j["access_token"] 
    