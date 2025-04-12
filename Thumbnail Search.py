import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from typing import List, Tuple

class ThumbnailCleanerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Thumbnail Cleaner")
        self.root.geometry("1000x700")
        
        # Variables
        self.folder_path = tk.StringVar()
        self.thumbnail_files = []
        self.selected_files = []
        self.current_preview_image = None  # To keep reference
        
        # Create UI
        self.create_widgets()
        
    def create_widgets(self):
        # Configure grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        
        # Folder selection frame
        folder_frame = ttk.LabelFrame(self.root, text="Folder Selection", padding=10)
        folder_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        ttk.Label(folder_frame, text="Folder:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(folder_frame, textvariable=self.folder_path, width=50).grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(folder_frame, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=5)
        ttk.Button(folder_frame, text="Search Thumbnails", command=self.search_thumbnails).grid(row=1, column=0, columnspan=3, pady=5)
        
        # Main content frame
        content_frame = ttk.Frame(self.root)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        content_frame.grid_columnconfigure(0, weight=3)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # Results frame (left side)
        results_frame = ttk.LabelFrame(content_frame, text="Found Thumbnails", padding=10)
        results_frame.grid(row=0, column=0, sticky="nsew", padx=5)
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        
        # Treeview for results
        self.tree = ttk.Treeview(results_frame, columns=("file", "reason"), show="headings")
        self.tree.heading("file", text="File Path")
        self.tree.heading("reason", text="Reason")
        self.tree.column("file", width=400)
        self.tree.column("reason", width=200)
        
        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(results_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)
        
        # Preview frame (right side)
        self.preview_frame = ttk.LabelFrame(content_frame, text="Image Preview", padding=10)
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        self.preview_frame.grid_rowconfigure(1, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        
        self.preview_label = ttk.Label(self.preview_frame, text="No image selected")
        self.preview_label.grid(row=1, column=0, sticky="nsew")
        
        # Action buttons
        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        
        ttk.Button(button_frame, text="Select All", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Deselect All", command=self.deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_selected).pack(side=tk.RIGHT, padx=5)
        
        # Bind events
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
    
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)
            self.clear_results()
    
    def clear_results(self):
        self.tree.delete(*self.tree.get_children())
        self.thumbnail_files = []
        self.selected_files = []
        self.update_preview(None)
    
    def search_thumbnails(self):
        folder = self.folder_path.get()
        if not folder:
            messagebox.showwarning("Warning", "Please select a folder first")
            return
        
        if not os.path.isdir(folder):
            messagebox.showerror("Error", "The specified path is not a valid directory")
            return
        
        self.clear_results()
        
        thumbnail_patterns = [
            # Common thumbnail naming patterns
            (r'^Thumbs\.db$', 'Windows thumbnail database'),
            (r'^\.thumbnails', 'Linux thumbnail cache'),
            (r'^thumbnail_', 'Filename starts with "thumbnail_"'),
            (r'_thumb(?:nail)?\.', 'Contains "_thumb" or "_thumbnail" before extension'),
            (r'\.thumb(?:nail)?\.', 'Contains ".thumb" or ".thumbnail" before extension'),
            (r'~[0-9]+x[0-9]+\.', 'Contains dimensions like ~100x100 in filename'),
            (r'\.small\.', 'Contains ".small." in filename'),
            (r'\.mini\.', 'Contains ".mini." in filename'),
            (r'^mini_', 'Filename starts with "mini_"'),
            (r'^small_', 'Filename starts with "small_"'),
        ]
        
        found_files = []
        
        for root, _, files in os.walk(folder):
            for filename in files:
                lower_filename = filename.lower()
                for pattern, reason in thumbnail_patterns:
                    if re.search(pattern, lower_filename, re.IGNORECASE):
                        full_path = os.path.join(root, filename)
                        found_files.append((full_path, reason))
                        break  # No need to check other patterns for this file
        
        self.thumbnail_files = found_files
        
        if not found_files:
            messagebox.showinfo("Info", "No thumbnail files found.")
            return
        
        for file_path, reason in found_files:
            self.tree.insert("", tk.END, values=(file_path, reason), tags=("unselected",))
        
        self.tree.tag_configure("selected", background="lightgreen")
        self.tree.tag_configure("unselected", background="")
    
    def on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        
        col = self.tree.identify_column(event.x)
        if col == "#1":  # Only toggle selection when clicking on the file column
            current_tags = self.tree.item(item, "tags")
            if "selected" in current_tags:
                self.tree.item(item, tags=("unselected",))
                if item in self.selected_files:
                    self.selected_files.remove(item)
            else:
                self.tree.item(item, tags=("selected",))
                if item not in self.selected_files:
                    self.selected_files.append(item)
    
    def on_tree_select(self, event):
        selected_item = self.tree.focus()
        if selected_item:
            file_path = self.tree.item(selected_item, "values")[0]
            self.update_preview(file_path)
    
    def update_preview(self, file_path):
        if not file_path:
            self.preview_label.config(text="No image selected")
            if hasattr(self, 'preview_image_label'):
                self.preview_image_label.grid_forget()
            return
        
        try:
            # Check if file is an image
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                # Open and resize the image
                img = Image.open(file_path)
                img.thumbnail((300, 300))  # Resize to fit in preview
                
                # Convert to PhotoImage
                self.current_preview_image = ImageTk.PhotoImage(img)
                
                # Create or update image label
                if not hasattr(self, 'preview_image_label'):
                    self.preview_image_label = ttk.Label(self.preview_frame)
                    self.preview_image_label.grid(row=1, column=0, sticky="nsew")
                
                self.preview_image_label.config(image=self.current_preview_image)
                self.preview_label.config(text=os.path.basename(file_path))
            else:
                self.preview_label.config(text="Not an image file")
                if hasattr(self, 'preview_image_label'):
                    self.preview_image_label.grid_forget()
        except Exception as e:
            self.preview_label.config(text=f"Error loading image: {str(e)}")
            if hasattr(self, 'preview_image_label'):
                self.preview_image_label.grid_forget()
    
    def select_all(self):
        self.selected_files = []
        for child in self.tree.get_children():
            self.tree.item(child, tags=("selected",))
            self.selected_files.append(child)
    
    def deselect_all(self):
        self.selected_files = []
        for child in self.tree.get_children():
            self.tree.item(child, tags=("unselected",))
    
    def get_selected_items(self):
        return [item for item in self.tree.get_children() if "selected" in self.tree.item(item, "tags")]
    
    def delete_selected(self):
        selected_items = self.get_selected_items()
        if not selected_items:
            messagebox.showwarning("Warning", "No files selected for deletion")
            return
        
        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete {len(selected_items)} files?\nThis action cannot be undone.",
            icon=messagebox.WARNING
        )
        
        if not confirm:
            return
        
        deleted_count = 0
        errors = []
        
        for item in selected_items:
            file_path = self.tree.item(item, "values")[0]
            try:
                os.remove(file_path)
                deleted_count += 1
                self.tree.delete(item)
            except OSError as e:
                errors.append(f"{file_path}: {str(e)}")
        
        message = f"Successfully deleted {deleted_count} files."
        if errors:
            message += f"\n\nFailed to delete {len(errors)} files:\n" + "\n".join(errors)
        
        messagebox.showinfo("Deletion Complete", message)
        
        # Update the selected files list
        self.selected_files = [item for item in self.selected_files if item in self.tree.get_children()]

if __name__ == "__main__":
    root = tk.Tk()
    app = ThumbnailCleanerApp(root)
    root.mainloop()