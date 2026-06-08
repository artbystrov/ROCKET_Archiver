"""Регистрация ассоциаций файлов в Windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import winreg

from archiver_core import SUPPORTED_EXTRACT_EXTENSIONS

PROG_ID = "ROCKETArchiver"
APP_NAME = "ROCKET Archiver"
DESCRIPTION = "ROCKET Archiver — распаковка архивов как на macOS"


def _exe_path() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    return str(Path(sys.argv[0]).resolve())


def _set_key(root, sub_key: str, value_name: str | None, value, value_type=winreg.REG_SZ):
    key = winreg.CreateKey(root, sub_key)
    try:
        if value_name is None:
            winreg.SetValue(key, "", value_type, value)
        else:
            winreg.SetValueEx(key, value_name, 0, value_type, value)
    finally:
        winreg.CloseKey(key)


def register_associations() -> list[str]:
    if sys.platform != "win32":
        raise OSError("Ассоциации поддерживаются только в Windows.")

    exe = _exe_path()
    command = f'"{exe}" "%1"'
    registered: list[str] = []

    _set_key(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{PROG_ID}", None, PROG_ID)
    _set_key(
        winreg.HKEY_CURRENT_USER,
        f"Software\\Classes\\{PROG_ID}",
        "FriendlyAppName",
        APP_NAME,
    )
    _set_key(
        winreg.HKEY_CURRENT_USER,
        f"Software\\Classes\\{PROG_ID}\\DefaultIcon",
        None,
        f'"{exe}",0',
    )
    _set_key(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{PROG_ID}\\shell\\open", None, "Открыть")
    _set_key(
        winreg.HKEY_CURRENT_USER,
        f"Software\\Classes\\{PROG_ID}\\shell\\open\\command",
        None,
        command,
    )

    for ext in sorted(SUPPORTED_EXTRACT_EXTENSIONS):
        _set_key(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}", None, PROG_ID)
        registered.append(ext)

    return registered


def unregister_associations() -> list[str]:
    if sys.platform != "win32":
        raise OSError("Ассоциации поддерживаются только в Windows.")

    removed: list[str] = []
    for ext in sorted(SUPPORTED_EXTRACT_EXTENSIONS):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}") as key:
                prog_id, _ = winreg.QueryValueEx(key, "")
            if prog_id == PROG_ID:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}")
                removed.append(ext)
        except OSError:
            continue

    try:
        winreg.DeleteKey(
            winreg.HKEY_CURRENT_USER,
            f"Software\\Classes\\{PROG_ID}\\DefaultIcon",
        )
    except OSError:
        pass
    try:
        winreg.DeleteKey(
            winreg.HKEY_CURRENT_USER,
            f"Software\\Classes\\{PROG_ID}\\shell\\open\\command",
        )
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{PROG_ID}\\shell\\open")
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{PROG_ID}\\shell")
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{PROG_ID}")
    except OSError:
        pass

    return removed


def open_default_apps_settings() -> None:
    if sys.platform != "win32":
        return
    os.startfile("ms-settings:defaultapps")  # type: ignore[attr-defined]


def association_status() -> dict[str, str | bool]:
    if sys.platform != "win32":
        return {"platform": sys.platform, "supported": False}

    linked = 0
    for ext in SUPPORTED_EXTRACT_EXTENSIONS:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}") as key:
                prog_id, _ = winreg.QueryValueEx(key, "")
            if prog_id == PROG_ID:
                linked += 1
        except OSError:
            continue

    total = len(SUPPORTED_EXTRACT_EXTENSIONS)
    return {
        "supported": True,
        "prog_id": PROG_ID,
        "exe": _exe_path(),
        "linked_extensions": linked,
        "total_extensions": total,
        "fully_registered": linked == total,
    }
