import json
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QTreeWidget, QTreeWidgetItem,
                             QListWidgetItem, QLabel, QPushButton, QSplitter, QFileDialog, QSizePolicy, QTextEdit,
                             QFormLayout, QLineEdit, QSpinBox, QMenu, QCheckBox)
from PySide6.QtGui import QDrag, QDesktopServices, QIcon
from PySide6.QtCore import Qt, QMimeData, QUrl, QTimer

from core.catalog import ui_objects, ui_object_instance
from core.engine_integration import EngineIntegration
from core.project_manager import ProjectManager
from core.ui_generator import DEFAULT_UI_SETTINGS, UI_SETTINGS_FILE, load_ui_settings, save_ui_settings
from ui.settings_dialog import SettingsDialog
from ui.canvas import Canvas
from ui.concept_tree import ConceptTree
from utils.ontology import Ontology

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"

class RunDialog(QDialog):
    """Asks where the generated API and UI should run."""
    def __init__(self, parent=None, api_host="127.0.0.1", api_port=5000, ui_host="127.0.0.1", ui_port=3000):
        super().__init__(parent)
        self.setWindowTitle("Run")
        form = QFormLayout(self)
        self.api_host = QLineEdit(api_host)
        self.api_port = QSpinBox()
        self.api_port.setRange(1, 65535)
        self.api_port.setValue(api_port)
        self.ui_host = QLineEdit(ui_host)
        self.ui_port = QSpinBox()
        self.ui_port.setRange(1, 65535)
        self.ui_port.setValue(ui_port)
        form.addRow("API IP:", self.api_host)
        form.addRow("API port:", self.api_port)
        form.addRow("UI IP:", self.ui_host)
        form.addRow("UI port:", self.ui_port)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return dict(api_host=self.api_host.text().strip() or "127.0.0.1", api_port=self.api_port.value(),
                    ui_host=self.ui_host.text().strip() or "127.0.0.1", ui_port=self.ui_port.value())


class UISettingsDialog(QDialog):
    """Edits the texts and layout of the generated web UI (saved in the project's ui_config.json)."""
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("UI Config")
        self.resize(420, 0)
        form = QFormLayout(self)
        self.title = QLineEdit()
        self.footer = QLineEdit()
        self.pipelines = QLineEdit()
        self.models = QLineEdit()
        self.header_height = self._spin(16, 400)
        self.header_fixed = QCheckBox("Fixed")
        self.sidebar_width = self._spin(100, 800)
        self.footer_height = self._spin(16, 400)
        self.footer_fixed = QCheckBox("Fixed")
        self.padding = self._spin(0, 200)
        form.addRow("Header title:", self.title)
        form.addRow("Header height (px):", self.header_height)
        form.addRow("", self.header_fixed)
        form.addRow("Sidebar group for pipelines:", self.pipelines)
        form.addRow("Sidebar group for business models:", self.models)
        form.addRow("Sidebar width (px):", self.sidebar_width)
        form.addRow("Footer text:", self.footer)
        form.addRow("Footer height (px):", self.footer_height)
        form.addRow("", self.footer_fixed)
        form.addRow("Content padding (px):", self.padding)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(lambda: self._fill(DEFAULT_UI_SETTINGS))
        form.addRow(buttons)
        self._fill(settings)

    @staticmethod
    def _spin(low: int, high: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        return spin

    def _fill(self, s: dict):
        self.title.setText(s["title"])
        self.footer.setText(s["footer"])
        self.pipelines.setText(s["groups"]["pipelines"])
        self.models.setText(s["groups"]["models"])
        self.header_height.setValue(s["header"]["height"])
        self.header_fixed.setChecked(s["header"]["fixed"])
        self.sidebar_width.setValue(s["sidebar"]["width"])
        self.footer_height.setValue(s["footerBar"]["height"])
        self.footer_fixed.setChecked(s["footerBar"]["fixed"])
        self.padding.setValue(s["contentPadding"])

    def values(self) -> dict:
        d = DEFAULT_UI_SETTINGS  # an emptied text falls back to its default
        return {"title": self.title.text().strip() or d["title"],
                "footer": self.footer.text().strip() or d["footer"],
                "groups": {"pipelines": self.pipelines.text().strip() or d["groups"]["pipelines"],
                           "models": self.models.text().strip() or d["groups"]["models"]},
                "header": {"height": self.header_height.value(), "fixed": self.header_fixed.isChecked()},
                "sidebar": {"width": self.sidebar_width.value()},
                "footerBar": {"height": self.footer_height.value(), "fixed": self.footer_fixed.isChecked()},
                "contentPadding": self.padding.value()}


class UserPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.layout = QVBoxLayout(self)

        self.project_manager = ProjectManager()
        self.engine_integration = EngineIntegration()
        self.concepts = Ontology()
        self.ui_objects = ui_objects()  # the same objects in every project: graph, table, text and image
        self.run_settings = dict(api_host="127.0.0.1", api_port=5000, ui_host="127.0.0.1", ui_port=3000)
        
        # Toolbar for Project Operations
        self.toolbar = QHBoxLayout()
        self.btn_project = QPushButton("Project")  # a push button with a menu, so it gets the same style as Help/Settings
        project_menu = QMenu(self.btn_project)
        self.act_new = project_menu.addAction(QIcon(str(ASSETS_DIR / "new-project.png")), "New Project")
        self.act_save = project_menu.addAction(QIcon(str(ASSETS_DIR / "save-project.png")), "Save Project")
        self.act_load = project_menu.addAction(QIcon(str(ASSETS_DIR / "load-project.png")), "Load Project")
        self.btn_project.setMenu(project_menu)
        self.btn_settings = QPushButton("Settings")
        self.btn_help = QPushButton("Help")
        self.btn_load_concepts = QPushButton("Load Concept Package")

        self.btn_ui_settings = QPushButton("UI Config")
        self.btn_ui_settings.setToolTip("Header title, footer text, sidebar group names and sizes of the generated web UI")
        
        self.btn_run = QPushButton("RUN")
        self._set_run_button(False)
        # Detects the API process ending by itself so the button goes back to RUN
        self.run_watch = QTimer(self)
        self.run_watch.timeout.connect(lambda: self._set_run_button(self.engine_integration.is_running()))
        self.run_watch.start(1000)
        
        self.toolbar.addWidget(self.btn_project)
        self.toolbar.addWidget(self.btn_help)
        self.toolbar.addWidget(self.btn_settings)
        self.toolbar.addStretch()
        self.toolbar.addWidget(self.btn_ui_settings)
        self.toolbar.addWidget(self.btn_run)
        
        self.layout.addLayout(self.toolbar)
        
        # Main splitter for toolbox/canvas and output console
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.layout.addWidget(self.main_splitter)

        # Top part: Splitter for Concept Toolbox and Canvas
        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Toolbox
        self.toolbox_container = QWidget()
        self.toolbox_layout = QVBoxLayout(self.toolbox_container)
        self.toolbox_layout.addWidget(QLabel("Concepts"))
        self.toolbox_layout.addWidget(self.btn_load_concepts)
        self.toolbox = ConceptTree()
        self.toolbox_layout.addWidget(self.toolbox)
        self.btn_remove_concepts = QPushButton("Remove Selected Package")
        self.btn_remove_concepts.setToolTip("Removes the package or folder selected in the tree from the project")
        self.toolbox_layout.addWidget(self.btn_remove_concepts)
        self.toolbox_layout.addWidget(QLabel("UI Objects"))
        self.ui_toolbox = ConceptTree()  # below the concepts: they belong to the platform, not to the project
        self.ui_toolbox.add_flat_tree("Show an output as", {c.name: key for key, c in self.ui_objects.items()})
        self.ui_toolbox.setMaximumHeight(165)
        self.toolbox_layout.addWidget(self.ui_toolbox)
        self.toolbox_container.setMinimumWidth(250)
        
        self.top_splitter.addWidget(self.toolbox_container)
        
        # Right side: Canvas
        self.canvas = Canvas(concept_lookup=self.find_concept)
        self.canvas.business_models_changed.connect(self._on_business_models_changed)
        # The canvas position goes to session.json shortly after the user stops moving it
        self._restoring_view = False
        self.view_save_timer = QTimer(self)
        self.view_save_timer.setSingleShot(True)
        self.view_save_timer.setInterval(500)
        self.view_save_timer.timeout.connect(lambda: self.project_manager.save_canvas_view(*self.canvas.view_position()))
        self.canvas.view_moved.connect(lambda *_: None if self._restoring_view else self.view_save_timer.start())
        self.top_splitter.addWidget(self.canvas)
        
        self.top_splitter.setStretchFactor(0, 1)
        self.top_splitter.setStretchFactor(1, 4)

        self.main_splitter.addWidget(self.top_splitter)

        # Bottom part: Output Console
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        self.output_console.setMinimumHeight(150)
        self.output_console.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        self.main_splitter.addWidget(self.output_console)
        
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)
        
        # Connect Project Management buttons
        self.act_new.triggered.connect(self.new_project)
        self.act_save.triggered.connect(self.save_project)
        self.act_load.triggered.connect(self.load_project)
        self.btn_help.clicked.connect(self.open_help)
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_ui_settings.clicked.connect(self.open_ui_settings)
        
        # Connect Run button
        self.btn_run.clicked.connect(self.run_engines)

        self.btn_remove_concepts.clicked.connect(self.remove_selected_concepts)
        self.toolbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.toolbox.customContextMenuRequested.connect(self._toolbox_menu)

        # Connect Concept button 
        self.btn_load_concepts.clicked.connect(self.load_concepts)
        
        # Load session project
        has_loaded_successfully, res = self.project_manager.load_session()
        if has_loaded_successfully & (res != ""):
            self.main_window.title_label.setText(f"PlatformBuilder - {res}")
            self.output_console.insertPlainText(f"Project ({res}) was loaded successfully.\n")
            self._restore_project()
        elif not has_loaded_successfully:
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Error in creating a new project!")
            dlg.setText(res)
            btn = dlg.exec()
            if btn == QMessageBox.Ok: dlg.close()

    def new_project(self):
        dir_path = QFileDialog.getExistingDirectory(
            parent=None, 
            caption="New Project", 
            dir="",
            options=QFileDialog.Option.ShowDirsOnly
        )
        if dir_path:
            has_created_successfully, res = self.project_manager.new_project(dir_path)
            if has_created_successfully:
                self.main_window.title_label.setText(f"PlatformBuilder - {res}")
                self.output_console.insertPlainText(f"New project created ({res})!\n")
                self._restoring_view = True
                self.view_save_timer.stop()
                self.canvas.clear_canvas()
                self.canvas.set_view_position(0, 0)
                self.concepts.clear()
                self.toolbox.clear()
                QTimer.singleShot(0, lambda: setattr(self, "_restoring_view", False))
            else:
                dlg = QMessageBox(self)
                dlg.setWindowTitle("Error in creating a new project!")
                dlg.setText(res)
                btn = dlg.exec()
                if btn == QMessageBox.Ok: dlg.close()

    def save_project(self):
        has_saved_successfully, res = self.project_manager.save_project(*self.canvas.serialize())
        if has_saved_successfully:
            self.output_console.insertPlainText(f"Project ({self.project_manager.get_proj_name()}) was saved!\n")
        else:
            dlg = QMessageBox(self)
            dlg.setWindowTitle(f"Error in saving the ({self.project_manager.get_proj_name()}) project!")
            dlg.setText(res)
            btn = dlg.exec()
            if btn == QMessageBox.Ok: dlg.close()

    def load_project(self):
        pbproj_path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "PlatformBuilder Project (*.pbproj)")
        if pbproj_path:
            has_loaded_successfully, res = self.project_manager.load_project(pbproj_path)
            if has_loaded_successfully:
                self.main_window.title_label.setText(f"PlatformBuilder - {res}")
                self.output_console.insertPlainText(f"Project ({self.project_manager.get_proj_name()}) was loaded successfully!\n")
                self._restore_project()
            else:
                dlg = QMessageBox(self)
                dlg.setWindowTitle("Error in loading the project!")
                dlg.setText(res)
                btn = dlg.exec()
                if btn == QMessageBox.Ok: dlg.close()

    def _show_error(self, title: str, text: str):
        dlg = QMessageBox(self)
        dlg.setWindowTitle(title)
        dlg.setText(text)
        dlg.exec()

    def _on_business_models_changed(self, business_models: list):
        matching = sum(1 for bm in business_models if bm.links)  # concepts wired together form a pipeline
        if hasattr(self.main_window, "status_bar"):  # not yet created while the session is restored
            self.main_window.status_bar.showMessage(f"Number of Matching Business Models: {matching}")

    def find_concept(self, key: str):
        """A concept of the project or one of the UI objects of the platform (each call gives a new UI object)."""
        return ui_object_instance(self.ui_objects, key or "") or self.concepts.concepts.get(key)

    def _refresh_toolbox(self):
        self.toolbox.add_concepts_tree(self.concepts.get_tree_data())

    def reload_concepts(self):
        """Re-reads the concept files (edited in the admin mode) keeping what is in the canvas."""
        placed, connections = self.canvas.serialize()
        placed, connections = self.project_manager.translate_keys(placed, connections, self.project_manager.key_map)
        self.project_manager.key_map = {}  # concepts renamed or moved in the admin mode keep their place in the canvas
        self._restore_project(placed, connections, view=self.canvas.view_position())
        self.output_console.insertPlainText("Concept files were reloaded.\n")

    def _restore_project(self, placed_concepts=None, connections=None, view=None):
        """Reloads the registered concept sources and redraws the canvas (the saved one, unless given), scrolled to
        `view` (the position saved in session.json, unless given)."""
        self._restoring_view = True  # clearing the canvas moves the scrollbars; that must not be saved
        self.view_save_timer.stop()
        self.concepts.clear()
        self.canvas.clear_canvas()
        info = self.project_manager.get_proj_info() or {}
        for source in info.get("concepts_sources", []):
            try:
                self.concepts.load_package(str(self.project_manager.resolve_concepts_source(source)))
            except Exception as e:
                self.output_console.insertPlainText(f"Could not load concepts from {source}: {e}\n")
        self._refresh_toolbox()
        for placed in info.get("active_concepts", []) if placed_concepts is None else placed_concepts:
            concept = self.find_concept(placed.get("key"))
            if concept:
                if placed.get("label") and concept.is_ui_object:
                    concept = replace(concept, label=placed["label"])
                self.canvas.add_concept(concept, placed["x"], placed["y"])
        for c in info.get("connections", []) if connections is None else connections:
            self.canvas.connect_by_name(c["src"], c["out"], c["dst"], c["in"])
        self.canvas.set_view_position(*(view or self.project_manager.get_canvas_view()))
        QTimer.singleShot(0, lambda: setattr(self, "_restoring_view", False))

    def load_concepts(self):
        """Loads a concept package folder with Simulators and MarketMechanisms."""
        if not self.project_manager.have_active_project():
            self._show_error("No active project", "Create or load a project before loading concepts.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Load Concept Package")
        if not folder:
            return
        # The package is copied into the project folder, and the project's copy is the one loaded
        ok, res = self.project_manager.add_concepts_package(folder)
        if not ok:
            self._show_error("Error in adding the concept package!", res)
            return
        try:
            found = self.concepts.load_package(res)
        except Exception as e:
            self._show_error("Error in loading the concepts!", str(e))
            return
        if not found:
            self._show_error("No concepts found", "No ontology under the selected folder declares a business model (an individual with bm:hasExternalCode).")
            return
        self._refresh_toolbox()
        self.output_console.insertPlainText(
            f"Loaded {len(found)} concept(s); the package was copied to: {res}\n")

    def _toolbox_menu(self, pos):
        item = self.toolbox.itemAt(pos)
        if item is None:
            return
        self.toolbox.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Remove", self.remove_selected_concepts)
        menu.exec(self.toolbox.viewport().mapToGlobal(pos))

    def remove_selected_concepts(self):
        """Removes the package or folder selected in the toolbox from the project (files included)."""
        item = self.toolbox.currentItem()
        if not self.project_manager.have_active_project() or item is None:
            return
        depth = 0
        node = item
        while node.parent() is not None:
            node, depth = node.parent(), depth + 1
        if depth > 1:
            self._show_error("Remove", "Select a package or a folder to remove it (not a single concept).")
            return
        package = item.text(0) if depth == 0 else item.parent().text(0)
        if depth == 0:
            what, targets = f"the package '{package}'", None
        else:
            what = f"the folder '{item.text(0)}' of the package '{package}'"
            targets = {Path(c.ttl_path).parent for c in self.concepts.concepts.values()
                       if c.package == package and c.group == item.text(0)}
        answer = QMessageBox.question(self, "Remove", f"Remove {what} and everything inside it from the project?\n"
                                      "The files are deleted from disk and this cannot be undone.")
        if answer != QMessageBox.Yes:
            return
        if targets is None:
            ok, res = self.project_manager.remove_package(package)
        else:
            results = [self.project_manager.remove_folder(t) for t in targets]
            ok, res = all(r[0] for r in results), next((r[1] for r in results if not r[0]), "")
        if not ok:
            self._show_error("Could not remove", res)
            return
        self.main_window.admin_view.files_changed = False
        self.reload_concepts()  # drops the removed concepts from the canvas
        self.output_console.insertPlainText(f"Removed {what}.\n")

    def open_help(self):
        QDesktopServices.openUrl(QUrl("https://github.com/JCGCosta/PlatformBuilder/wiki")) # Placeholder for actual wiki link
        self.output_console.insertPlainText("Opening help documentation.\n")
        
    def open_settings(self):
        settings_dialog = SettingsDialog(self.main_window)
        settings_dialog.exec()
        self.output_console.insertPlainText("Settings updated.\n")

    def _ui_settings_path(self):
        if not self.project_manager.have_active_project():
            return None
        return Path(self.project_manager.get_proj_dir_path()) / UI_SETTINGS_FILE

    def open_ui_settings(self):
        path = self._ui_settings_path()
        if path is None:
            self._show_error("No active project", "Create or load a project to configure its UI settings.")
            return
        dialog = UISettingsDialog(load_ui_settings(path), self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            save_ui_settings(path, dialog.values())
        except OSError as e:
            self._show_error("Could not save the UI settings", str(e))
            return
        self.output_console.insertPlainText(f"UI settings saved to {path}. They apply the next time the UI is generated (RUN).\n")

    def _set_run_button(self, running: bool):
        self.btn_run.setText("STOP" if running else "RUN")
        color = "#c0392b" if running else "#27ae60"
        self.btn_run.setStyleSheet(f"background-color: {color}; font-weight: bold;")

    def run_engines(self):
        if self.engine_integration.is_running():
            self.engine_integration.stop()
            self._set_run_button(False)
            self.output_console.insertPlainText("API and UI stopped.\n")
            return
        dialog = RunDialog(self, **self.run_settings)
        if dialog.exec() != QDialog.Accepted:
            return
        self.run_settings = dialog.values()
        bms = self.canvas.business_models
        self.output_console.insertPlainText(f"Generating the API and UI for {len(bms)} business model(s)...\n")
        path = self._ui_settings_path()
        if path is not None and not path.is_file():
            save_ui_settings(path, DEFAULT_UI_SETTINGS)  # gives the user a file to edit
        self.engine_integration.run_engines(bms, log_callback=self.output_console.append, ui_settings=load_ui_settings(path), **self.run_settings)
        self._set_run_button(self.engine_integration.is_running())
        self.output_console.insertPlainText("Engine operations completed.\n")
