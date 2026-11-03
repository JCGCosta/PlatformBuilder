import itertools
from dataclasses import replace
import zlib
from typing import Callable, List, Optional

from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
                               QGraphicsPathItem, QGraphicsSimpleTextItem, QGraphicsLineItem, QMenu, QInputDialog)
from PySide6.QtGui import QBrush, QPen, QColor, QPainter, QPainterPath, QFont, QFontMetrics
from PySide6.QtCore import Qt, Signal, QPointF, QTimer

from core.catalog import Concept, ComposedBusinessModel, Link, UI_OBJECT_SCHEMAS

TITLE_HEIGHT = 36
PORT_HEIGHT, PORT_GAP, PORT_MARGIN, PORT_PADDING = 24, 6, 10, 14
COLUMN_GAP = 30  # minimum space between the inputs and outputs columns

NODE_COLOR = "#2c3e50"
UI_OBJECT_COLOR = "#6c3483"  # UI objects (graph, table, text, image) are not concepts, so they look different

PORT_FONT = QFont()
PORT_FONT.setPointSize(8)

# Ports are colored by data type (inputs and outputs of the same type share the color).
TYPE_COLORS = {
    "str": "#2980b9", "int": "#27ae60", "float": "#16a085", "bool": "#8e44ad",
    "list": "#d35400", "dict": "#c0392b", "UploadFile": "#7f8c8d",
}
FALLBACK_COLORS = ["#b7950b", "#1f618d", "#117864", "#76448a", "#a04000", "#922b21", "#2e4053", "#af601a"]


def type_color(type_: str) -> str:
    if type_ in TYPE_COLORS:
        return TYPE_COLORS[type_]
    return FALLBACK_COLORS[zlib.crc32(type_.encode()) % len(FALLBACK_COLORS)]


def port_text(name: str, type_: str) -> str:
    return f"{name} : {type_}"


def port_width(name: str, type_: str) -> float:
    return QFontMetrics(PORT_FONT).horizontalAdvance(port_text(name, type_)) + PORT_PADDING * 2


class PortItem(QGraphicsPathItem):
    """Rounded rectangle representing one input (left) or output (right) of a concept."""
    def __init__(self, owner: "ConceptItem", name: str, type_: str, is_output: bool, x: float, y: float, width: float):
        super().__init__(owner)
        self.owner, self.name, self.type, self.is_output, self.width = owner, name, type_, is_output, width
        self.connections: List["ConnectionLine"] = []

        path = QPainterPath()
        path.addRoundedRect(0, 0, width, PORT_HEIGHT, PORT_HEIGHT / 2, PORT_HEIGHT / 2)
        self.setPath(path)
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(type_color(type_))))
        self.setPen(QPen(QColor("#ecf0f1")))
        self.setToolTip(f"{name} : {type_}")
        self.setZValue(1)

        label = QGraphicsSimpleTextItem(port_text(name, type_), self)
        label.setFont(PORT_FONT)
        label.setBrush(QBrush(QColor("white")))
        label.setPos((width - label.boundingRect().width()) / 2,
                     (PORT_HEIGHT - label.boundingRect().height()) / 2)

    def anchor(self) -> QPointF:
        """Scene point where connection lines attach: right edge of outputs, left edge of inputs."""
        x = self.width if self.is_output else 0
        return self.mapToScene(QPointF(x, PORT_HEIGHT / 2))

    def can_connect_to(self, other: "PortItem") -> bool:
        """An output can feed an input of another concept when the types match and no cycle is created. The input of
        a UI object accepts the types listed for it in the catalog (Graph: dict | list, Table: list, Text: any)."""
        return (self.is_output and not other.is_output and self.owner is not other.owner and not self.owner.concept.is_ui_object
                and (other.owner.concept.accepts(self.type) if other.owner.concept.is_ui_object else self.type == other.type)
                and not other.owner.reaches(self.owner))


class ConnectionLine(QGraphicsLineItem):
    def __init__(self, source: PortItem, dest: PortItem):
        super().__init__()
        self.source, self.dest = source, dest
        pen = QPen(QColor("#27ae60"))
        pen.setWidth(3)
        self.setPen(pen)
        self.setZValue(1)  # above the concept squares (z=0) and their ports
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        source.connections.append(self)
        dest.connections.append(self)
        self.update_position()

    def update_position(self):
        a, b = self.source.anchor(), self.dest.anchor()
        self.setLine(a.x(), a.y(), b.x(), b.y())

    def detach(self):
        for port in (self.source, self.dest):
            if self in port.connections:
                port.connections.remove(self)
        if self.scene():
            self.scene().removeItem(self)


class ConceptItem(QGraphicsRectItem):
    """Square with the concept title; inputs on the left and outputs on the right as rounded rectangles."""
    def __init__(self, concept: Concept, x, y):
        super().__init__(0, 0, 10, 10)
        self.concept = concept
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(UI_OBJECT_COLOR if concept.is_ui_object else NODE_COLOR)))
        self.setPen(QPen(QColor("#ecf0f1")))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

        title = self.title_item = QGraphicsSimpleTextItem(concept.title, self)
        title.setBrush(QBrush(QColor("white")))
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        
        self.setToolTip(f"UI object: shows the outputs linked to it as a {concept.ui_format.lower()} in the generated platform.\n"
                        f"{UI_OBJECT_SCHEMAS[concept.ui_format]}"
                        if concept.is_ui_object else f"{concept.package} / {concept.group} / {concept.name}")
        inputs = [(d.name, d.type) for d in concept.inputs]
        outputs = [(d.name, d.type) for d in concept.outputs]
        step = PORT_HEIGHT + PORT_GAP
        # Size the node to its content: each column is as wide as its longest "name : type"
        in_width = max((port_width(n, t) for n, t in inputs), default=0)
        out_width = max((port_width(n, t) for n, t in outputs), default=0)
        self._ports_width, self._out_width = in_width + out_width + COLUMN_GAP + 2 * PORT_MARGIN, out_width
        width = max(self._ports_width, title.boundingRect().width() + 2 * PORT_MARGIN)
        self.inputs = [PortItem(self, n, t, False, PORT_MARGIN, TITLE_HEIGHT + i * step, in_width)
                       for i, (n, t) in enumerate(inputs)]
        self.outputs = [PortItem(self, n, t, True, width - PORT_MARGIN - out_width, TITLE_HEIGHT + i * step, out_width)
                        for i, (n, t) in enumerate(outputs)]
        title.setPos((width - title.boundingRect().width()) / 2, 8)
        if concept.is_ui_object:
            self.inputs[0].setToolTip(UI_OBJECT_SCHEMAS[concept.ui_format])
            self.outputs[0].setToolTip("Not connectable: the result is shown in the generated platform")
        self.setRect(0, 0, width, TITLE_HEIGHT + max(len(inputs), len(outputs), 1) * step + PORT_MARGIN)

    def rename(self, label: str):
        """Shows `label` as the title of a UI object (its key, the unique id, does not change) and resizes the node."""
        self.concept = replace(self.concept, label=label.strip())
        self.title_item.setText(self.concept.title)
        width = max(self._ports_width, self.title_item.boundingRect().width() + 2 * PORT_MARGIN)
        self.title_item.setPos((width - self.title_item.boundingRect().width()) / 2, 8)
        for port in self.outputs:
            port.setX(width - PORT_MARGIN - self._out_width)
        self.setRect(0, 0, width, self.rect().height())
        for port in self.ports():
            for line in port.connections:
                line.update_position()

    def reaches(self, target: "ConceptItem") -> bool:
        """True if `target` is downstream of this concept (following output connections)."""
        seen, stack = set(), [self]
        while stack:
            item = stack.pop()
            if item is target:
                return True
            if id(item) in seen:
                continue
            seen.add(id(item))
            stack += [line.dest.owner for port in item.outputs for line in port.connections]
        return False

    def ports(self) -> List[PortItem]:
        return self.inputs + self.outputs

    def port(self, name: str, is_output: bool) -> Optional[PortItem]:
        return next((p for p in (self.outputs if is_output else self.inputs) if p.name == name), None)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.ports():
                for line in port.connections:
                    line.update_position()
        return super().itemChange(change, value)


class Canvas(QGraphicsView):
    business_models_changed = Signal(list)  # List[ComposedBusinessModel]
    view_moved = Signal(int, int)  # scrollbar values (x, y) every time the visible area moves

    def __init__(self, concept_lookup: Optional[Callable[[str], Optional[Concept]]] = None):
        super().__init__()
        self.concept_lookup = concept_lookup or (lambda key: None)
        self.scene = QGraphicsScene(0, 0, 4000, 2000)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)
        self.setBackgroundBrush(QBrush(QColor("#34495e")))
        self.business_models: List[ComposedBusinessModel] = []
        self._drag_source: Optional[PortItem] = None
        self._drag_line: Optional[QGraphicsLineItem] = None
        self._pan_last = None  # last mouse position while panning with the middle button
        self._pending_view: Optional[tuple] = None  # a position asked before the view had its final size
        for bar in (self.horizontalScrollBar(), self.verticalScrollBar()):
            bar.valueChanged.connect(lambda _=None: self.view_moved.emit(*self.view_position()))

    # -- visible area -------------------------------------------------------
    def view_position(self) -> tuple:
        return self.horizontalScrollBar().value(), self.verticalScrollBar().value()

    def set_view_position(self, x: int, y: int):
        """Scrolls to (x, y). The scrollbar ranges only exist once the view has its size, so a position that does not
        fit yet is kept and applied when the view is shown or resized."""
        self._pending_view = (x, y)
        self._apply_pending_view()

    def _apply_pending_view(self):
        if self._pending_view is None:
            return
        x, y = self._pending_view
        self.horizontalScrollBar().setValue(x)
        self.verticalScrollBar().setValue(y)
        if self.isVisible() and self.view_position() == (x, y):
            # Qt still shifts the view when its first resize is processed, so the position is applied once more
            # on the next turn of the event loop before it is let go
            QTimer.singleShot(0, self._release_pending_view)

    def _release_pending_view(self):
        if self._pending_view is not None:
            x, y = self._pending_view
            self.horizontalScrollBar().setValue(x)
            self.verticalScrollBar().setValue(y)
            self._pending_view = None

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_pending_view()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_pending_view()

    # -- queries ----------------------------------------------------------
    def concept_items(self) -> List[ConceptItem]:
        return [i for i in self.scene.items() if isinstance(i, ConceptItem)]

    def connection_lines(self) -> List[ConnectionLine]:
        return [i for i in self.scene.items() if isinstance(i, ConnectionLine)]

    def _port_at(self, view_pos) -> Optional[PortItem]:
        return next((i for i in self.scene.items(self.mapToScene(view_pos)) if isinstance(i, PortItem)), None)

    # -- model ------------------------------------------------------------
    def clear_canvas(self):
        self.scene.clear()
        self.refresh_business_models()

    def add_concept(self, concept: Concept, x: float, y: float) -> ConceptItem:
        item = ConceptItem(concept, x, y)
        self.scene.addItem(item)
        self.refresh_business_models()
        return item

    def connect_ports(self, source: PortItem, dest: PortItem) -> bool:
        if not source.can_connect_to(dest):
            return False
        if any(line.source is source for line in dest.connections):
            return False  # already connected; an input may be fed by several outputs (alternative pipelines)
        self.scene.addItem(ConnectionLine(source, dest))
        self.refresh_business_models()
        return True

    def connect_by_name(self, src_key: str, out_name: str, dst_key: str, in_name: str) -> bool:
        by_key = {i.concept.key: i for i in self.concept_items()}
        src, dst = by_key.get(src_key), by_key.get(dst_key)
        if not src or not dst:
            return False
        out_port, in_port = src.port(out_name, True), dst.port(in_name, False)
        return bool(out_port and in_port and self.connect_ports(out_port, in_port))

    def refresh_business_models(self):
        """A business model is a pipeline: a final concept (one whose outputs feed nothing) with everything upstream
        of it, ordered so that producers run before consumers. An input fed by several outputs is an alternative:
        each choice of one source per such input is its own business model."""
        by_id = {id(i): i for i in self.concept_items() if not i.concept.is_ui_object}
        links = {}  # (src id, dst id) -> Link, for every connection between concepts
        shown = []  # links from an output to a UI object: not part of any pipeline, shown by the models having the source
        for line in self.connection_lines():
            src, dst = line.source.owner, line.dest.owner
            link = Link(src.concept, line.source.name, dst.concept, line.dest.name)
            if dst.concept.is_ui_object:
                shown.append((id(src), link))
            else:
                links[(id(src), id(dst), line.dest.name, line.source.name)] = link

        def position(k):
            return by_id[k].pos().x(), by_id[k].pos().y()

        def compose(group, chosen):
            mine = [key for key in chosen if key[1] in group]
            order, pending = [], set(group)  # topological order (the graph is acyclic by construction)
            while pending:
                ready = sorted((k for k in pending if all(key[0] not in pending for key in mine if key[1] == k)), key=position)
                order += ready
                pending -= set(ready)
            return ComposedBusinessModel([by_id[k].concept for k in order],
                                         [links[key] for k in order for key in sorted(mine) if key[1] == k],
                                         [link for src, link in shown if src in group])

        feeding = {}  # (dst id, input name) -> every link key feeding that input
        for key in links:
            feeding.setdefault((key[1], key[2]), []).append(key)

        def expand(done, pending, chosen):
            """Yields (concepts, links) for every way of picking one source per fed input, upstream of `pending`."""
            if not pending:
                yield done, chosen
                return
            node = min(pending)
            inputs = [keys for (dst, _), keys in feeding.items() if dst == node]
            choices = list(itertools.product(*inputs))
            # the alternatives of a concept are its alternative producers, so every input with several sources must
            # take its source from the same producer (otherwise A.x + B.y and B.x + A.y would be extra pipelines)
            consistent = [c for c in choices if len({key[0] for key in c if len(feeding[(key[1], key[2])]) > 1}) <= 1]
            for choice in consistent or choices:
                producers = {key[0] for key in choice}
                yield from expand(done | {node}, (pending - {node}) | (producers - done - {node}), chosen | set(choice))

        # one business model per final concept (feeds nothing) and per way of reaching it from its producers
        found = []
        sinks = [k for k in sorted(by_id, key=position) if not any(key[0] == k for key in links)]
        for sink in sinks:
            for group, chosen in expand(frozenset(), {sink}, frozenset()):
                found.append(compose(set(group), chosen))
        self.business_models = found
        self.business_models_changed.emit(found)

    def serialize(self):
        """Returns (concepts, connections) in the format stored in the project file."""
        concepts = [{"key": i.concept.key, "x": i.pos().x(), "y": i.pos().y(), **({"label": i.concept.label} if i.concept.label else {})}
                    for i in self.concept_items()]
        connections = [{"src": l.source.owner.concept.key, "out": l.source.name,
                        "dst": l.dest.owner.concept.key, "in": l.dest.name} for l in self.connection_lines()]
        return concepts, connections

    # -- interaction: drag from an output port to a compatible input port -------
    def _set_targets_highlight(self, source: Optional[PortItem]):
        for item in self.concept_items():
            for port in item.inputs:
                port.setOpacity(0.35 if source and not source.can_connect_to(port) else 1.0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:  # pan the canvas
            self._pan_last = event.pos()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        port = self._port_at(event.pos())
        if event.button() == Qt.MouseButton.LeftButton and port and port.is_output:
            self._drag_source = port
            self._drag_line = QGraphicsLineItem()
            self._drag_line.setPen(QPen(QColor("#f1c40f"), 2, Qt.PenStyle.DashLine))
            self._drag_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._drag_line.setZValue(2)
            self.scene.addItem(self._drag_line)
            self._update_drag_line(event.pos())
            self._set_targets_highlight(port)
            return
        super().mousePressEvent(event)

    def _update_drag_line(self, view_pos):
        a, b = self._drag_source.anchor(), self.mapToScene(view_pos)
        self._drag_line.setLine(a.x(), a.y(), b.x(), b.y())

    def mouseMoveEvent(self, event):
        if self._pan_last is not None:
            delta = event.pos() - self._pan_last
            self._pan_last = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        if self._drag_source:
            self._update_drag_line(event.pos())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._pan_last is not None:
            self._pan_last = None
            self.viewport().unsetCursor()
            event.accept()
            return
        if self._drag_source:
            target = self._port_at(event.pos())
            self.scene.removeItem(self._drag_line)
            source, self._drag_source, self._drag_line = self._drag_source, None, None
            self._set_targets_highlight(None)
            if target:
                self.connect_ports(source, target)
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in self.scene.selectedItems():
                if isinstance(item, ConnectionLine):
                    item.detach()
                elif isinstance(item, ConceptItem):
                    for port in item.ports():
                        for line in list(port.connections):
                            line.detach()
                    self.scene.removeItem(item)
            self.refresh_business_models()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Right click on a UI object: rename it."""
        item = next((i for i in self.items(event.pos()) if isinstance(i, ConceptItem)), None)
        item = item or next((i.owner for i in self.items(event.pos()) if isinstance(i, PortItem)), None)
        if item is None or not item.concept.is_ui_object:
            return
        menu = QMenu(self)
        rename = menu.addAction("Rename...")
        if menu.exec(event.globalPos()) is rename:
            name, ok = QInputDialog.getText(self, "Rename", f"Name of this {item.concept.ui_format.lower()}:", text=item.concept.title)
            if ok and name.strip():
                item.rename(name)
                self.refresh_business_models()  # the name is also the title of its visualization in the generated platform

    # -- drag and drop from the concept toolbox ---------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        concept = self.concept_lookup(event.mimeData().text())
        event.acceptProposedAction()
        if concept is None:
            return
        if concept.is_ui_object:  # UI objects can be placed as many times as wanted, each one with its own number
            taken = {i.concept.instance for i in self.concept_items() if i.concept.key.partition("#")[0] == concept.key.partition("#")[0]}
            concept = replace(concept, instance=next(n for n in itertools.count(1) if n not in taken))
        elif any(i.concept is concept for i in self.concept_items()):
            return  # each concept is placed once
        pos = self.mapToScene(event.position().toPoint())
        self.add_concept(concept, pos.x(), pos.y())
