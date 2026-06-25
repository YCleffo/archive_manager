import tkinter as tk
from tkinter import ttk
from typing import Callable
from pathlib import Path
from .scroll import AutoScrollbar
from ..file_utils import format_size, format_modified
from ..search_utils import SearchResult

class SearchPanelFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, callbacks: dict[str, Callable]) -> None:
        super().__init__(master)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        search_bar = ttk.Frame(self, padding=(0, 8, 0, 4))
        search_bar.grid(row=0, column=0, sticky="ew")
        search_bar.columnconfigure(1, weight=1)

        ttk.Label(search_bar, text="Поиск:").grid(row=0, column=0, padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_bar, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew")

        ttk.Label(search_bar, text="Расширения:").grid(row=0, column=2, padx=(8, 6))
        self.ext_var = tk.StringVar()
        self.ext_entry = ttk.Entry(search_bar, textvariable=self.ext_var, width=18)
        self.ext_entry.grid(row=0, column=3)

        self.content_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(search_bar, text="Искать внутри файлов", variable=self.content_var).grid(row=0, column=4, padx=(8, 2))
        ttk.Button(search_bar, text="Найти", command=callbacks.get("start_search")).grid(row=0, column=5, padx=2)
        ttk.Button(search_bar, text="Стоп", command=callbacks.get("stop_search")).grid(row=0, column=6, padx=2)

        self.search_entry.bind("<Return>", lambda _e: callbacks.get("start_search")() if callbacks.get("start_search") else None)

        self.tree = ttk.Treeview(
            self,
            columns=("path", "match", "kind", "size", "modified"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("path", text="Результат", anchor="w")
        self.tree.heading("match", text="Совпадение", anchor="w")
        self.tree.heading("kind", text="Тип", anchor="w")
        self.tree.heading("size", text="Размер", anchor="w")
        self.tree.heading("modified", text="Изменён", anchor="w")
        
        self.tree.column("path", width=620, anchor="w")
        self.tree.column("match", width=100, anchor="w")
        self.tree.column("kind", width=100, anchor="w")
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("modified", width=150, anchor="w")

        search_scroll = AutoScrollbar(self, orient="vertical", command=self.tree.yview)
        search_scroll_x = AutoScrollbar(self, orient="horizontal", command=self.tree.xview)
        
        self.tree.grid(row=1, column=0, sticky="nsew")
        search_scroll.grid(row=1, column=1, sticky="ns")
        search_scroll_x.grid(row=2, column=0, sticky="ew")
        
        self.tree.configure(yscrollcommand=search_scroll.set, xscrollcommand=search_scroll_x.set)
        
        self.tree.bind("<Double-1>", lambda _e: callbacks.get("open_search_result")() if callbacks.get("open_search_result") else None)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def insert_result(self, item: SearchResult) -> None:
        self.tree.insert(
            "",
            "end",
            iid=str(item.path),
            values=(
                str(item.path),
                item.match_type,
                item.kind,
                format_size(item.size),
                format_modified(item.modified),
            ),
        )

    def get_query(self) -> str:
        return self.search_var.get().strip()

    def get_extensions(self) -> str:
        return self.ext_var.get()

    def get_include_content(self) -> bool:
        return self.content_var.get()

    def get_selected_path(self) -> Path | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return Path(selection[0])
