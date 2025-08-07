import tkinter as tk
import sys
from tkinter import filedialog, simpledialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
import os
import numpy as np

class BoundingBoxLabeler:
    def __init__(self, root, selected_folder):
        self.root = root
        self.root.title("Bounding Box Labeling Tool")
        self.root.geometry("1280x720")
        self.root.state("zoomed")

        self.image_folder = selected_folder
        self.image_files = [f for f in os.listdir(selected_folder)
                            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
        self.image_index = 0

        self.class_colors = {}
        self.current_class = None
        self.bboxes = []
        self.selected_box = None
        self.dragging = False
        self.resizing = False
        self.resize_corner = None

        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_start = None

        self.start_x = self.start_y = self.end_x = self.end_y = None

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

        tk.Label(self.sidebar, text="Navigation:").pack(anchor="w", pady=(10, 2))
        tk.Button(self.sidebar, text="Previous Image", command=self.prev_image).pack(fill="x", pady=2)
        tk.Button(self.sidebar, text="Next Image", command=self.next_image).pack(fill="x", pady=2)

        tk.Label(self.sidebar, text="Actions:").pack(anchor="w", pady=(10, 2))
        tk.Button(self.sidebar, text="Save Boxes", command=self.save_boxes).pack(fill="x", pady=2)
        tk.Button(self.sidebar, text="Close", command=self.root.quit).pack(fill="x", pady=2)

        tk.Label(self.sidebar, text="Image List:").pack(anchor="w", pady=(10, 2))
        self.image_listbox = tk.Listbox(self.sidebar, height=15)
        self.image_listbox.pack(fill="both", expand=True)
        for idx, img in enumerate(self.image_files):
            self.image_listbox.insert(idx, img)
        self.image_listbox.bind("<<ListboxSelect>>", self.on_image_select)

        # Left click: draw bounding boxes
        self.canvas.bind("<ButtonPress-1>", self.on_draw_press)
        self.canvas.bind("<B1-Motion>", self.on_draw_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_draw_release)

        # Middle click: pan the image
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)

        # Mouse wheel: zoom
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

       # Right click: select/move/resize bounding boxes
        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release)


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

    def on_image_select(self, event):
        selection = event.widget.curselection()
        if selection:
            self.image_index = selection[0]
            self.load_image()

    def load_image(self):
        image_path = os.path.join(self.image_folder, self.image_files[self.image_index])
        self.cv_image = cv2.imread(image_path)
        self.original_image = self.cv_image.copy()
        self.bboxes = []

        label_path = os.path.join(self.image_folder, "Box_labels", f"{os.path.splitext(self.image_files[self.image_index])[0]}.txt")
        if os.path.exists(label_path):
            with open(label_path, "r") as f:
                for line in f.readlines():
                    parts = line.strip().split()
                    if len(parts) == 5:
                        class_idx = int(parts[0])
                        x1, y1, x2, y2 = map(int, map(float, parts[1:]))
                        cls_name = list(self.class_colors.keys())[class_idx] if class_idx < len(self.class_colors) else f"class_{class_idx}"
                        self.bboxes.append((cls_name, x1, y1, x2, y2))

        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.display_image()
        self.image_listbox.select_clear(0, tk.END)
        self.image_listbox.select_set(self.image_index)
        self.image_listbox.see(self.image_index)

    def display_image(self):
        image = self.original_image.copy()
        for cls_name, x1, y1, x2, y2 in self.bboxes:
            color = self.class_colors.get(cls_name, (0, 255, 0))
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            cv2.putText(image, cls_name, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)

        resized = cv2.resize(image, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_LINEAR)
        self.tk_image = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)))
        self.canvas.delete("all")

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        self.offset_x = (canvas_width - resized.shape[1]) // 2 if self.offset_x == 0 else self.offset_x
        self.offset_y = (canvas_height - resized.shape[0]) // 2 if self.offset_y == 0 else self.offset_y
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.tk_image)

    def canvas_to_image_coords(self, x, y):
        return int((x - self.offset_x) / self.scale), int((y - self.offset_y) / self.scale)
    
    def get_resize_corner(self, x, y, x1, y1, x2, y2, threshold=10):
     corners = {
        "tl": (x1, y1),
        "tr": (x2, y1),
        "bl": (x1, y2),
        "br": (x2, y2)
     }
     for name, (cx, cy) in corners.items():
         if abs(x - cx) <= threshold and abs(y - cy) <= threshold:
            return name
     return None

    def on_draw_press(self, event):
     x, y = self.canvas_to_image_coords(event.x, event.y)
     self.start_x, self.start_y = x, y
     self.end_x = self.end_y = None
     self.dragging = False
     self.resizing = False
     self.selected_box = None

    def on_draw_drag(self, event):
     x, y = self.canvas_to_image_coords(event.x, event.y)
     self.end_x, self.end_y = x, y
     self.display_image()

    def on_draw_release(self, event):
     if self.current_class and self.start_x is not None and self.end_x is not None:
        x1, y1 = min(self.start_x, self.end_x), min(self.start_y, self.end_y)
        x2, y2 = max(self.start_x, self.end_x), max(self.start_y, self.end_y)
        self.bboxes.append((self.current_class, x1, y1, x2, y2))
     self.display_image()
    
    def on_right_press(self, event):
     x, y = self.canvas_to_image_coords(event.x, event.y)
     for i, (cls, x1, y1, x2, y2) in enumerate(reversed(self.bboxes)):
        resize_corner = self.get_resize_corner(x, y, x1, y1, x2, y2)
        if resize_corner:
            self.selected_box = len(self.bboxes) - 1 - i
            self.resizing = True
            self.resize_corner = resize_corner
            self.start_x, self.start_y = x, y
            return
        if x1 <= x <= x2 and y1 <= y <= y2:
            self.selected_box = len(self.bboxes) - 1 - i
            self.dragging = True
            self.start_x, self.start_y = x, y
            return
     self.selected_box = None
     self.dragging = False
     self.resizing = False

    def on_right_drag(self, event):
     x, y = self.canvas_to_image_coords(event.x, event.y)
     if self.resizing and self.selected_box is not None:
        cls, x1, y1, x2, y2 = self.bboxes[self.selected_box]
        if self.resize_corner == "tl":
            x1, y1 = x, y
        elif self.resize_corner == "tr":
            x2, y1 = x, y
        elif self.resize_corner == "bl":
            x1, y2 = x, y
        elif self.resize_corner == "br":
            x2, y2 = x, y
        self.bboxes[self.selected_box] = (cls, min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
     elif self.dragging and self.selected_box is not None:
        cls, x1, y1, x2, y2 = self.bboxes[self.selected_box]
        dx, dy = x - self.start_x, y - self.start_y
        self.bboxes[self.selected_box] = (cls, x1 + dx, y1 + dy, x2 + dx, y2 + dy)
        self.start_x, self.start_y = x, y
     self.display_image()

    def on_right_release(self, event):
     self.dragging = False
     self.resizing = False
     self.resize_corner = None
     self.selected_box = None
     self.display_image()

    def on_mouse_press(self, event):
     x, y = self.canvas_to_image_coords(event.x, event.y)
     for i, (cls, x1, y1, x2, y2) in enumerate(reversed(self.bboxes)):
         resize_corner = self.get_resize_corner(x, y, x1, y1, x2, y2)
         if resize_corner:
             self.selected_box = len(self.bboxes) - 1 - i
             self.resizing = True
             self.resize_corner = resize_corner
             return
         if x1 <= x <= x2 and y1 <= y <= y2:
             self.selected_box = len(self.bboxes) - 1 - i
             self.dragging = True
             return
     self.start_x, self.start_y = x, y
     self.end_x = self.end_y = None
     self.dragging = False
     self.resizing = False
     self.selected_box = None


    def on_mouse_drag(self, event):
     x, y = self.canvas_to_image_coords(event.x, event.y)
     if self.resizing and self.selected_box is not None:
        cls, x1, y1, x2, y2 = self.bboxes[self.selected_box]
        if self.resize_corner == "tl":
            x1, y1 = x, y
        elif self.resize_corner == "tr":
            x2, y1 = x, y
        elif self.resize_corner == "bl":
            x1, y2 = x, y
        elif self.resize_corner == "br":
            x2, y2 = x, y
        self.bboxes[self.selected_box] = (cls, min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
     elif self.dragging and self.selected_box is not None:
        cls, x1, y1, x2, y2 = self.bboxes[self.selected_box]
        dx, dy = x - self.start_x, y - self.start_y
        self.bboxes[self.selected_box] = (cls, x1 + dx, y1 + dy, x2 + dx, y2 + dy)
        self.start_x, self.start_y = x, y
     else:
        self.end_x, self.end_y = x, y
     self.display_image()


    def on_mouse_release(self, event):
     if not self.dragging and not self.resizing and self.current_class and self.start_x and self.end_x:
        x1, y1 = min(self.start_x, self.end_x), min(self.start_y, self.end_y)
        x2, y2 = max(self.start_x, self.end_x), max(self.start_y, self.end_y)
        self.bboxes.append((self.current_class, x1, y1, x2, y2))
     self.dragging = False
     self.resizing = False
     self.resize_corner = None
     self.selected_box = None
     self.display_image()


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


    def save_boxes(self):
        os.makedirs(os.path.join(self.image_folder, "Box_labels"), exist_ok=True)
        save_path = os.path.join(self.image_folder, "Box_labels", f"{os.path.splitext(self.image_files[self.image_index])[0]}.txt")
        with open(save_path, "w") as f:
            for cls_name, x1, y1, x2, y2 in self.bboxes:
                class_idx = list(self.class_colors.keys()).index(cls_name)
                f.write(f"{class_idx} {x1} {y1} {x2} {y2}\n")
        messagebox.showinfo("Saved", f"Boxes saved to {save_path}")

    def prev_image(self):
        if self.image_index > 0:
            self.image_index -= 1
            self.load_image()

    def next_image(self):
        if self.image_index < len(self.image_files) - 1:
            self.image_index += 1
            self.load_image()


def launch_labeling_app(folder):
    root = tk.Tk()
    app = BoundingBoxLabeler(root, folder)
    root.mainloop()


# if __name__ == "__main__":
#     if len(sys.argv) > 1:
#         selected_folder = sys.argv[1]
#         launch_labeling_app(selected_folder)
#     else:
#         print("❌ Error: No folder path provided to basic_label.py")
pass

def run_bounding_box(selected_folder):
    root = tk.Tk()
    app = BoundingBoxLabeler(root, selected_folder)
    root.mainloop()
