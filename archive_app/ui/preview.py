import tkinter as tk
from tkinter import ttk
from .scroll import AutoScrollbar

class ArchivePreviewWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc, title: str, text: str) -> None:
        super().__init__(master)
        self.title(f"Содержимое архива — {title}")
        self.geometry("760x520")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        frame = ttk.Frame(self, padding=8)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        text_widget = tk.Text(frame, wrap="none")
        text_widget.insert("1.0", text)
        text_widget.configure(state="disabled")
        text_widget.grid(row=0, column=0, sticky="nsew")
        
        scroll_y = AutoScrollbar(frame, orient="vertical", command=text_widget.yview)  # type: ignore
        scroll_x = AutoScrollbar(frame, orient="horizontal", command=text_widget.xview)  # type: ignore
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        text_widget.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
