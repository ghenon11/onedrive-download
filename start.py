import customtkinter as ctk
from tkinter import messagebox, filedialog
import logging, threading, traceback, time
from PIL import Image
import config
from onedrive_authorization_utils import (
    save_refresh_token, load_access_token_from_file,
    procure_new_tokens_from_user, get_new_access_token_using_refresh_token,
    save_access_token, load_refresh_token_from_file
)
from generate_list import generate_list_of_all_files_and_folders
from download_list import download_the_list_of_files

class OneDriveDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OneDrive Offline Backup")
        # Set the dimensions of the window
        width = 600
        height = 600

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
        
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.init_frame = ctk.CTkFrame(self.main_frame)
        # Load and set background image
        self.bg_photo=ctk.CTkImage(light_image=Image.open(config.BG_IMG), size=(self.init_frame.cget("width")-10, (self.init_frame.cget("width")-10)*200/250))  # Adjust size 
        self.bg_label = ctk.CTkLabel(self.init_frame, image=self.bg_photo, text="",compound="left").grid(row=0, column=1, rowspan=2)
        ctk.CTkLabel(self.init_frame, text="OneDrive OfflineBackup", font=("Arial", 16, "bold")).grid(row=0, column=0, pady=5)
        ctk.CTkButton(self.init_frame, text="Get Refresh and Access Tokens", command=self.get_refresh_and_access_tokens).grid(row=1, column=0, pady=5)
        self.init_frame.grid_rowconfigure(0, weight=1)
        self.init_frame.grid_columnconfigure(0, weight=1)
        self.init_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        
        self.genlist_frame = ctk.CTkFrame(self.main_frame)
        self.genlist_frame.grid_rowconfigure(0, weight=1)
        self.genlist_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.genlist_frame, text="Set OneDrive Starting Directory:").grid(row=0, column=0, sticky="w")
        self.root_dir_var = ctk.StringVar(value=config.ONEDRIVEDIR_PATH)
        ctk.CTkEntry(self.genlist_frame, textvariable=self.root_dir_var, width=350).grid(row=1, column=0, pady=5,padx=5)
        ctk.CTkButton(self.genlist_frame, text="Set Root Directory", command=self.set_onedrive_directory).grid(row=1, column=1, pady=5,padx=5)
        ctk.CTkButton(self.genlist_frame, text="Generate List of Files", command=self.generate_list).grid(row=2, column=0,  pady=5,columnspan=2)
        self.genlist_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        
        self.download_frame = ctk.CTkFrame(self.main_frame)
        self.download_frame.grid_rowconfigure(0, weight=1)
        self.download_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.download_frame, text="Set Download Directory:").grid(row=0, column=0, sticky="w")
        self.download_dir_var = ctk.StringVar(value=config.OFFLINEBACKUP_PATH)
        ctk.CTkEntry(self.download_frame, textvariable=self.download_dir_var, width=350).grid(row=1, column=0, pady=5,padx=5)
        ctk.CTkButton(self.download_frame, text="Choose Directory", command=self.choose_directory).grid(row=1, column=1, pady=5,padx=5)
        ctk.CTkButton(self.download_frame, text="Download Files", command=self.download_files).grid(row=2, column=0, columnspan=2,pady=5)
        self.download_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        
        self.status_frame = ctk.CTkFrame(self.main_frame)
        self.status_frame.grid_rowconfigure(0, weight=1)
        self.status_frame.grid_columnconfigure(0, weight=1)
        #self.status_text = ctk.CTkTextbox(self.status_frame, width=400, height=80)
        self.status_text = ctk.CTkTextbox(self.status_frame, height=80)
        self.status_text.grid(row=0, column=0, pady=10,padx=5,sticky="nsew") 
        self.progress_var = ctk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(self.status_frame, variable=self.progress_var, width=350)
        self.progress_bar.grid(row=1, column=0, pady=10)
        self.progress_bar.set(0)
        self.status_frame.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")

        self.end_frame = ctk.CTkFrame(self.main_frame)
        self.end_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(self.end_frame, text="Stop", fg_color="red", command=self.stop_download).grid(row=0, column=0, pady=5)
        ctk.CTkButton(self.end_frame, text="Exit", fg_color="red", command=self.exit_app).grid(row=1, column=0, pady=5)
        self.end_frame.grid(row=4, column=0, padx=10, pady=5, sticky="nsew")

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
    
    def update_ui(self):
        self.status_text.delete("1.0", "end")
        self.status_text.insert("1.0", config.status_str)
        if config.progress_num >= 0:
            if self.progress_bar.cget("mode")=="indeterminate":
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
            self.progress_var.set(config.progress_num / (config.progress_tot or 1))
        self.after(1000, self.update_ui)  # Update every second

    def get_refresh_and_access_tokens(self):
        try:
            access_token, refresh_token, name = procure_new_tokens_from_user()
            save_refresh_token(refresh_token)
            messagebox.showinfo("Success", f"Hello {name}! Tokens saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def use_refresh_token_to_get_new_access_token(self):
        try:
            refresh_token = load_refresh_token_from_file()
            if not refresh_token:
                messagebox.showerror("Error", "No refresh token found.")
                return
            new_access_token = get_new_access_token_using_refresh_token(refresh_token)
            save_access_token(new_access_token)
            config.status_str = "New access token saved successfully."
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def generate_list(self):
        config.stop_flag=False
        config.progress_num=-1
        
        self.progress_bar.configure(mode="indeterminate")

        self.progress_bar.start()
        threading.Thread(target=self._generate_list, daemon=True).start()
    
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
        config.progress_num=0
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        threading.Thread(target=self._download_files, daemon=True).start()
    
    def _download_files(self):
        try:
            self.use_refresh_token_to_get_new_access_token()
            access_token = load_access_token_from_file()
            if not access_token:
                messagebox.showerror("Error", "No access token found.")
                return
            download_the_list_of_files()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def choose_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.download_dir_var.set(directory)
            config.OFFLINEBACKUP_PATH = directory
            config.status_str = f"Download directory set to: {directory}"
    
    def set_onedrive_directory(self):
        config.ONEDRIVEDIR_PATH = self.root_dir_var.get()
        config.status_str = f"OneDrive Root directory set to: {config.ONEDRIVEDIR_PATH}"
    
    def stop_download(self):
        config.stop_flag = True
        config.status_str = "Stopping downloads..."
    
    def confirm_close(self):
        if messagebox.askyesno("Confirm Close", "Are you sure you want to close?"):
            self.exit_app()
    
    def exit_app(self):
        self.stop_download()
        self.quit()

if __name__ == "__main__":
    config.initialize()
    config.init_logging()
    logging.getLogger(__name__)
    logging.info("Application starts")
    app = OneDriveDownloader()
    app.mainloop()
