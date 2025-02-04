import tkinter as tk
from tkinter import messagebox
import logging
import os
from onedrive_authorization_utils import (
    save_refresh_token, load_access_token_from_file,
    procure_new_tokens_from_user, get_new_access_token_using_refresh_token,
    save_access_token, load_refresh_token_from_file
)
from generate_list import generate_list_of_all_files_and_folders
from download_list import download_the_list_of_files

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

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
        messagebox.showinfo("Success", "New access token has been saved.")
        logging.info("New access token saved successfully.")
    except Exception as e:
        logging.error(f"Error refreshing access token: {e}")
        messagebox.showerror("Error", f"Failed to refresh access token: {str(e)}")

def generate_list():
    try:
        access_token = load_access_token_from_file()
        if not access_token:
            logging.error("No access token found.")
            messagebox.showerror("Error", "No access token found. Please authenticate first.")
            return
        generate_list_of_all_files_and_folders(access_token=access_token)
        messagebox.showinfo("Success", "File list generated successfully.")
        logging.info("File list generation completed.")
    except Exception as e:
        logging.error(f"Error generating file list: {e}")
        messagebox.showerror("Error", f"Failed to generate file list: {str(e)}")

def download_files():
    try:
        access_token = load_access_token_from_file()
        if not access_token:
            logging.error("No access token found.")
            messagebox.showerror("Error", "No access token found. Please authenticate first.")
            return
        download_the_list_of_files(access_token)
        messagebox.showinfo("Success", "Files downloaded successfully.")
        logging.info("File download completed.")
    except Exception as e:
        logging.error(f"Error downloading files: {e}")
        messagebox.showerror("Error", f"Failed to download files: {str(e)}")

def main():
    root = tk.Tk()
    root.title("OneDrive Downloader")
    root.geometry("400x300")
    
    tk.Label(root, text="OneDrive Downloader", font=("Arial", 14, "bold")).pack(pady=10)
    
    tk.Button(root, text="Get Refresh and Access Tokens", command=get_refresh_and_access_tokens, width=40).pack(pady=5)
    tk.Button(root, text="Use Refresh Token to Get New Access Token", command=use_refresh_token_to_get_new_access_token, width=40).pack(pady=5)
    tk.Button(root, text="Generate List of All Files and Folders", command=generate_list, width=40).pack(pady=5)
    tk.Button(root, text="Download Files from Generated List", command=download_files, width=40).pack(pady=5)
    
    tk.Button(root, text="Exit", command=root.quit, width=40, bg="red", fg="white").pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()
