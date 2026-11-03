from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtGui import QDrag
from PySide6.QtCore import Qt, QMimeData

KEY_ROLE = Qt.ItemDataRole.UserRole


class ConceptTree(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setDragEnabled(True)

    def add_concepts_tree(self, tree_data: list):
        """tree_data: [{"package_name": str, "concepts": {"Simulators": {name: concept_key}, ...}}]
        (see Ontology.get_tree_data). Leaves (level 3) are draggable and carry the concept key."""
        self.clear()
        for package in tree_data:
            root_folder = QTreeWidgetItem(self, [package["package_name"]])
            root_folder.setFlags(root_folder.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            for group_name, concepts in package["concepts"].items():
                group_item = QTreeWidgetItem(root_folder, [group_name])
                group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
                for concept_name, concept_key in concepts.items():
                    leaf = QTreeWidgetItem(group_item, [concept_name])
                    leaf.setData(0, KEY_ROLE, concept_key)
                    leaf.setFlags(leaf.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        self.expandAll()

    def add_flat_tree(self, title: str, entries: dict):
        """A single folder with draggable leaves: entries is {name: key}."""
        self.add_concepts_tree([{"package_name": title, "concepts": {}}])
        folder = self.topLevelItem(0)
        for name, key in entries.items():
            leaf = QTreeWidgetItem(folder, [name])
            leaf.setData(0, KEY_ROLE, key)
            leaf.setFlags(leaf.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        self.expandAll()

    def startDrag(self, supportedActions):
        item = self.currentItem()
        # Only leaves (concepts) can be dragged
        if item and item.childCount() == 0 and item.parent() is not None:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(item.data(0, KEY_ROLE))
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.MoveAction)
