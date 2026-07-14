from __future__ import annotations

import os
import sys
import traceback
from importlib import resources
from typing import Any, Dict

import yaml
from PyQt5.QtCore import QThread, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices, QFont, QIcon, QPalette, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pisicevir import __version__
from pisicevir.analysis.classifier import Classifier
from pisicevir.analysis.planning import create_initial_plan
from pisicevir.linter.linter import RecipeLinter
from pisicevir.renderers.generator import RecipeGenerator
from pisicevir.source_adapters.deb import DebAdapter


class Worker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, action: str, **kwargs: Any):
        super().__init__()
        self.action = action
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            if self.action == "inspect":
                result = DebAdapter(self.kwargs["path"]).inspect()
                self.finished.emit(result)
                return
            if self.action == "generate":
                generator = RecipeGenerator(
                    self.kwargs["source_path"],
                    self.kwargs["inspection"],
                    self.kwargs["plan"],
                    self.kwargs["output"],
                )
                path = generator.generate()
                self.finished.emit({"status": "success", "path": path})
                return
            raise ValueError(f"Unknown worker action: {self.action}")
        except Exception:
            self.error.emit(traceback.format_exc())


class PisicevirGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pisicevir - PISI Recipe Generator")
        self.resize(1000, 700)
        self.package_info: Dict[str, Any] | None = None
        self.package_path: str | None = None
        self.worker: Worker | None = None
        self.setup_ui()

    def setup_about_menu(self) -> None:
        help_menu = self.menuBar().addMenu("&Help")

        about_pisicevir_action = QAction("About pisicevir", self)
        about_pisicevir_action.setStatusTip("About pisicevir and its GitHub project")
        about_pisicevir_action.triggered.connect(self.show_about_pisicevir)
        help_menu.addAction(about_pisicevir_action)

        about_pisi_action = QAction("About PISI Linux", self)
        about_pisi_action.setStatusTip("About PISI Linux and its website")
        about_pisi_action.triggered.connect(self.show_about_pisi_linux)
        help_menu.addAction(about_pisi_action)

    def setup_ui(self) -> None:
        self.setup_about_menu()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        logo_path = resources.files("pisicevir").joinpath("assets", "logo.png")
        logo_pixmap = QPixmap(str(logo_path))
        if not logo_pixmap.isNull():
            self.setWindowIcon(QIcon(logo_pixmap))

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        logo_label = QLabel()
        logo_label.setFixedSize(48, 48)
        logo_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setToolTip("Pisi Linux")
        if not logo_pixmap.isNull():
            logo_label.setPixmap(
                logo_pixmap.scaled(
                    48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        header_layout.addWidget(logo_label)

        header = QLabel("Pisicevir Desktop")
        header.setFont(QFont("Sans Serif", 18, QFont.Bold))
        header.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(header, 1)
        main_layout.addLayout(header_layout, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        self.btn_open = QPushButton("Open Package (.deb)")
        self.btn_open.setFixedHeight(40)
        self.btn_open.clicked.connect(self.open_package)
        left_layout.addWidget(self.btn_open)

        self.info_label = QLabel("No package loaded")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666;")
        left_layout.addWidget(self.info_label)

        self.list_files = QListWidget()
        payload_label = QLabel("Payload entries:")
        payload_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        left_layout.addWidget(payload_label)
        left_layout.addWidget(self.list_files, 1)
        splitter.addWidget(left_panel)

        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plan_text = QTextEdit()
        self.plan_text.setReadOnly(False)
        self.tabs.addTab(self.plan_text, "Transformation Plan")
        self.linter_text = QTextEdit()
        self.linter_text.setReadOnly(True)
        self.tabs.addTab(self.linter_text, "Linter Report")
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 700])

        bottom_layout = QHBoxLayout()
        self.btn_generate = QPushButton("Generate Reviewed Recipe")
        self.btn_generate.setEnabled(False)
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.clicked.connect(self.generate_recipe)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_generate)
        main_layout.addLayout(bottom_layout)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def open_package(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Debian Package", "", "Debian Packages (*.deb)"
        )
        if not file_path:
            return
        self.package_path = file_path
        self.btn_generate.setEnabled(False)
        self.status_bar.showMessage(f"Inspecting {os.path.basename(file_path)}...")
        self.worker = Worker("inspect", path=file_path)
        self.worker.finished.connect(self.on_inspect_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_inspect_finished(self, result: Dict[str, Any]) -> None:
        self.package_info = result
        metadata = result["metadata"]
        classification = Classifier(
            metadata, result["payload"], result["maintainer_scripts"]
        ).classify()

        dependency_count = sum(len(groups) for groups in result["dependencies"].values())
        self.info_label.setText(
            f"<b>Package:</b> {metadata['Package']}<br>"
            f"<b>Version:</b> {metadata['Version']}<br>"
            f"<b>Class:</b> {classification['conversion_class']}<br>"
            f"<b>Policy:</b> {classification['policy_family']}<br>"
            f"<b>Dependency groups:</b> {dependency_count}"
        )
        self.list_files.clear()
        for entry in result["payload"][:100]:
            self.list_files.addItem(f"{entry['kind']}: {entry['path']}")
        if len(result["payload"]) > 100:
            self.list_files.addItem(f"... and {len(result['payload']) - 100} more entries")

        plan = create_initial_plan(result, classification)
        self.plan_text.setPlainText(yaml.safe_dump(plan, sort_keys=False))
        self.btn_generate.setEnabled(True)
        self.status_bar.showMessage(
            "Inspection complete. Map dependencies, review payload decisions, and set approved: true."
        )

    def generate_recipe(self) -> None:
        if self.package_info is None or self.package_path is None:
            return
        try:
            plan = yaml.safe_load(self.plan_text.toPlainText())
            if not isinstance(plan, dict):
                raise ValueError("Transformation plan must be a YAML mapping")
        except Exception as exc:
            self.on_error(f"Invalid transformation plan:\n{exc}")
            return

        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return
        package_name = self.package_info["metadata"].get("Package", "generated-recipe")
        full_output = os.path.join(output_dir, package_name)
        self.status_bar.showMessage("Generating reviewed recipe...")
        self.worker = Worker(
            "generate",
            source_path=self.package_path,
            inspection=self.package_info,
            plan=plan,
            output=full_output,
        )
        self.worker.finished.connect(self.on_generate_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_generate_finished(self, result: Dict[str, Any]) -> None:
        path = result["path"]
        findings = RecipeLinter(path).lint()
        if not findings:
            self.linter_text.setPlainText(
                "No implemented lint checks reported an issue. Build validation is still required."
            )
        else:
            self.linter_text.setPlainText(
                "\n".join(
                    f"[{finding['severity']}] {finding['code']}: {finding['message']}"
                    for finding in findings
                )
            )
        self.tabs.setCurrentIndex(1)
        self.status_bar.showMessage(f"Recipe generated at {path}")

    def on_error(self, message: str) -> None:
        self.status_bar.showMessage("Operation failed")
        self.linter_text.setPlainText(message)
        self.tabs.setCurrentIndex(1)

    def show_about_dialog(
        self, title: str, html: str, link_url: str, link_button_text: str
    ) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setTextFormat(Qt.RichText)
        dialog.setTextInteractionFlags(Qt.TextBrowserInteraction)
        dialog.setText(html)
        link_button = dialog.addButton(link_button_text, QMessageBox.ActionRole)
        dialog.addButton(QMessageBox.Ok)

        dialog.exec_()
        if dialog.clickedButton() is link_button:
            QDesktopServices.openUrl(QUrl(link_url))

    def show_about_pisicevir(self) -> None:
        self.show_about_dialog(
            "About pisicevir",
            f"""
            <h2>pisicevir {__version__}</h2>
            <p>Policy-driven external package importer and native PISI recipe generator.</p>
            <p>Project page: <a href="https://github.com/zbalkan/pisicevir">github.com/zbalkan/pisicevir</a></p>
            """,
            "https://github.com/zbalkan/pisicevir",
            "Open GitHub",
        )

    def show_about_pisi_linux(self) -> None:
        self.show_about_dialog(
            "About PISI Linux",
            """
            <h2>PISI Linux</h2>
            <p>PISI Linux is an independent GNU/Linux distribution using PISI packages.</p>
            <p>Website: <a href="https://pisilinux.org">pisilinux.org</a></p>
            """,
            "https://pisilinux.org",
            "Open Website",
        )


def main() -> int:
    app = QApplication(sys.argv)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(239, 240, 241))
    palette.setColor(QPalette.WindowText, QColor(49, 54, 59))
    palette.setColor(QPalette.Base, QColor(252, 252, 252))
    palette.setColor(QPalette.AlternateBase, QColor(239, 240, 241))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, QColor(49, 54, 59))
    palette.setColor(QPalette.Text, QColor(49, 54, 59))
    palette.setColor(QPalette.Button, QColor(239, 240, 241))
    palette.setColor(QPalette.ButtonText, QColor(49, 54, 59))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(41, 128, 185))
    palette.setColor(QPalette.Highlight, QColor(61, 174, 233))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(palette)

    window = PisicevirGUI()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
