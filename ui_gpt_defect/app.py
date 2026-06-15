from __future__ import annotations

import importlib.util
import sys
import traceback
import faulthandler
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


_ACTIVE_MODE_WINDOW = None


STEP_LABELS = [
    "模式選擇",
    "Homepage",
    "資料上傳",
    "裁切尺寸與圖像裁切",
    "ROI / Target Area",
    "Prompt 編輯",
    "模型參數",
    "Aggregate",
    "執行生成",
    "Export / 輸出",
]


BASE_SELECTOR_QSS = """
    QWidget { font-family: 'Microsoft JhengHei', 'Noto Sans TC', Arial; font-size: 14px; }
    QMainWindow { background: #06111f; }
    #Sidebar { background: #0b1220; border-right: 1px solid #1e293b; }
    #StepScroll, #StepScrollViewport, #StepContainer { background: #0b1220; border: 0px; }
    #StepScroll QScrollBar:vertical { background: #0b1220; width: 8px; margin: 0px; }
    #StepScroll QScrollBar::handle:vertical { background: #334155; border-radius: 4px; min-height: 24px; }
    #StepScroll QScrollBar::add-line:vertical, #StepScroll QScrollBar::sub-line:vertical { height: 0px; background: #0b1220; }
    #AppTitle { color: #e5e7eb; font-size: 24px; font-weight: 800; padding: 8px 0 6px 0 }
    #SideHint { color: #b8d4f5; background: #0f1a2e; padding: 8px; border-radius: 10px; }
    #StatusBox { color: #d1d5db; background: #08101d; border: 1px solid #334155; border-radius: 12px; padding: 10px; }
    #StepButton { text-align: left; padding: 9px 12px; border-radius: 16px; color: #f8fafc; background: #111827; border: 2px solid #334155; margin: 2px 0; outline: none; }
    #StepButton:hover { background: #18283d; border: 2px solid #38bdf8; margin-top: 2px; margin-bottom: 2px; }
    #StepButton[status="locked"] { color: #64748b; background: #111827; border: 2px solid #334155; }
    #StepButton[status="locked"]:hover { color: #64748b; background: #0f172a; border: 2px dashed #ef4444; }
    #StepButton[status="dirty"] { color: #ffffff; background: #3b111d; border: 2px solid #ff477e; }
    #StepButton[status="done"] { color: #ffffff; background: #07351f; border: 2px solid #00f5a0; }
    #StepButton[status="current_dirty"] { color: #ffffff; background: #421323; border: 3px solid #ff3f7f; }
    #StepButton[status="current_done"] { color: #ffffff; background: #0a3d2a; border: 3px solid #00f5a0; }
    #SelectorSurface { background: #f8fafc; border-radius: 20px; }
    #PageScroll { background: transparent; border: 0px; }
    #Header { background: #eef4fb; border-radius: 18px; padding: 8px; }
    #PageTitle { color: #0f172a; font-size: 25px; font-weight: 800; }
    #ModeChoiceCard { background: #ffffff; border: 2px solid #cbd5e1; border-radius: 22px; }
    #ModeChoiceCard:hover { background: #f8fbff; border: 3px solid #2563eb; }
    #ModeStepText { color: #64748b; font-size: 23px; font-weight: 800; }
    #ModeTitle { color: #0f172a; font-size: 52px; font-weight: 900; }
    #ModeSubtitle { color: #334155; font-size: 22px; font-weight: 700; }
    #PrimaryButton { background: #2563eb; color: white; border: 1px solid #1d4ed8; border-radius: 11px; padding: 9px 14px; min-height: 28px; font-weight: 700; }
    #PrimaryButton:hover { background: #1d4ed8; }
"""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def mode_title(mode: str) -> str:
    return "Gen Defect" if mode == "defect" else "Gen Food"


class SidebarStepButton(QPushButton):
    def __init__(self, index: int, title: str, status: str = "locked") -> None:
        super().__init__(f"Step {index}\n{title}")
        self.index = index
        self.setObjectName("StepButton")
        self.setProperty("status", status)
        self.setCheckable(True)
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class ModeCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, subtitle: str, accent: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ModeChoiceCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(520)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"""
            QFrame#ModeChoiceCard {{
                background: #ffffff;
                border: 2px solid #cbd5e1;
                border-left: 12px solid {accent};
                border-radius: 22px;
            }}
            QFrame#ModeChoiceCard:hover {{
                background: #f8fbff;
                border: 3px solid {accent};
                border-left: 14px solid {accent};
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 36, 36, 36)
        lay.setSpacing(18)
        lay.addStretch(1)
        step = QLabel("Step 0")
        step.setObjectName("ModeStepText")
        step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title)
        title_label.setObjectName("ModeTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("ModeSubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setWordWrap(True)
        lay.addWidget(step)
        lay.addWidget(title_label)
        lay.addWidget(subtitle_label)
        lay.addStretch(1)
        enter_btn = QPushButton("進入此模式")
        enter_btn.setObjectName("PrimaryButton")
        enter_btn.setMinimumHeight(54)
        enter_btn.clicked.connect(self.clicked.emit)
        lay.addWidget(enter_btn)

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


class UnifiedMainWindow(QMainWindow):
    """Single-window entry point that keeps Step 0 and mode workflows together.

    The previous merge used a standalone mode-selection window and then opened or
    transplanted a second MainWindow.  This shell keeps one QMainWindow for the
    whole lifetime of the app.  Step 0 is a normal page in the root stack; each
    selected mode is loaded as another root-stack page and keeps its original
    internal workflow/sidebar untouched.
    """

    def __init__(self) -> None:
        super().__init__()
        self.root = project_root()
        self._mode_modules: dict[str, object] = {}
        self._mode_windows: dict[str, QMainWindow] = {}
        self._mode_widgets: dict[str, QWidget] = {}
        self._mode_stack_indexes: dict[str, int] = {}
        self._active_mode: str | None = None
        self._active_mode_window = None
        self.setWindowTitle("GPT GenImage UI")
        self.resize(1480, 920)
        self.setMinimumSize(1120, 740)
        self.setAcceptDrops(True)

        self.root_stack = QStackedWidget()
        self.root_stack.setObjectName("RootStack")
        self.selector_page = self._build_selector_page()
        self.root_stack.addWidget(self.selector_page)
        self.setCentralWidget(self.root_stack)
        self._apply_selector_style()

    # ---------- Step 0 selector UI ----------
    def _build_selector_page(self) -> QWidget:
        central = QWidget()
        main = QHBoxLayout(central)
        main.setContentsMargins(14, 14, 14, 14)
        main.setSpacing(14)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(240)
        sidebar.setMaximumWidth(340)
        side_lay = QVBoxLayout(sidebar)
        side_lay.setContentsMargins(16, 16, 16, 16)
        side_lay.setSpacing(10)
        title = QLabel("GPT GenImage UI")
        title.setObjectName("AppTitle")
        side_lay.addWidget(title)
        hint = QLabel("Step 0 選擇生成模式；選定後在同一個視窗接續 Step 1～9。")
        hint.setObjectName("SideHint")
        hint.setWordWrap(True)
        side_lay.addWidget(hint)

        step_container = QWidget()
        step_container.setObjectName("StepContainer")
        step_container.setAutoFillBackground(False)
        step_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        step_lay = QVBoxLayout(step_container)
        step_lay.setContentsMargins(0, 0, 0, 0)
        step_lay.setSpacing(9)
        for idx, label in enumerate(STEP_LABELS):
            status = "current_done" if idx == 0 else "locked"
            btn = SidebarStepButton(idx, label, status=status)
            btn.setChecked(idx == 0)
            if idx == 0:
                btn.clicked.connect(self.show_selector)
            else:
                btn.clicked.connect(lambda checked=False, i=idx: self._warn_select_mode_first(i))
            step_lay.addWidget(btn)
        step_lay.addStretch(1)

        step_scroll = QScrollArea()
        step_scroll.setObjectName("StepScroll")
        step_scroll.setWidgetResizable(True)
        step_scroll.setFrameShape(QFrame.Shape.NoFrame)
        step_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        step_scroll.viewport().setObjectName("StepScrollViewport")
        step_scroll.viewport().setAutoFillBackground(False)
        step_scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        step_scroll.setWidget(step_container)
        side_lay.addWidget(step_scroll, 1)
        status = QLabel("Status: 等待選擇模式")
        status.setObjectName("StatusBox")
        status.setWordWrap(True)
        side_lay.addWidget(status)
        main.addWidget(sidebar, 0)

        surface = QWidget()
        surface.setObjectName("SelectorSurface")
        surface_lay = QVBoxLayout(surface)
        surface_lay.setContentsMargins(16, 16, 16, 16)
        surface_lay.setSpacing(12)

        header = QFrame()
        header.setObjectName("Header")
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(14, 12, 14, 12)
        page_title = QLabel("Step 0｜模式選擇")
        page_title.setObjectName("PageTitle")
        header_lay.addWidget(page_title)
        surface_lay.addWidget(header)

        cards = QWidget()
        cards_lay = QHBoxLayout(cards)
        cards_lay.setContentsMargins(0, 0, 0, 0)
        cards_lay.setSpacing(14)
        defect_card = ModeCard("Gen Defect", "接續原 Defect 流程", "#2563eb")
        food_card = ModeCard("Gen Food", "接續原 Food 流程", "#16a34a")
        defect_card.clicked.connect(lambda: self.open_mode("defect"))
        food_card.clicked.connect(lambda: self.open_mode("food"))
        cards_lay.addWidget(defect_card, 1)
        cards_lay.addWidget(food_card, 1)
        surface_lay.addWidget(cards, 1)
        main.addWidget(surface, 1)
        return central

    def _apply_selector_style(self) -> None:
        self.setStyleSheet(BASE_SELECTOR_QSS)

    def _warn_select_mode_first(self, step_index: int) -> None:
        QMessageBox.information(self, "尚未選擇模式", f"請先在 Step 0 選擇 Gen Defect 或 Gen Food，再接續 Step {step_index}。")

    # ---------- mode loading / integration ----------
    def _load_mode_module(self, mode: str):
        if mode in self._mode_modules:
            return self._mode_modules[mode]
        mode_dir = self.root / "modes" / mode
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
        self._mode_modules[mode] = module
        return module

    def _append_outer_styles(self, mode_stylesheet: str) -> str:
        # Keep selector-only widgets styled even after applying a mode's original
        # stylesheet to the single outer QMainWindow.
        return (mode_stylesheet or "") + "\n" + BASE_SELECTOR_QSS

    def _make_return_step_button(self, module) -> QPushButton:
        try:
            btn = module.StepButton(0, "模式選擇")
        except Exception:
            btn = SidebarStepButton(0, "模式選擇", status="done")
        btn.setObjectName("StepButton")
        btn.setText("Step 0\n模式選擇")
        btn.setCheckable(True)
        btn.setChecked(False)
        btn.setProperty("status", "done")
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        try:
            btn.setMinimumHeight(64)
            btn.setMaximumHeight(64)
        except Exception:
            pass
        btn.clicked.connect(self.show_selector)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        return btn

    def _install_mode_step0_button(self, mode: str, window: QMainWindow, module) -> None:
        if getattr(window, "_genui_outer_step0_installed", False):
            return
        step_layout = getattr(window, "step_layout", None)
        if step_layout is None:
            return
        btn = self._make_return_step_button(module)
        step_layout.insertWidget(0, btn)
        window._genui_outer_step0_installed = True
        window._genui_outer_step0_button = btn

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

    def open_mode(self, mode: str) -> None:
        try:
            if mode not in {"defect", "food"}:
                raise ValueError(f"Unknown mode: {mode}")
            module = self._load_mode_module(mode)
            if mode not in self._mode_widgets:
                window = module.MainWindow()
                mode_central = window.takeCentralWidget()
                if mode_central is None:
                    raise RuntimeError(f"Mode window has no central widget: {mode}")
                mode_central.setParent(None)
                self._install_mode_step0_button(mode, window, module)
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
            self.setStyleSheet(self._append_outer_styles(window.styleSheet()))
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
                if hasattr(window, "update_step_buttons"):
                    window.update_step_buttons()
            except Exception:
                pass
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.critical(self, "Open mode failed", f"{type(exc).__name__}: {exc}")

    def show_selector(self) -> None:
        win = self._active_mode_window
        try:
            if win is not None and hasattr(win, "is_generation_running") and win.is_generation_running():
                QMessageBox.warning(self, "Generating", "生成圖片期間已鎖定模式切換，請等待完成或停止目前程序。")
                return
        except Exception:
            pass
        self._active_mode = None
        self._active_mode_window = None
        self._set_active_event_filter(None)
        self.setWindowTitle("GPT GenImage UI")
        self.setMinimumSize(1120, 740)
        self._apply_selector_style()
        self.root_stack.setCurrentWidget(self.selector_page)

    # ---------- event forwarding ----------
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
        win = self._active_mode_window
        if win is not None:
            try:
                win.dragMoveEvent(event)
                return
            except Exception:
                pass
        super().dragMoveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        win = self._active_mode_window
        if win is not None:
            try:
                win.dropEvent(event)
                return
            except Exception:
                pass
        super().dropEvent(event)


# Backward-compatible alias for tools that import MainWindow from ui_gpt_defect.app.
MainWindow = UnifiedMainWindow


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
    win = UnifiedMainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
