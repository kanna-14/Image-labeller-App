import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import cv2
import json

class DetectionLabelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Detection Labeller")

        self.classes = []
        self.current_class = None
        self.current_image_index = 0
        self.images = []
        self.boxes = {}  # filename -> list of boxes [(x1, y1, x2, y2, class)]
        self.zoom_scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_start = None
        self.editing_box = None
        self.resizing_corner = None

        self.setup_ui()

    def setup_ui(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.top_frame = tk.Frame(self.main_frame)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Button(self.top_frame, text="Select Image Folder", command=self.select_folder).pack(side=tk.LEFT, padx=5)
        tk.Label(self.top_frame, text="Class:").pack(side=tk.LEFT)

        self.class_entry = tk.Entry(self.top_frame)
        self.class_entry.pack(side=tk.LEFT)

        tk.Button(self.top_frame, text="Add Class", command=self.add_class).pack(side=tk.LEFT, padx=5)

        self.class_combo = ttk.Combobox(self.top_frame, values=self.classes, state='readonly')
        self.class_combo.pack(side=tk.LEFT, padx=5)
        self.class_combo.bind("<<ComboboxSelected>>", self.select_class)

        tk.Button(self.top_frame, text="Save", command=self.save_boxes).pack(side=tk.LEFT, padx=5)
        tk.Button(self.top_frame, text="Prev", command=self.prev_image).pack(side=tk.LEFT, padx=5)
        tk.Button(self.top_frame, text="Next", command=self.next_image).pack(side=tk.LEFT, padx=5)
        tk.Button(self.top_frame, text="Delete Box", command=self.delete_selected_box).pack(side=tk.LEFT, padx=5)
        tk.Button(self.top_frame, text="Close", command=self.root.quit).pack(side=tk.LEFT, padx=5)

        self.right_frame = tk.Frame(self.main_frame)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.image_listbox = tk.Listbox(self.right_frame)
        self.image_listbox.pack(fill=tk.Y, expand=True)
        self.image_listbox.bind("<<ListboxSelect>>", self.on_image_select)

        self.canvas = tk.Canvas(self.main_frame, bg='gray', cursor="cross")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.canvas.bind("<Button-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.pan)

    def select_folder(self):
        self.image_folder = filedialog.askdirectory(title="Select Image Folder")
        if not self.image_folder:
            return
        self.annotation_folder = os.path.join(self.image_folder, "annotations")
        self.label_folder = os.path.join(self.image_folder, "labels")
        os.makedirs(self.annotation_folder, exist_ok=True)
        os.makedirs(self.label_folder, exist_ok=True)

        self.images = [f for f in os.listdir(self.image_folder) if f.lower().endswith(('jpg', 'jpeg', 'png', 'bmp'))]
        self.image_listbox.delete(0, tk.END)
        for img in self.images:
            self.image_listbox.insert(tk.END, img)
        if self.images:
            self.current_image_index = 0
            self.load_image()

    def add_class(self):
        new_class = self.class_entry.get().strip()
        if new_class and new_class not in self.classes:
            self.classes.append(new_class)
            self.class_combo['values'] = self.classes
            self.class_combo.set(new_class)
            self.current_class = new_class
            self.class_entry.delete(0, tk.END)

    def select_class(self, event):
        self.current_class = self.class_combo.get()

    def on_image_select(self, event):
        selection = self.image_listbox.curselection()
        if selection:
            self.current_image_index = selection[0]
            self.load_image()

    def load_image(self):
        filename = self.images[self.current_image_index]
        path = os.path.join(self.image_folder, filename)
        self.image = Image.open(path)
        self.original_image = self.image.copy()
        self.canvas.delete("all")
        self.zoom_scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.display_image()
        self.draw_boxes()

    def display_image(self):
        w, h = int(self.image.width * self.zoom_scale), int(self.image.height * self.zoom_scale)
        try:
            resample_method = Image.Resampling.LANCZOS
        except:
            resample_method = Image.ANTIALIAS
        resized = self.original_image.resize((w, h), resample_method)
        self.tk_image = ImageTk.PhotoImage(resized)
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.tk_image, tags="IMG")

    def get_class_color(self, cls):
        index = self.classes.index(cls) if cls in self.classes else 0
        color_list = ["red", "green", "blue", "orange", "purple", "cyan", "yellow"]
        return color_list[index % len(color_list)]

    def draw_boxes(self):
        self.canvas.delete("BOX")
        filename = self.images[self.current_image_index]
        for i, (x1, y1, x2, y2, cls) in enumerate(self.boxes.get(filename, [])):
            color = self.get_class_color(cls)
            self.canvas.create_rectangle(x1*self.zoom_scale + self.offset_x, y1*self.zoom_scale + self.offset_y,
                                         x2*self.zoom_scale + self.offset_x, y2*self.zoom_scale + self.offset_y,
                                         outline=color, width=2, tags="BOX")

    def save_boxes(self):
        filename = self.images[self.current_image_index]
        json_path = os.path.join(self.annotation_folder, filename + ".json")
        txt_path = os.path.join(self.label_folder, os.path.splitext(filename)[0] + ".txt")
        data = self.boxes.get(filename, [])
        with open(json_path, 'w') as f:
            json.dump(data, f)

        if data and self.original_image:
            img_w, img_h = self.original_image.size
            with open(txt_path, 'w') as f:
                for x1, y1, x2, y2, cls in data:
                    class_id = self.classes.index(cls)
                    xc = (x1 + x2) / 2 / img_w
                    yc = (y1 + y2) / 2 / img_h
                    w = abs(x2 - x1) / img_w
                    h = abs(y2 - y1) / img_h
                    f.write(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")

        messagebox.showinfo("Saved", f"Annotations saved to:\n{json_path}\n{txt_path}")

    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_image()

    def next_image(self):
        if self.current_image_index < len(self.images) - 1:
            self.current_image_index += 1
            self.load_image()

    def on_left_click(self, event):
        x, y = (event.x - self.offset_x) / self.zoom_scale, (event.y - self.offset_y) / self.zoom_scale
        filename = self.images[self.current_image_index]
        self.editing_box = None
        self.resizing_corner = None
        for i, (x1, y1, x2, y2, cls) in enumerate(self.boxes.get(filename, [])):
            if abs(x - x1) < 10 and abs(y - y1) < 10:
                self.editing_box = i
                self.resizing_corner = "tl"
                return
            elif abs(x - x2) < 10 and abs(y - y1) < 10:
                self.editing_box = i
                self.resizing_corner = "tr"
                return
            elif abs(x - x1) < 10 and abs(y - y2) < 10:
                self.editing_box = i
                self.resizing_corner = "bl"
                return
            elif abs(x - x2) < 10 and abs(y - y2) < 10:
                self.editing_box = i
                self.resizing_corner = "br"
                return
            elif x1 <= x <= x2 and y1 <= y <= y2:
                self.editing_box = i
                self.drag_start = (x, y)
                return
        if not self.current_class:
            messagebox.showwarning("Class Not Selected", "Please select a class.")
            return
        self.start_x = x
        self.start_y = y

    def on_right_click(self, event):
        if hasattr(self, 'start_x'):
            x, y = (event.x - self.offset_x) / self.zoom_scale, (event.y - self.offset_y) / self.zoom_scale
            x1, y1 = min(self.start_x, x), min(self.start_y, y)
            x2, y2 = max(self.start_x, x), max(self.start_y, y)
            filename = self.images[self.current_image_index]
            self.boxes.setdefault(filename, []).append((x1, y1, x2, y2, self.current_class))
            self.draw_boxes()

    def on_drag(self, event):
        x, y = (event.x - self.offset_x) / self.zoom_scale, (event.y - self.offset_y) / self.zoom_scale
        filename = self.images[self.current_image_index]
        if self.editing_box is not None:
            x1, y1, x2, y2, cls = self.boxes[filename][self.editing_box]
            if self.resizing_corner == "tl":
                x1, y1 = x, y
            elif self.resizing_corner == "tr":
                x2, y1 = x, y
            elif self.resizing_corner == "bl":
                x1, y2 = x, y
            elif self.resizing_corner == "br":
                x2, y2 = x, y
            else:
                dx = x - self.drag_start[0]
                dy = y - self.drag_start[1]
                x1 += dx
                y1 += dy
                x2 += dx
                y2 += dy
                self.drag_start = (x, y)
            self.boxes[filename][self.editing_box] = (x1, y1, x2, y2, cls)
            self.draw_boxes()

    def delete_selected_box(self):
        filename = self.images[self.current_image_index]
        if self.editing_box is not None and filename in self.boxes:
            del self.boxes[filename][self.editing_box]
            self.editing_box = None
            self.draw_boxes()

    def zoom(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_scale *= factor
        self.canvas.delete("all")
        self.display_image()
        self.draw_boxes()

    def start_pan(self, event):
        self.drag_start = (event.x, event.y)

    def pan(self, event):
        if self.drag_start:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            self.offset_x += dx
            self.offset_y += dy
            self.drag_start = (event.x, event.y)
            self.canvas.delete("all")
            self.display_image()
            self.draw_boxes()

if __name__ == '__main__':
    root = tk.Tk()
    app = DetectionLabelApp(root)
    root.mainloop()
