import os
import logging
from queue import Queue

import utils


def initialize(): 
    global OFFLINEBACKUP_PATH, ONEDRIVEDIR_PATH, MAX_RETRIES,MAX_WORKERS,MAX_WORKERS_GEN,INSTALL_DIR,BG_IMG,stop_flag,num_error,MAX_ERRORS,status_str,progress_num,progress_tot,MIN_FREE_SPACE_BYTES,LOG_FILE,LOG_LEVEL,LOG_BACKUP_COUNT,TIMEOUT,folder_queue,accesstoken,file_list
    INSTALL_DIR=utils.get_main_dir()
    OFFLINEBACKUP_PATH = os.path.join(INSTALL_DIR, "Downloads")
    ONEDRIVEDIR_PATH = "/Pictures"
    MAX_RETRIES = 3
    MAX_WORKERS = 10
    MAX_WORKERS_GEN = 20
    LOG_LEVEL=logging.INFO
    stop_flag=False
    num_error=0
    MAX_ERRORS=max(MAX_WORKERS, MAX_WORKERS_GEN)+5
    status_str=""
    progress_num=0
    progress_tot=10000
    MIN_FREE_SPACE_BYTES = 5 * 1024 * 1024 * 1024  # 1GB
    LOG_FILE = os.path.join(INSTALL_DIR,"logs", "OneDriveOfflineBackup.log")
    BG_IMG = os.path.join(INSTALL_DIR,"imgs","backup.png")
    LOG_BACKUP_COUNT = 10  # Keep up to 10 backup logs
    TIMEOUT = 20
    accesstoken=""
    file_list=[]
    folder_queue = Queue()

