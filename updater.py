import json
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

    def _create_update_script(self, downloaded_file):
        target_exe = os.path.abspath(self._resolve_running_exe())
        app_dir = os.path.dirname(target_exe)
        temp_dir = os.path.dirname(os.path.abspath(downloaded_file))
        desktop = self._windows_desktop_dir()
        shortcut_path = os.path.join(desktop, self.desktop_shortcut_name)

        config_path = os.path.join(temp_dir, "update_config.json")
        ps1_path = os.path.join(temp_dir, "update.ps1")
        launcher_path = os.path.join(temp_dir, "update.bat")

        config = {
            "new_exe": os.path.abspath(downloaded_file),
            "target_exe": target_exe,
            "app_dir": app_dir,
            "shortcut_path": shortcut_path,
            "temp_dir": temp_dir,
            "parent_pid": os.getpid(),
            "app_label": self.app_label,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        ps1 = r"""$ErrorActionPreference = 'Continue'
$ConfigPath = Join-Path -Path $PSScriptRoot -ChildPath 'update_config.json'
$config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

$NewExe = $config.new_exe
$TargetExe = $config.target_exe
$AppDir = $config.app_dir
$ShortcutPath = $config.shortcut_path
$TempDir = $config.temp_dir
$ParentPid = [int]$config.parent_pid
$AppLabel = $config.app_label
$StagingExe = "$TargetExe.new"
$BackupExe = "$TargetExe.bak"
$LogFile = Join-Path -Path $AppDir -ChildPath 'rocket_update.log'

function Write-Log {
    param([string]$Message)
    try {
        "$(Get-Date -Format o) $Message" | Out-File -LiteralPath $LogFile -Append -Encoding utf8
    } catch {}
}

function Test-FileSize {
    param([string]$Path, [long]$ExpectedSize)
    return (Test-Path -LiteralPath $Path) -and ((Get-Item -LiteralPath $Path).Length -eq $ExpectedSize)
}

Write-Log "=== Update start ==="
Write-Log "NewExe=$NewExe"
Write-Log "TargetExe=$TargetExe"
Write-Log "ParentPid=$ParentPid"

try {
    Wait-Process -Id $ParentPid -Timeout 90 -ErrorAction SilentlyContinue
} catch {
    Write-Log "Wait-Process: $_"
}

$srcSize = (Get-Item -LiteralPath $NewExe).Length
$installed = $false

if (Test-Path -LiteralPath $TargetExe) {
    try {
        Copy-Item -LiteralPath $TargetExe -Destination $BackupExe -Force -ErrorAction Stop
        Write-Log "Backup=$BackupExe"
    } catch {
        Write-Log "Backup skipped: $_"
    }
}

for ($attempt = 1; $attempt -le 25; $attempt++) {
    try {
        if (Test-Path -LiteralPath $StagingExe) {
            Remove-Item -LiteralPath $StagingExe -Force -ErrorAction SilentlyContinue
        }
        Copy-Item -LiteralPath $NewExe -Destination $StagingExe -Force -ErrorAction Stop
        if (-not (Test-FileSize -Path $StagingExe -ExpectedSize $srcSize)) {
            throw "Staging size mismatch"
        }
        Move-Item -LiteralPath $StagingExe -Destination $TargetExe -Force -ErrorAction Stop
        if (Test-FileSize -Path $TargetExe -ExpectedSize $srcSize) {
            $installed = $true
            Write-Log "Install OK on attempt $attempt"
            break
        }
        throw "Target size mismatch after move"
    } catch {
        Write-Log "Attempt $attempt failed: $_"
    }
    Start-Sleep -Seconds 2
}

if (-not $installed) {
    Write-Log "FAILED: restoring backup if possible"
    if (Test-Path -LiteralPath $BackupExe) {
        try {
            Copy-Item -LiteralPath $BackupExe -Destination $TargetExe -Force -ErrorAction Stop
            Write-Log "Restored from backup"
        } catch {
            Write-Log "Restore failed: $_"
        }
    }
    Add-Type -AssemblyName System.Windows.Forms
    [void][System.Windows.Forms.MessageBox]::Show(
        "Не удалось установить обновление.`n`nСкачанный файл сохранён:`n$NewExe`n`nСкопируйте его вручную в:`n$TargetExe",
        $AppLabel,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    )
    exit 1
}

if (Test-Path -LiteralPath $BackupExe) {
    Remove-Item -LiteralPath $BackupExe -Force -ErrorAction SilentlyContinue
}

try {
    if (Test-Path -LiteralPath $ShortcutPath) {
        Remove-Item -LiteralPath $ShortcutPath -Force
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetExe
    $shortcut.WorkingDirectory = $AppDir
    $shortcut.Save()
    Write-Log "Shortcut=$ShortcutPath -> $TargetExe"
} catch {
    Write-Log "Shortcut error: $_"
}

Start-Process -LiteralPath $TargetExe -WorkingDirectory $AppDir
Start-Sleep -Seconds 2

try {
    Remove-Item -LiteralPath $TempDir -Recurse -Force
} catch {
    Write-Log "Temp cleanup error: $_"
}
"""

        with open(ps1_path, "w", encoding="utf-8-sig") as f:
            f.write(ps1)

        with open(launcher_path, "w", encoding="utf-8") as f:
            f.write(
                """@echo off
chcp 65001 > nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1"
"""
            )

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if sys.platform == "win32":
            creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

        subprocess.Popen(
            ["cmd.exe", "/c", launcher_path],
            cwd=temp_dir,
            creationflags=creationflags,
            close_fds=True,
        )

        if hasattr(self, "update_window") and self.update_window.winfo_exists():
            self.update_window.destroy()

        os._exit(0)
