from __future__ import annotations

import argparse
import os
from pathlib import Path

import psutil


def current_build_process_tree_pids() -> set[int]:
    """Return the build helper PID and its launcher-parent chain.

    On Windows, ``.venv/ Scripts/python.exe`` may start the base interpreter as
    a child process. Those build-helper processes must not be mistaken for a
    separately running Portable Account Browser instance.
    """
    current_pid = os.getpid()
    ignored = {current_pid}
    try:
        ignored.update(parent.pid for parent in psutil.Process(current_pid).parents())
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        pass
    return ignored


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()

    root = str(args.project_root.resolve()).casefold()
    profiles = str((args.project_root / "data" / "profiles").resolve()).casefold()
    ignored_pids = current_build_process_tree_pids()
    found: list[str] = []

    for process in psutil.process_iter(["pid", "name", "cmdline", "exe"]):
        try:
            if process.pid in ignored_pids:
                continue
            name = (process.info.get("name") or "").casefold()
            command = " ".join(process.info.get("cmdline") or []).casefold()
            executable = (process.info.get("exe") or "").casefold()

            is_launcher = name in {
                "python.exe",
                "pythonw.exe",
                "emailportablebrowser.exe",
                "portableaccountbrowser.exe",
            } and (root in command or root in executable)
            is_profile_browser = name in {"chrome.exe", "chromium.exe"} and (
                profiles in command and "--user-data-dir" in command
            )
            if is_launcher or is_profile_browser:
                found.append(f"PID {process.pid}: {process.info.get('name') or 'process'}")
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue

    if found:
        print("ERROR: Close Portable Account Browser and its Chromium window before building.")
        for item in found:
            print(f"- {item}")
        return 1

    print("Application/browser process check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
