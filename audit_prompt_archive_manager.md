# Prompt для прямой правки проекта «Менеджер файлов / Архиватор»

Ты — senior Python/PySide6 developer. Работай с проектом как с реальным десктопным файловым менеджером/архиватором.

Главная цель: **сразу исправить код проекта**.  
**Не пиши отдельный отчёт, аудит, выводы, объяснения и длинные комментарии.**  
На выходе нужен только исправленный проект/архив с кодом.

## Контекст проекта

Проект: Python 3.10+, PySide6/Qt.

Функции приложения:

- просмотр папок;
- навигация по файловой системе;
- копирование, перемещение, переименование и удаление файлов/папок;
- создание ZIP-архивов;
- распаковка ZIP/TAR/TAR.GZ/TGZ/TAR.BZ2;
- просмотр содержимого архива;
- поиск файлов по имени;
- поиск текста внутри файлов;
- подсчёт размера папок;
- GUI на PySide6.

## Что уже проверено в текущей версии

Для текущей версии проекта `archive_manager(3).zip`:

- `python -m compileall .` проходит успешно;
- `python -m pytest -q` проходит успешно: 11 тестов;
- `send2trash>=1.8.3` уже добавлен в `requirements.txt`;
- базовые security-тесты уже есть в `tests/test_security.py`;
- TAR уже распаковывается без `extractall()`;
- поиск уже пропускает `.git`, `.venv`, `node_modules`, `__pycache__` и другие служебные папки;
- подсказки пути уже не делают принудительную замену `/` на `\`.

Не трать время на повторное добавление уже сделанных исправлений. Проверь их аккуратно, но правь только то, что ещё реально не доделано или сделано криво.

## Что обязательно проверить перед правками

1. Распакуй проект.
2. Запусти:

```bash
python -m compileall .
```

3. Если тесты доступны, запусти:

```bash
python -m pytest -q
```

4. Проверь зависимости из `requirements.txt`.
5. Проверь соответствие README реальным файлам проекта.
6. Проверь, что приложение запускается через `main.py`.
7. После правок снова запусти `compileall` и тесты.

## Главная новая задача

Нужно **максимально убрать зависимость от проводника/файлового менеджера операционной системы** и сделать работу с файлами через само приложение.

Под «проводником ОС» имеются в виду:

- системный диалог выбора папки `QFileDialog.getExistingDirectory(...)`;
- открытие файлов через системные приложения по умолчанию `os.startfile`, `open`, `xdg-open` как основной сценарий;
- любые действия, которые выбрасывают пользователя из приложения в Explorer/Finder/системный файловый менеджер.

Допускается оставить системное открытие только как второстепенную опцию в меню `Ещё`, например `Открыть в системе`, но **двойной клик и кнопка “Открыть” должны работать внутри приложения**.

---

## 1. Заменить системный выбор папки на внутренний диалог

Файл: `archive_app/app.py`  
Сейчас:

```python
selected = QFileDialog.getExistingDirectory(
    self, "Выберите папку", str(self.current_path)
)
```

Это открывает системный проводник. Нужно убрать основной сценарий через `QFileDialog`.

### Что сделать

Создать внутренний диалог выбора папки, например:

```text
archive_app/ui/folder_picker.py
```

Диалог должен быть на PySide6 и работать внутри приложения:

- сверху строка текущего пути;
- кнопки `Назад`, `Вверх`, `Домой`, `Обновить`;
- список/таблица папок текущей директории;
- двойной клик по папке открывает её внутри диалога;
- кнопка `Выбрать эту папку` возвращает текущую папку;
- кнопка `Отмена` закрывает диалог;
- использовать стили приложения из `theme.py`;
- не использовать `QFileDialog`.

Минимальная логика:

```python
class FolderPickerDialog(QDialog):
    def __init__(self, start_path: Path, icons: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.selected_path = Path(start_path).expanduser().resolve()
        ...

    def load_directory(self, path: Path) -> None:
        ...

    def accept_current(self) -> None:
        self.accept()
```

В `ArchiveManagerApp.choose_directory()` заменить системный диалог на внутренний:

```python
def choose_directory(self) -> None:
    dialog = FolderPickerDialog(self.current_path, self.icons, self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        self.load_directory(dialog.selected_path)
```

Не забудь убрать неиспользуемый импорт `QFileDialog` из `app.py`.

---

## 2. Двойной клик по файлу не должен сразу открывать системное приложение

Файл: `archive_app/app.py`  
Сейчас при открытии файла вызывается:

```python
open_in_system(path)
```

Это выбрасывает пользователя в приложение ОС. Нужно сделать внутреннее открытие.

### Что сделать

Создать внутренний просмотрщик файлов, например:

```text
archive_app/ui/preview_dialog.py
```

Или расширить существующий `ArchivePreviewDialog`, если так проще.

Внутренний просмотрщик должен поддерживать минимум:

1. **Текстовые файлы**: `.txt`, `.md`, `.py`, `.json`, `.csv`, `.html`, `.css`, `.js`, `.ts`, `.xml`, `.yml`, `.yaml`, `.ini`, `.log`, `.sql`, `.sh`, `.bat`, `.ps1`.
    - Открывать в `QPlainTextEdit` или `QTextEdit` в режиме read-only.
    - Ограничить чтение, например до 2–5 МБ, чтобы не зависал UI.

2. **Изображения**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`.
    - Показывать внутри `QLabel`/`QScrollArea` через `QPixmap`.
    - Масштабировать под окно, но не ломать пропорции.

3. **Архивы**: `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`.
    - При двойном клике показывать содержимое архива внутри приложения.
    - Не открывать системный архиватор.

4. **Остальные файлы**:
    - Показывать внутреннее окно свойств: имя, путь, тип, размер, дата изменения.
    - Не запускать автоматически внешнее приложение.
    - Можно добавить кнопку `Открыть в системе`, но только как дополнительную ручную опцию.

В `open_selected()` сделать такую логику:

```python
def open_selected(self) -> None:
    path = self.get_selected_path()
    if path is None:
        return

    try:
        if path.is_dir():
            self.load_directory(path)
            return

        if is_supported_archive(path):
            self.show_archive_contents_for_path(path)
            return

        self.show_internal_preview(path)
        self.set_status(f"Открыто внутри программы: {path.name}")
    except Exception as exc:
        QMessageBox.critical(self, "Ошибка", f"Не удалось открыть:\n{exc}")
```

Существующую функцию `open_in_system()` можно оставить в `file_utils.py`, но не использовать как основной путь. Добавить отдельное действие в меню `Ещё`:

```text
Открыть в системе
```

И только оно может вызывать `open_in_system(path)`.

---

## 3. Исправить текст удаления: сейчас код удаляет в корзину, а UI пишет «без корзины»

Файлы:

- `archive_app/app.py`
- `README.md`

В текущей версии `delete_items()` использует `send2trash`, но в интерфейсе всё ещё есть старые тексты:

```python
"Удалить выбранные объекты без корзины"
```

и диалог:

```python
"Удалить выбранные объекты без корзины?"
```

Нужно заменить на корректные формулировки:

```text
Переместить выбранные объекты в корзину?
```

```text
Это действие не удаляет файлы безвозвратно, но Ctrl+Z внутри программы не восстанавливает удаление из корзины.
```

В README в списке возможностей заменить:

```text
Удаление файлов и папок без помещения в корзину.
```

на:

```text
Удаление файлов и папок с перемещением в системную корзину.
```

---

## 4. Показывать в статусе, сколько файлов и папок выбрано

Сейчас в `FileTable` есть сигнал:

```python
selection_changed = Signal()
```

но он не используется.

### Что сделать

Файл: `archive_app/ui/tables.py`

В `FileTable.__init__()` подключить стандартный сигнал таблицы к пользовательскому сигналу:

```python
self.itemSelectionChanged.connect(self.selection_changed.emit)
```

Файл: `archive_app/app.py`

После создания таблицы подключить:

```python
self.file_table.selection_changed.connect(self.update_selection_status)
```

Добавить методы:

```python
def _count_paths(self, paths: list[Path]) -> tuple[int, int, int]:
    files = 0
    folders = 0
    for path in paths:
        try:
            if path.is_dir():
                folders += 1
            else:
                files += 1
        except OSError:
            files += 1
    return len(paths), files, folders


def _selection_text(self) -> str:
    paths = self.get_selected_paths()
    total, files, folders = self._count_paths(paths)
    if total == 0:
        return "Ничего не выбрано"
    return f"Выбрано: {total} | файлов: {files} | папок: {folders}"


def _clipboard_text(self) -> str:
    count = len(self._clipboard_paths)
    if count == 0:
        return "Буфер пуст"
    mode = "вырезано" if self._clipboard_is_cut else "скопировано"
    return f"В буфере: {mode} {count} | можно вставить: {count}"


def update_selection_status(self) -> None:
    self.set_status(f"{self._selection_text()} | {self._clipboard_text()}")
```

После загрузки новой папки тоже обновлять статус так, чтобы была информация о текущей папке и выбранных объектах:

```python
self.set_status(f"Открыто: {path} | объектов: {len(entries)} | {self._selection_text()} | {self._clipboard_text()}")
```

При любых операциях, где сейчас статус полностью перетирается, не терять информацию о буфере и выделении. Можно сделать общий метод:

```python
def set_status_with_context(self, message: str) -> None:
    self.set_status(f"{message} | {self._selection_text()} | {self._clipboard_text()}")
```

И использовать его после копирования, вставки, удаления, переименования, создания архива, распаковки и загрузки папки.

---

## 5. Динамически писать количество выбранных объектов на кнопках

Нужно, чтобы кнопки показывали состояние, а не всегда были одинаковыми.

### Что должно быть

Когда ничего не выбрано:

```text
Копировать
Вырезать
Удалить
```

Когда выбрано 3 объекта:

```text
Копировать (3)
Вырезать (3)
Удалить (3)
```

Когда выбран 1 объект:

```text
Копировать (1)
Вырезать (1)
Удалить (1)
```

### Что сделать

В `app.py` добавить метод:

```python
def update_action_counts(self) -> None:
    selected_count = len(self.get_selected_paths())
    clipboard_count = len(self._clipboard_paths)

    self.app_actions["copy"].setText(
        f"Копировать ({selected_count})" if selected_count else "Копировать"
    )
    self.app_actions["cut"].setText(
        f"Вырезать ({selected_count})" if selected_count else "Вырезать"
    )
    self.app_actions["delete"].setText(
        f"Удалить ({selected_count})" if selected_count else "Удалить"
    )

    if clipboard_count:
        self.app_actions["paste"].setText(f"Вставить ({clipboard_count})")
        self.app_actions["paste"].setToolTip(
            f"Можно вставить объектов: {clipboard_count}"
        )
        self.app_actions["paste"].setStatusTip(
            f"Можно вставить объектов: {clipboard_count}"
        )
        self.app_actions["paste"].setEnabled(True)
    else:
        self.app_actions["paste"].setText("Вставить")
        self.app_actions["paste"].setToolTip("Вставить объекты из буфера")
        self.app_actions["paste"].setStatusTip("Вставить объекты из буфера")
        self.app_actions["paste"].setEnabled(False)
```

Вызывать `update_action_counts()`:

- после создания `ActionBar`;
- после изменения выделения;
- после копирования;
- после вырезания;
- после вставки;
- после загрузки новой папки;
- после удаления;
- после сброса буфера.

---

## 6. После копирования/вырезания кнопки должны показывать, сколько скопировано и сколько можно вставить

Сейчас после копирования статус пишет только:

```python
self.set_status(f"В буфере {len(paths)} объектов (Копирование)")
```

Нужно сделать понятнее.

### После копирования

```python
def copy_selected(self) -> None:
    paths = self.get_selected_paths()
    if not paths:
        QMessageBox.information(self, "Копирование", "Выберите файлы или папки")
        return

    self._clipboard_paths = paths
    self._clipboard_is_cut = False
    self.update_action_counts()
    self.set_status_with_context(
        f"Скопировано в буфер: {len(paths)} | можно вставить: {len(paths)}"
    )
```

Кнопка `Вставить` должна стать:

```text
Вставить (N)
```

Tooltip/statusTip кнопки `Вставить`:

```text
Можно вставить объектов: N
```

### После вырезания

```python
self.set_status_with_context(
    f"Вырезано в буфер: {len(paths)} | можно вставить: {len(paths)}"
)
```

Кнопка `Вставить` тоже:

```text
Вставить (N)
```

### После вставки копированием

Если это копирование, буфер должен остаться доступным:

```python
self.set_status_with_context(
    f"Скопировано объектов: {count} | можно вставить ещё: {len(self._clipboard_paths)}"
)
self.update_action_counts()
```

### После вставки вырезанием

Если это перемещение, буфер надо очистить:

```python
self._clipboard_paths = []
self._clipboard_is_cut = False
self.update_action_counts()
self.set_status_with_context(f"Перемещено объектов: {count} | буфер очищен")
```

---

## 7. Сделать отображение выделения устойчивым после сортировки

`selected_paths()` берёт выбранные строки через `selectedRows()`. Это нормально, но после сортировки/обновления таблицы выделение сбрасывается. Нужно явно обновлять статус и кнопки после `set_entries()`.

В конце `FileTable.set_entries()`:

```python
self.clearSelection()
self.selection_changed.emit()
```

Или в `ArchiveManagerApp.load_directory(...).on_result(...)` после `self.file_table.set_entries(entries)` вызвать:

```python
self.update_action_counts()
self.update_selection_status()
```

---

## 8. Улучшить подсказки пути и убрать inline style у popup

Сейчас в `navigation_bar.py` popup подсказок дополнительно получает inline stylesheet:

```python
popup.setStyleSheet("QListView { border-radius: 0px; ... }")
```

Лучше убрать inline style и оставить всё в `theme.py`, иначе стили расползаются по проекту.

В `navigation_bar.py` оставить только:

```python
popup = self.completer.popup()
if popup is not None:
    popup.setObjectName("PathCompleterPopup")
    popup.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
```

В `theme.py` держать весь стиль:

```css
QListView#PathCompleterPopup {
	background: #ffffff;
	color: #1d2733;
	border: 1px solid #d8e0ea;
	border-radius: 8px;
	padding: 4px;
	outline: 0;
	selection-background-color: #edf4ff;
	selection-color: #172033;
}

QListView#PathCompleterPopup::item {
	min-height: 28px;
	border-radius: 6px;
	padding: 6px 10px;
	margin: 1px 0;
}

QListView#PathCompleterPopup::item:hover {
	background: #f3f7fb;
	color: #172033;
}

QListView#PathCompleterPopup::item:selected {
	background: #edf4ff;
	color: #172033;
}
```

---

## 9. Проверить ZIP-распаковку: не использовать небезопасный `ZipFile.extract()`

TAR уже распаковывается вручную, но ZIP всё ещё использует:

```python
archive.extract(member, destination)
```

Даже если `_safe_target()` вызывается заранее, лучше сделать ZIP так же явно и безопасно, как TAR:

```python
if member.is_dir():
    target.mkdir(parents=True, exist_ok=True)
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member, "r") as src, open(target, "wb") as dst:
        shutil.copyfileobj(src, dst)
```

Перед записью оставить проверки:

- `_safe_target(destination, member.filename)`;
- лимит количества файлов;
- лимит размера одного файла;
- лимит общего размера;
- подозрительное сжатие;
- конфликт файл/папка.

---

## 10. README привести к новому поведению

Обновить README после правок:

- больше не писать, что основная навигация делается через системный проводник;
- написать, что выбор папки выполняется во внутреннем диалоге приложения;
- написать, что двойной клик по файлу открывает внутренний просмотрщик;
- написать, что внешнее открытие доступно только дополнительной командой, если оставлено;
- написать, что статус показывает количество выбранных файлов/папок;
- написать, что кнопка `Вставить` показывает количество объектов в буфере.

---

## 11. Минимальные тесты, которые нужно добавить или обновить

Не обязательно делать GUI-тесты тяжёлыми. Достаточно покрыть утилитарную логику и smoke-проверки.

Добавить/обновить тесты:

1. ZIP с `../evil.txt` не распаковывается.
2. ZIP с абсолютным путём не распаковывается.
3. TAR с `../evil.txt` не распаковывается.
4. TAR с symlink не распаковывается.
5. TAR с hardlink не распаковывается.
6. ZIP bomb по количеству файлов отклоняется.
7. ZIP bomb по размеру отклоняется.
8. Нельзя создать ZIP внутри архивируемой папки.
9. Нельзя копировать папку внутрь самой себя.
10. Нельзя переместить папку внутрь самой себя.
11. `PathCompleter.update_suggestions()` работает без принудительной замены `/` на `\`.
12. В проекте нет основного сценария `QFileDialog.getExistingDirectory` для выбора папки.
13. `open_selected()` не вызывает `open_in_system()` для обычного двойного клика по файлу.
14. Метод обновления action-кнопок выставляет `Вставить (N)` при наличии N объектов в буфере.
15. Метод статуса формирует текст с количеством выбранных файлов и папок.

---

## Финальная проверка

После всех изменений выполнить:

```bash
python -m compileall .
python -m pytest -q
```

Если тесты требуют Qt в headless-режиме, использовать:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

На выходе нужен только исправленный проект/архив с кодом. Не добавляй отдельный отчёт.
