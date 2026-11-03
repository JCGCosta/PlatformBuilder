"""Loads business-model concepts from ontologies and composes the ones wired together in the canvas.

The platform is domain agnostic: a concept is any individual that has `bm:hasExternalCode`
(an OntologyToAPI business model). Its inputs are its `bm:hasParameter` items and its outputs are
its `bm:hasOutputMetadata` items. Any output can feed any input of another concept when the types match.
"""
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List

from rdflib import Graph, Namespace, URIRef

BM = Namespace("http://www.cedri.com/OntologyToAPI-BusinessModel#")
MD = Namespace("http://www.cedri.com/OntologyToAPI-Metadata#")
EXCODE = Namespace("http://www.cedri.com/OntologyToAPI-ExternalCode#")


def _local(uri) -> str:
    return str(uri).split("#")[-1].split("/")[-1]


@dataclass(frozen=True)
class DataItem:
    name: str
    type: str


@dataclass
class Concept:
    """A business model individual loaded from an ontology."""
    name: str
    package: str   # the folder selected by the user
    package_dir: str  # absolute path of that folder
    group: str     # the folder that directly contains the .ttl
    ttl_path: str
    function: str
    python_file: str
    libs: List[str] = field(default_factory=list)
    uri: str = ""  # IRI of the business model individual
    inputs: List[DataItem] = field(default_factory=list)   # bm:hasParameter
    outputs: List[DataItem] = field(default_factory=list)  # bm:hasOutputMetadata
    ui_format: str = ""  # a UI object of PlatformBuilder (Graph, Table, Text or Image), not a concept: it has no endpoint
    instance: int = 1    # UI objects can be placed many times in the canvas: Graph, Graph#2, Graph#3...
    label: str = ""      # name given by the user to a UI object; the key (with the instance) stays its unique id

    @property
    def is_ui_object(self) -> bool:
        return bool(self.ui_format)

    @property
    def key(self) -> str:
        base = f"{self.package}/{self.group}/{self.name}"
        return base if self.instance == 1 else f"{base}#{self.instance}"

    def accepts(self, type_: str) -> bool:
        """For a UI object: whether an output of this type can be linked to its Data input."""
        accepted = UI_OBJECT_ACCEPTS[self.ui_format][0]
        return accepted is None or type_.split("[")[0].strip().lower() in accepted

    @property
    def title(self) -> str:
        return self.label or (self.name if self.instance == 1 else f"{self.name} {self.instance}")


@dataclass(frozen=True)
class Link:
    """Output `out` of `src` feeds input `inp` of `dst`."""
    src: Concept
    out: str
    dst: Concept
    inp: str


@dataclass
class ComposedBusinessModel:
    """A connected set of concepts, executed in dependency order."""
    concepts: List[Concept]   # topological order
    links: List[Link]
    displays: List[Link] = field(default_factory=list)  # outputs of its concepts shown by UI objects (Link.dst)

    @property
    def name(self) -> str:
        return "_".join(c.name for c in self.concepts)

    def fed(self, concept: Concept) -> Dict[str, Link]:
        return {l.inp: l for l in self.links if l.dst is concept}

    def exposed_parameters(self) -> List[tuple]:
        """Inputs not fed by another concept, which the platform user must fill: (exposed_name, concept, item).
        A name that appears in more than one concept is prefixed with the concept name."""
        free = [(c, d) for c in self.concepts for d in c.inputs if d.name not in self.fed(c)]
        counts = {}
        for _, d in free:
            counts[d.name] = counts.get(d.name, 0) + 1
        return [(d.name if counts[d.name] == 1 else f"{c.name}_{d.name}", c, d) for c, d in free]


UI_OBJECT_PACKAGE, UI_OBJECT_GROUP = "PlatformBuilder", "UI"
UI_OBJECT_FORMATS = ("Graph", "Table", "Text", "Image")
# Types each UI object accepts in its Data input, by the part of the output type before "[" (list[float] -> list);
# None accepts any type. The label is what the port shows. The UI still checks the value it receives when it runs.
UI_OBJECT_ACCEPTS = {
    "Graph": ({"dict", "list", "object", "object_list", "json"}, "dict | list"),
    "Table": ({"list", "object_list", "json"}, "list"),
    "Text": (None, "any"),
    "Image": ({"str", "string", "object", "json", "dict"}, "str (base64)"),
}
# What each UI object accepts in its Data input (shown when hovering it)
UI_OBJECT_SCHEMAS = {
    "Graph": 'Data: a dict\n'
             '  {\n'
             '    "graphType": "line" | "bar" | "scatter" | "pie",   (optional)\n'
             '    "title": "...",   (optional)\n'
             '    "independent": {"name": "...", "values": [...]},\n'
             '    "dependent": [\n'
             '      {"name": "...", "values": [...]}\n'
             '    ]\n'
             '  }\n'
             'with every series as long as the independent values;\n'
             'or a list of records (dicts): the first column is the independent\n'
             'variable and every numeric column is plotted as a series.',
    "Table": 'Data: a list of records, one dict per row\n'
             '  [\n'
             '    {"column": value, ...}\n'
             '  ]\n'
             'The columns are the keys of the records.',
    "Text": "Data: any value.\nA string is shown as it is, anything else as JSON.",
    "Image": 'Data: an image encoded in base64\n'
             '  a string with the bytes of a PNG, JPEG, GIF, WebP, BMP or SVG file,\n'
             '  with or without the "data:image/...;base64," prefix;\n'
             '  or a dict {"image": "<base64>", "title": "..."}   (title optional).',
}


def ui_objects() -> Dict[str, Concept]:
    """The UI objects every project can use, by key. The linked outputs are shown as a graph, table, text or image in the
    generated platform. They are not served by OntologyToAPI and never run: they only describe how to show a value."""
    return {c.key: c for c in (
        Concept(name=fmt, package=UI_OBJECT_PACKAGE, package_dir="", group=UI_OBJECT_GROUP, ttl_path="", function="",
                python_file="", inputs=[DataItem("Data", UI_OBJECT_ACCEPTS[fmt][1])],
                outputs=[DataItem("results", fmt)],  # mock output, only so the node is laid out like a concept's; never connectable
                ui_format=fmt) for fmt in UI_OBJECT_FORMATS)}


def ui_object_instance(objects: Dict[str, Concept], key: str):
    """The UI object for a key such as 'PlatformBuilder/UI/Graph#2' (None if it is not one), as its own instance."""
    base, _, number = key.partition("#")
    template = objects.get(base)
    if template is None or (number and not number.isdigit()):
        return None
    return replace(template, instance=int(number) if number else 1)


def _package_root(ttl_path: Path, selected_root: Path):
    rel = ttl_path.resolve().relative_to(selected_root.resolve())
    return selected_root.resolve().name, (rel.parent.name or selected_root.resolve().name)


def _items(g: Graph, subject, predicate, label_of) -> List[DataItem]:
    return [DataItem(label_of(o), type_) for o in g.objects(subject, predicate)
            for type_ in [str(g.value(o, BM.hasParameterType) or g.value(o, MD.hasType) or "")]]


def load_concepts(ttl_path: str, selected_root: str) -> List[Concept]:
    """Parses one ontology file and returns every business model individual in it."""
    g = Graph()
    g.parse(ttl_path, format="turtle")
    package, group = _package_root(Path(ttl_path), Path(selected_root))
    param_label = lambda p: str(g.value(p, BM.hasParameterLabel) or _local(p))
    concepts = []
    for ind in set(g.subjects(BM.hasExternalCode, None)):
        if not isinstance(ind, URIRef):
            continue
        code = g.value(ind, BM.hasExternalCode)
        concepts.append(Concept(
            name=_local(ind), package=package, package_dir=str(Path(selected_root).resolve()), group=group,
            ttl_path=str(Path(ttl_path).resolve()),
            function=str(g.value(code, EXCODE.hasFunction) or ""),
            python_file=str(g.value(code, EXCODE.hasPythonFile) or ""),
            libs=[str(o) for o in g.objects(code, EXCODE.requiresLib)],
            uri=str(ind),
            inputs=_items(g, ind, BM.hasParameter, param_label),
            outputs=_items(g, ind, BM.hasOutputMetadata, _local),
        ))
    return concepts
