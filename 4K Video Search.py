import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import subprocess
import platform
import threading
import queue
from queue import Empty
import time

# Common 4K resolutions
FOURK_RESOLUTIONS = [
    (3840, 2160), (4096, 2160), (3840, 2560), 
    (2160, 3840), (2880, 2160), (4000, 3000),
    (4096, 3072), (3840, 2400), (3200, 1800)
]

class VideoScanner:
    def __init__(self, root_folder):
        self.root_folder = root_folder
        self.stop_event = threading.Event()
        self.result_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        
    def scan(self):
        """Scan for 4K videos in background thread"""
        try:
            for root, _, files in os.walk(self.root_folder):
                if self.stop_event.is_set():
                    break
                    
                for file in files:
                    if self.stop_event.is_set():
                        break
                        
                    file_path = os.path.join(root, file)
                    if self.is_4k_video(file_path):
                        try:
                            size = os.path.getsize(file_path) / (1024 * 1024)
                            self.result_queue.put((file_path, size))
                        except:
                            continue
                    
                    # Update progress every 10 files
                    if len(files) > 0 and files.index(file) % 10 == 0:
                        self.progress_queue.put((root, files.index(file)/len(files)*100))
            
            self.progress_queue.put(("Done", 100))
        except Exception as e:
            self.progress_queue.put(("Error", str(e)))
            
    def stop(self):
        self.stop_event.set()
        
    def is_4k_video(self, file_path):
        """Optimized version with quick filename check first"""
        if not file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm')):
            return False
            
        # Quick filename check before full probe
        filename = os.path.basename(file_path).lower()
        for res in FOURK_RESOLUTIONS:
            if f"{res[0]}x{res[1]}" in filename or f"{res[1]}x{res[0]}" in filename:
                return True
                
        # Fall back to slower ffprobe check if needed
        try:
            import ffmpeg
            probe = ffmpeg.probe(file_path)
            video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            if video_stream:
                w, h = int(video_stream.get('width', 0)), int(video_stream.get('height', 0))
                return any((w == r[0] and h == r[1]) or (w == r[1] and h == r[0]) for r in FOURK_RESOLUTIONS)
        except:
            pass
            
        return False

class VideoSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("4K Video Search Tool")
        self.root.geometry("900x650")
        self.scanner = None
        self.potplayer_path = self.find_potplayer()
        self.create_widgets()
        
    def find_potplayer(self):
        """Attempt to locate PotPlayer executable"""
        possible_paths = [
            r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe",
            r"C:\Program Files (x86)\DAUM\PotPlayer\PotPlayerMini.exe",
            r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini.exe"
        ]
        for path in possible_paths:
            if os.path.isfile(path):
                return path
        # Fallback: Prompt user if not found
        messagebox.showwarning("PotPlayer Not Found", "PotPlayer executable not found. Please select PotPlayer executable for previews.")
        path = filedialog.askopenfilename(filetypes=[("PotPlayer Executable", "*.exe")])
        if path and os.path.isfile(path):
            return path
        return None
        
    def create_widgets(self):
        # Control panel
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(control_frame, text="Folder:").pack(side='left')
        
        self.folder_entry = tk.Entry(control_frame)
        self.folder_entry.pack(side='left', fill='x', expand=True, padx=5)
        
        self.browse_btn = tk.Button(control_frame, text="Browse", command=self.browse_folder)
        self.browse_btn.pack(side='left', padx=5)
        
        self.search_btn = tk.Button(control_frame, text="Search", command=self.start_search)
        self.search_btn.pack(side='left', padx=5)
        
        self.stop_btn = tk.Button(control_frame, text="Stop", command=self.stop_search, state='disabled')
        self.stop_btn.pack(side='left')
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress.pack(fill='x', padx=10, pady=5)
        
        self.progress_label = tk.Label(self.root, text="Ready")
        self.progress_label.pack()
        
        # Results treeview
        self.tree_frame = tk.Frame(self.root)
        self.tree_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.tree = ttk.Treeview(self.tree_frame, columns=('size', 'path'), show='headings')
        self.tree.heading('size', text='Size (MB)')
        self.tree.heading('path', text='File Path')
        self.tree.column('size', width=100, anchor='e')
        self.tree.column('path', width=700, anchor='w')
        
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Preview", command=self.preview_video)
        self.context_menu.add_command(label="Open Location", command=self.open_location)
        self.tree.bind('<Button-3>', self.show_context_menu)
        self.tree.bind('<Double-1>', lambda e: self.preview_video())
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor='w')
        self.status_bar.pack(fill='x', padx=10, pady=5)
        
        # Start periodic UI updates
        self.update_ui()
        
    def update_ui(self):
        """Periodically check for updates from scanner thread"""
        if self.scanner:
            try:
                # Process progress updates
                while True:
                    progress = self.scanner.progress_queue.get_nowait()
                    if progress[0] == "Done":
                        self.progress_var.set(100)
                        self.progress_label.config(text="Scan complete")
                        self.stop_btn.config(state='disabled')
                        self.search_btn.config(state='normal')
                    elif progress[0] == "Error":
                        messagebox.showerror("Error", progress[1])
                    else:
                        folder, percent = progress
                        self.progress_var.set(percent)
                        self.progress_label.config(text=f"Scanning: {folder[:50]}...")
                        
            except Empty:
                pass
                
            # Process results
            try:
                while True:
                    path, size = self.scanner.result_queue.get_nowait()
                    self.tree.insert('', 'end', values=(f"{size:.2f}", path))
                    self.status_var.set(f"Found {len(self.tree.get_children())} files")
            except Empty:
                pass
                
        # Schedule next update
        self.root.after(200, self.update_ui)
        
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder)
            
    def start_search(self):
        folder = self.folder_entry.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Please select a valid folder")
            return
            
        # Clear previous results
        self.tree.delete(*self.tree.get_children())
        self.status_var.set("Searching...")
        
        # Disable search button during scan
        self.search_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        # Start scanner thread
        self.scanner = VideoScanner(folder)
        self.scan_thread = threading.Thread(target=self.scanner.scan, daemon=True)
        self.scan_thread.start()
        
    def stop_search(self):
        if self.scanner:
            self.scanner.stop()
            self.status_var.set("Scan stopped")
            self.stop_btn.config(state='disabled')
            self.search_btn.config(state='normal')
            
    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
            
    def open_location(self):
        selected = self.tree.selection()
        if selected:
            path = self.tree.item(selected[0])['values'][1]
            open_file_location(path)
            
    def preview_video(self):
        selected = self.tree.selection()
        if not selected:
            return
            
        path = self.tree.item(selected[0])['values'][1]
        if not os.path.isfile(path):
            messagebox.showerror("Error", "File not found.")
            return
            
        if not self.potplayer_path:
            messagebox.showerror("Error", "PotPlayer not configured. Please select PotPlayer executable.")
            self.potplayer_path = filedialog.askopenfilename(filetypes=[("PotPlayer Executable", "*.exe")])
            if not self.potplayer_path:
                return
                
        try:
            subprocess.Popen([self.potplayer_path, path], shell=False)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open PotPlayer: {str(e)}")
            
def open_file_location(path):
    """Cross-platform file location opener"""
    try:
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(['open', '-R', path])
        else:  # Linux
            subprocess.Popen(['xdg-open', os.path.dirname(path)])
    except Exception as e:
        messagebox.showerror("Error", f"Could not open location:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoSearchApp(root)
    root.mainloop()