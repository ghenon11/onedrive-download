import sys,os

def initialize(): 
    global OFFLINEBACKUP_PATH, ONEDRIVEDIR_PATH, MAX_RETRIES,MAX_WORKERS,INSTALL_DIR,stop_flag,status_str,progress_num,progress_tot
    INSTALL_DIR=get_main_dir()
    OFFLINEBACKUP_PATH = os.path.join(INSTALL_DIR, "Downloads")
    ONEDRIVEDIR_PATH = "/Pictures"
    MAX_RETRIES = 3
    MAX_WORKERS = 5
    stop_flag=False
    status_str=""
    progress_num=0
    progress_tot=10000
    
def get_main_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    if os.path.dirname(sys.argv[0]):
        return os.path.dirname(sys.argv[0]) # name of file
    return os.path.dirname(__file__)