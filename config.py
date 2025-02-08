import sys,os,shutil,logging
from logging.handlers import RotatingFileHandler
from queue import Queue

def initialize(): 
    global OFFLINEBACKUP_PATH, ONEDRIVEDIR_PATH, MAX_RETRIES,MAX_WORKERS,MAX_WORKERS_GEN,INSTALL_DIR,stop_flag,num_error,MAX_ERRORS,status_str,progress_num,progress_tot,MIN_FREE_SPACE_BYTES,LOG_FILE,LOG_LEVEL,LOG_BACKUP_COUNT,TIMEOUT,folder_queue
    INSTALL_DIR=get_main_dir()
    OFFLINEBACKUP_PATH = os.path.join(INSTALL_DIR, "Downloads")
    ONEDRIVEDIR_PATH = "/Pictures"
    MAX_RETRIES = 3
    MAX_WORKERS = 10
    MAX_WORKERS_GEN = 20
    LOG_LEVEL=logging.INFO
    stop_flag=False
    num_error=0
    MAX_ERRORS=max(MAX_WORKERS, MAX_WORKERS_GEN)
    status_str=""
    progress_num=0
    progress_tot=10000
    MIN_FREE_SPACE_BYTES = 5 * 1024 * 1024 * 1024  # 1GB
    LOG_FILE = os.path.join(INSTALL_DIR,"logs", "OneDriveOfflineBackup.log")
    LOG_BACKUP_COUNT = 10  # Keep up to 10 backup logs
    TIMEOUT = 20
    folder_queue = Queue()

def ensure_directories(one_directory):
    try:
        if os.path.isdir(one_directory):
            result=os.makedirs(one_directory, exist_ok=True)
        else:            
            result=os.makedirs(os.path.basename(os.path.dirname(one_directory)), exist_ok=True)
    except Exception as e:
        print(f"Error ensure directories: {e}")
    return result
        
def init_logging():   
    # Configure logging
    #logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s(%(thread)d) - %(levelname)s - %(message)s")
    # Rotate the log file at each startup
    ensure_directories(LOG_FILE)
    if os.path.exists(LOG_FILE):
        try:
            for i in range(LOG_BACKUP_COUNT, 0, -1):
                old_log = f"{LOG_FILE}.{i}"
                older_log = f"{LOG_FILE}.{i - 1}" if i > 1 else LOG_FILE
                if os.path.exists(old_log):
                    os.remove(old_log)  # Remove the target log if it already exists
                if os.path.exists(older_log):
                    os.rename(older_log, old_log)
        except Exception as e:
            print(f"Error rotating logs at startup: {e}")
            
    logging.basicConfig(
        format='%(asctime)s::%(name)s(%(thread)d)::%(levelname)s::%(message)s',
        level=LOG_LEVEL,
        handlers=[
            RotatingFileHandler(LOG_FILE, maxBytes=50 * 1024 * 1024, backupCount=LOG_BACKUP_COUNT)
        ]
    )

    
def get_main_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    if os.path.dirname(sys.argv[0]):
        return os.path.dirname(sys.argv[0]) # name of file
    return os.path.dirname(__file__)
    
def has_enough_space(folder):
    """Check if there is at least 1GB of free space."""
    if os.path.isfile(folder) or os.path.isdir(folder):
        total, used, free = shutil.disk_usage(folder)
        return free >= MIN_FREE_SPACE_BYTES
    return True