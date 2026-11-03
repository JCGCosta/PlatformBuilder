from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QComboBox, QLabel

from core.templates import NAME_RE


class NewPackageDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Package")
        form = QFormLayout(self)
        self.name = QLineEdit()
        form.addRow("Package name:", self.name)
        self.error = QLabel()
        self.error.setStyleSheet("color: #e74c3c;")
        form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _validate(self):
        if NAME_RE.match(self.name.text().strip()):
            self.accept()
        else:
            self.error.setText("Use letters, digits and _ (starting with a letter).")

    def value(self) -> str:
        return self.name.text().strip()


class NewFolderDialog(QDialog):
    """A folder inside a package; the concepts live in these folders."""
    def __init__(self, packages, parent=None, current=None):
        super().__init__(parent)
        self.setWindowTitle("New Folder")
        form = QFormLayout(self)
        self.package = QComboBox()
        self.package.addItems(packages)
        if current in packages:
            self.package.setCurrentText(current)
        self.name = QLineEdit()
        form.addRow("Package:", self.package)
        form.addRow("Folder name:", self.name)
        self.error = QLabel()
        self.error.setStyleSheet("color: #e74c3c;")
        form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _validate(self):
        if NAME_RE.match(self.name.text().strip()):
            self.accept()
        else:
            self.error.setText("Use letters, digits and _ (starting with a letter).")

    def values(self):
        return self.package.currentText(), self.name.text().strip()


class NewConceptDialog(QDialog):
    def __init__(self, packages, groups_of, parent=None, current=None):
        """groups_of: callable package name -> its folders."""
        super().__init__(parent)
        self.setWindowTitle("New Concept")
        self.groups_of = groups_of
        form = QFormLayout(self)
        self.package = QComboBox()
        self.package.addItems(packages)
        if current in packages:
            self.package.setCurrentText(current)
        self.group = QComboBox()
        self.name = QLineEdit()
        form.addRow("Package:", self.package)
        form.addRow("Folder:", self.group)
        form.addRow("Concept name:", self.name)
        self.error = QLabel()
        self.error.setStyleSheet("color: #e74c3c;")
        form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.package.currentTextChanged.connect(self._load_groups)
        self._load_groups(self.package.currentText())

    def _load_groups(self, package):
        self.group.clear()
        self.group.addItems(self.groups_of(package))

    def _validate(self):
        if not self.group.currentText():
            self.error.setText("The package has no folders yet (+ > New Folder).")
        elif not NAME_RE.match(self.name.text().strip()):
            self.error.setText("Use letters, digits and _ (starting with a letter).")
        else:
            self.accept()

    def values(self):
        return self.package.currentText(), self.group.currentText(), self.name.text().strip()


class MoveConceptDialog(QDialog):
    """Where to move a concept: a package and a folder of it (an existing one, or a new name)."""
    def __init__(self, packages, groups_of, parent=None, current=None):
        super().__init__(parent)
        self.setWindowTitle("Move Concept")
        self.groups_of = groups_of
        form = QFormLayout(self)
        self.package = QComboBox()
        self.package.addItems(packages)
        if current in packages:
            self.package.setCurrentText(current)
        self.group = QComboBox()
        self.group.setEditable(True)
        form.addRow("Package:", self.package)
        form.addRow("Folder:", self.group)
        self.error = QLabel()
        self.error.setStyleSheet("color: #e74c3c;")
        form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.package.currentTextChanged.connect(self._load_groups)
        self._load_groups(self.package.currentText())

    def _load_groups(self, package):
        self.group.clear()
        self.group.addItems(self.groups_of(package))

    def _validate(self):
        if NAME_RE.match(self.group.currentText().strip()):
            self.accept()
        else:
            self.error.setText("Use letters, digits and _ (starting with a letter).")

    def values(self):
        return self.package.currentText(), self.group.currentText().strip()
