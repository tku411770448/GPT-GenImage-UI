#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import traceback
import faulthandler
import re
from datetime import datetime, timedelta
from pathlib import Path

# Do not litter the project tree with __pycache__/.pyc files. Imports performed
# after this line (including the mode apps loaded via importlib) skip bytecode
# caching; spawned generation subprocesses get PYTHONDONTWRITEBYTECODE=1 too.
sys.dont_write_bytecode = True

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget, QWidget
except ImportError as exc:
    msg = str(exc)
    if "PySide6" in msg or "QtCore" in msg or "DLL load failed" in msg:
        print("[ERROR] PySide6/Qt 匯入失敗。")
        print("請確認已在專案 .venv 中安裝 requirements.txt：")
        print(r"  python -m venv .venv")
        print(r"  .\.venv\Scripts\activate   # Windows")
        print(r"  source .venv/bin/activate    # Linux/macOS")
        print(r"  python -m pip install --upgrade pip")
        print(r"  python -m pip install -r requirements.txt")
        print(r"  python launch_ui.py")
        raise SystemExit(1) from exc
    raise

_ACTIVE_MODE_WINDOW = None


def project_root() -> Path:
    # launch_ui.py lives at the repository root, so the root is its own parent.
    return Path(__file__).resolve().parent


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def mode_title(mode: str) -> str:
    return "Gen Defect" if mode == "defect" else "Gen Food"


class UnifiedMainWindow(QMainWindow):
    """Single-window host without the old Step 0 mode-selector page.

    The project manager is now Step 1.  New Project chooses the mode; when the
    selected mode differs from the active workflow this host switches internally
    and immediately creates the project in the correct mode module.
    """

    def __init__(self) -> None:
        super().__init__()
        self.root = project_root()
        self._mode_modules: dict[str, object] = {}
        self._mode_windows: dict[str, QMainWindow] = {}
        self._mode_widgets: dict[str, QWidget] = {}
        self._mode_stack_indexes: dict[str, int] = {}
        self._active_mode: str | None = None
        self._active_mode_window: QMainWindow | None = None
        self.setWindowTitle("GPT GenImage UI")
        self.resize(1480, 920)
        self.setMinimumSize(1120, 740)
        self.setAcceptDrops(True)
        self.root_stack = QStackedWidget()
        self.root_stack.setObjectName("RootStack")
        self.setCentralWidget(self.root_stack)
        default_mode = self._load_last_mode()
        self.open_mode(default_mode)
        # Preload the other workflow before the window is shown, so the first
        # mode switch from New Project does not pay the full module/widget setup cost.
        for mode in ("defect", "food"):
            if mode != default_mode:
                try:
                    self.open_mode(mode)
                except Exception:
                    traceback.print_exc()
        self.open_mode(default_mode)

    def _load_last_mode(self) -> str:
        # Launcher state is no longer persisted (_launcher_state/launcher_state.json removed).
        # The shared Homepage shows both modes' projects regardless of the initial host mode,
        # so always start on the defect workflow.
        return "defect"

    def _load_mode_module(self, mode: str):
        if mode in self._mode_modules:
            return self._mode_modules[mode]
        mode_dir = self.root / "modes" / mode
        # Each mode's UI package follows the ui_gpt_<mode> naming convention
        # (modes/defect/ui_gpt_defect, modes/food/ui_gpt_food).
        app_path = mode_dir / f"ui_gpt_{mode}" / "app.py"
        if not app_path.exists():
            raise FileNotFoundError(f"Missing mode app: {app_path}")
        module_name = f"genui_{mode}_app"
        spec = importlib.util.spec_from_file_location(module_name, app_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load mode module: {app_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        self._mode_modules[mode] = module
        return module

    def _set_active_event_filter(self, window: QMainWindow | None) -> None:
        app = QApplication.instance()
        if app is None:
            return
        for win in self._mode_windows.values():
            try:
                app.removeEventFilter(win)
            except Exception:
                pass
        if window is not None:
            try:
                app.installEventFilter(window)
            except Exception:
                pass

    def open_mode(self, mode: str) -> QMainWindow:
        if mode not in {"defect", "food"}:
            mode = "defect"
        module = self._load_mode_module(mode)
        if mode not in self._mode_widgets:
            window = module.MainWindow()
            window._mode_switch_callback = self.create_project_in_mode
            window._mode_open_callback = self.open_project_in_mode
            window._mode_action_callback = self.project_action_in_mode
            mode_central = window.takeCentralWidget()
            if mode_central is None:
                raise RuntimeError(f"Mode window has no central widget: {mode}")
            mode_central.setParent(None)
            idx = self.root_stack.addWidget(mode_central)
            self._mode_windows[mode] = window
            self._mode_widgets[mode] = mode_central
            self._mode_stack_indexes[mode] = idx
        window = self._mode_windows[mode]
        widget = self._mode_widgets[mode]
        self._active_mode = mode
        self._active_mode_window = window
        global _ACTIVE_MODE_WINDOW
        _ACTIVE_MODE_WINDOW = window
        self._set_active_event_filter(window)
        self.setStyleSheet(window.styleSheet())
        self.setWindowTitle(f"GPT GenImage UI - {mode_title(mode)}")
        try:
            self.setMinimumSize(window.minimumSize())
        except Exception:
            self.setMinimumSize(1120, 740)
        self.root_stack.setCurrentWidget(widget)
        try:
            window.resize(self.size())
            if hasattr(window, "update_sidebar_responsive"):
                window.update_sidebar_responsive()
            if hasattr(window, "refresh_project_list"):
                window.refresh_project_list()
            # The shared OpenAI API key lives in one repo-root .env; re-sync the
            # Homepage field every time a mode is shown so a key saved earlier (or in
            # the other mode) appears as already saved and never needs re-entering.
            if hasattr(window, "refresh_api_placeholder"):
                window.refresh_api_placeholder()
            if hasattr(window, "update_step_buttons"):
                window.update_step_buttons()
        except Exception:
            pass
        return window


    def open_project_in_mode(self, mode: str, project_id: str) -> None:
        """Switch to the requested workflow and open its project from the shared Homepage."""
        try:
            if self._active_mode_window is not None and hasattr(self._active_mode_window, "is_generation_running") and self._active_mode_window.is_generation_running():
                QMessageBox.warning(self, "Generating", "生成圖片期間已鎖定模式切換，請等待完成或停止目前程序。")
                return
        except Exception:
            pass
        window = self.open_mode(mode)
        try:
            window.open_project_by_id(project_id)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.critical(self, "Open project failed", f"{type(exc).__name__}: {exc}")

    def project_action_in_mode(self, action: str, mode: str, project_id: str) -> None:
        """Run a project-card action in its owning mode."""
        window = self.open_mode(mode)
        try:
            if action == "copy":
                window.copy_project_by_id(project_id)
            elif action == "rename":
                window.rename_project_by_id(project_id)
            elif action == "delete":
                window.delete_project_by_id(project_id)
            else:
                window.open_project_by_id(project_id)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.critical(self, "Project action failed", f"{type(exc).__name__}: {exc}")

    def create_project_in_mode(self, mode: str, project_name: str, class_name: str) -> None:
        try:
            if self._active_mode_window is not None and hasattr(self._active_mode_window, "is_generation_running") and self._active_mode_window.is_generation_running():
                QMessageBox.warning(self, "Generating", "生成圖片期間已鎖定模式切換，請等待完成或停止目前程序。")
                return
        except Exception:
            pass
        window = self.open_mode(mode)
        try:
            window.create_project_with_values(project_name, class_name, mode)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.critical(self, "Create project failed", f"{type(exc).__name__}: {exc}")

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        win = self._active_mode_window
        if win is not None:
            try:
                win.resize(self.size())
                if hasattr(win, "update_sidebar_responsive"):
                    win.update_sidebar_responsive()
            except Exception:
                pass

    def dragEnterEvent(self, event):  # noqa: N802
        win = self._active_mode_window
        if win is not None:
            try:
                win.dragEnterEvent(event)
                return
            except Exception:
                pass
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        self.dragEnterEvent(event)

    def dropEvent(self, event):  # noqa: N802
        win = self._active_mode_window
        if win is not None:
            try:
                win.dropEvent(event)
                return
            except Exception:
                pass
        super().dropEvent(event)


MainWindow = UnifiedMainWindow


def prune_old_log(path: Path, max_age: timedelta = timedelta(minutes=10)) -> None:
    """Drop log entries older than `max_age` (full-timestamp, minute/second granularity).

    log.txt is one append-only file whose entries start with a timestamped line such
    as ``[YYYY-MM-DDTHH:MM:SS...]`` or ``===== YYYY-MM-DDTHH:MM:SS... =====`` (a crash
    banner may be followed by un-timestamped traceback lines). Each line inherits the
    keep/drop decision of the most recent timestamped line, so a whole multi-line
    traceback is pruned as a unit. Runs once per launch; safe no-op if the file is
    missing/locked.

    NOTE: the threshold is intentionally short (10 minutes) so the timed deletion can
    be verified quickly during testing; restore a longer age for production.
    """
    try:
        if not path.exists():
            return
        cutoff = datetime.now() - max_age
        line_ts = re.compile(r"^(?:\[|=====\s+)(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
        kept: list[str] = []
        keep_current = True
        for ln in lines:
            md = line_ts.match(ln)
            if md:
                try:
                    keep_current = datetime.fromisoformat(md.group(1)) >= cutoff
                except ValueError:
                    keep_current = True
            if keep_current:
                kept.append(ln)
        if len(kept) != len(lines):
            path.write_text("".join(kept), encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    root = project_root()
    app = QApplication.instance() or QApplication(sys.argv)
    # Single shared log file at the repo root (replaces the old logs/ folder).
    app_log = root / "log.txt"
    # Housekeeping: delete log entries older than 10 minutes on each launch (short
    # threshold for testing the timed deletion; raise it for production use).
    prune_old_log(app_log, max_age=timedelta(minutes=10))
    try:
        crash_log = app_log.open("a", encoding="utf-8")
        faulthandler.enable(file=crash_log, all_threads=True)
        app._ui_crash_log = crash_log
    except Exception:
        pass

    # Record the project startup time so log.txt always shows when each run began.
    try:
        with app_log.open("a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.now().isoformat(timespec='seconds')} | GenUI launched (python {sys.version.split()[0]}, platform {sys.platform}) =====\n")
    except Exception:
        pass

    def _excepthook(exc_type, exc, tb):
        try:
            with app_log.open("a", encoding="utf-8") as f:
                f.write(f"\n===== {datetime.now().isoformat(timespec='seconds')} | uncaught =====\n")
                traceback.print_exception(exc_type, exc, tb, file=f)
        except Exception:
            pass
        try:
            QMessageBox.critical(None, "UI error", f"{exc_type.__name__}: {exc}")
        except Exception:
            pass

    sys.excepthook = _excepthook
    win = UnifiedMainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
