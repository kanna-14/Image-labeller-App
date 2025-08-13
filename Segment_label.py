# Updated full code as per your request

import tkinter as tk
import sys
from tkinter import filedialog, simpledialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
import os
import numpy as np

class SegmentationLabeler:
    def __init__(self, root, selected_folder):
        self.root = root
        self.root.title("Segmentation Labeling Tool")
        self.root.geometry("1280x720")
        self.root.state("zoomed")

        self.image_folder = selected_folder
        self.image_files = [f for f in os.listdir(selected_folder)
                            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
        self.image_index = 0

        self.class_colors = {}
        self.current_class = None
        self.drawing_mode = "pen"
        self.drawing = False
        self.pen_thickness = 2

        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.pan_start = None

        self.start_x = self.start_y = self.end_x = self.end_y = None
        self.polygon_points = []


        self.mask = None
        self.display_mask = None

        self.setup_ui()
        self.load_image()

    def setup_ui(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=6)
        self.root.grid_columnconfigure(1, weight=1)

        self.canvas = tk.Canvas(self.root, bg="black", cursor="cross")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.sidebar = tk.Frame(self.root, bg="#f0f0f0", padx=10, pady=10)
        self.sidebar.grid(row=0, column=1, sticky="nsew")

        tk.Label(self.sidebar, text="Class Name:").pack(anchor="w")
        self.class_entry = tk.Entry(self.sidebar)
        self.class_entry.pack(fill="x", pady=2)
        tk.Button(self.sidebar, text="Add Class", command=self.add_class).pack(fill="x", pady=2)

        tk.Label(self.sidebar, text="Select Class:").pack(anchor="w")
        self.class_dropdown = ttk.Combobox(self.sidebar, state="readonly")
        self.class_dropdown.pack(fill="x", pady=2)
        self.class_dropdown.bind("<<ComboboxSelected>>", self.select_class)

        tk.Label(self.sidebar, text="Drawing Mode:").pack(anchor="w", pady=(10, 2))
        tk.Button(self.sidebar, text="Pen Mode", command=lambda: self.set_mode("pen")).pack(fill="x", pady=2)
        tk.Button(self.sidebar, text="Erase Mode", command=lambda: self.set_mode("erase")).pack(fill="x", pady=2)
        tk.Button(self.sidebar, text="Rect Mode", command=lambda: self.set_mode("rect")).pack(fill="x", pady=2)

        tk.Label(self.sidebar, text="Navigation:").pack(anchor="w", pady=(10, 2))
        tk.Button(self.sidebar, text="Previous Image", command=self.prev_image).pack(fill="x", pady=2)
        tk.Button(self.sidebar, text="Next Image", command=self.next_image).pack(fill="x", pady=2)

        tk.Label(self.sidebar, text="Actions:").pack(anchor="w", pady=(10, 2))
        tk.Button(self.sidebar, text="Save Label", command=self.save_mask).pack(fill="x", pady=2)
        tk.Button(self.sidebar, text="Close", command=self.root.quit).pack(fill="x", pady=2)

        tk.Label(self.sidebar, text="Image List:").pack(anchor="w", pady=(10, 2))
        self.image_listbox = tk.Listbox(self.sidebar, height=15)
        self.image_listbox.pack(fill="both", expand=True)
        for idx, img in enumerate(self.image_files):
            self.image_listbox.insert(idx, img)
        self.image_listbox.bind("<<ListboxSelect>>", self.on_image_select)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<ButtonPress-3>", self.start_pan)
        self.canvas.bind("<B3-Motion>", self.do_pan)
        self.canvas.bind("<Double-Button-1>", self.finish_polygon)

    def on_image_select(self, event):
        selection = event.widget.curselection()
        if selection:
            self.image_index = selection[0]
            self.load_image()

    def add_class(self):
        name = self.class_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a class name.")
            return
        if name in self.class_colors:
            self.class_dropdown.set(name)
            self.current_class = name
            return

        color = tuple(np.random.randint(0, 256, 3).tolist())
        self.class_colors[name] = color
        self.class_dropdown["values"] = list(self.class_colors.keys())
        self.class_dropdown.set(name)
        self.current_class = name
        self.class_entry.delete(0, tk.END)

    def select_class(self, event):
        self.current_class = self.class_dropdown.get()

    def set_mode(self, mode):
        self.drawing_mode = mode
        self.polygon_points.clear()
        self.display_image()

    def load_image(self):
        image_path = os.path.join(self.image_folder, self.image_files[self.image_index])
        self.cv_image = cv2.imread(image_path)
        self.original_image = self.cv_image.copy()
        self.mask = np.zeros(self.cv_image.shape[:2], dtype=np.uint8)

        mask_folder = os.path.join(self.image_folder, "labels")
        label_path = os.path.join(mask_folder, f"{os.path.splitext(self.image_files[self.image_index])[0]}.txt")
        if os.path.exists(label_path):
            self.mask = np.loadtxt(label_path, dtype=np.uint8)
            if self.mask.shape != self.cv_image.shape[:2]:
                self.mask = np.zeros(self.cv_image.shape[:2], dtype=np.uint8)
        self.display_mask = self.mask.copy()
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.display_image()
        self.image_listbox.select_clear(0, tk.END)
        self.image_listbox.select_set(self.image_index)
        self.image_listbox.see(self.image_index)

    def display_image(self):
        overlay = self.original_image.copy()
        for idx, cls in enumerate(self.class_colors.keys(), 1):
            overlay[self.display_mask == idx] = self.class_colors[cls]

        if self.drawing_mode == "rect" and self.drawing and self.start_x and self.start_y and self.end_x and self.end_y:
            cv2.rectangle(overlay, (self.start_x, self.start_y), (self.end_x, self.end_y), (0, 255, 255), 1)

        resized = cv2.resize(overlay, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_NEAREST)
        self.tk_image = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)))
        self.canvas.delete("all")
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        self.offset_x = (canvas_width - resized.shape[1]) // 2 if self.offset_x == 0 else self.offset_x
        self.offset_y = (canvas_height - resized.shape[0]) // 2 if self.offset_y == 0 else self.offset_y
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.tk_image)

        if self.drawing_mode in ["pen", "erase"] and len(self.polygon_points) > 1:
            scaled_points = [((x * self.scale) + self.offset_x, (y * self.scale) + self.offset_y)
                             for x, y in self.polygon_points]
            self.canvas.create_line(scaled_points, fill="red", width=2)

    def canvas_to_image_coords(self, x, y):
        return int((x - self.offset_x) / self.scale), int((y - self.offset_y) / self.scale)

    def on_mouse_press(self, event):
        if not self.current_class and self.drawing_mode != "erase":
            messagebox.showwarning("Warning", "Please select a class first.")
            return
        x, y = self.canvas_to_image_coords(event.x, event.y)
        if self.drawing_mode in ["pen", "erase"]:
            self.polygon_points = [(x, y)]
        elif self.drawing_mode == "rect":
            self.start_x, self.start_y = x, y
            self.drawing = True

    def on_mouse_drag(self, event):
        x, y = self.canvas_to_image_coords(event.x, event.y)
        if self.drawing_mode in ["pen", "erase"]:
            self.polygon_points.append((x, y))
            cv2.line(self.display_mask,
                     self.polygon_points[-2],
                     self.polygon_points[-1],
                     0 if self.drawing_mode == "erase" else list(self.class_colors.keys()).index(self.current_class) + 1,
                     thickness=self.pen_thickness)
        elif self.drawing_mode == "rect" and self.drawing:
            self.end_x, self.end_y = x, y
        self.display_image()

    def on_mouse_release(self, event):
        if self.drawing_mode == "rect" and self.drawing:
            x1, y1 = self.start_x, self.start_y
            x2, y2 = self.canvas_to_image_coords(event.x, event.y)
            x1, x2 = sorted((x1, x2))
            y1, y2 = sorted((y1, y2))
            gray = cv2.cvtColor(self.original_image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
            class_idx = list(self.class_colors.keys()).index(self.current_class) + 1
            self.display_mask[y1:y2, x1:x2][binary == 0] = class_idx  # Inverse binary
        self.drawing = False
        self.polygon_points.clear()
        self.display_image()

    def finish_polygon(self, event):
        self.on_mouse_release(event)

    def on_mouse_wheel(self, event):
        cx = self.canvas.winfo_width() // 2
        cy = self.canvas.winfo_height() // 2
        image_x, image_y = self.canvas_to_image_coords(cx, cy)
        if event.delta > 0:
            self.scale *= 1.1
        else:
            self.scale /= 1.1
        new_image_x, new_image_y = image_x * self.scale, image_y * self.scale
        self.offset_x = cx - int(new_image_x)
        self.offset_y = cy - int(new_image_y)
        self.display_image()

    def start_pan(self, event):
        self.pan_start = (event.x, event.y)

    def do_pan(self, event):
        if self.pan_start:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start = (event.x, event.y)
            self.display_image()

    def save_mask(self):
        self.mask = self.display_mask.copy()
        base = os.path.splitext(self.image_files[self.image_index])[0]
        mask_folder = os.path.join(self.image_folder, "Segment_labels")
        os.makedirs(mask_folder, exist_ok=True)
        save_path = os.path.join(mask_folder, f"{base}.txt")
        np.savetxt(save_path, self.mask, fmt="%d")
        messagebox.showinfo("Saved", f"Mask saved to {save_path}")

    def prev_image(self):
        if self.image_index > 0:
            self.image_index -= 1
            self.load_image()

    def next_image(self):
        if self.image_index < len(self.image_files) - 1:
            self.image_index += 1
            self.load_image()

pass
def run_segment_label(folder):
    root = tk.Tk()
    app = SegmentationLabeler(root, folder)
    root.mainloop()
