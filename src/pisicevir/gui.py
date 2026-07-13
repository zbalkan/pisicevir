import sys
import os
import yaml
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QFileDialog, QTextEdit, QLabel, QListWidget, 
                             QProgressBar, QStatusBar, QFrame, QSplitter, QTabWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

from pisicevir.source_adapters.deb import DebAdapter
from pisicevir.analysis.classifier import Classifier
from pisicevir.renderers.generator import RecipeGenerator
from pisicevir.linter.linter import RecipeLinter

class Worker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, action, **kwargs):
        super().__init__()
        self.action = action
        self.kwargs = kwargs

    def run(self):
        try:
            if self.action == "inspect":
                adapter = DebAdapter(self.kwargs["path"])
                result = adapter.inspect()
                self.finished.emit(result)
            elif self.action == "generate":
                generator = RecipeGenerator(
                    self.kwargs["metadata"], 
                    self.kwargs["payload"], 
                    self.kwargs["plan"], 
                    self.kwargs["output"]
                )
                generator.generate()
                self.finished.emit({"status": "success", "path": self.kwargs["output"]})
        except Exception as e:
            self.error.emit(str(e))

class PisicevirGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pisicevir - PISI Recipe Generator")
        self.resize(1000, 700)
        self.setup_ui()
        self.package_info = None
        self.plan = None

    def setup_ui(self):
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header
        header = QLabel("Pisicevir Desktop")
        header.setFont(QFont("Arial", 18, QFont.Bold))
        main_layout.addWidget(header)

        # Splitter for main content
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel: Actions and Package Info
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.btn_open = QPushButton("Open Package (.deb)")
        self.btn_open.setFixedHeight(40)
        self.btn_open.clicked.connect(self.open_package)
        left_layout.addWidget(self.btn_open)

        self.info_label = QLabel("No package loaded")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666;")
        left_layout.addWidget(self.info_label)

        self.list_files = QListWidget()
        left_layout.addWidget(QLabel("Payload Files:"))
        left_layout.addWidget(self.list_files)

        splitter.addWidget(left_panel)

        # Right panel: Tabs for Plan, Recipe, and Logs
        self.tabs = QTabWidget()
        
        # Tab 1: Transformation Plan
        self.plan_text = QTextEdit()
        self.plan_text.setReadOnly(True)
        self.tabs.addTab(self.plan_text, "Transformation Plan")
        
        # Tab 2: Linter Results
        self.linter_text = QTextEdit()
        self.linter_text.setReadOnly(True)
        self.tabs.addTab(self.linter_text, "Linter Report")
        
        splitter.addWidget(self.tabs)
        splitter.setSizes([300, 700])

        # Bottom Actions
        bottom_layout = QHBoxLayout()
        self.btn_generate = QPushButton("Generate Recipe")
        self.btn_generate.setEnabled(False)
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.clicked.connect(self.generate_recipe)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_generate)
        main_layout.addLayout(bottom_layout)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def open_package(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Debian Package", "", "Debian Packages (*.deb)")
        if file_path:
            self.status_bar.showMessage(f"Inspecting {os.path.basename(file_path)}...")
            self.worker = Worker("inspect", path=file_path)
            self.worker.finished.connect(self.on_inspect_finished)
            self.worker.error.connect(self.on_error)
            self.worker.start()

    def on_inspect_finished(self, result):
        self.package_info = result
        metadata = result["metadata"]
        pkg_name = metadata.get("Package", "Unknown")
        version = metadata.get("Version", "Unknown")
        
        self.info_label.setText(f"<b>Package:</b> {pkg_name}<br><b>Version:</b> {version}")
        self.status_bar.showMessage("Inspection complete")
        
        self.list_files.clear()
        for f in result["payload"][:100]: # Limit to first 100 for performance
            self.list_files.addItem(f)
        if len(result["payload"]) > 100:
            self.list_files.addItem(f"... and {len(result['payload']) - 100} more files")

        # Automatically classify and create a plan
        classifier = Classifier(metadata, result["payload"])
        classification = classifier.classify()
        
        self.plan = {
            "source_type": "deb",
            "conversion_class": classification["conversion_class"],
            "policy_family": classification["policy_family"],
            "install": {
                "preserve": [{"source": "usr/share/*", "target": "/usr/share/"}]
            }
        }
        self.plan_text.setText(yaml.dump(self.plan, default_flow_style=False))
        self.btn_generate.setEnabled(True)

    def generate_recipe(self):
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if output_dir:
            pkg_name = self.package_info["metadata"].get("Package", "generated-recipe")
            full_output = os.path.join(output_dir, pkg_name)
            
            self.status_bar.showMessage("Generating recipe...")
            self.worker = Worker("generate", 
                                metadata=self.package_info["metadata"], 
                                payload=self.package_info["payload"],
                                plan=self.plan,
                                output=full_output)
            self.worker.finished.connect(self.on_generate_finished)
            self.worker.error.connect(self.on_error)
            self.worker.start()

    def on_generate_finished(self, result):
        path = result["path"]
        self.status_bar.showMessage(f"Recipe generated at {path}")
        
        # Run linter
        linter = RecipeLinter(path)
        findings = linter.lint()
        
        if not findings:
            self.linter_text.setText("No issues found. The recipe is valid.")
        else:
            report = ""
            for f in findings:
                report += f"[{f['severity']}] {f['code']}: {f['message']}\n"
            self.linter_text.setText(report)
        
        self.tabs.setCurrentIndex(1) # Switch to linter tab

    def on_error(self, message):
        self.status_bar.showMessage(f"Error: {message}")
        self.linter_text.setText(f"An error occurred:\n{message}")

def main():
    app = QApplication(sys.argv)
    
    # Simple KDE-like styling (Breeze theme colors)
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
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
