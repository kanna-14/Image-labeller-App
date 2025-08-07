import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import cv2
import shutil
import torch
from torchvision.ops import nms
from pathlib import Path
import json


def run_yolo_detection(model_path, image_source, conf_thres=0.3, iou_thres=0.4):
    model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path, force_reload=False)
    model.conf = conf_thres
    model.iou = iou_thres

    color_map = {
        0: (0, 255, 0),    # Normal
        1: (0, 0, 255),    # Defect
        2: (255, 0, 0),    # Blue
        3: (0, 255, 255),  # Yellow
        4: (255, 0, 255),  # Magenta
    }

    output_images = {}  # filename -> processed image

    image_list = []
    if os.path.isdir(image_source):
        image_formats = ('.jpg', '.jpeg', '.png', '.bmp')
        image_list = [str(p) for p in Path(image_source).rglob("*") if p.suffix.lower() in image_formats]
    else:
        image_list = [image_source]

    for image_path in image_list:
        img = cv2.imread(image_path)
        if img is None:
            continue

        results = model(image_path)
        names = results.names
        pred = results.xyxy[0]

        if pred is not None and len(pred):
            boxes = pred[:, :4]
            scores = pred[:, 4]
            keep = nms(boxes, scores, iou_thres)
            filtered_preds = pred[keep]

            for *xyxy, conf, cls_id in filtered_preds:
                x1, y1, x2, y2 = map(int, xyxy)
                class_id = int(cls_id)
                color = color_map.get(class_id, (255, 255, 255))
                label = names[class_id]
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)
                #cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        filename = os.path.basename(image_path)
        output_images[filename] = img

    return output_images  # dictionary of filename: annotated image


def run_yolo_detection_single(model_path, image_path, conf_thres=0.3, iou_thres=0.4):
    model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path, force_reload=False)
    model.conf = conf_thres
    model.iou = iou_thres

    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load image: {image_path}")
        return None

    results = model(image_path)
    names = results.names
    pred = results.xyxy[0]

    color_map = {
        0: (0, 255, 0),
        1: (0, 0, 255),
        2: (255, 0, 0),
        3: (0, 255, 255),
        4: (255, 0, 255),
    }

    if pred is not None and len(pred):
        boxes = pred[:, :4]
        scores = pred[:, 4]
        keep = nms(boxes, scores, iou_thres)
        filtered_preds = pred[keep]

        for *xyxy, conf, cls_id in filtered_preds:
            x1, y1, x2, y2 = map(int, xyxy)
            class_id = int(cls_id)
            color = color_map.get(class_id, (255, 255, 255))
            label = names[class_id]

            cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)
            #cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    return img, filtered_preds, names


class YOLOApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Testify")

        self.model_path = None
        self.image_folder = None
        self.image_list = []
        self.selected_image = None
        self.output_dir = None

        self.zoom_factor = 1.0
        self.imgtk = None
        self.canvas_image = None
        self.canvas_offset = [0, 0]
        self.pan_start = None
        self.current_displayed_file = None

        self.setup_ui()

    def setup_ui(self):
     # Top buttons frame with background color
     top_frame = tk.Frame(self.root, bg="#2e2e2e")  # Dark gray background
     top_frame.pack(fill=tk.X)

     button_style = {
        "padx": 5,
        "pady": 3,
        "fg": "Black",        # Text color
        "font": ("Arial", 10, "bold")
     }
    
     # Frame for results displa

 
     tk.Button(top_frame, text="Load Model", bg="#8CA58C", command=self.load_model, **button_style).pack(side=tk.LEFT, padx=5)
     tk.Button(top_frame, text="Load Folder", bg="#8CA58C", command=self.load_folder, **button_style).pack(side=tk.LEFT, padx=5)
     tk.Button(top_frame, text="Test", bg="#8CA58C", command=self.test_single_image, **button_style).pack(side=tk.LEFT, padx=5)
     tk.Button(top_frame, text="Test All", bg="#8CA58C", command=self.test_all_images, **button_style).pack(side=tk.LEFT, padx=5)
     tk.Button(top_frame, text="Save Images", bg="#8CA58C", command=self.save_classified_results, **button_style).pack(side=tk.LEFT, padx=5)
     tk.Button(top_frame, text="Refresh", bg="#8CA58C", command=self.refresh_display, **button_style).pack(side=tk.LEFT, padx=5)
     tk.Button(top_frame, text="Refresh All", bg="#8CA58C", command=self.refresh_all_images, **button_style).pack(side=tk.LEFT, padx=5)
     tk.Button(top_frame, text="Close", bg="#582A2A", command=self.root.quit, **button_style).pack(side=tk.RIGHT, padx=5)

     # Main layout
     main_frame = tk.Frame(self.root)
     main_frame.pack(fill=tk.BOTH, expand=True)

     #  result_frame = tk.Frame(main_frame, bg="#f0f0f0", relief=tk.SUNKEN, borderwidth=2)
     #  result_frame.pack(side=tk.RIGHT, fill=tk.X)

     #  self.result_label = tk.Label(result_frame, text="", justify=tk.LEFT, anchor="nw", bg="#f0f0f0")
     #  self.result_label.pack(side=tk.TOP, expand=True, padx=5, pady=5)

     self.listbox = tk.Listbox(main_frame, width=30)
     self.listbox.pack(side=tk.LEFT, fill=tk.Y)
     self.listbox.bind("<<ListboxSelect>>", self.select_image)

     self.canvas = tk.Canvas(main_frame, bg="black")
     self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

     self.canvas.bind("<MouseWheel>", self.zoom)
     self.canvas.bind("<ButtonPress-1>", self.start_pan)
     self.canvas.bind("<B1-Motion>", self.do_pan)


    def load_model(self):
        path = filedialog.askopenfilename(title="Select YOLOv5 Model", filetypes=[("PyTorch model", "*.pt")])
        if path:
            self.model_path = path
            messagebox.showinfo("Loaded", f"Model loaded:\n{path}")

    def load_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Images")
        if folder:
            self.image_folder = folder
            self.output_dir = os.path.join(folder, "output")
            os.makedirs(self.output_dir, exist_ok=True)
            self.image_list = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.png', '.bmp'))]
            self.listbox.delete(0, tk.END)
            for img in self.image_list:
                self.listbox.insert(tk.END, img)
 
    def select_image(self, event):
        if self.listbox.curselection():
            index = self.listbox.curselection()[0]
            filename = self.image_list[index]
            self.selected_image = os.path.join(self.image_folder, filename)
            annotated_path = os.path.join(self.output_dir, filename)
            self.current_displayed_file = filename
            if os.path.exists(annotated_path):
                self.show_image(annotated_path)
            else:
                self.show_image(self.selected_image)

    def show_image(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            return

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.original_image = Image.fromarray(img)
        self.zoom_factor = 1.0
        self.canvas_offset = [0, 0]
        self.render_image()

    def render_image(self):
        if not hasattr(self, "original_image"):
            return

        w, h = self.original_image.size
        zoomed = self.original_image.resize((int(w * self.zoom_factor), int(h * self.zoom_factor)))
        self.imgtk = ImageTk.PhotoImage(zoomed)

        self.canvas.delete("all")
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        cx = (canvas_w - zoomed.width) // 2 + self.canvas_offset[0]
        cy = (canvas_h - zoomed.height) // 2 + self.canvas_offset[1]

        self.canvas_image = self.canvas.create_image(cx, cy, anchor=tk.NW, image=self.imgtk)

    def zoom(self, event):
        delta = 0.1 if event.delta > 0 else -0.1
        new_zoom = self.zoom_factor + delta
        if 0.1 < new_zoom < 5.0:
            self.zoom_factor = new_zoom
            self.render_image()

    def start_pan(self, event):
        self.pan_start = (event.x, event.y)

    def do_pan(self, event):
        if self.pan_start:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            self.canvas_offset[0] += dx
            self.canvas_offset[1] += dy
            self.pan_start = (event.x, event.y)
            self.render_image()

    def test_single_image(self):
        if not self.model_path:
            messagebox.showerror("Error", "Model not loaded.")
            return
        if not self.listbox.curselection():
            messagebox.showerror("Error", "No image selected.")
            return

        index = self.listbox.curselection()[0]
        filename = self.image_list[index]
        input_path = os.path.join(self.image_folder, filename)
        result = run_yolo_detection_single(self.model_path, input_path)
        if result is not None:
            save_path = os.path.join(self.output_dir, filename)
            cv2.imwrite(save_path, result)
            self.show_image(save_path)

    def test_all_images(self):
        if not self.model_path or not self.image_folder:
            messagebox.showerror("Error", "Model and folder required.")
            return

        result_dict = run_yolo_detection(self.model_path, self.image_folder)
        for filename, img in result_dict.items():
            save_path = os.path.join(self.output_dir, filename)
            cv2.imwrite(save_path, img)

        messagebox.showinfo("Done", f"Processed all images.\nSaved to: {self.output_dir}")

        # Automatically show current selection again
        if self.current_displayed_file:
            annotated_path = os.path.join(self.output_dir, self.current_displayed_file)
            if os.path.exists(annotated_path):
                self.show_image(annotated_path)

    def refresh_display(self):
        if self.current_displayed_file:
            original_path = os.path.join(self.image_folder, self.current_displayed_file)
            if os.path.exists(original_path):
                self.show_image(original_path)
 
    def refresh_all_images(self):
     if not self.output_dir or not os.path.exists(self.output_dir):
        messagebox.showinfo("Nothing to Refresh", "No output directory found.")
        return

     for filename in self.image_list:
        output_img_path = os.path.join(self.output_dir, filename)
        if os.path.exists(output_img_path):
            try:
                os.remove(output_img_path)
            except Exception as e:
                print(f"Failed to remove {output_img_path}: {e}")

     messagebox.showinfo("Refresh All", "All annotated images cleared.")
    
     # Reload selected image from original path
     if self.listbox.curselection():
        index = self.listbox.curselection()[0]
        self.selected_image = os.path.join(self.image_folder, self.image_list[index])
        self.show_image(self.selected_image)

    def save_classified_results(self):
        if not self.output_dir or not os.path.exists(self.output_dir):
            messagebox.showerror("Error", "Run detection first.")
            return

        save_dir = os.path.join(self.output_dir, "classified_results")
        os.makedirs(save_dir, exist_ok=True)

        for img in os.listdir(self.output_dir):
            if img.lower().endswith(('.jpg', '.png', '.bmp')):
                src = os.path.join(self.output_dir, img)
                dst = os.path.join(save_dir, img)
                shutil.copy(src, dst)

        messagebox.showinfo("Saved", f"Images saved to:\n{save_dir}")

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1000x700")
    app = YOLOApp(root)
    root.mainloop()
