@echo off
setlocal
cd /d "%~dp0"

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller не найден. Установите: pip install pyinstaller
    exit /b 1
)

pyinstaller --clean ROCKET_Archiver.spec
if errorlevel 1 (
    echo Сборка завершилась с ошибкой.
    exit /b 1
)

echo.
echo Готово: dist\ROCKET_Archiver_v1.1.1.exe
echo Внутри упакованы bin\7z.exe и img\Icon.ico.
echo.
echo После установки: запустите exe, вкладка «По умолчанию» — зарегистрируйте ассоциации.
endlocal
