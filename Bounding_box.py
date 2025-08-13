import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk

class BoundingBoxLabeler:
    def __init__(self, root, project_folder):
        self.root = root
        self.root.title("Bounding Box Labeling Tool")
        try:
            self.root.state("zoomed")
        except Exception:
            pass

        # project and folders
        self.project_folder = project_folder
        self.image_folder = os.path.join(project_folder, "images")
        self.labels_folder = os.path.join(project_folder, "Box_labels")
        os.makedirs(self.labels_folder, exist_ok=True)

        # file lists
        self.image_files = sorted([f for f in os.listdir(self.image_folder)
                                   if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))])
        self.image_index = 0

        # classes: keep ordered list + color map (to preserve indices)
        self.class_names = []              # list of class names in order -> index
        self.class_colors = {}             # class_name -> (r,g,b)
        self.current_class = None
        self.bboxes = []

        # selection / interaction state
        self.selected_box = None
        self.drawing = False
        self.dragging = False
        self.resizing = False
        self.resize_corner = None  # 'tl','tr','bl','br'
        self.start_x_image = self.start_y_image = None
        self.prev_mouse_x = self.prev_mouse_y = None

        # view transform (image -> canvas)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # UI elements placeholders
        self.canvas = None
        self.image_listbox = None
        self.class_entry = None
        self.class_dropdown = None
        self.tk_image = None
        self.original_image = None
        self.cv_image = None

        # build UI + bindings
        self.setup_ui()
        self.load_classes()   # load classes.txt if exists (populates class_names & class_colors)

        if self.image_files:
            self.load_image()
        else:
            messagebox.showinfo("Info", "No images found in project images folder.")

    # ---------------- UI setup ----------------
    def setup_ui(self):
     # Main area on the left
     main_area = tk.Frame(self.root)
     main_area.pack(side="left", fill="both", expand=True)

     # ==== Toolbar (buttons + class selector) ====
     toolbar = tk.Frame(main_area)
     toolbar.pack(side="top", pady=5, fill="x")

     btn_prev = tk.Button(
     toolbar, text="←\nprev", font=("Arial", 16), width=3, command=self.prev_image,
     bg="#ffcccc", fg="black", activebackground="#f0efef", activeforeground="white")
     btn_prev.pack(side="left", padx=5)

     btn_next = tk.Button(
     toolbar, text="→\nnext", font=("Arial", 16), width=3, command=self.next_image,
     bg="#ccffcc", fg="black", activebackground="#eef5ee", activeforeground="white")
     btn_next.pack(side="left", padx=5)

     btn_save = tk.Button(
     toolbar, text="💾\nSave", font=("Arial", 16), width=3, command=self.save_boxes,
     bg="#ccccff", fg="black", activebackground="#ececf1", activeforeground="white")
     btn_save.pack(side="left", padx=5)

     # Class selector
     tk.Label(toolbar, text="Class:").pack(side="left", padx=(15, 5))
     self.class_dropdown = ttk.Combobox(toolbar, state="readonly", values=self.class_names)
     self.class_dropdown.pack(side="left", padx=5)
     self.class_dropdown.bind("<<ComboboxSelected>>", self.on_class_selected)

     #  # ==== Canvas below toolbar ====
     #  self.canvas = tk.Canvas(main_area, bg="black", cursor="cross")
     #  self.canvas.pack(fill="both", expand=True)

     # Wrap canvas in a frame with scrollbars
     canvas_frame = tk.Frame(main_area)
     canvas_frame.pack(fill="both", expand=True)

     self.canvas = tk.Canvas(canvas_frame, bg="black", cursor="cross")
     self.canvas.grid(row=0, column=0, sticky="nsew")

     # Scrollbars
     x_scroll = tk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
     x_scroll.grid(row=1, column=0, sticky="ew")
     y_scroll = tk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
     y_scroll.grid(row=0, column=1, sticky="ns")

     self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)

     canvas_frame.rowconfigure(0, weight=1)
     canvas_frame.columnconfigure(0, weight=1)

     # ==== Sidebar ====
     sidebar = tk.Frame(self.root, padx=10, pady=10)
     sidebar.pack(side="right", fill="y")

     tk.Label(sidebar, text="Images:").pack(anchor="w", pady=(8, 0))

     self.labeled_count_label = tk.Label(sidebar, text="")
     self.labeled_count_label.pack(anchor="w", pady=(0, 6))

     list_frame = tk.Frame(sidebar)
     list_frame.pack(fill="both", expand=True)

     self.image_listbox = tk.Listbox(list_frame)
     self.image_listbox.pack(side="left", fill="both", expand=True)

     scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.image_listbox.yview)
     scrollbar.pack(side="right", fill="y")

     self.image_listbox.config(yscrollcommand=scrollbar.set)
     self.image_listbox.bind("<<ListboxSelect>>", self.on_image_select)

     # Load image list initially
     self.refresh_image_list()

        # for idx, fname in enumerate(self.image_files):
        #     self.image_listbox.insert(idx, fname)
        # self.image_listbox.bind("<<ListboxSelect>>", self.on_image_select)

        # canvas bindings (mouse)
     self.canvas.bind("<ButtonPress-1>", self.on_left_press)            # left down
     self.canvas.bind("<B1-Motion>", self.on_left_drag)                # left drag
     self.canvas.bind("<ButtonRelease-1>", self.on_left_release)       # left up

     self.canvas.bind("<ButtonPress-3>", self.on_right_press)          # right click (context)
     self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)             # zoom (win)
     self.canvas.bind("<ButtonPress-2>", self.on_middle_press)         # middle press
     self.canvas.bind("<B2-Motion>", self.on_middle_drag)              # middle drag pan

        # keyboard bindings
     self.root.bind("<Delete>", lambda e: self.delete_selected_box())

    # ---------------- classes file handling ----------------
    def classes_file_path(self):
        return os.path.join(self.project_folder, "classes.txt")

    def load_classes(self):
        self.class_names = []
        self.class_colors = {}
        path = self.classes_file_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        # format: idx cls_name r g b
                        idx = parts[0]  # ignore index, use order from file
                        cls_name = " ".join(parts[1:-3])
                        r,g,b = map(int, parts[-3:])
                        self.class_names.append(cls_name)
                        self.class_colors[cls_name] = (r,g,b)
        # update dropdown
        self.class_dropdown['values'] = self.class_names
        if self.class_names and not self.current_class:
            self.current_class = self.class_names[0]
            self.class_dropdown.set(self.current_class)

    def save_classes(self):
        path = self.classes_file_path()
        with open(path, "w", encoding="utf-8") as f:
            for idx, cls_name in enumerate(self.class_names):
                r,g,b = self.class_colors.get(cls_name, (0,255,0))
                f.write(f"{idx} {cls_name} {r} {g} {b}\n")

    def on_class_selected(self, event=None):
        sel = self.class_dropdown.get()
        if sel:
            self.current_class = sel
            # if a box selected, optionally update it immediately
            if self.selected_box is not None:
                self.bboxes[self.selected_box] = (sel, *self.bboxes[self.selected_box][1:])
                self.save_boxes()
                self.display_image()

    # ---------------- image & labels load/save ----------------
    def load_image(self):
        # load classes first to ensure indices
        self.load_classes()

        img_path = os.path.join(self.image_folder, self.image_files[self.image_index])
        self.cv_image = cv2.imread(img_path)
        if self.cv_image is None:
            messagebox.showerror("Error", f"Cannot open image: {img_path}")
            return
        self.original_image = self.cv_image.copy()
        self.bboxes = []
        self.selected_box = None

        # reset view (center)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # load label YOLO format if exists
        label_path = os.path.join(self.labels_folder, f"{os.path.splitext(self.image_files[self.image_index])[0]}.txt")
        if os.path.exists(label_path):
            h, w = self.cv_image.shape[:2]
            with open(label_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        cls_idx = int(parts[0])
                        cx, cy, bw, bh = map(float, parts[1:])
                        x1 = int((cx - bw/2) * w)
                        y1 = int((cy - bh/2) * h)
                        x2 = int((cx + bw/2) * w)
                        y2 = int((cy + bh/2) * h)
                        # map index -> class name if available
                        if 0 <= cls_idx < len(self.class_names):
                            cname = self.class_names[cls_idx]
                        else:
                            cname = f"class_{cls_idx}"
                            if cname not in self.class_names:
                                self.class_names.append(cname)
                                self.class_colors.setdefault(cname, (0,255,0))
                        self.bboxes.append((cname, x1, y1, x2, y2))

        # update listbox selection
        self.image_listbox.select_clear(0, tk.END)
        self.image_listbox.select_set(self.image_index)
        self.image_listbox.see(self.image_index)
        # repaint
        self.display_image()

    def save_boxes(self):
     if self.cv_image is None:
        return
     os.makedirs(self.labels_folder, exist_ok=True)
     save_path = os.path.join(
        self.labels_folder,
        f"{os.path.splitext(self.image_files[self.image_index])[0]}.txt")
     h, w = self.cv_image.shape[:2]
     with open(save_path, "w", encoding="utf-8") as f:
        for cls_name, x1, y1, x2, y2 in self.bboxes:
            # clamp bbox
            x1c = max(0, min(x1, w - 1))
            x2c = max(0, min(x2, w - 1))
            y1c = max(0, min(y1, h - 1))
            y2c = max(0, min(y2, h - 1))
            if x2c <= x1c or y2c <= y1c:
                continue
            cx = ((x1c + x2c) / 2) / w
            cy = ((y1c + y2c) / 2) / h
            bw = (x2c - x1c) / w
            bh = (y2c - y1c) / h
            # find class index
            if cls_name in self.class_names:
                cls_idx = self.class_names.index(cls_name)
            else:
                # append unknown class at end
                self.class_names.append(cls_name)
                self.class_colors.setdefault(cls_name, (0, 255, 0))
                self.save_classes()
            f.write(f"{cls_idx} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

     # ✅ Update current listbox row with ✔
     self.image_listbox.delete(self.image_index)
     self.image_listbox.insert(self.image_index, f"✔ {self.image_files[self.image_index]}")
     self.image_listbox.select_clear(0, tk.END)
     self.image_listbox.select_set(self.image_index)

     # ✅ Update labeled count
     self.update_labeled_count()


    def update_labeled_count(self):
     labeled_count = 0
     for fname in self.image_files:
        label_path = os.path.join(self.labels_folder, f"{os.path.splitext(fname)[0]}.txt")
        if os.path.exists(label_path):
            labeled_count += 1
     self.labeled_count_label.config(
         text=f"Labeled: {labeled_count} / {len(self.image_files)}")

    def refresh_image_list(self):
     self.image_listbox.delete(0, tk.END)
     labeled_count = 0

     for idx, fname in enumerate(self.image_files):
        label_path = os.path.join(self.labels_folder, f"{os.path.splitext(fname)[0]}.txt")
        if os.path.exists(label_path):
            display_name = f"✔ {fname}"  # mark labeled
            labeled_count += 1
        else:
            display_name = f"    {fname}"
        self.image_listbox.insert(idx, display_name)

     self.labeled_count_label.config(
        text=f"Labeled: {labeled_count} / {len(self.image_files)}")

    # ---------------- coordinate transforms ----------------
    def canvas_to_image(self, cx, cy):
        """Canvas coords -> image pixel coords (ints)."""
        ix = int((cx - self.offset_x) / self.scale)
        iy = int((cy - self.offset_y) / self.scale)
        return ix, iy

    def image_to_canvas(self, ix, iy):
        """Image pixel -> canvas coords (ints)."""
        cx = int(ix * self.scale + self.offset_x)
        cy = int(iy * self.scale + self.offset_y)
        return cx, cy

    # ---------------- display ----------------
    def display_image(self):
     image = self.original_image.copy()

     # Draw boxes
     for idx, (cls_name, x1, y1, x2, y2) in enumerate(self.bboxes):
        color = self.class_colors.get(cls_name, (0, 255, 0))
        if idx == self.selected_box:
            overlay = image.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            cv2.addWeighted(overlay, 0.3, image, 0.7, 0, image)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 1)
        else:
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 1)

     # Apply zoom
     resized = cv2.resize(image, None, fx=self.scale, fy=self.scale,
                         interpolation=cv2.INTER_LINEAR)
     self.tk_image = ImageTk.PhotoImage(
        Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)))

     self.canvas.delete("all")
     self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.tk_image)

     # Set scroll region to the image's size
     self.canvas.config(scrollregion=(0, 0, resized.shape[1], resized.shape[0]))


    # ---------------- mouse handling ----------------
    def find_box_at(self, ix, iy):
        """Return topmost box index containing point (image coords) or (None, corner) if near corner."""
        # iterate reverse to prefer topmost (last drawn)
        for i in range(len(self.bboxes)-1, -1, -1):
            cls, x1,y1,x2,y2 = self.bboxes[i]
            # check corner proximity
            corner = self.get_near_corner(ix, iy, x1,y1,x2,y2, th=1)
            if corner:
                return i, corner
            if x1 <= ix <= x2 and y1 <= iy <= y2:
                return i, None
        return None, None

    def get_near_corner(self, x, y, x1,y1,x2,y2, th=1):
        """Return corner name if (x,y) near any corner (in image pixels)"""
        corners = {"tl":(x1,y1), "tr":(x2,y1), "bl":(x1,y2), "br":(x2,y2)}
        for name,(cx,cy) in corners.items():
            if abs(x-cx) <= th and abs(y-cy) <= th:
                return name
        return None

    def on_left_press(self, event):
        ix, iy = self.canvas_to_image(event.x, event.y)
        # detect if clicking on a box corner or inside box
        idx, corner = self.find_box_at(ix, iy)
        if idx is not None:
            # select that box
            self.selected_box = idx
            if corner:
                # start resizing
                self.resizing = True
                self.resize_corner = corner
            else:
                # start dragging
                self.dragging = True
            self.prev_mouse_x, self.prev_mouse_y = ix, iy
            self.display_image()
            return

        # otherwise start drawing a new box
        if not self.current_class and not self.class_names:
            messagebox.showwarning("Warning", "No class defined. Add a class first.")
            return
        if not self.current_class:
            # if no explicit selection, pick first class
            self.current_class = self.class_names[0]
            self.class_dropdown.set(self.current_class)

        self.drawing = True
        self.start_x_image, self.start_y_image = ix, iy
        self.end_x_image, self.end_y_image = ix, iy
        # clear selection
        self.selected_box = None
        self.display_image()

    def on_left_drag(self, event):
        ix, iy = self.canvas_to_image(event.x, event.y)
        if self.drawing:
            self.end_x_image, self.end_y_image = ix, iy
            self.display_image()
            return
        if self.dragging and self.selected_box is not None and self.prev_mouse_x is not None:
            dx = ix - self.prev_mouse_x
            dy = iy - self.prev_mouse_y
            cls, x1,y1,x2,y2 = self.bboxes[self.selected_box]
            nx1, ny1, nx2, ny2 = x1+dx, y1+dy, x2+dx, y2+dy
            # clamp
            H,W = self.original_image.shape[:2]
            nx1, ny1 = max(0,int(nx1)), max(0,int(ny1))
            nx2, ny2 = min(W-1,int(nx2)), min(H-1,int(ny2))
            self.bboxes[self.selected_box] = (cls, nx1, ny1, nx2, ny2)
            self.prev_mouse_x, self.prev_mouse_y = ix, iy
            self.display_image()
            return
        if self.resizing and self.selected_box is not None:
            cls, x1,y1,x2,y2 = self.bboxes[self.selected_box]
            sx1, sy1, sx2, sy2 = x1,y1,x2,y2
            if self.resize_corner == "tl":
                nx1, ny1 = ix, iy
                nx2, ny2 = sx2, sy2
            elif self.resize_corner == "tr":
                nx1, ny1 = sx1, iy
                nx2, ny2 = ix, sy2
            elif self.resize_corner == "bl":
                nx1, ny1 = ix, sy1
                nx2, ny2 = sx2, iy
            else:  # br
                nx1, ny1 = sx1, sy1
                nx2, ny2 = ix, iy
            # normalize
            nx1, nx2 = min(nx1,nx2), max(nx1,nx2)
            ny1, ny2 = min(ny1,ny2), max(ny1,ny2)
            H,W = self.original_image.shape[:2]
            nx1, ny1 = max(0,int(nx1)), max(0,int(ny1))
            nx2, ny2 = min(W-1,int(nx2)), min(H-1,int(ny2))
            self.bboxes[self.selected_box] = (cls, nx1, ny1, nx2, ny2)
            self.display_image()
            return

    def on_left_release(self, event):
        ix, iy = self.canvas_to_image(event.x, event.y)
        if self.drawing:
            x1, y1 = self.start_x_image, self.start_y_image
            x2, y2 = ix, iy
            x1, x2 = sorted([int(x1), int(x2)])
            y1, y2 = sorted([int(y1), int(y2)])
            # ignore tiny
            if abs(x2-x1) > 5 and abs(y2-y1) > 5:
                self.bboxes.append((self.current_class, x1, y1, x2, y2))
                self.selected_box = len(self.bboxes) - 1
                self.save_boxes()
            self.drawing = False
            self.start_x_image = self.start_y_image = self.end_x_image = self.end_y_image = None
            self.display_image()
            return

        if self.dragging:
            self.dragging = False
            self.prev_mouse_x = self.prev_mouse_y = None
            self.save_boxes()
            self.display_image()
            return

        if self.resizing:
            self.resizing = False
            self.resize_corner = None
            self.save_boxes()
            self.display_image()
            return

    # ---------------- right click / context menu ----------------
    def on_right_press(self, event):
        ix, iy = self.canvas_to_image(event.x, event.y)
        idx, corner = self.find_box_at(ix, iy)
        if idx is not None:
            self.selected_box = idx
            # show context menu
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Change Class", command=self.change_selected_box_class)
            menu.add_command(label="Delete Box", command=self.delete_selected_box)
            menu.post(event.x_root, event.y_root)
        else:
            # clear selection if clicked outside
            self.selected_box = None
            self.display_image()

    def change_selected_box_class(self):
     if self.selected_box is None:
        return
     if not self.class_names:
        messagebox.showwarning("Warning", "No classes available.")
        return

     # popup window
     top = tk.Toplevel(self.root)
     top.title("Change Class")
     top.geometry("300x100")
     tk.Label(top, text="Select Class:").pack(pady=5)

     cls_var = tk.StringVar(value=self.bboxes[self.selected_box][0])
     cb = ttk.Combobox(top, textvariable=cls_var, state="readonly", values=self.class_names)
     cb.pack(pady=5)

     def apply_change():
        new_cls = cls_var.get()
        if new_cls:
            cls, x1, y1, x2, y2 = self.bboxes[self.selected_box]
            self.bboxes[self.selected_box] = (new_cls, x1, y1, x2, y2)
            self.save_boxes()
            self.display_image()
        top.destroy()

     tk.Button(top, text="OK", command=apply_change).pack(pady=5)


    def delete_selected_box(self):
        if self.selected_box is None:
            return
        del self.bboxes[self.selected_box]
        # normalize selection
        self.selected_box = None
        self.save_boxes()
        self.display_image()

    # ---------------- listbox & navigation ----------------
    def on_image_select(self, event):
        sel = event.widget.curselection()
        if sel:
            idx = sel[0]
            self.set_selected_image_index(idx)

    def set_selected_image_index(self, idx):
        if idx < 0 or idx >= len(self.image_files):
            return
        self.image_index = idx
        # update listbox highlight colors (blue highlight)
        for i in range(self.image_listbox.size()):
            self.image_listbox.itemconfig(i, foreground="black", background="white")
        self.image_listbox.itemconfig(idx, foreground="white", background="blue")
        self.load_image()

    def prev_image(self):
        if self.image_index > 0:
            self.set_selected_image_index(self.image_index - 1)

    def next_image(self):
        if self.image_index < len(self.image_files) - 1:
            self.set_selected_image_index(self.image_index + 1)

    # ---------------- pan & zoom ----------------
    def on_mouse_wheel(self, event):
        # zoom towards mouse pointer
        mx, my = event.x, event.y
        ix, iy = self.canvas_to_image(mx, my)
        if event.delta > 0:
            factor = 1.15
        else:
            factor = 1/1.15
        old_scale = self.scale
        self.scale *= factor
        # maintain focus point under mouse
        self.offset_x = mx - int(ix * self.scale)
        self.offset_y = my - int(iy * self.scale)
        self.display_image()

    def on_middle_press(self, event):
        self.pan_start = (event.x, event.y)

    def on_middle_drag(self, event):
        if getattr(self, "pan_start", None) is None:
            return
        dx = event.x - self.pan_start[0]
        dy = event.y - self.pan_start[1]
        self.offset_x += dx
        self.offset_y += dy
        self.pan_start = (event.x, event.y)
        self.display_image()

    # ---------------- utilities ----------------
    def canvas_to_image(self, cx, cy):
        ix = int(round((cx - self.offset_x) / self.scale))
        iy = int(round((cy - self.offset_y) / self.scale))
        # clamp
        if self.original_image is not None:
            H,W = self.original_image.shape[:2]
            ix = max(0, min(W-1, ix))
            iy = max(0, min(H-1, iy))
        return ix, iy

# ---------------- runnable functions ----------------
def run_bounding_box(project_folder):
    root = tk.Tk()
    app = BoundingBoxLabeler(root, project_folder)
    root.mainloop()

if __name__ == "__main__":
    # direct run: ask for project folder
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select project folder")
    root.destroy()
    if folder:
        run_bounding_box(folder)
