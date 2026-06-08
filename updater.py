import os
import subprocess
import sys
import tempfile
import threading
from tkinter import messagebox, Toplevel, ttk
from urllib.parse import urlparse
import tkinter as tk

try:
    import requests
except ImportError:
    requests = None


class Updater:
    def __init__(
        self,
        root,
        current_version,
        repo_url,
        github_token=None,
        app_label="ROCKET Archiver",
        desktop_shortcut_name="ROCKET Archiver.lnk",
        release_exe_template="ROCKET_Archiver_v{version}.exe",
        user_agent="ROCKET-Archiver-Updater",
    ):
        self.root = root
        self.current_version = current_version.lstrip("vV")
        self.repo_url = repo_url
        self.github_token = github_token
        self.app_label = app_label
        self.desktop_shortcut_name = desktop_shortcut_name
        self.release_exe_template = release_exe_template
        self.user_agent = user_agent

        parsed = urlparse(repo_url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError("Invalid repository URL")

        self.owner = path_parts[0]
        self.repo = path_parts[1]
        self.api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"

    def check_for_updates(self, silent=False):
        if requests is None:
            if not silent and self.root:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Ошибка",
                        "Для проверки обновлений нужен пакет requests:\npip install requests",
                    ),
                )
            return False

        try:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": self.user_agent,
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"

            response = requests.get(self.api_url, headers=headers, timeout=15)
            response.raise_for_status()

            release_data = response.json()
            latest_version = release_data.get("tag_name", "").lstrip("vV")

            if not latest_version:
                raise ValueError("Не удалось определить последнюю версию")

            if self._compare_versions(latest_version, self.current_version) > 0:
                if not silent:
                    self._show_update_dialog(release_data)
                return True
            if not silent:
                messagebox.showinfo("Обновление", "Установлена последняя версия.")
            return False

        except Exception as e:
            if not silent and self.root:
                self.root.after(
                    0,
                    lambda err=e: messagebox.showerror("Ошибка", f"Не удалось проверить обновления:\n{err}"),
                )
            return False

    def _compare_versions(self, v1, v2):
        def parse_version(v):
            return [int(part) for part in v.split(".") if part.isdigit()]

        return (parse_version(v1) > parse_version(v2)) - (parse_version(v1) < parse_version(v2))

    def _show_update_dialog(self, release_data):
        self.update_window = Toplevel(self.root)
        self.update_window.title("Доступно обновление")
        self.update_window.resizable(False, False)
        self.update_window.transient(self.root)
        self.update_window.grab_set()
        self.update_window.attributes("-topmost", 1)

        width, height = 520, 420
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 2
        self.update_window.geometry(f"{width}x{height}+{x}+{y}")

        self.update_window.grid_rowconfigure(1, weight=1)
        self.update_window.grid_columnconfigure(0, weight=1)

        ttk.Label(
            self.update_window,
            text=f"Доступна версия {release_data.get('tag_name', '')}",
            font=("Arial", 14, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))

        body_frame = ttk.Frame(self.update_window)
        body_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 10))
        body_frame.grid_rowconfigure(0, weight=1)
        body_frame.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(body_frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(body_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        def _on_frame_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(scrollable_window, width=event.width)

        scrollable_frame.bind("<Configure>", _on_frame_configure)
        scrollable_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        body = release_data.get("body", "") or "Описание обновления отсутствует."
        ttk.Label(scrollable_frame, text=body, wraplength=460, justify="left").pack(
            fill="x", expand=True, anchor="nw"
        )

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        def _bind_mousewheel(_event=None):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"))

        def _unbind_mousewheel(_event=None):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        bottom_frame = ttk.Frame(self.update_window)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(bottom_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self.progress_label = ttk.Label(bottom_frame, text="")
        self.progress_label.grid(row=1, column=0, sticky="w", pady=(0, 10))

        btn_frame = ttk.Frame(bottom_frame)
        btn_frame.grid(row=2, column=0)
        ttk.Button(btn_frame, text="Обновить", command=lambda: self._start_update(release_data)).pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="Позже", command=self.update_window.destroy).pack(side="left", padx=5)

    def _start_update(self, release_data):
        threading.Thread(target=self._download_and_install, args=(release_data,), daemon=True).start()

    def _get_download_url(self, release_data):
        version = release_data["tag_name"]
        for asset in release_data.get("assets", []):
            if asset["name"].lower().endswith((".exe", ".zip", ".dmg")):
                return asset["browser_download_url"]
        clean_version = str(version).lstrip("vV")
        file_name = self.release_exe_template.format(version=clean_version)
        return f"https://github.com/{self.owner}/{self.repo}/releases/download/{version}/{file_name}".replace(
            " ", "%20"
        )

    def _get_asset_download(self, asset):
        headers = {
            "Accept": "application/octet-stream",
            "User-Agent": self.user_agent,
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        response = requests.get(asset["url"], headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        return response

    def _download_and_install(self, release_data):
        try:
            asset = None
            for item in release_data.get("assets", []):
                if item["name"].lower().endswith((".exe", ".zip")):
                    asset = item
                    break

            if not asset:
                raise ValueError("Не найден файл .exe или .zip в релизе GitHub.")

            response = self._get_asset_download(asset)
            temp_dir = tempfile.mkdtemp()
            download_path = os.path.join(temp_dir, asset["name"])
            total_size = int(asset.get("size", 0))
            downloaded = 0

            with open(download_path, "wb") as f:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = downloaded / total_size * 100
                            self.progress_var.set(percent)
                            size_mb = downloaded / 1024 / 1024
                            total_mb = total_size / 1024 / 1024
                            self.progress_label.config(
                                text=f"Загружено: {size_mb:.2f} МБ / {total_mb:.2f} МБ ({percent:.1f}%)"
                            )
                        else:
                            self.progress_label.config(text=f"Загружено: {downloaded / 1024:.2f} КБ")
                        self.update_window.update_idletasks()

            self._create_update_script(download_path)
            os._exit(0)

        except Exception as e:
            messagebox.showerror("Ошибка обновления", str(e))

    @staticmethod
    def _resolve_running_exe():
        """Путь к запущенному exe (для PyInstaller надёжнее sys.executable, чем argv[0])."""
        if getattr(sys, "frozen", False):
            return os.path.abspath(sys.executable)
        return os.path.abspath(sys.argv[0])

    @staticmethod
    def _windows_desktop_dir():
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
                if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0 and buf.value:
                    return buf.value
            except Exception:
                pass
        return os.path.join(os.path.expanduser("~"), "Desktop")

    @staticmethod
    def _cmd_path(path):
        return os.path.abspath(path).replace("\\", "/")

    def _create_update_script(self, downloaded_file):
        target_exe = self._resolve_running_exe()
        app_dir = os.path.dirname(target_exe)
        temp_dir = os.path.dirname(downloaded_file)
        desktop = self._windows_desktop_dir()
        update_bat = os.path.join(temp_dir, "update.bat")
        exe_name = os.path.basename(target_exe)

        new_exe = self._cmd_path(downloaded_file)
        target = self._cmd_path(target_exe)
        staging = self._cmd_path(target_exe + ".new")
        work_dir = self._cmd_path(app_dir)
        desktop_path = self._cmd_path(desktop)
        temp = self._cmd_path(temp_dir)
        shortcut_path = f"{desktop_path}/{self.desktop_shortcut_name}"

        with open(update_bat, "w", encoding="utf-8") as f:
            f.write(
                f"""@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul
echo Обновление {self.app_label}...
echo Установка в: {target}

set "NEW_EXE={new_exe}"
set "TARGET_EXE={target}"
set "STAGING_EXE={staging}"
set "APP_DIR={work_dir}"
set "SHORTCUT={shortcut_path}"

timeout /t 2 /nobreak > nul

set /a ATTEMPTS=0
:retry_copy
set /a ATTEMPTS+=1
if !ATTEMPTS! gtr 20 goto copy_failed

del "%STAGING_EXE%" > nul 2>&1
copy /Y "%NEW_EXE%" "%STAGING_EXE%" > nul 2>&1
if not exist "%STAGING_EXE%" goto wait_retry

for %%F in ("%NEW_EXE%") do set SRC_SIZE=%%~zF
for %%F in ("%STAGING_EXE%") do set DST_SIZE=%%~zF
if not !SRC_SIZE! equ !DST_SIZE! (
    del "%STAGING_EXE%" > nul 2>&1
    goto wait_retry
)

move /Y "%STAGING_EXE%" "%TARGET_EXE%" > nul 2>&1
if not exist "%TARGET_EXE%" goto wait_retry

for %%F in ("%TARGET_EXE%") do set FINAL_SIZE=%%~zF
if not !SRC_SIZE! equ !FINAL_SIZE! goto wait_retry
goto copy_ok

:wait_retry
if !ATTEMPTS! equ 5 taskkill /f /im "{exe_name}" > nul 2>&1
timeout /t 2 /nobreak > nul
goto retry_copy

:copy_failed
echo.
echo Не удалось установить обновление.
echo Новая версия сохранена здесь: %NEW_EXE%
echo Файл программы должен быть здесь: %TARGET_EXE%
echo Старая версия не удалена.
echo.
pause
exit /b 1

:copy_ok
del "%SHORTCUT%" > nul 2>&1
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%');$s.TargetPath='%TARGET_EXE%';$s.WorkingDirectory='%APP_DIR%';$s.Save()"
start "" "%TARGET_EXE%"
timeout /t 2 /nobreak > nul
rmdir /s /q "{temp}"
"""
            )

        subprocess.Popen(f'cmd /c "{update_bat}"', shell=True)

        if hasattr(self, "update_window") and self.update_window.winfo_exists():
            self.update_window.destroy()

        os._exit(0)
