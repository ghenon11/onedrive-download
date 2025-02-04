def initialize(): 
    global OFFLINEBACKUP_PATH, ONEDRIVEDIR_PATH, MAX_RETRIES,MAX_WORKERS,stop_flag
    OFFLINEBACKUP_PATH = "D:\OneDriveOfflineBackup"
    ONEDRIVEDIR_PATH = "/Pictures/bestof/bestof_2018_08_venise_croatie"
    MAX_RETRIES = 3
    MAX_WORKERS = 5
    stop_flag=False