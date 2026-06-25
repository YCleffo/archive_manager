# Audit Prompt для прямой правки проекта «Менеджер файлов / Архиватор»

Ты — senior Python/PySide6 reviewer. Работай с проектом как с реальным десктопным файловым менеджером/архиватором.

Главная цель: **найти проблемы и сразу исправить код проекта**.  
Не описывай результаты отдельно и не делай длинные выводы. На выходе нужен только исправленный проект/архив с кодом.

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

## Что обязательно проверить перед правками

1. Распакуй проект.
2. Запусти синтаксическую проверку:

```bash
python -m compileall .
```

3. Проверь зависимости из `requirements.txt`.
4. Проверь соответствие README реальным файлам проекта.
5. Проверь, что приложение запускается через `main.py`.
6. После правок снова запусти `compileall`.

## Найденные проблемы, которые надо исправить

### 1. `send2trash` используется, но отсутствует в зависимостях

В `archive_app/file_utils.py` используется:

```python
from send2trash import send2trash
```

Но в `requirements.txt` сейчас есть только:

```txt
PySide6>=6.7
```

Нужно добавить:

```txt
send2trash>=1.8.3
```

И привести README в соответствие: удаление теперь выполняется через корзину, а не напрямую.

---

### 2. README не соответствует проекту

В README указан `run.sh`, но в архиве его нет.

Исправить одним из двух способов:

- либо добавить рабочий `run.sh`;
- либо убрать упоминание `run.sh` из README и структуры проекта.

Также README сейчас пишет, что удаление выполняется без корзины, но код уже использует `send2trash`. Это нужно исправить.

---

### 3. Распаковка TAR всё ещё опасна

Файл: `archive_app/archive_utils.py`.

Текущая логика TAR:

- проверяет путь участника архива;
- частично проверяет symlink/hardlink;
- опасные ссылки просто пропускает через `continue`;
- затем вызывает `archive.extractall(...)`.

Нужно сделать безопаснее:

- не использовать `extractall()` для TAR;
- не пропускать опасные элементы молча;
- полностью запретить symlink, hardlink, device, fifo и другие спецфайлы в TAR;
- распаковывать только обычные файлы и директории;
- проверять каждый путь до записи;
- проверять лимиты до распаковки;
- не позволять перезаписывать папку файлом и файл папкой.

Минимальная логика проверки TAR-элемента:

```python
def _validate_tar_member(member: tarfile.TarInfo) -> None:
    if member.issym() or member.islnk():
        raise ValueError(f"Ссылки в TAR запрещены: {member.name}")

    if member.isdev() or member.isfifo():
        raise ValueError(f"Спецфайлы в TAR запрещены: {member.name}")

    if not (member.isfile() or member.isdir()):
        raise ValueError(f"Неподдерживаемый тип элемента TAR: {member.name}")
```

---

### 4. `_safe_target()` надо усилить

Текущая проверка:

```python
if ".." in member_name_clean:
    raise ValueError(...)
```

Проблемы:

- строка `abc..txt` ошибочно считается опасной;
- абсолютные пути лучше запрещать, а не превращать в относительные через `lstrip`;
- Windows drive paths вроде `C:\...` нужно запрещать;
- UNC-пути нужно запрещать;
- проверять надо части пути, а не подстроку.

Сделать отдельную нормализацию имени из архива.

Пример направления:

```python
from pathlib import PurePosixPath, PureWindowsPath

def _validate_archive_name(member_name: str) -> str:
    raw = member_name.replace("\\", "/").strip()

    if not raw:
        raise ValueError("Пустое имя элемента архива")

    posix = PurePosixPath(raw)
    windows = PureWindowsPath(member_name)

    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"Абсолютный путь запрещён: {member_name}")

    parts = [part for part in posix.parts if part not in ("", ".")]

    if any(part == ".." for part in parts):
        raise ValueError(f"Выход за пределы папки запрещён: {member_name}")

    return "/".join(parts)
```

`_safe_target(destination, member_name)` должен использовать это имя и после `resolve()` обязательно проверять `relative_to(destination)`.

---

### 5. Добавить лимиты распаковки

Сейчас есть общие лимиты, но нужно сделать их полнее.

Добавить:

```python
MAX_EXTRACT_FILES = 10_000
MAX_EXTRACT_TOTAL_SIZE = 2 * 1024 * 1024 * 1024
MAX_EXTRACT_SINGLE_FILE_SIZE = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 500
```

Проверить:

- количество элементов;
- общий размер;
- размер одного файла;
- подозрительное сжатие;
- `compress_size == 0` при `file_size > 0`.

Для ZIP:

```python
if member.file_size > MAX_EXTRACT_SINGLE_FILE_SIZE:
    raise ValueError(f"Файл слишком большой: {member.filename}")

if member.compress_size == 0 and member.file_size > 0:
    raise ValueError(f"Подозрительный ZIP-элемент: {member.filename}")

if member.compress_size > 0 and member.file_size / member.compress_size > MAX_COMPRESSION_RATIO:
    raise ValueError(f"Подозрительный уровень сжатия: {member.filename}")
```

---

### 6. Не архивировать выходной ZIP внутрь самого себя

Файл: `archive_app/archive_utils.py`.

Проверка уже добавлена, но её надо сделать надёжной и понятной.

Нужна функция:

```python
def _is_same_or_inside(child: Path, parent: Path) -> bool:
    child = child.resolve()
    parent = parent.resolve()
    return child == parent or parent in child.parents
```

Перед созданием архива:

```python
for source in paths:
    base = source if source.is_dir() else source.parent
    if _is_same_or_inside(output_zip, base):
        raise ValueError("Нельзя сохранять архив внутрь архивируемой папки")
```

При обходе `source.rglob("*")` дополнительно пропускать сам `output_zip`, если он каким-то образом появился во время работы.

---

### 7. Копирование и перемещение папки внутрь себя

Файл: `archive_app/file_utils.py`.

Проверка уже есть, но её лучше вынести в общую функцию и не делать через `try/except AttributeError`.

Добавить:

```python
def _is_same_or_inside(child: Path, parent: Path) -> bool:
    child = child.resolve()
    parent = parent.resolve()
    return child == parent or parent in child.parents
```

Использовать в `copy_items()` и `move_items()`:

```python
if source.is_dir() and _is_same_or_inside(destination, source):
    raise ValueError(f"Нельзя копировать или перемещать папку внутрь самой себя: {source.name}")
```

---

### 8. Поиск может быть тяжёлым на больших папках

Файл: `archive_app/search_utils.py`.

Нужно добавить исключения для служебных папок:

```python
EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
}
```

При поиске пропускать эти директории.

Также не читать содержимое через symlink и не делать `stat()` с переходом по ссылкам там, где это не нужно.

---

### 9. Старый поиск может смешаться с новым

Файл: `archive_app/app.py`.

Сейчас старый worker может успеть прислать результаты после запуска нового поиска.

Нужно добавить идентификатор поиска:

```python
self.search_generation = 0
```

При запуске поиска увеличивать:

```python
self.search_generation += 1
generation = self.search_generation
```

Подключать сигналы через lambda/partial и игнорировать результаты неактуального поколения:

```python
worker.signals.result.connect(
    lambda result, gen=generation: self.insert_search_result(result, gen)
)
```

Метод:

```python
def insert_search_result(self, result: SearchResult, generation: int) -> None:
    if generation != self.search_generation:
        return
    self.search_panel.add_result(result)
```

То же сделать для `finished` и `error`.

---

### 10. Старые загрузки папок могут перезаписать новые

Файл: `archive_app/app.py`.

`load_directory()` теперь запускается через worker. Если пользователь быстро перейдёт в другую папку, старый worker может вернуться позже и заменить таблицу.

Нужно добавить поколение загрузки:

```python
self.load_generation = 0
```

В `load_directory()`:

```python
self.load_generation += 1
generation = self.load_generation
```

В `on_result`:

```python
if generation != self.load_generation:
    return
```

---

### 11. Подсказки пути надо сделать кроссплатформенными

Файл: `archive_app/ui/navigation_bar.py`.

Сейчас есть Windows-зависимость:

```python
text = text.replace("/", "\")
```

Нужно убрать принудительную замену `/` на `\`.

Использовать `pathlib` и `os.sep`.

Пример направления:

```python
def update_suggestions(self, text: str) -> None:
    text = os.path.expanduser(text.strip())

    if not text:
        self.string_list_model.setStringList([])
        return

    ends_with_sep = text.endswith((os.sep, "/", "\\"))
    current = Path(text)
    dir_path = current if ends_with_sep else current.parent

    if not dir_path.exists() or not dir_path.is_dir():
        self.string_list_model.setStringList([])
        return

    try:
        suggestions: list[str] = []
        with os.scandir(dir_path) as it:
            entries = sorted(it, key=lambda e: (not e.is_dir(), e.name.casefold()))
            for entry in entries[:100]:
                suffix = os.sep if entry.is_dir() else ""
                suggestions.append(str(Path(entry.path)) + suffix)

        self.string_list_model.setStringList(suggestions)
    except OSError:
        self.string_list_model.setStringList([])
```

Не забудь добавить импорт:

```python
from pathlib import Path
```

---

### 12. Выпадающий список подсказок пути надо покрасить в цвет приложения

Файл: `archive_app/ui/navigation_bar.py`.

После:

```python
self.path_edit.setCompleter(self.completer)
```

добавить:

```python
popup = self.completer.popup()
popup.setObjectName("PathCompleterPopup")
popup.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
```

Файл: `archive_app/ui/theme.py`.

Добавить стиль:

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

### 13. Закрытие приложения

Файл: `archive_app/app.py`.

Сейчас `os._exit()` уже не используется — это хорошо.

Проверить, что:

- закрытие не обрывает активную архивацию/распаковку;
- если операции ещё идут, пользователь получает предупреждение;
- `QThreadPool.waitForDone(1000)` не оставляет повреждённые файлы без предупреждения.

---

## Минимальные тесты, которые нужно добавить

Создать папку `tests/`.

Покрыть:

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

## Финальная проверка

После всех изменений выполнить:

```bash
python -m compileall .
```

Если добавлены тесты:

```bash
python -m pytest
```

На выходе нужен только исправленный проект/архив с кодом.
