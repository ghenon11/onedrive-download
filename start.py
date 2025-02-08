import tkinter as tk
from tkinter import ttk
from tkinter import messagebox, filedialog
import logging
import os,threading,time,traceback
import config
from onedrive_authorization_utils import (
    save_refresh_token, load_access_token_from_file,
    procure_new_tokens_from_user, get_new_access_token_using_refresh_token,
    save_access_token, load_refresh_token_from_file
)
from generate_list import generate_list_of_all_files_and_folders
from download_list import download_the_list_of_files


def get_refresh_and_access_tokens():
    try:
        logging.info("Starting token procurement process.")
        access_token, refresh_token, name = procure_new_tokens_from_user()
        save_refresh_token(refresh_token)
        messagebox.showinfo("Success", f"Hello {name}! Tokens have been saved securely.")
        logging.info("Tokens saved successfully.")
    except Exception as e:
        logging.error(f"Error obtaining tokens: {e}")
        messagebox.showerror("Error", f"Failed to obtain tokens: {str(e)}")

def use_refresh_token_to_get_new_access_token():
    try:
        refresh_token = load_refresh_token_from_file()
        if refresh_token is None:
            logging.error("No refresh token found.")
            messagebox.showerror("Error", "No refresh token found. Please generate a new one.")
            return
        new_access_token = get_new_access_token_using_refresh_token(refresh_token)
        save_access_token(new_access_token)
        logging.info("New access token saved successfully.")
        config.status_str="New access token saved successfully."
    except Exception as e:
        logging.error(f"Error refreshing access token: {e}")
        messagebox.showerror("Error", f"Failed to refresh access token: {str(e)}")

def generate_list():
    global progress_bar
    
    def start_generate():
        try:
            generate_list_of_all_files_and_folders(access_token=access_token)
        except Exception as e:
            logging.error(f"Error in start generate list: {e}")
            logging.error("Traceback: %s", traceback.format_exc())
            
    try:
        use_refresh_token_to_get_new_access_token()
        access_token = load_access_token_from_file()
        if not access_token:
            logging.error("No access token found.")
            messagebox.showerror("Error", "No access token found. Please authenticate first.")
            return
        
        config.stop_flag=False
        config.progress_num=-1
        progress_bar.config(mode="indeterminate")
        progress_bar.config(maximum=100)
        progress_bar.start()
        # generate_list_of_all_files_and_folders(access_token=access_token)
        # messagebox.showinfo("Success", "File list generated successfully.")
        # logging.info("File list generation completed.")
        recording_thread = threading.Thread(target=start_generate, daemon=True)
        recording_thread.start()
        
    except Exception as e:
        logging.error(f"Error generating file list: {e}")
        logging.error("Traceback: %s", traceback.format_exc())
        messagebox.showerror("Error", f"Failed to generate file list: {str(e)}")

def download_files():
        
    #Launch process_recording in a separate thread.
    def start_download():
        try:
            download_the_list_of_files()
        except Exception as e:
            logging.error(f"Error in start download: {e}")
            logging.error("Traceback: %s", traceback.format_exc())
      
    try:
        use_refresh_token_to_get_new_access_token()
        access_token = load_access_token_from_file()
        if not access_token:
            logging.error("No access token found.")
            messagebox.showerror("Error", "No access token found. Please authenticate first.")
            return
        #download_the_list_of_files()
        # Start the thread
        config.stop_flag=False
        recording_thread = threading.Thread(target=start_download, daemon=True)
        recording_thread.start()
        
    except Exception as e:
        logging.error(f"Error downloading files: {e}")
        messagebox.showerror("Error", f"Failed to download files: {str(e)}")

def main():
    
    global status_text,progress_bar
    
    def exit_button():
        try:
            stop_download()
            root.quit()
        except Exception as e:
            logging.error("Error when exiting", str(e))
    
    def confirm_close():
        result = messagebox.askyesno("Confirm Close", "Are you sure you want to close?")
        if result:
            exit_button()

    def choose_directory():
        directory = filedialog.askdirectory(title="Choose Download Directory", initialdir=config.OFFLINEBACKUP_PATH)
        if directory:
            download_dir_var.set(directory)
            config.OFFLINEBACKUP_PATH = download_dir_var.get()
            config.status_str="Success\nDownload directory set to: "+config.OFFLINEBACKUP_PATH

    def choose_onedrivedirectory():
        config.ONEDRIVEDIR_PATH = root_dir_var.get()
        config.status_str="Success\nOneDrive Root directory set to: "+config.ONEDRIVEDIR_PATH
       # messagebox.showinfo("Success", f"OneDrive Root directory set to: {config.ONEDRIVEDIR_PATH}")
    
    def stop_download():
        config.stop_flag = True
        logging.info("Stopping identification and new downloads...")
        #messagebox.showinfo("Stopping", "New Identification and download have been stopped.")
        
   
    root = tk.Tk()
    root.title("OneDrive Downloader")
    root.geometry("400x600")
    root.protocol("WM_DELETE_WINDOW", confirm_close)
    
    tk.Label(root, text="OneDrive Downloader", font=("Arial", 14, "bold")).pack(pady=10)
    
    tk.Button(root, text="Get Refresh and Access Tokens", command=get_refresh_and_access_tokens, width=40).pack(pady=5)
    
   
    tk.Label(root, text="OneDrive Root Directory:").pack()
    root_dir_var = tk.StringVar(value=config.ONEDRIVEDIR_PATH)
    tk.Entry(root, textvariable=root_dir_var, width=50).pack()
    tk.Button(root, text="Set OneDrive Root Directory", command=choose_onedrivedirectory).pack()
    tk.Button(root, text="Generate List of All Files and Folders", command=generate_list, width=40).pack(pady=5)
    
    tk.Label(root, text="Download Directory:").pack()
    download_dir_var = tk.StringVar(value=config.OFFLINEBACKUP_PATH)
    tk.Entry(root, textvariable=download_dir_var, width=50).pack()
    tk.Button(root, text="Choose Directory", command=choose_directory).pack()
    tk.Button(root, text="Download Files from Generated List", command=download_files, width=40).pack(pady=5)
    
    
    status_text=tk.Text(root,width=40,height=4)
    status_text.insert(tk.END, config.status_str)
    status_text.pack(pady=10)
    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(root, variable=progress_var, length=300)
    progress_bar.pack(pady=10)
       
    #tk.Button(root, text="Get New Access Token", command=use_refresh_token_to_get_new_access_token, width=40).pack(pady=5)
    
    
    tk.Button(root, text="Stop Processing", command=stop_download, fg="red").pack()
    tk.Button(root, text="Exit", command=exit_button, width=40, bg="red", fg="white").pack(pady=10)
    
    def update_progress_bar():
        while True:
            status_text.delete('1.0',tk.END)
            status_text.insert('1.0', config.status_str)
            test=progress_bar["mode"]
            if test == "determinate":
                if config.progress_num>=0:
                    progress_var.set(config.progress_num)
                    progress_bar.config(maximum=config.progress_tot)
                # else:
                    # if config.progress_num==-1: # generating file mode
                        # progress_bar.config(mode="indeterminate")
                        # time.sleep(1)
                        # progress_bar.config(maximum=100)
                        # progress_bar.start()
            else:
                if config.progress_num==0:
                    progress_bar.stop()
                    progress_bar.config(mode="determinate")
                    progress_var.set(config.progress_num)
                    progress_bar.config(maximum=100)
            time.sleep(1)
            
    # Start a thread to update the progress bar
    thread = threading.Thread(target=update_progress_bar, daemon=True)
    thread.start()

    root.mainloop()
    
if __name__ == "__main__":
    config.initialize()
    config.init_logging()
    logging = logging.getLogger(__name__)
    print(f"Logging in file {config.LOG_FILE}")
    main()
