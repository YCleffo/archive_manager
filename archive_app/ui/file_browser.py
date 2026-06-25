import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional
from pathlib import Path
from .scroll import AutoScrollbar
from ..file_utils import format_modified, format_size

class FileBrowserFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, callbacks: dict[str, Callable]) -> None:
        super().__init__(master)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            self,
            columns=("name", "kind", "size", "modified", "path"),
            displaycolumns=("name", "kind", "size", "modified"),
            show="headings",
            selectmode="extended",
        )
        self.tree.heading("name", text="Имя", anchor="w", command=lambda: self.sort_tree("name", False))
        self.tree.heading("kind", text="Тип", anchor="w", command=lambda: self.sort_tree("kind", False))
        self.tree.heading("size", text="Размер", anchor="w", command=lambda: self.sort_tree("size", False))
        self.tree.heading("modified", text="Изменён", anchor="w", command=lambda: self.sort_tree("modified", False))
        
        self.tree.column("name", width=480, anchor="w")
        self.tree.column("kind", width=120, anchor="w")
        self.tree.column("size", width=120, anchor="e")
        self.tree.column("modified", width=160, anchor="w")

        file_scroll = AutoScrollbar(self, orient="vertical", command=self.tree.yview)
        file_scroll_x = AutoScrollbar(self, orient="horizontal", command=self.tree.xview)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        file_scroll.grid(row=0, column=1, sticky="ns")
        file_scroll_x.grid(row=1, column=0, sticky="ew")
        
        self.tree.configure(yscrollcommand=file_scroll.set, xscrollcommand=file_scroll_x.set)

        self.context_menu = tk.Menu(self, tearoff=False)
        self.context_menu.add_command(label="Открыть", command=callbacks.get("open_selected"))
        self.context_menu.add_command(label="Показать содержимое архива", command=callbacks.get("show_archive_contents"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Создать ZIP", command=callbacks.get("create_zip_from_selection"))
        self.context_menu.add_command(label="Распаковать", command=callbacks.get("extract_selected_archive"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Копировать", command=callbacks.get("copy_selected"))
        self.context_menu.add_command(label="Переместить", command=callbacks.get("move_selected"))
        self.context_menu.add_command(label="Переименовать", command=callbacks.get("rename_selected"))
        self.context_menu.add_command(label="Удалить", command=callbacks.get("delete_selected"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Размер папки", command=callbacks.get("calculate_selected_size"))

        self.tree.bind("<Double-1>", lambda _e: callbacks.get("open_selected")() if callbacks.get("open_selected") else None)
        self.tree.bind("<Return>", lambda _e: callbacks.get("open_selected")() if callbacks.get("open_selected") else None)
        self.tree.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        if item and item not in self.tree.selection():
            self.tree.selection_set(item)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def sort_tree(self, column: str, reverse: bool) -> None:
        rows = [(self.tree.set(item, column), item) for item in self.tree.get_children("")]
        rows.sort(reverse=reverse, key=lambda pair: pair[0].casefold())
        for index, (_value, item) in enumerate(rows):
            self.tree.move(item, "", index)
        self.tree.heading(column, command=lambda: self.sort_tree(column, not reverse))

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def insert_entry(self, entry) -> None:
        icon_name = "[Папка] " + entry.name if entry.is_dir else "[Файл] " + entry.name
        self.tree.insert(
            "",
            "end",
            iid=str(entry.path),
            values=(
                icon_name,
                entry.kind,
                format_size(entry.size),
                format_modified(entry.modified),
                str(entry.path),
            ),
        )

    def get_selected_paths(self) -> list[Path]:
        return [Path(item) for item in self.tree.selection()]

    def get_selected_path(self) -> Optional[Path]:
        selected = self.get_selected_paths()
        return selected[0] if selected else None
