import os
import datetime

def scan_directory(output_filename="file_scan_report.txt", root_dir="."):
    with open(output_filename, 'w', encoding='utf-8') as f:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    stat = os.stat(filepath)
                    size = stat.st_size
                    mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"Файл: {filepath} | Размер: {size} байт | Изменен: {mtime}\n")
                except Exception as e:
                    f.write(f"Файл: {filepath} | Ошибка доступа: {e}\n")

if __name__ == "__main__":
    print(f"Начинаю сканирование файлов в директории {os.path.abspath('.')}...")
    scan_directory()
    print("Сканирование завершено. Результат сохранен в file_scan_report.txt")
