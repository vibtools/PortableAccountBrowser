from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

import psutil

WM_CLOSE = 0x0010


def _process_tree(pid: int) -> list[psutil.Process]:
    try:
        root = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []

    processes = [root]
    try:
        processes.extend(root.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return processes


def _post_wm_close(process_ids: set[int]) -> None:
    if os.name != "nt" or not process_ids:
        return

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    user32.EnumWindows.argtypes = [enum_proc_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.PostMessageW.restype = wintypes.BOOL

    @enum_proc_type
    def enum_proc(hwnd: int, _lparam: int) -> bool:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in process_ids and user32.IsWindowVisible(hwnd):
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True

    user32.EnumWindows(enum_proc, 0)


def close_process_tree(pid: int, graceful_timeout: float = 8.0) -> None:
    processes = _process_tree(pid)
    if not processes:
        return

    process_ids = {process.pid for process in processes}
    if os.name == "nt":
        _post_wm_close(process_ids)
    else:
        for process in processes:
            try:
                process.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    _, alive = psutil.wait_procs(processes, timeout=graceful_timeout)
    for process in alive:
        try:
            process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    _, alive = psutil.wait_procs(alive, timeout=3.0)
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def find_portable_chromium_processes(profiles_root: Path) -> list[psutil.Process]:
    root_text = str(profiles_root.resolve()).casefold()
    matches: list[psutil.Process] = []

    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (process.info.get("name") or "").casefold()
            if name not in {"chrome.exe", "chromium.exe", "chrome", "chromium"}:
                continue
            command_line = " ".join(process.info.get("cmdline") or []).casefold()
            if root_text in command_line and "--user-data-dir" in command_line:
                matches.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return matches


def close_orphaned_portable_chromium(profiles_root: Path) -> int:
    matched = find_portable_chromium_processes(profiles_root)
    root_pids: set[int] = set()
    matched_pids = {process.pid for process in matched}

    for process in matched:
        try:
            parent = process.parent()
            if parent is None or parent.pid not in matched_pids:
                root_pids.add(process.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            root_pids.add(process.pid)

    for pid in root_pids:
        close_process_tree(pid)
    return len(root_pids)
