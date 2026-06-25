from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .archive_utils import create_zip_archive, extract_archive, is_supported_archive, list_archive_members
from .file_utils import (
    copy_items,
    create_folder,
    delete_items,
    list_directory,
    move_items,
    open_in_system,
    rename_item,
    format_size,
    calculate_folder_size,
)
from .search_utils import SearchResult, search_files

from .ui.scroll import _on_shift_scroll_global
from .ui.preview import ArchivePreviewWindow
from .ui.toolbar import ToolbarFrame
from .ui.file_browser import FileBrowserFrame
from .ui.search_panel import SearchPanelFrame


class ArchiveManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Python Archive Manager")
        self.geometry("1120x720")
        self.minsize(900, 560)

        self.current_path = Path.home().resolve()
        self.history: list[Path] = []
        self.search_cancel_event: threading.Event | None = None
        self.search_queue: queue.Queue[SearchResult | str] = queue.Queue()

        self._build_style()
        self._build_widgets()
        self._bind_events()

        self.bind_all("<Shift-MouseWheel>", _on_shift_scroll_global)
        self.bind_all("<Shift-Button-4>", _on_shift_scroll_global)
        self.bind_all("<Shift-Button-5>", _on_shift_scroll_global)

        self.load_directory(self.current_path, add_history=False)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        
        bg_color = "#f8f9fa"
        fg_color = "#212529"
        accent_color = "#0d6efd"
        
        self.configure(bg=bg_color)
        
        style.configure(".", font=("Segoe UI", 10), background=bg_color, foreground=fg_color)
        
        style.configure("Treeview", rowheight=30, borderwidth=0, font=("Segoe UI", 10))
        style.map("Treeview", background=[("selected", accent_color)], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=5, background="#e9ecef", relief="flat")
        style.map("Treeview.Heading", background=[("active", "#dee2e6")])
        
        style.configure("TButton", padding=(4, 2), font=("Segoe UI", 10))
        style.configure("Toolbar.TButton", padding=(4, 2), font=("Segoe UI", 10))
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, font=("Segoe UI", 10))
        style.configure("TPanedwindow", background=bg_color)

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        callbacks = {
            "go_back": self.go_back,
            "go_up": self.go_up,
            "go_home": self.go_home,
            "refresh": self.refresh,
            "new_folder": self.new_folder,
            "rename_selected": self.rename_selected,
            "delete_selected": self.delete_selected,
            "copy_selected": self.copy_selected,
            "move_selected": self.move_selected,
            "create_zip_from_selection": self.create_zip_from_selection,
            "extract_selected_archive": self.extract_selected_archive,
            "calculate_selected_size": self.calculate_selected_size,
            "navigate_from_entry": self.navigate_from_entry,
            "open_selected": self.open_selected,
            "show_archive_contents": self.show_archive_contents,
            "start_search": self.start_search,
            "stop_search": self.stop_search,
            "open_search_result": self.open_search_result,
        }

        self.toolbar = ToolbarFrame(self, callbacks=callbacks, initial_path=str(self.current_path))
        self.toolbar.grid(row=0, column=0, sticky="ew")

        # row 1 is occupied by paned window
        self.rowconfigure(1, weight=1)
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))

        self.file_browser = FileBrowserFrame(main_pane, callbacks=callbacks)
        main_pane.add(self.file_browser, weight=3) # type: ignore

        self.search_panel = SearchPanelFrame(main_pane, callbacks=callbacks)
        main_pane.add(self.search_panel, weight=2) # type: ignore

        status_frame = ttk.Frame(self, padding=(8, 0, 8, 8))
        status_frame.grid(row=2, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(status_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

    def _bind_events(self) -> None:
        self.bind("<F5>", lambda _event: self.refresh())
        self.bind("<Alt-Up>", lambda _event: self.go_up())
        self.bind("<Delete>", lambda _event: self.delete_selected())

    def set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.update_idletasks()

    def load_directory(self, path: Path, add_history: bool = True) -> None:
        try:
            path = Path(path).expanduser().resolve()
            if not path.exists() or not path.is_dir():
                raise NotADirectoryError(str(path))
            if add_history and path != self.current_path:
                self.history.append(self.current_path)
            self.current_path = path
            self.toolbar.set_path(str(path))
            self.file_browser.clear()
            entries = list_directory(path)
            for entry in entries:
                self.file_browser.insert_entry(entry)
            self.set_status(f"Открыто: {path} | объектов: {len(entries)}")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{exc}")
            self.set_status("Ошибка открытия папки")

    def refresh(self) -> None:
        self.load_directory(self.current_path, add_history=False)

    def navigate_from_entry(self) -> None:
        self.load_directory(Path(self.toolbar.get_path()))

    def go_up(self) -> None:
        parent = self.current_path.parent
        if parent != self.current_path:
            self.load_directory(parent)

    def go_home(self) -> None:
        self.load_directory(Path.home())

    def go_back(self) -> None:
        if not self.history:
            self.set_status("История пуста")
            return
        previous = self.history.pop()
        self.load_directory(previous, add_history=False)

    def open_selected(self) -> None:
        path = self.file_browser.get_selected_path()
        if path is None:
            return
        try:
            if path.is_dir():
                self.load_directory(path)
            else:
                open_in_system(path)
                self.set_status(f"Открыто: {path.name}")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть:\n{exc}")

    def new_folder(self) -> None:
        name = simpledialog.askstring("Новая папка", "Введите имя папки:", parent=self)
        if not name:
            return
        try:
            created = create_folder(self.current_path, name)
            self.refresh()
            self.set_status(f"Создана папка: {created.name}")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def rename_selected(self) -> None:
        path = self.file_browser.get_selected_path()
        if path is None:
            messagebox.showinfo("Переименование", "Выберите один файл или папку")
            return
        new_name = simpledialog.askstring("Переименовать", "Новое имя:", initialvalue=path.name, parent=self)
        if not new_name or new_name == path.name:
            return
        try:
            renamed = rename_item(path, new_name)
            self.refresh()
            self.set_status(f"Переименовано: {renamed.name}")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def delete_selected(self) -> None:
        paths = self.file_browser.get_selected_paths()
        if not paths:
            messagebox.showinfo("Удаление", "Выберите файлы или папки")
            return
        names = "\n".join(path.name for path in paths[:10])
        if len(paths) > 10:
            names += f"\n...и ещё {len(paths) - 10}"
        answer = messagebox.askyesno("Удалить", f"Удалить выбранные объекты без корзины?\n\n{names}")
        if not answer:
            return
        try:
            delete_items(paths)
            self.refresh()
            self.set_status(f"Удалено объектов: {len(paths)}")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось удалить:\n{exc}")

    def copy_selected(self) -> None:
        paths = self.file_browser.get_selected_paths()
        if not paths:
            messagebox.showinfo("Копирование", "Выберите файлы или папки")
            return
        destination = filedialog.askdirectory(title="Куда копировать?", initialdir=str(self.current_path))
        if not destination:
            return
        try:
            copied = copy_items(paths, Path(destination))
            self.refresh()
            self.set_status(f"Скопировано объектов: {len(copied)}")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось скопировать:\n{exc}")

    def move_selected(self) -> None:
        paths = self.file_browser.get_selected_paths()
        if not paths:
            messagebox.showinfo("Перемещение", "Выберите файлы или папки")
            return
        destination = filedialog.askdirectory(title="Куда переместить?", initialdir=str(self.current_path))
        if not destination:
            return
        try:
            moved = move_items(paths, Path(destination))
            self.refresh()
            self.set_status(f"Перемещено объектов: {len(moved)}")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось переместить:\n{exc}")

    def create_zip_from_selection(self) -> None:
        paths = self.file_browser.get_selected_paths()
        if not paths:
            messagebox.showinfo("Создать ZIP", "Выберите файлы или папки для архивации")
            return
        default_name = "archive.zip" if len(paths) != 1 else f"{paths[0].stem}.zip"
        output = filedialog.asksaveasfilename(
            title="Сохранить ZIP",
            initialdir=str(self.current_path),
            initialfile=default_name,
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
        )
        if not output:
            return

        def worker() -> None:
            try:
                self.after(0, self.set_status, "Создание архива...")
                create_zip_archive(Path(output), paths, progress=lambda name: self.after(0, self.set_status, f"Архивирую: {Path(name).name}"))
                self.after(0, self.refresh)
                self.after(0, messagebox.showinfo, "Готово", f"Архив создан:\n{output}")
                self.after(0, self.set_status, f"Архив создан: {Path(output).name}")
            except Exception as exc:
                self.after(0, messagebox.showerror, "Ошибка", f"Не удалось создать архив:\n{exc}")
                self.after(0, self.set_status, "Ошибка создания архива")

        threading.Thread(target=worker, daemon=True).start()

    def extract_selected_archive(self) -> None:
        path = self.file_browser.get_selected_path()
        if path is None or not path.is_file() or not is_supported_archive(path):
            selected = filedialog.askopenfilename(
                title="Выберите архив",
                initialdir=str(self.current_path),
                filetypes=[
                    ("Archives", "*.zip *.tar *.tar.gz *.tgz *.tar.bz2"),
                    ("All files", "*.*"),
                ],
            )
            if not selected:
                return
            path = Path(selected)

        destination = filedialog.askdirectory(title="Куда распаковать?", initialdir=str(path.parent))
        if not destination:
            return

        def worker() -> None:
            try:
                self.after(0, self.set_status, "Распаковка архива...")
                extract_archive(path, Path(destination), progress=lambda name: self.after(0, self.set_status, f"Распаковываю: {name}"))
                self.after(0, self.load_directory, Path(destination), True)
                self.after(0, messagebox.showinfo, "Готово", f"Архив распакован в:\n{destination}")
                self.after(0, self.set_status, f"Распаковано: {path.name}")
            except Exception as exc:
                self.after(0, messagebox.showerror, "Ошибка", f"Не удалось распаковать архив:\n{exc}")
                self.after(0, self.set_status, "Ошибка распаковки")

        threading.Thread(target=worker, daemon=True).start()

    def calculate_selected_size(self) -> None:
        path = self.file_browser.get_selected_path()
        if not path or not path.is_dir():
            messagebox.showinfo("Размер", "Выберите папку для подсчёта размера")
            return
            
        def worker() -> None:
            self.after(0, self.set_status, f"Вычисление размера: {path.name}...")
            total_size, total_files = calculate_folder_size(path)
            self.after(0, messagebox.showinfo, "Размер папки", f"Папка: {path.name}\nРазмер: {format_size(total_size)}\nФайлов: {total_files}")
            self.after(0, self.set_status, f"Размер {path.name}: {format_size(total_size)}")
            
        threading.Thread(target=worker, daemon=True).start()

    def show_archive_contents(self) -> None:
        path = self.file_browser.get_selected_path()
        if path is None or not path.is_file() or not is_supported_archive(path):
            messagebox.showinfo("Архив", "Выберите ZIP/TAR-архив")
            return
        try:
            members = list_archive_members(path)
            preview = "\n".join(members[:200])
            if len(members) > 200:
                preview += f"\n...и ещё {len(members) - 200} элементов"
            ArchivePreviewWindow(self, path.name, preview or "Архив пуст")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось прочитать архив:\n{exc}")

    def start_search(self) -> None:
        query = self.search_panel.get_query()
        if not query:
            messagebox.showinfo("Поиск", "Введите запрос")
            return
        self.stop_search(silent=True)
        self.search_panel.clear()
        self.search_cancel_event = threading.Event()
        self.set_status("Поиск запущен...")

        def worker() -> None:
            try:
                for result in search_files(
                    self.current_path,
                    query=query,
                    extensions_raw=self.search_panel.get_extensions(),
                    include_content=self.search_panel.get_include_content(),
                    cancel_event=self.search_cancel_event,
                ):
                    self.search_queue.put(result)
                self.search_queue.put("__DONE__")
            except Exception as exc:
                self.search_queue.put(f"__ERROR__{exc}")

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self.process_search_queue)

    def stop_search(self, silent: bool = False) -> None:
        if self.search_cancel_event is not None:
            self.search_cancel_event.set()
            if not silent:
                self.set_status("Поиск остановлен")

    def process_search_queue(self) -> None:
        processed = 0
        while processed < 100:
            try:
                item = self.search_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            if item == "__DONE__":
                self.set_status(f"Поиск завершён.")
                return
            if isinstance(item, str) and item.startswith("__ERROR__"):
                messagebox.showerror("Ошибка поиска", item.replace("__ERROR__", "", 1))
                self.set_status("Ошибка поиска")
                return
            if isinstance(item, SearchResult):
                self.search_panel.insert_result(item)
        self.after(100, self.process_search_queue)

    def open_search_result(self) -> None:
        path = self.search_panel.get_selected_path()
        if not path:
            return
        try:
            if path.is_dir():
                self.load_directory(path)
            elif path.exists():
                open_in_system(path)
            else:
                messagebox.showwarning("Поиск", "Файл уже не существует")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть результат:\n{exc}")


def main() -> None:
    app = ArchiveManagerApp()
    app.mainloop()
