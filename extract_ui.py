"""Окно прогресса распаковки в стиле Windows."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from archiver_core import extract_archive, find_icon_path


def _apply_icon(window: tk.Misc) -> None:
    icon = find_icon_path()
    if icon:
        try:
            window.iconbitmap(icon)
        except Exception:
            pass


class ExtractProgressDialog:
    def __init__(self, archive: Path, parent: tk.Misc | None = None):
        self.archive = archive.resolve()
        self._done = threading.Event()
        self._error: str | None = None
        self._out_dir: Path | None = None

        if parent is None:
            self.root = tk.Tk()
            self._owns_root = True
        else:
            self.root = tk.Toplevel(parent)
            self._owns_root = False

        self.root.title("ROCKET Archiver")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        _apply_icon(self.root)

        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        self.title_var = tk.StringVar(
            value=f"Распаковка «{self.archive.name}»…"
        )
        ttk.Label(frame, textvariable=self.title_var).pack(anchor="w", pady=(0, 10))

        bar_row = ttk.Frame(frame)
        bar_row.pack(fill="x")
        bar_row.grid_columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            bar_row,
            variable=self.progress_var,
            maximum=100,
            length=360,
            mode="determinate",
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew")

        self.percent_var = tk.StringVar(value="0%")
        ttk.Label(bar_row, textvariable=self.percent_var, width=5).grid(
            row=0, column=1, padx=(8, 0)
        )

        self.file_var = tk.StringVar(value="")
        ttk.Label(
            frame,
            textvariable=self.file_var,
            foreground="#555",
            wraplength=380,
        ).pack(anchor="w", pady=(8, 0))

        self._center_window(420, 130)

        if not self._owns_root:
            self.root.transient(parent)
            self.root.grab_set()

    def _center_window(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _on_progress(self, percent: float, message: str = "") -> None:
        clamped = max(0.0, min(100.0, float(percent)))
        self.progress_var.set(clamped)
        self.percent_var.set(f"{int(round(clamped))}%")
        if message:
            self.file_var.set(message)
        self.root.update_idletasks()

    def _worker(self) -> None:
        try:
            def callback(percent: float, message: str = "") -> None:
                self.root.after(0, lambda: self._on_progress(percent, message))

            self._out_dir = extract_archive(self.archive, progress_callback=callback)
            self.root.after(0, lambda: self._on_progress(100, "Готово"))
        except Exception as exc:
            self._error = str(exc)
        finally:
            self.root.after(0, self._finish)

    def _finish(self) -> None:
        if self._error:
            messagebox.showerror("Ошибка распаковки", self._error, parent=self.root)
        self._done.set()
        if self._owns_root:
            self.root.quit()
        else:
            self.root.grab_release()
            self.root.destroy()

    def run(self) -> tuple[bool, Path | None]:
        threading.Thread(target=self._worker, daemon=True).start()
        if self._owns_root:
            self.root.mainloop()
            self.root.destroy()
        else:
            self.root.wait_window()
        return self._error is None, self._out_dir


def extract_with_progress(archive: Path, parent: tk.Misc | None = None) -> int:
    dialog = ExtractProgressDialog(archive, parent=parent)
    ok, _out_dir = dialog.run()
    return 0 if ok else 1
