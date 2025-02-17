import logging, threading, traceback, time
import argparse, configparser
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image
from pathlib import Path

import config,utils
from onedrive_authorization_utils import (
    save_refresh_token, load_access_token_from_file,
    procure_new_tokens_from_user, get_new_access_token_using_refresh_token,
    save_access_token, load_refresh_token_from_file
)
from generate_list import generate_list_of_all_files_and_folders
from download_list import download_the_list_of_files

__author__ = "Guillaume HENON"
__version__ = "0.6"
#
# Microsoft Graph documentation
# https://learn.microsoft.com/en-us/onedrive/developer/rest-api/?view=odsp-graph-online

class OneDriveDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OneDrive Offline Backup")
        # Set the dimensions of the window
        width = 600
        height = 680

        # Get the screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Calculate the position to center the window
        x = (screen_width / 2) - (width / 2)
        y = (screen_height / 2) - (height / 2)

        # Set the geometry of the window
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.confirm_close)
        self.iconphoto(True, tk.PhotoImage(file=config.BG_IMG))
        
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.init_frame = ctk.CTkFrame(self.main_frame)
        # Load and set background image
        self.bg_photo=ctk.CTkImage(light_image=Image.open(config.BG_IMG), size=(self.init_frame.cget("width")-10, (self.init_frame.cget("width")-10)*200/250))  # Adjust size 
        self.bg_label = ctk.CTkLabel(self.init_frame, image=self.bg_photo, text="",compound="left").grid(row=0, column=1, rowspan=3)
        ctk.CTkLabel(self.init_frame, text="ONEDRIVE OFFLINE BACKUP", font=("Roboto", 24, "bold"),text_color="#1565c0").grid(row=0, column=0, pady=5)
        ctk.CTkLabel(self.init_frame, text="One time setup: " ,anchor="s",justify="right").grid(row=1, column=0,sticky="sw")
        ctk.CTkButton(self.init_frame, text="Get Tokens", command=self.get_refresh_and_access_tokens).grid(row=2, column=0, padx=5,pady=5,sticky="w")
        self.init_frame.grid_rowconfigure(0, weight=1)
        self.init_frame.grid_columnconfigure(0, weight=1)
        self.init_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        
        self.genlist_frame = ctk.CTkFrame(self.main_frame)
        self.genlist_frame.grid_rowconfigure(0, weight=1)
        self.genlist_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.genlist_frame, text="Set OneDrive Starting Directory and exclusions (separated by ;)").grid(row=0, column=0, sticky="w")
        self.root_dir_var = ctk.StringVar()
        self.root_dir_var.set(config.ONEDRIVEDIR_PATH)
        ctk.CTkEntry(self.genlist_frame, textvariable=self.root_dir_var, width=350).grid(row=1, column=0, pady=5,padx=5)
        ctk.CTkButton(self.genlist_frame, text="Set Root Directory", command=self.set_onedrive_directory).grid(row=1, column=1, pady=5,padx=5)
        self.exclude_var = ctk.StringVar()
        ctk.CTkEntry(self.genlist_frame, textvariable=self.exclude_var, width=350).grid(row=2, column=0, pady=5,padx=5)
        ctk.CTkButton(self.genlist_frame, text="Generate List of Files", fg_color="green", hover_color="darkgreen",command=self.generate_list).grid(row=2, column=1,  pady=5)
        self.genlist_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        
        self.exclude_var.set("SubstringInFileToExclude;SubstringInFolderToExclude")
        
        self.download_frame = ctk.CTkFrame(self.main_frame)
        self.download_frame.grid_rowconfigure(0, weight=1)
        self.download_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.download_frame, text="Set Download Directory:").grid(row=0, column=0, sticky="w")
        self.download_dir_var = ctk.StringVar(value=config.OFFLINEBACKUP_PATH)
        ctk.CTkEntry(self.download_frame, textvariable=self.download_dir_var, width=350).grid(row=1, column=0, pady=5,padx=5)
        ctk.CTkButton(self.download_frame, text="Choose Directory", command=self.choose_directory).grid(row=1, column=1, pady=5,padx=5)
        self.check_var = ctk.IntVar()
        self.checkbox = ctk.CTkCheckBox(self.download_frame, text="Process last errors", variable=self.check_var)
        self.checkbox.deselect()
        self.checkbox.grid(row=2,column=1,pady=5)
        ctk.CTkButton(self.download_frame, text="Download Files", fg_color="green",hover_color="darkgreen",command=self.download_files).grid(row=2, column=0,pady=5)
        self.download_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        
        self.status_frame = ctk.CTkFrame(self.main_frame)
        self.status_frame.grid_rowconfigure(0, weight=1)
        self.status_frame.grid_columnconfigure(0, weight=1)
        #self.status_text = ctk.CTkTextbox(self.status_frame, width=400, height=80)
        self.status_text = ctk.CTkTextbox(self.status_frame, height=110)
        self.status_text.grid(row=0, column=0, pady=10,padx=5,sticky="nsew") 
        self.progress_var = ctk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(self.status_frame, variable=self.progress_var, width=350)
        self.oneprogress_var = ctk.DoubleVar()
        self.oneprogress_bar = ctk.CTkProgressBar(self.status_frame, variable=self.oneprogress_var, width=350)
        self.progress_bar.grid(row=1, column=0, pady=10)
        self.progress_bar.set(0)
        self.oneprogress_bar.grid(row=2, column=0, pady=10)
        self.oneprogress_bar.set(0)
        self.status_frame.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")

        self.end_frame = ctk.CTkFrame(self.main_frame)
        self.end_frame.grid_columnconfigure(0, weight=1)
        self.end_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(self.end_frame, text="Stop Processing", fg_color="red", hover_color="darkred",command=self.stop_download).grid(row=0, column=0, pady=5)
        ctk.CTkButton(self.end_frame, text="Exit Application", fg_color="red", hover_color="darkred",command=self.exit_app).grid(row=0, column=1, pady=5)
        self.end_frame.grid(row=4, column=0, padx=10, pady=5, sticky="nsew")
        
        spec_text=f"{__author__} - gui.henon@gmail.com - Version {__version__} - 2025"
        ctk.CTkLabel(self.main_frame, text=spec_text, font=("Arial", 9),anchor="e",justify="right").grid(row=5, column=0, sticky="ne")
        
        # self.center_window(self)
        self.update_ui()
                
    def center_window(window):
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")
    
    def update_download_status(self):
        
        try:
            biggestsize=0
            downloadstatus=""            
            download_in_progress = config.downloadinprogress  # List of dicts
            if not download_in_progress:
                if config.progress_num>0:
                    return "No download in progress"
                else:
                    return ""
           
            nb_download = len(download_in_progress)
            downloaded=None
            # Find the biggest file by size
            for entry in download_in_progress:
                if int(entry["size"])>biggestsize:
                    biggestfile = entry["name"]
                    biggestsize = int(entry["size"])  # Convert bytes to MB
                    filefolder=entry["parentReference"]["path"]
                    filefolder=filefolder.replace("/drive/root:","")
                    downloaded=entry.get("downloaded",None)
    
            if biggestsize<1*1024*1024:
                textsize="<0"
            else:
                textsize=str(int(biggestsize/1024/1024))
            # Constructing status messages
            if nb_download == 1:
                downloadstatus = f"1 download in progress, file is {biggestfile} ({textsize}Mb) in {filefolder}"
            else:
                downloadstatus = f"{nb_download} downloads in progress, biggest file is {biggestfile} ({textsize}Mb) in {filefolder}"
            if downloaded:
                downloadstatus=f"{downloadstatus}\nProgress: {int(downloaded/1024/1024)} / {int(biggestsize/1024/1024)} Mb"
                download_ratio=downloaded / (biggestsize or 1)
                self.oneprogress_var.set(download_ratio)
            else:
                self.oneprogress_var.set(0)
        except Exception as e:
            logging.error(f"Error processing updateui")
            logging.error("Traceback: %s", traceback.format_exc())
        return downloadstatus
    
    def update_ui(self):
        text=config.status_str
        download_status=self.update_download_status()
        text=f"{text}\n{download_status}"
        if config.num_error>0:
            if config.num_error==1:
                text=f"{text}\n{config.num_error} error so far"
            else:
                text=f"{text}\n{config.num_error} errors so far"
            if config.isprocessing==False:
                text=f"{text}\n{config.num_error} errors in last run"
            
        
        if config.stop_flag==True:
            text=f"{text}\nStopping current Operations..."
        #logging.debug(f"Config status: {config.status_str}")
        self.status_text.delete("1.0", "end")
        self.status_text.insert("1.0", text)
        if config.progress_num >= 0:
            if self.progress_bar.cget("mode")=="indeterminate":
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
            progress_ratio=config.progress_num / (config.progress_tot or 1)
            self.progress_var.set(progress_ratio)
        self.after(2000, self.update_ui)  # Update every 2 seconds

    def get_refresh_and_access_tokens(self):
        try:
            access_token, refresh_token, name = procure_new_tokens_from_user()
            if refresh_token:
                save_refresh_token(refresh_token)
                messagebox.showinfo("Success", f"Hello {name}! Tokens saved successfully.")
            else:
                messagebox.showinfo("Initialisation", "Set MS_OPENGRAPH_APP_CODE environment variable with the code you find in your browser and restart")
        except Exception as e:
            messagebox.showerror("Error", f"Error when procuring token {e}")

    def use_refresh_token_to_get_new_access_token(self):
        try:
            refresh_token = load_refresh_token_from_file()
            if not refresh_token:
                messagebox.showerror("Error", "No refresh token found.")
                return
            new_access_token = get_new_access_token_using_refresh_token(refresh_token)
            save_access_token(new_access_token)
        except Exception as e:
            messagebox.showerror("Error", f"Error when refreshing token {e}")

    def generate_list(self):
        config.stop_flag=False
        if config.isprocessing==False:
            config.isprocessing=True
            config.progress_num=-1
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            threading.Thread(target=self._generate_list, daemon=True).start()
        else:
            messagebox.showerror("Error", "Operation in progress, generation not possible now")
            
    
    def _generate_list(self):
        try:
            self.use_refresh_token_to_get_new_access_token()
            access_token = load_access_token_from_file()
            if not access_token:
                messagebox.showerror("Error", "No access token found.")
                return
            generate_list_of_all_files_and_folders(access_token)
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def download_files(self):
        config.stop_flag=False
        if config.isprocessing==False:
            config.isprocessing=True
            config.status_str="Initializing downloads"
            config.num_error=0
            exclusions=self.exclude_var.get()
            if exclusions:
                config.exclusion_list=exclusions.split(";")
            else:
                config.exclusion_list=[]
            file_path = Path(__file__)
            file_name = file_path.name      
            config.exclusion_list.append(file_name)
            logfile_path = Path(config.LOG_FILE)
            logfile_name = logfile_path.name
            config.exclusion_list.append(logfile_name)
            logging.debug(f"Exclusions are {config.exclusion_list}")
            config.progress_num=0
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            threading.Thread(target=self._download_files, daemon=True).start()
            threading.Thread(target=self._get_new_access_token, daemon=True).start()
        else:
            messagebox.showerror("Error", "Operation in progress, download not possible now")
        
    
    def _get_new_access_token(self):
        try:
            logging.info("Refreshing Token")
            self.use_refresh_token_to_get_new_access_token()
            access_token = load_access_token_from_file()
            config.accesstoken=access_token
            logging.debug("Token refreshed")
            self.after(1200000, self._get_new_access_token) # every 20 mins refresh token (TTL is often 60mins)
        except Exception as e:
            logging.error("Error refreshing access token: {e}")
    
    def _download_files(self):
        try:
            self.use_refresh_token_to_get_new_access_token()
            access_token = load_access_token_from_file()
            config.accesstoken=access_token
            if not access_token:
                messagebox.showerror("Error", "No access token found.")
                return
            download_the_list_of_files(self.checkbox.get())
        except Exception as e:
            messagebox.showerror("Error", f"When launching file download: {e}")
    
    def choose_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.download_dir_var.set(directory)
            config.OFFLINEBACKUP_PATH = directory
            config.status_str = f"Download directory set to: {directory}"
            log.info(config.status_str)
    
    def set_onedrive_directory(self):
        config.ONEDRIVEDIR_PATH = self.root_dir_var.get()
        config.status_str = f"OneDrive Root directory set to: {config.ONEDRIVEDIR_PATH}"
        log.info(config.status_str)
    
    def stop_download(self):
        config.stop_flag = True
    
    def confirm_close(self):
        if messagebox.askyesno("Confirm Close", "Are you sure you want to close?"):
            self.exit_app()
    
    def exit_app(self):
        self.stop_download()
        logging.info("Exiting Application")
        self.quit()

def update_cmdline_download_status():

    try:
        biggestsize=0
        download_status=""
        biggestfile="No biggest file"
        download_in_progress = config.downloadinprogress  # List of dicts
        if not download_in_progress:
            if config.progress_num>0:
                download_status="No download in progress"
        else:
            nb_download = len(download_in_progress)
            downloaded=None
            # Find the biggest file by size
            for entry in download_in_progress:
                if int(entry["size"])>biggestsize:
                    biggestfile = entry["name"]
                    biggestsize = int(entry["size"])  # Convert bytes to MB
                    filefolder=entry["parentReference"]["path"]
                    filefolder=filefolder.replace("/drive/root:","")
                    downloaded=entry.get("downloaded",None)

            if biggestsize<1*1024*1024:
                textsize="<0"
            else:
                textsize=str(int(biggestsize/1024/1024))
            # Constructing status messages
            if nb_download == 1:
                download_status = f"1 download in progress, file is {biggestfile} ({textsize}Mb) in {filefolder}"
            else:
                download_status = f"{nb_download} downloads in progress, biggest file is {biggestfile} ({textsize}Mb) in {filefolder}"
            if downloaded:
                download_status=f"{download_status} - Progress: {int(downloaded/1024/1024)} / {int(biggestsize/1024/1024)} Mb"
                download_ratio=downloaded / (biggestsize or 1)

        text=config.status_str
        text=f"{text} - {download_status}"
        if config.num_error>0:
            if config.num_error==1:
                text=f"{text} - {config.num_error} error so far"
            else:
                text=f"{text} - {config.num_error} errors so far"
            if config.isprocessing==False:
                text=f"{text} - {config.num_error} errors in last run"
    
        logging.info(text)    
              
    except Exception as e:
        logging.error(f"Error processing update command line status")
        logging.error("Traceback: %s", traceback.format_exc())
        
def generate_and_download():
    try:
      
        new_access_token = get_new_access_token_using_refresh_token(load_refresh_token_from_file())
        save_access_token(new_access_token)
        access_token = new_access_token
        if not access_token:
            logging.error("No Access Token")
            return None
        logging.info("*** Generating OneDrive files list")
        generate_list_of_all_files_and_folders(access_token)
        
        logging.info("*** Synchronising Personal OneDrive")
        
        file_path = Path(__file__)
        file_name = file_path.name      
        config.exclusion_list.append(file_name)
        logfile_path = Path(config.LOG_FILE)
        logfile_name = logfile_path.name
        config.exclusion_list.append(logfile_name)
        logging.debug(f"Exclusions are {config.exclusion_list}")
        config.progress_num=0
        config.num_error=0
               
        load_refresh_token_from_file()
        new_access_token = get_new_access_token_using_refresh_token(load_refresh_token_from_file())
        save_access_token(new_access_token)
        access_token = new_access_token
        config.accesstoken=access_token
        rt = utils.RepeatedTimer(10, update_cmdline_download_status)
        download_the_list_of_files(0)
        rt.stop()
        
    except Exception as e:
        logging.error(f"Error during command line processing")
        logging.error("Traceback: %s", traceback.format_exc())
        return None
    return config.num_error
    
    
    
if __name__ == "__main__":
    config.initialize()
        
    ap = argparse.ArgumentParser(description="Script to synchronize personal OneDrive with a local folder")
    # Add the arguments to the parser
    ap.add_argument("-d", "--debug", action="store_true",help="Set debug mode")
    ap.add_argument("-r", "--root", help="Set OneDrive Root Directory")
    ap.add_argument("-l", "--localdir",help="Set Local Download Directory")
    args = ap.parse_args()
    
    if args.debug:
        config.LOG_LEVEL=logging.DEBUG
    
    utils.init_logging()    
    logging.getLogger(__name__)
 
    localdir=args.localdir
    rootpath=args.root
    if localdir:
        config.iscommandline=True
        if rootpath:
            if "/" in rootpath:
                config.ONEDRIVEDIR_PATH=rootpath
            else:
                logging.warning(f"Invalid OneDrive Root Directory: {rootpath}")
        if localdir:
            if utils.path_exists(localdir):
                config.OFFLINEBACKUP_PATH=args.localdir
            else:
                logging.warning(f"Local Directory {localdir} does not exists")
                
            
        logging.info(f"Using command line version of the script with OneDrive root {config.OFFLINEBACKUP_PATH} and download directory {config.ONEDRIVEDIR_PATH}")
    else:
        config.iscommandline=False
    
    logging.info("Application starts")
    config.isprocessing=False
    
    if config.iscommandline==False:
        app = OneDriveDownloader()
        app.mainloop()
    else:
        generate_and_download()
        
    logging.info("Application ends")
            
