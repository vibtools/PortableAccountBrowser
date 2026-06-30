from __future__ import annotations

import argparse
import sys
import tkinter as tk
from tkinter import messagebox

from epb.app_icon import apply_window_icon
from epb.config import (
    APP_NAME,
    APP_USER_MODEL_ID,
    APP_VERSION,
    ensure_runtime_directories,
)
from epb.database import Database
from epb.diagnostics import collect_diagnostics, report_as_json, report_as_text
from epb.logging_setup import configure_logging
from epb.single_instance import SingleInstance
from epb.windows_ui import set_process_app_user_model_id
from epb.ui import EmailProfileBrowserApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="verify project-local paths, Chromium, SQLite, and portable TEMP settings",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print diagnostics as JSON; valid only with --diagnose",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
    )
    return parser


def _safe_print(text: str, stream) -> None:
    """Write CLI output only when a console stream exists.

    PyInstaller windowed executables set stdout/stderr to None. Diagnostics still
    need to return a reliable process exit code for the release verifier.
    """
    if stream is not None:
        print(text, file=stream)


def run_diagnostics(as_json: bool) -> int:
    report = collect_diagnostics()
    _safe_print(
        report_as_json(report) if as_json else report_as_text(report),
        sys.stdout,
    )
    return 0 if report.passed else 1


def run_gui() -> int:
    ensure_runtime_directories()
    set_process_app_user_model_id(APP_USER_MODEL_ID)
    logger = configure_logging()

    instance = SingleInstance()
    if not instance.acquire():
        root = tk.Tk()
        apply_window_icon(root)
        root.withdraw()
        messagebox.showwarning(APP_NAME, f"{APP_NAME} is already running.")
        root.destroy()
        return 1

    root: tk.Tk | None = None
    try:
        database = Database()
        database.initialize()

        root = tk.Tk()
        apply_window_icon(root)
        EmailProfileBrowserApp(root=root, database=database, logger=logger)
        root.mainloop()
        return 0
    except Exception:
        logger.exception("Fatal application error")
        try:
            error_root = root or tk.Tk()
            apply_window_icon(error_root)
            error_root.withdraw()
            messagebox.showerror(
                APP_NAME,
                "The application could not start. Check data/logs/app.log for details.",
            )
            error_root.destroy()
        except Exception:
            pass
        return 2
    finally:
        instance.release()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.json and not args.diagnose:
        _safe_print("--json must be used with --diagnose", sys.stderr)
        return 2
    if args.diagnose:
        return run_diagnostics(args.json)
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
