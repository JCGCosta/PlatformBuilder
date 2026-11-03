from pathlib import Path

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QTreeView, QFileSystemModel, QSplitter, QLabel,
                             QToolButton, QMenu, QMessageBox, QDialog, QInputDialog)
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QShortcut, QKeySequence
from core.reorganize import Reorganizer
from core.templates import create_concept_files
from ui.editor import CodeEditor
from ui.new_concept_dialog import NewPackageDialog, NewFolderDialog, NewConceptDialog, MoveConceptDialog

EDITABLE = {".py", ".ttl", ".owl", ".json"}
HIDDEN_DIRS = {"__pycache__", ".git", ".idea"}


class ProjectFilterModel(QSortFilterProxyModel):
    """Shows the folders and the editable files of the project; the .pbproj (and everything else) stays hidden,
    so it is only changed by the platform."""

    def filterAcceptsRow(self, row, parent):
        model = self.sourceModel()
        index = model.index(row, 0, parent)
        if model.isDir(index):
            return model.fileName(index) not in HIDDEN_DIRS
        return Path(model.fileName(index)).suffix.lower() in EDITABLE


class AdminPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.project_dir = None
        self.files_changed = False  # a file was saved since the user view last reloaded the concepts
        self.layout = QHBoxLayout(self)

        # Splitter for File Explorer and Editor
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: File Explorer of the active project
        self.explorer_widget = QWidget()
        self.explorer_layout = QVBoxLayout(self.explorer_widget)
        header = QHBoxLayout()
        self.explorer_title = QLabel("Project Explorer")
        header.addWidget(self.explorer_title, 1)
        self.btn_add = QToolButton()
        self.btn_add.setText("+")
        self.btn_add.setToolTip("Add a package or a concept to the project")
        self.btn_add.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.btn_add)
        menu.addAction("New Package...", self.new_package)
        menu.addAction("New Folder...", self.new_folder)
        menu.addAction("New Concept...", self.new_concept)
        self.btn_add.setMenu(menu)
        header.addWidget(self.btn_add)
        self.btn_remove = QToolButton()
        self.btn_remove.setText("✕")
        self.btn_remove.setToolTip("Remove the selected package or folder from the project")
        self.btn_remove.clicked.connect(self.remove_selected)
        header.addWidget(self.btn_remove)
        self.explorer_layout.addLayout(header)

        self.model = QFileSystemModel()
        self.proxy = ProjectFilterModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)

        self.tree = QTreeView()
        self.tree.setModel(self.proxy)
        for column in (1, 2, 3):  # size, type, date
            self.tree.setColumnHidden(column, True)
        self.tree.setHeaderHidden(True)
        self.tree.doubleClicked.connect(self.open_file)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        QShortcut(QKeySequence.StandardKey.Delete, self.tree, activated=self.remove_selected,
                  context=Qt.ShortcutContext.WidgetShortcut)
        self.explorer_layout.addWidget(self.tree)
        self.splitter.addWidget(self.explorer_widget)

        # Right side: Editor
        self.editor = CodeEditor()
        self.editor.files_saved.connect(lambda: setattr(self, "files_changed", True))
        self.splitter.addWidget(self.editor)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 4)
        self.layout.addWidget(self.splitter)

    def set_project(self, project_dir, name: str = "") -> bool:
        """Points the explorer at the active project folder. Returns False if the user cancelled closing unsaved files."""
        project_dir = str(Path(project_dir).resolve()) if project_dir else None
        if project_dir == self.project_dir:
            return True
        if not self.editor.close_all():
            return False
        self.project_dir = project_dir
        if not project_dir:
            self.explorer_title.setText("Project Explorer (no active project)")
            self.model.setRootPath("")
            self.tree.setRootIndex(self.proxy.mapFromSource(self.model.index("")))
            return True
        self.explorer_title.setText(f"Project Explorer - {name or Path(project_dir).name}")
        root = self.model.setRootPath(project_dir)
        self.tree.setRootIndex(self.proxy.mapFromSource(root))
        return True

    def open_file(self, index):
        source = self.proxy.mapToSource(index)
        if self.model.isDir(source):
            return
        self.editor.open_file(self.model.filePath(source))

    def _project_manager(self):
        pm = self.main_window.user_view.project_manager
        if not pm.have_active_project():
            QMessageBox.warning(self, "No active project", "Create or load a project first.")
            return None
        return pm

    def _show_in_tree(self, path):
        index = self.proxy.mapFromSource(self.model.index(str(path)))
        if index.isValid():
            self.tree.scrollTo(index)
            self.tree.setCurrentIndex(index)

    def new_package(self):
        pm = self._project_manager()
        if not pm:
            return
        dialog = NewPackageDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        ok, res = pm.create_package(dialog.value())
        if not ok:
            QMessageBox.warning(self, "Could not create the package", res)
            return
        self.files_changed = True
        self._show_in_tree(res)

    def _selected_package(self, pm):
        """The package of the file/folder selected in the tree, to preselect it in the dialogs."""
        index = self.tree.currentIndex()
        if not index.isValid():
            return None
        path = Path(self.model.filePath(self.proxy.mapToSource(index)))
        for package in pm.list_packages():
            package_dir = pm.package_dir(package)
            if package_dir == path or package_dir in path.parents:
                return package
        return None

    def new_folder(self):
        pm = self._project_manager()
        if not pm:
            return
        packages = pm.list_packages()
        if not packages:
            QMessageBox.information(self, "No packages", "Create a package first (+ > New Package).")
            return
        dialog = NewFolderDialog(packages, self, self._selected_package(pm))
        if dialog.exec() != QDialog.Accepted:
            return
        ok, res = pm.create_group(*dialog.values())
        if not ok:
            QMessageBox.warning(self, "Could not create the folder", res)
            return
        self._show_in_tree(res)

    def new_concept(self):
        pm = self._project_manager()
        if not pm:
            return
        packages = pm.list_packages()
        if not packages:
            QMessageBox.information(self, "No packages", "Create a package first (+ > New Package).")
            return
        dialog = NewConceptDialog(packages, pm.list_groups, self, self._selected_package(pm))
        if dialog.exec() != QDialog.Accepted:
            return
        package, group, name = dialog.values()
        try:
            group_dir = create_concept_files(pm.package_dir(package), group, name)
        except OSError as e:
            QMessageBox.warning(self, "Could not create the concept", str(e))
            return
        self.files_changed = True
        self._show_in_tree(group_dir)
        self.editor.open_file(group_dir / f"{name}.ttl")
        self.editor.open_file(group_dir / f"{name}.py")

    def _tree_menu(self, pos):
        index = self.tree.indexAt(pos)
        if index.isValid():
            self.tree.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction("New Folder...", self.new_folder)
        menu.addAction("New Concept...", self.new_concept)
        kind, path, package = self._selection_kind()
        if kind:
            menu.addSeparator()
            menu.addAction("Rename...", self.rename_selected)
            if kind in ("folder", "concept"):
                menu.addAction("Move...", self.move_selected)
        menu.addSeparator()
        menu.addAction("Remove", self.remove_selected)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _selection_kind(self):
        """What is selected in the tree: ("package" | "folder" | "concept" | None, its path, its package name)."""
        index = self.tree.currentIndex()
        pm = self.main_window.user_view.project_manager
        if not index.isValid() or not pm.have_active_project():
            return None, None, None
        path = Path(self.model.filePath(self.proxy.mapToSource(index))).resolve()
        for package in pm.list_packages():
            package_dir = pm.package_dir(package).resolve()
            if package_dir == path:
                return "package", path, package
            if package_dir in path.parents:
                depth = len(path.relative_to(package_dir).parts)
                if path.is_dir():
                    return ("folder" if depth == 1 else None), path, package
                if depth == 2 and path.suffix.lower() in (".ttl", ".py"):
                    return "concept", path, package
        return None, None, None

    def _reorganize(self, operation, affected: Path, what: str, *args):
        """Closes the open files that are about to move, runs the operation and shows the result."""
        if not self.editor.close_under(affected):
            return
        ok, res = operation(*args)
        if not ok:
            QMessageBox.warning(self, f"Could not {what}", res)
            return
        self.files_changed = True
        self._show_in_tree(res)

    def rename_selected(self):
        pm = self._project_manager()
        kind, path, package = self._selection_kind()
        if not pm or not kind:
            return
        old = package if kind == "package" else path.stem if kind == "concept" else path.name
        new, ok = QInputDialog.getText(self, f"Rename {kind}", f"New name for the {kind} '{old}':", text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        reorganizer = Reorganizer(pm)
        if kind == "package":
            self._reorganize(reorganizer.rename_package, path, "rename the package", package, new)
        elif kind == "folder":
            self._reorganize(reorganizer.rename_folder, path, "rename the folder", path, new)
        else:
            if not self.editor.close_under(path.with_suffix(".py")):
                return
            self._reorganize(reorganizer.rename_concept, path.with_suffix(".ttl"), "rename the concept", path.with_suffix(".ttl"), new)

    def move_selected(self):
        pm = self._project_manager()
        kind, path, package = self._selection_kind()
        if not pm or kind not in ("folder", "concept"):
            return
        reorganizer = Reorganizer(pm)
        if kind == "folder":
            others = [p for p in pm.list_packages() if p != package]
            if not others:
                QMessageBox.information(self, "Move", "There is no other package to move the folder to.")
                return
            dest, ok = QInputDialog.getItem(self, "Move folder", f"Move the folder '{path.name}' to the package:", others, 0, False)
            if ok:
                self._reorganize(reorganizer.move_folder, path, "move the folder", path, dest)
            return
        dialog = MoveConceptDialog(pm.list_packages(), pm.list_groups, self, package)
        if dialog.exec() != QDialog.Accepted:
            return
        dest_package, dest_group = dialog.values()
        if not self.editor.close_under(path.with_suffix(".py")):
            return
        self._reorganize(reorganizer.move_concept, path.with_suffix(".ttl"), "move the concept",
                         path.with_suffix(".ttl"), dest_package, dest_group)

    def remove_selected(self):
        """Removes the selected package or folder (and everything in it) from the project."""
        pm = self._project_manager()
        if not pm:
            return
        index = self.tree.currentIndex()
        path = Path(self.model.filePath(self.proxy.mapToSource(index))) if index.isValid() else None
        package = next((p for p in pm.list_packages() if path and pm.package_dir(p) == path.resolve()), None)
        inside = path and any(pm.package_dir(p) in path.resolve().parents for p in pm.list_packages())
        if not package and not (inside and path.is_dir()):
            QMessageBox.information(self, "Remove", "Select a package or a folder inside a package to remove it.")
            return
        kind = "package" if package else "folder"
        answer = QMessageBox.question(
            self, f"Remove {kind}", f"Remove the {kind} '{path.name}' and everything inside it from the project?\n"
            "The files are deleted from disk and this cannot be undone.")
        if answer != QMessageBox.Yes or not self.editor.close_under(path):
            return
        ok, res = pm.remove_package(package) if package else pm.remove_folder(path)
        if not ok:
            QMessageBox.warning(self, f"Could not remove the {kind}", res)
            return
        self.files_changed = True
