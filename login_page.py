import tkinter as tk
from tkinter import messagebox, filedialog
import os
import subprocess
import datetime
import json
import ctypes
import shutil
import numpy as np
import tkinter.colorchooser as colorchooser
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
        #self.state('zoomed')

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
        self.controller.state('zoomed')

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

        # tk.Button(center_frame, text="Close", width=20, command=controller.destroy).pack(pady=10)
        tk.Button(center_frame, text="Delete User", width=20, command=self.delete_user).pack()

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        global USERS
        USERS = load_users()

        if USERS.get(username) == password:
            # messagebox.showinfo("Login Successful", f"Welcome {username}")
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
     self.controller.state('zoomed')

     self.class_names = []
     self.class_colors = {}

     # Main Title
     tk.Label(self, text="Create Project", font=("Times New Roman", 36, "bold")).pack(pady=20)

     # Project Details Frame
     project_frame = tk.LabelFrame(self, text="Project Details", padx=15, pady=15, font=("Arial", 12, "bold"))
     project_frame.pack(pady=10, ipadx=10, ipady=10)

     tk.Label(project_frame, text="Project Name:", font=("Arial", 11)).grid(row=0, column=0, sticky="w", pady=5)
     self.project_name_entry = tk.Entry(project_frame, width=40)
     self.project_name_entry.grid(row=0, column=1, pady=5)

     tk.Label(project_frame, text="Select Labeling Mode:", font=("Arial", 11)).grid(row=1, column=0, sticky="w", pady=5)
     self.mode_var = tk.StringVar(value="detection")
     tk.Radiobutton(project_frame, text="Detection", variable=self.mode_var, value="detection").grid(row=1, column=1, sticky="w")
     tk.Radiobutton(project_frame, text="Segmentation", variable=self.mode_var, value="segmentation").grid(row=1, column=1, sticky="e")

     tk.Button(project_frame, text="Select Image Folder", width=25, command=self.select_folder).grid(row=2, column=0, columnspan=2, pady=10)

     # Class Creation Frame
     class_frame = tk.LabelFrame(self, text="Add Classes Before Creating Project", padx=15, pady=15, font=("Arial", 12, "bold"))
     class_frame.pack(pady=10, ipadx=10, ipady=10)

     self.class_entry = tk.Entry(class_frame, width=30)
     self.class_entry.grid(row=0, column=0, padx=5, pady=5)
     tk.Button(class_frame, text="Add Class", width=15, command=self.add_class).grid(row=0, column=1, padx=5, pady=5)

     # Action Buttons Frame
     action_frame = tk.Frame(self)
     action_frame.pack(fill="x", pady=10, padx=10)
     button_frame = tk.Frame(action_frame)
     button_frame.pack(anchor="center")  

     tk.Button(button_frame, text="Browse Project", command=self.browse_project, width=15).pack(side="left", padx=(0, 5))
     tk.Button(button_frame, text="Create Project", command=self.create_project, width=15).pack(side="left", padx=(0, 5))
     tk.Button(button_frame, text="Close", width=15, command=controller.destroy).pack(side="left")


    def select_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Images")
        if folder:
            self.selected_folder = folder
            # messagebox.showinfo("Folder Selected", folder)

    def create_project(self):
        project_name = self.project_name_entry.get().strip()
        if not project_name:
            messagebox.showerror("Error", "Project name cannot be empty")
            return
        if not self.selected_folder:
            messagebox.showerror("Error", "No image folder selected")
            return
        if not self.class_names:
            messagebox.showerror("Error", "Please add at least one class before creating the project")
            return

        safe_project_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        project_folder = os.path.join(os.path.dirname(self.selected_folder), safe_project_name)
        os.makedirs(project_folder, exist_ok=True)

        images_folder = os.path.join(project_folder, "images")
        labels_folder = os.path.join(project_folder, "Box_labels")
        os.makedirs(images_folder, exist_ok=True)
        os.makedirs(labels_folder, exist_ok=True)

        # Copy images
        supported_exts = (".jpg", ".jpeg", ".png", ".bmp")
        copied_count = 0
        for img_file in os.listdir(self.selected_folder):
            if img_file.lower().endswith(supported_exts):
                src_path = os.path.join(self.selected_folder, img_file)
                dst_path = os.path.join(images_folder, img_file)
                if not os.path.exists(dst_path):
                    shutil.copy2(src_path, dst_path)
                    copied_count += 1

        # Save metadata
        project_file_path = os.path.join(project_folder, "project.txt")
        username = getattr(self.controller, "current_user", "UnknownUser")
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode_selected = self.mode_var.get().capitalize()

        with open(project_file_path, "w") as f:
            f.write(f"Project Name: {project_name}\n")
            f.write(f"Created By: {username}\n")
            f.write(f"Creation Date & Time: {now_str}\n")
            f.write(f"Labeling Mode: {mode_selected}\n")
            f.write(f"Image Folder: images\n")
            f.write(f"Labels Folder: Box_labels\n")

        # Save classes.txt
        classes_file = os.path.join(project_folder, "classes.txt")
        with open(classes_file, "w", encoding="utf-8") as f:
            for idx, cls_name in enumerate(self.class_names):
                r, g, b = self.class_colors[cls_name]
                f.write(f"{idx} {cls_name} {r} {g} {b}\n")

        # messagebox.showinfo(
        #     "Success",
        #     f"Project '{project_name}' created at:\n{project_folder}\n\nImages copied: {copied_count}")

        # Launch labeling tool
        self.controller.destroy()
        if mode_selected.lower() == "detection":
            run_bounding_box(project_folder)
        else:
            run_segment_label(project_folder)

    def browse_project(self):
        folder_selected = filedialog.askdirectory(title="Select Project Folder")
        if not folder_selected:
            return
        project_file_path = os.path.join(folder_selected, "project.txt")
        if not os.path.exists(project_file_path):
            messagebox.showerror("Error", "This folder does not contain a valid project.")
            return
        self.controller.destroy()
        run_bounding_box(folder_selected)

    def hex_to_rgb(hex_color):
     hex_color = hex_color.lstrip('#')
     return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def add_class(self):
     class_name = self.class_entry.get().strip()
     if not class_name:
        return
     if class_name in self.class_names:
        return
    
     color = colorchooser.askcolor(title=f"Choose color for class '{class_name}'")
     if color[0] is None:
        return
    
     # Store RGB tuple (integers)
     self.class_colors[class_name] = tuple(map(int, color[0]))
    
     # Store class name
     self.class_names.append(class_name)
    
     # Clear entry box
     self.class_entry.delete(0, tk.END)
