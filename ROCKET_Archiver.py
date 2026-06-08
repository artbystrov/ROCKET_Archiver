#!/usr/bin/env python3
"""ROCKET Archiver — распаковка по двойному клику (как Archive Utility на macOS)."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from archiver_core import (
    SUPPORTED_EXTRACT_EXTENSIONS,
    create_zip,
    find_7z_path,
    find_icon_path,
    is_supported_archive,
    open_in_explorer,
)
from extract_ui import ExtractProgressDialog, extract_with_progress
from windows_assoc import (
    association_status,
    open_default_apps_settings,
    register_associations,
    unregister_associations,
)

APP_VERSION = "1.1.1"
GITHUB_REPO_URL = "https://github.com/artbystrov/ROCKET_Archiver"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or None


class ArchiverApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.current_version = APP_VERSION
        self.root.title(f"ROCKET Archiver v{self.current_version}")
        self.root.minsize(480, 360)
        self.updater = None

        icon = find_icon_path()
        if icon:
            try:
                self.root.iconbitmap(icon)
            except Exception:
                pass

        self._init_updater()
        self._build_ui()
        self._create_menu()
        self._refresh_assoc_status()

    def _init_updater(self) -> None:
        try:
            app_dir = Path(__file__).resolve().parent
            if str(app_dir) not in sys.path:
                sys.path.insert(0, str(app_dir))
            from updater import Updater

            self.updater = Updater(
                root=self.root,
                current_version=self.current_version,
                repo_url=GITHUB_REPO_URL,
                github_token=GITHUB_TOKEN,
                release_exe_template="ROCKET_Archiver_v{version}.exe",
            )
        except Exception:
            self.updater = None

    def _create_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        if self.updater is not None:
            file_menu.add_command(
                label="Проверить обновления",
                command=lambda: threading.Thread(
                    target=self.updater.check_for_updates,
                    daemon=True,
                ).start(),
            )
            file_menu.add_separator()
        file_menu.add_command(label="О программе", command=self._show_about)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)
        menubar.add_cascade(label="Файл", menu=file_menu)
        self.root.config(menu=menubar)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "О программе",
            f"ROCKET Archiver v{self.current_version}\n\n"
            "Распаковка архивов по двойному клику (как на macOS).\n"
            "Поддержка ZIP, RAR, 7z и других форматов.\n\n"
            f"{GITHUB_REPO_URL}",
        )

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        header = ttk.Label(
            self.root,
            text=f"ROCKET Archiver v{self.current_version}",
            font=("Segoe UI", 16, "bold"),
        )
        header.pack(anchor="w", **pad)

        subtitle = ttk.Label(
            self.root,
            text="Двойной клик по архиву → папка с тем же именем рядом с файлом (как на Mac).",
            wraplength=440,
        )
        subtitle.pack(anchor="w", padx=12, pady=(0, 10))

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=12, pady=4)

        extract_tab = ttk.Frame(notebook)
        compress_tab = ttk.Frame(notebook)
        settings_tab = ttk.Frame(notebook)
        notebook.add(extract_tab, text="Распаковка")
        notebook.add(compress_tab, text="Архивация ZIP")
        notebook.add(settings_tab, text="По умолчанию")

        ttk.Label(
            extract_tab,
            text="Выберите архив — будет распакован в папку рядом с файлом.",
            wraplength=420,
        ).pack(anchor="w", **pad)
        ttk.Button(
            extract_tab,
            text="Выбрать архив…",
            command=self._pick_and_extract,
        ).pack(anchor="w", **pad)

        ttk.Label(
            compress_tab,
            text="Выберите файлы или папки — будет создан ZIP-архив.",
            wraplength=420,
        ).pack(anchor="w", **pad)
        compress_btns = ttk.Frame(compress_tab)
        compress_btns.pack(anchor="w", padx=12, pady=6)
        ttk.Button(
            compress_btns,
            text="Файлы → ZIP…",
            command=lambda: self._pick_and_compress(pick_dir=False),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            compress_btns,
            text="Папка → ZIP…",
            command=lambda: self._pick_and_compress(pick_dir=True),
        ).pack(side="left")

        self.assoc_status_var = tk.StringVar(value="")
        ttk.Label(
            settings_tab,
            textvariable=self.assoc_status_var,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", **pad)

        btn_row = ttk.Frame(settings_tab)
        btn_row.pack(anchor="w", padx=12, pady=4)
        ttk.Button(
            btn_row,
            text="Зарегистрировать ассоциации",
            command=self._register_assoc,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            btn_row,
            text="Убрать ассоциации",
            command=self._unregister_assoc,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            btn_row,
            text="Параметры Windows…",
            command=open_default_apps_settings,
        ).pack(side="left")

        hint = (
            "После регистрации откройте «Параметры → Приложения по умолчанию» "
            "и выберите ROCKET Archiver для нужных типов файлов, "
            "либо щёлкните правой кнопкой по архиву → «Открыть с помощью» → "
            "«Всегда использовать это приложение»."
        )
        ttk.Label(settings_tab, text=hint, wraplength=420, foreground="#555").pack(
            anchor="w", **pad
        )

        tool_status = "7-Zip: найден" if find_7z_path() else "7-Zip: не найден (нужен для RAR и др.)"
        ttk.Label(self.root, text=tool_status, foreground="#666").pack(anchor="w", padx=12, pady=4)

    def _refresh_assoc_status(self) -> None:
        status = association_status()
        if not status.get("supported"):
            self.assoc_status_var.set("Ассоциации доступны только в Windows.")
            return
        linked = status.get("linked_extensions", 0)
        total = status.get("total_extensions", 0)
        if status.get("fully_registered"):
            text = f"Зарегистрировано расширений: {linked} из {total}. Готово к использованию."
        else:
            text = (
                f"Зарегистрировано расширений: {linked} из {total}. "
                "Нажмите «Зарегистрировать ассоциации», затем подтвердите в Windows."
            )
        self.assoc_status_var.set(text)

    def _register_assoc(self) -> None:
        try:
            exts = register_associations()
            self._refresh_assoc_status()
            messagebox.showinfo(
                "Готово",
                f"Ассоциации записаны ({len(exts)} типов).\n\n"
                "Теперь в Windows выберите ROCKET Archiver программой по умолчанию "
                "для архивов (кнопка «Параметры Windows…» или «Открыть с помощью»).",
            )
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _unregister_assoc(self) -> None:
        try:
            removed = unregister_associations()
            self._refresh_assoc_status()
            messagebox.showinfo("Готово", f"Снято ассоциаций: {len(removed)}")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _pick_and_extract(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTRACT_EXTENSIONS))
        path = filedialog.askopenfilename(
            title="Выберите архив",
            filetypes=[("Архивы", exts), ("Все файлы", "*.*")],
        )
        if path:
            self._run_extract(Path(path))

    def _pick_and_compress(self, pick_dir: bool = False) -> None:
        if pick_dir:
            folder = filedialog.askdirectory(title="Выберите папку для ZIP")
            if not folder:
                return
            paths = (folder,)
        else:
            paths = filedialog.askopenfilenames(
                title="Выберите файлы для ZIP",
                filetypes=[("Все файлы", "*.*")],
            )
            if not paths:
                return

        default_name = Path(paths[0]).stem + ".zip"
        out = filedialog.asksaveasfilename(
            title="Сохранить ZIP как",
            defaultextension=".zip",
            initialfile=default_name,
            filetypes=[("ZIP-архив", "*.zip")],
        )
        if not out:
            return
        try:
            result = create_zip(list(paths), out)
            messagebox.showinfo("Готово", f"Создан архив:\n{result}")
            open_in_explorer(result.parent)
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _run_extract(self, archive: Path) -> None:
        ExtractProgressDialog(archive, parent=self.root).run()


def _archive_from_argv(argv: list[str]) -> Path | None:
    for arg in argv:
        if arg.startswith("-"):
            continue
        path = Path(arg)
        if path.is_file() and is_supported_archive(path):
            return path.resolve()
    return None


def quick_extract(archive: Path) -> int:
    """Режим двойного клика: окно прогресса, папка рядом с архивом."""
    return extract_with_progress(archive)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ROCKET Archiver")
    parser.add_argument("files", nargs="*", help="Архив для распаковки")
    parser.add_argument("--register", action="store_true", help="Зарегистрировать ассоциации")
    parser.add_argument("--unregister", action="store_true", help="Снять ассоциации")
    parser.add_argument("--gui", action="store_true", help="Открыть окно программы")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)

    if args.register:
        register_associations()
        print("Ассоциации зарегистрированы.")
        return 0
    if args.unregister:
        unregister_associations()
        print("Ассоциации сняты.")
        return 0

    archive = _archive_from_argv(args.files)
    if archive and not args.gui:
        return quick_extract(archive)

    root = tk.Tk()
    app = ArchiverApp(root)
    if archive:
        root.after(100, lambda: app._run_extract(archive))

    if app.updater is not None:

        def check_updates_in_thread() -> None:
            try:
                updated = app.updater.check_for_updates(silent=True)
                if updated:
                    root.after(0, lambda: app.updater.check_for_updates(silent=False))
            except Exception:
                pass

        root.after(500, lambda: threading.Thread(target=check_updates_in_thread, daemon=True).start())

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
