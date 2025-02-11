import sys,os,shutil,logging
from logging.handlers import RotatingFileHandler
import threading
from contextlib import contextmanager

import config

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
    ensure_directories(config.LOG_FILE)
    if os.path.exists(config.LOG_FILE):
        try:
            for i in range(config.LOG_BACKUP_COUNT, 0, -1):
                old_log = f"{config.LOG_FILE}.{i}"
                older_log = f"{config.LOG_FILE}.{i - 1}" if i > 1 else config.LOG_FILE
                if os.path.exists(old_log):
                    os.remove(old_log)  # Remove the target log if it already exists
                if os.path.exists(older_log):
                    os.rename(older_log, old_log)
        except Exception as e:
            print(f"Error rotating logs at startup: {e}")
            
    logging.basicConfig(
        format='%(asctime)s::%(name)s(%(thread)d)::%(levelname)s::%(message)s',
        level=config.LOG_LEVEL,
        handlers=[
            RotatingFileHandler(config.LOG_FILE, maxBytes=50 * 1024 * 1024, backupCount=config.LOG_BACKUP_COUNT)
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
        return free >= config.MIN_FREE_SPACE_BYTES
    return True
    
    import threading
from contextlib import contextmanager


class TimeoutLock(object):
    def __init__(self):
        self._lock = threading.Lock()

    def acquire(self, blocking=True, timeout=-1):
        return self._lock.acquire(blocking, timeout)

    @contextmanager
    def acquire_timeout(self, timeout):
        result = self._lock.acquire(timeout=timeout)
        yield result
        if result:
            self._lock.release()

    def release(self):
        self._lock.release()