import tkinter as tk
from tkinter import messagebox, filedialog
import os
import subprocess
import datetime
import json
import ctypes
from Bounding_box import run_bounding_box
from Segment_label import run_segment_label

# Secure hidden file path
def get_user_file_path():
    hidden_dir = os.path.join(os.environ["PROGRAMDATA"], "ImageLabeler")
    os.makedirs(hidden_dir, exist_ok=True)
    return os.path.join(hidden_dir, "users.json")

def save_users(users_dict):
    filepath = get_user_file_path()
    with open(filepath, "w") as f:
        json.dump(users_dict, f, indent=4)
    try:
        ctypes.windll.kernel32.SetFileAttributesW(filepath, 0x02)  # Hide file (Windows)
    except:
        pass

def load_users():
    filepath = get_user_file_path()
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

USERS = load_users()

class App(tk.Tk):   
    def __init__(self):
        super().__init__()
        self.title("Image Labeling Tool")
        self.geometry("900x600")
        self.minsize(600, 400)
        self.resizable(True, True)

        container = tk.Frame(self)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (LoginPage, SignupPage, ActionSelectionPage, ProjectCreationPage):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(LoginPage)
        self.current_user = None

    def show_frame(self, page):
        frame = self.frames[page]
        frame.tkraise()


class LoginPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        center_frame = tk.Frame(self)
        center_frame.pack(expand=True)

        tk.Label(center_frame, text="Login", font=("Times New Roman", 32)).pack(pady=20)
        tk.Label(center_frame, text="Username").pack()
        self.username_entry = tk.Entry(center_frame, width=30)
        self.username_entry.pack(pady=5)

        tk.Label(center_frame, text="Password").pack()
        self.password_entry = tk.Entry(center_frame, show="*", width=30)
        self.password_entry.pack(pady=5)

        btn_frame = tk.Frame(center_frame)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Login", width=15, command=self.login).grid(row=0, column=0, padx=10)
        tk.Button(btn_frame, text="Signup", width=15, command=lambda: controller.show_frame(SignupPage)).grid(row=0, column=1, padx=10)

        tk.Button(center_frame, text="Close", width=20, command=controller.destroy).pack(pady=10)
        tk.Button(center_frame, text="Delete User", width=20, command=self.delete_user).pack()

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        global USERS
        USERS = load_users()

        if USERS.get(username) == password:
            messagebox.showinfo("Login Successful", f"Welcome {username}")
            self.controller.current_user = username
            self.controller.show_frame(ActionSelectionPage)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password")

    def delete_user(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        global USERS
        USERS = load_users()

        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return

        if username not in USERS:
            messagebox.showerror("Error", "User does not exist")
            return

        if USERS[username] != password:
            messagebox.showerror("Error", "Incorrect password")
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{username}'?"):
            del USERS[username]
            save_users(USERS)
            messagebox.showinfo("Deleted", f"User '{username}' deleted successfully.")
            self.username_entry.delete(0, tk.END)
            self.password_entry.delete(0, tk.END)


class SignupPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        main_frame = tk.Frame(self)
        main_frame.pack(expand=True)

        tk.Label(main_frame, text="Sign Up", font=("Times New Roman", 32)).pack(pady=20)
        tk.Label(main_frame, text="New Username").pack()
        self.new_username_entry = tk.Entry(main_frame)
        self.new_username_entry.pack(pady=5)

        tk.Label(main_frame, text="New Password").pack()
        self.new_password_entry = tk.Entry(main_frame, show="*")
        self.new_password_entry.pack(pady=5)

        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Create Account", width=20, command=self.create_account).grid(row=0, column=0, padx=10)
        tk.Button(btn_frame, text="Back to Login", width=20, command=lambda: controller.show_frame(LoginPage)).grid(row=0, column=1, padx=10)

    def create_account(self):
        username = self.new_username_entry.get().strip()
        password = self.new_password_entry.get().strip()
        global USERS
        USERS = load_users()

        if not username or not password:
            messagebox.showerror("Error", "Username and password cannot be empty.")
            return

        if username in USERS:
            messagebox.showerror("Error", "Username already exists.")
            return

        USERS[username] = password
        save_users(USERS)
        messagebox.showinfo("Success", "Account created successfully. Please login.")
        self.controller.show_frame(LoginPage)


class ActionSelectionPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        frame = tk.Frame(self)
        frame.pack(expand=True)

        tk.Label(frame, text="Select Action", font=("Times New Roman", 28)).pack(pady=30)

        tk.Button(frame, text="Label", width=20, height=2,
                  command=lambda: controller.show_frame(ProjectCreationPage)).pack(pady=10)

        tk.Button(frame, text="Train/Test", width=20, height=2,
                  command=self.launch_test_mode).pack(pady=10)

        tk.Button(frame, text="Logout", width=20, height=2,
                  command=lambda: controller.show_frame(LoginPage)).pack(pady=10)

    def launch_test_mode(self):
        folder = filedialog.askdirectory(title="Select Image Folder for Test Mode")
        if folder:
            try:
                subprocess.Popen(["python", "Test_mode.py", folder])
                self.controller.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Could not launch Test_mode.py: {e}")


class ProjectCreationPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.selected_folder = None

        main_frame = tk.Frame(self)
        main_frame.pack(expand=True)

        tk.Label(main_frame, text="Create Project", font=("Times New Roman", 32)).pack(pady=20)

        tk.Label(main_frame, text="Project Name").pack()
        self.project_name_entry = tk.Entry(main_frame)
        self.project_name_entry.pack(pady=5)

        tk.Label(main_frame, text="Select Labeling Mode").pack()
        self.mode_var = tk.StringVar(value="detection")
        tk.Radiobutton(main_frame, text="Detection", variable=self.mode_var, value="detection").pack(anchor="w")
        tk.Radiobutton(main_frame, text="Segmentation", variable=self.mode_var, value="segmentation").pack(anchor="w")

        tk.Button(main_frame, text="Select Image Folder", width=25, command=self.select_folder).pack(pady=5)
        tk.Button(main_frame, text="Create Project", width=25, command=self.create_project).pack(pady=5)
        tk.Button(main_frame, text="Close", width=25, command=controller.destroy).pack(pady=5)

    def select_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Images")
        if folder:
            self.selected_folder = folder
            messagebox.showinfo("Folder Selected", folder)

    def create_project(self):
        project_name = self.project_name_entry.get().strip()
        if not project_name:
            messagebox.showerror("Error", "Project name cannot be empty")
            return
        if not self.selected_folder:
            messagebox.showerror("Error", "No folder selected")
            return

        safe_project_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        project_file_name = f"{safe_project_name}.txt"
        project_file_path = os.path.join(self.selected_folder, project_file_name)

        username = getattr(self.controller, "current_user", "UnknownUser")
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode_selected = self.mode_var.get().capitalize()

        try:
            with open(project_file_path, "w") as f:
                f.write(f"Project Name: {project_name}\n")
                f.write(f"Created By: {username}\n")
                f.write(f"Creation Date & Time: {now_str}\n")
                f.write(f"Labeling Mode: {mode_selected}\n")

            messagebox.showinfo("Success", f"Project '{project_name}' saved as '{project_file_name}'.")
            self.controller.destroy()

            if self.mode_var.get() == "detection":
               run_bounding_box(self.selected_folder)
            else:
               run_segment_label(self.selected_folder)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save project file: {e}")
