import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict
from .scroll import AutoScrollbar

class ToolbarFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, callbacks: Dict[str, Callable[[], None]], initial_path: str = "") -> None:
        super().__init__(master)
        self.columnconfigure(0, weight=1)
        
        # --- Toolbar with buttons ---
        toolbar_container = ttk.Frame(self)
        toolbar_container.grid(row=0, column=0, sticky="ew")
        toolbar_container.columnconfigure(0, weight=1)

        bg_color = "#f8f9fa"
        try:
            bg_color = master.cget("bg") # type: ignore
        except Exception:
            pass

        self.toolbar_canvas = tk.Canvas(toolbar_container, height=44, highlightthickness=0, bg=bg_color)
        self.toolbar_canvas.grid(row=0, column=0, sticky="ew")

        toolbar_scroll = AutoScrollbar(toolbar_container, orient="horizontal", command=self.toolbar_canvas.xview)  # type: ignore
        toolbar_scroll.grid(row=1, column=0, sticky="ew")
        self.toolbar_canvas.configure(xscrollcommand=toolbar_scroll.set)

        toolbar = ttk.Frame(self.toolbar_canvas, padding=(8, 8, 8, 4))
        self.toolbar_canvas.create_window((0, 0), window=toolbar, anchor="nw")

        def on_toolbar_configure(event: tk.Event) -> None:
            self.toolbar_canvas.configure(scrollregion=self.toolbar_canvas.bbox("all"))
        toolbar.bind("<Configure>", on_toolbar_configure)

        buttons_def = [
            ("Назад", "go_back"),
            ("Вверх", "go_up"),
            ("Домой", "go_home"),
            ("Обновить", "refresh"),
            ("Новая папка", "new_folder"),
            ("Переименовать", "rename_selected"),
            ("Удалить", "delete_selected"),
            ("Копировать", "copy_selected"),
            ("Переместить", "move_selected"),
            ("Создать ZIP", "create_zip_from_selection"),
            ("Распаковать", "extract_selected_archive"),
            ("Размер папки", "calculate_selected_size"),
        ]
        
        for index, (text, cmd_name) in enumerate(buttons_def):
            cmd = callbacks.get(cmd_name)
            if cmd:
                ttk.Button(toolbar, text=text, command=cmd, style="Toolbar.TButton", cursor="hand2").grid(row=0, column=index, padx=2)

        # --- Path entry ---
        path_frame = ttk.Frame(self, padding=(8, 0, 8, 6))
        path_frame.grid(row=1, column=0, sticky="ew")
        path_frame.columnconfigure(1, weight=1)
        
        ttk.Label(path_frame, text="Путь:").grid(row=0, column=0, padx=(0, 6))
        self.path_var = tk.StringVar(value=initial_path)
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=1, sticky="ew")
        
        nav_cmd = callbacks.get("navigate_from_entry")
        if nav_cmd:
            ttk.Button(path_frame, text="Перейти", command=nav_cmd, cursor="hand2").grid(row=0, column=2, padx=(6, 0))
            self.path_entry.bind("<Return>", lambda _event: nav_cmd()) # type: ignore

    def set_path(self, path: str) -> None:
        self.path_var.set(path)
        
    def get_path(self) -> str:
        return self.path_var.get()
