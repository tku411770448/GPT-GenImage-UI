from __future__ import annotations

import importlib.util
import sys
import traceback
import faulthandler
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QVBoxLayout, QWidget


_ACTIVE_MODE_WINDOW = None


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


class ModeCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, subtitle: str, accent: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ModeCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(f"""
            QFrame#ModeCard {{
                background: #ffffff;
                border: 1px solid #dbe3ef;
                border-left: 10px solid {accent};
                border-radius: 0px;
            }}
            QFrame#ModeCard:hover {{
                background: #f8fbff;
                border: 2px solid {accent};
                border-left: 12px solid {accent};
            }}
            QLabel#StepText {{
                color: #64748b;
                font-size: 24px;
                font-weight: 800;
            }}
            QLabel#ModeTitle {{
                color: #0f172a;
                font-size: 52px;
                font-weight: 900;
            }}
            QLabel#ModeSubtitle {{
                color: #334155;
                font-size: 22px;
                font-weight: 600;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(48, 48, 48, 48)
        lay.setSpacing(18)
        lay.addStretch(1)
        step = QLabel("Step 0")
        step.setObjectName("StepText")
        step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_title = QLabel(title)
        mode_title.setObjectName("ModeTitle")
        mode_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_title.setWordWrap(True)
        mode_subtitle = QLabel(subtitle)
        mode_subtitle.setObjectName("ModeSubtitle")
        mode_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_subtitle.setWordWrap(True)
        lay.addWidget(step)
        lay.addWidget(mode_title)
        lay.addWidget(mode_subtitle)
        lay.addStretch(1)

    def mousePressEvent(self, event):  # noqa: N802
        if event is None or event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            if event is not None:
                event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ModeSelectorWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GPT GenImage UI - Step 0")
        self.resize(1480, 920)
        self.setMinimumSize(960, 620)
        self._mode_window = None
        self._mode_module = None
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.defect_card = ModeCard("Gen Defect", "接續原 Defect 流程", "#2563eb")
        self.food_card = ModeCard("Gen Food", "接續原 Food 流程", "#16a34a")
        self.defect_card.clicked.connect(lambda: self.open_mode("defect"))
        self.food_card.clicked.connect(lambda: self.open_mode("food"))
        lay.addWidget(self.defect_card, 1)
        lay.addWidget(self.food_card, 1)
        self.setCentralWidget(central)

    def open_mode(self, mode: str) -> None:
        try:
            mode_dir = project_root() / "modes" / mode
            app_path = mode_dir / "ui_gpt_defect" / "app.py"
            if not app_path.exists():
                raise FileNotFoundError(f"Missing mode app: {app_path}")
            module_name = f"genui_{mode}_app"
            spec = importlib.util.spec_from_file_location(module_name, app_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load mode module: {app_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            global _ACTIVE_MODE_WINDOW
            window = module.MainWindow()
            mode_central = window.takeCentralWidget()
            if mode_central is None:
                raise RuntimeError(f"Mode window has no central widget: {mode}")
            self._mode_window = window
            self._mode_module = module
            _ACTIVE_MODE_WINDOW = window
            self.setWindowTitle(window.windowTitle())
            self.setMinimumSize(window.minimumSize())
            self.resize(window.size())
            self.setAcceptDrops(window.acceptDrops())
            self.setCentralWidget(mode_central)
            window.resize(self.size())
            if hasattr(window, "update_sidebar_responsive"):
                window.update_sidebar_responsive()
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.critical(self, "Open mode failed", f"{type(exc).__name__}: {exc}")

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if self._mode_window is not None:
            self._mode_window.resize(self.size())
            if hasattr(self._mode_window, "update_sidebar_responsive"):
                self._mode_window.update_sidebar_responsive()

    def dragEnterEvent(self, event):  # noqa: N802
        if self._mode_window is not None:
            self._mode_window.dragEnterEvent(event)
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        if self._mode_window is not None:
            self._mode_window.dragMoveEvent(event)
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        if self._mode_window is not None:
            self._mode_window.dropEvent(event)
            return
        super().dropEvent(event)


# Backward-compatible alias for tools that import MainWindow from ui_gpt_defect.app.
MainWindow = ModeSelectorWindow


def main() -> None:
    root = project_root()
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        log_dir = ensure_dir(root / "logs")
        crash_log = (log_dir / "ui_crash.log").open("a", encoding="utf-8")
        faulthandler.enable(file=crash_log, all_threads=True)
        app._ui_crash_log = crash_log
    except Exception:
        pass

    def _excepthook(exc_type, exc, tb):
        try:
            log_dir = ensure_dir(root / "logs")
            with (log_dir / "ui_error.log").open("a", encoding="utf-8") as f:
                f.write(f"\n===== {datetime.now().isoformat(timespec='seconds')} | uncaught =====\n")
                traceback.print_exception(exc_type, exc, tb, file=f)
        except Exception:
            pass
        try:
            QMessageBox.critical(None, "UI error", f"{exc_type.__name__}: {exc}")
        except Exception:
            pass

    sys.excepthook = _excepthook
    win = ModeSelectorWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
