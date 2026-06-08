"""Ядро ROCKET Archiver: распаковка и создание ZIP."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Форматы, которые открываем по двойному клику и в GUI.
SUPPORTED_EXTRACT_EXTENSIONS = {
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".tgz",
    ".tbz",
    ".tbz2",
    ".txz",
    ".cab",
    ".iso",
    ".wim",
    ".arj",
    ".lzh",
    ".lz",
    ".z",
    ".cpio",
    ".rpm",
    ".deb",
    ".msi",
    ".dmg",
    ".xar",
    ".pkg",
}

# Составные расширения (проверяем до простого suffix).
COMPOUND_EXTENSIONS = (
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.z",
)


def app_search_roots() -> list[Path]:
    roots: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    roots.append(Path(__file__).resolve().parent)
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _path_executable(path: Path) -> bool:
    if not path.is_file():
        return False
    if sys.platform == "win32" or os.name == "nt":
        return True
    if path.suffix.lower() == ".exe":
        return False
    return os.access(path, os.X_OK)


def find_7z_path() -> str | None:
    tool_names = ["7z.exe", "7z", "7zz.exe", "7zz", "7za.exe", "7za"]
    candidates: list[Path] = []
    for root in app_search_roots():
        for name in tool_names:
            candidates.append(root / "bin" / name)
        for name in tool_names:
            candidates.append(root / name)
            candidates.append(root / "tools" / name)

    for candidate in candidates:
        if _path_executable(candidate):
            return str(candidate.resolve())

    for name in ("7z", "7zz", "7za"):
        system_path = shutil.which(name)
        if system_path:
            return system_path
    return None


def archive_extension(path: Path) -> str | None:
    name_lower = path.name.lower()
    for ext in COMPOUND_EXTENSIONS:
        if name_lower.endswith(ext):
            return ext
    ext = path.suffix.lower()
    if ext in SUPPORTED_EXTRACT_EXTENSIONS:
        return ext
    return None


def is_supported_archive(path: Path | str) -> bool:
    return archive_extension(Path(path)) is not None


def unique_output_dir(parent: Path, base_name: str) -> Path:
    """Папка рядом с архивом; при коллизии — «имя 2», «имя 3» (как на macOS)."""
    candidate = parent / base_name
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = parent / f"{base_name} {index}"
        if not candidate.exists():
            return candidate
        index += 1


def default_extract_dir(archive_path: Path) -> Path:
    archive_path = archive_path.resolve()
    stem = archive_path.stem
    for ext in COMPOUND_EXTENSIONS:
        if archive_path.name.lower().endswith(ext):
            stem = archive_path.name[: -len(ext)]
            break
    return unique_output_dir(archive_path.parent, stem)


def _run_7z_extract(tool_path: str, archive_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        tool_path,
        "x",
        "-y",
        f"-o{target_dir}",
        str(archive_path),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "неизвестная ошибка").strip()
        raise RuntimeError(f"Ошибка распаковки: {err}")


def extract_archive(archive_path: Path | str, target_dir: Path | str | None = None) -> Path:
    archive_path = Path(archive_path).resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Архив не найден: {archive_path}")
    if not is_supported_archive(archive_path):
        raise ValueError(f"Неподдерживаемый формат: {archive_path.name}")

    out_dir = Path(target_dir).resolve() if target_dir else default_extract_dir(archive_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = archive_extension(archive_path)
    if ext == ".zip":
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(out_dir)
        return out_dir

    tool_path = find_7z_path()
    if not tool_path:
        raise RuntimeError(
            "Для этого формата нужен 7-Zip (7z.exe в папке bin или в PATH)."
        )
    _run_7z_extract(tool_path, archive_path, out_dir)
    return out_dir


def create_zip(sources: list[Path | str], output_zip: Path | str) -> Path:
    output_zip = Path(output_zip).resolve()
    if output_zip.suffix.lower() != ".zip":
        output_zip = output_zip.with_suffix(".zip")

    paths = [Path(p).resolve() for p in sources]
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"Не найден: {p}")

    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if len(paths) == 1 and paths[0].is_dir():
            root = paths[0]
            for child in sorted(root.rglob("*")):
                if child.is_file():
                    arc_name = child.relative_to(root)
                    zf.write(child, arcname=str(arc_name).replace("\\", "/"))
        else:
            for path in paths:
                if path.is_dir():
                    for child in sorted(path.rglob("*")):
                        if child.is_file():
                            arc_name = Path(path.name) / child.relative_to(path)
                            zf.write(child, arcname=str(arc_name).replace("\\", "/"))
                else:
                    zf.write(path, arcname=path.name)

    return output_zip


def open_in_explorer(path: Path) -> None:
    path = path.resolve()
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
