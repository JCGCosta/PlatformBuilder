from pathlib import Path
from typing import Dict, List

from core.catalog import Concept, load_concepts


class Ontology:
    """Registry of the concepts (business models) loaded in the current project."""

    def __init__(self):
        self.concepts: Dict[str, Concept] = {}

    def clear(self):
        self.concepts.clear()

    def load_package(self, folder: str) -> List[Concept]:
        """Loads every .ttl found under the selected folder."""
        found = []
        for ttl in sorted(Path(folder).rglob("*.ttl")):
            found += load_concepts(str(ttl), folder)
        for concept in found:
            self.concepts[concept.key] = concept
        return found

    def get_tree_data(self) -> list:
        """Tree for the toolbox, from the folder structure: selected folder > folder with the .ttl > concept.
        [{"package_name": str, "concepts": {group: {concept_name: concept_key}}}]"""
        packages: Dict[str, dict] = {}
        for c in self.concepts.values():
            packages.setdefault(c.package, {}).setdefault(c.group, {})[c.name] = c.key
        return [{"package_name": pkg, "concepts": groups} for pkg, groups in packages.items()]
