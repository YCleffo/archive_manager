@echo off
chcp 65001 >nul
title Менеджер Архивов
color 0f

echo ========================================================
echo                 ЗАПУСК ПРИЛОЖЕНИЯ
echo ========================================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    color 0c
    echo [ОШИБКА] Python не найден в системе. 
    echo Убедитесь, что Python установлен и добавлен в системный PATH.
    pause
    exit /b 1
)

echo [ИНФО] Проверка установленных библиотек...
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    color 0e
    echo [ПРЕДУПРЕЖДЕНИЕ] Библиотека PySide6 не установлена.
    echo.
    choice /C YN /M "Установить недостающие зависимости из requirements.txt (Y - Да, N - Нет)?"
    if errorlevel 2 (
        color 0c
        echo.
        echo [ОШИБКА] Без необходимых библиотек приложение не запустится.
        pause
        exit /b 1
    )
    echo.
    echo [ИНФО] Выполняется установка...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        color 0c
        echo.
        echo [ОШИБКА] Произошла ошибка при установке зависимостей.
        pause
        exit /b 1
    )
    color 0f
    echo [УСПЕХ] Зависимости успешно установлены!
    echo.
)

echo [ИНФО] Все системы в норме. Запускаем главную программу...
echo ========================================================
echo.

python main.py

echo.
echo [ИНФО] Приложение завершило работу.
pause
