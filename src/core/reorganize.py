"""Renames and moves the packages, folders and concepts of a project, keeping consistent everything that points to them:
the excode:hasPythonFile of the ontologies, the packages registered in the .pbproj and the concepts placed in the canvas."""
import re
import shutil
from pathlib import Path
from typing import Callable, List, Tuple

from core.catalog import load_concepts
from core.templates import NAME_RE

PYTHON_FILE_RE = re.compile(r'(excode:hasPythonFile\s+")([^"]*)(")')


def _identifier_re(name: str):
    """`name` as part of the identifiers a concept created from the template derives from it (Name:Name, NameFunction,
    Name_Class, RunName), but not inside other words."""
    return re.compile(rf"(?:(?<![A-Za-z0-9])|(?<=Run)){re.escape(name)}(?![a-z0-9])")


def _replace_identifiers(text: str, old: str, new: str) -> str:
    """Renames the identifiers derived from `old`, leaving the excode:hasPythonFile paths alone (they are fixed apart)."""
    pattern, out, last = _identifier_re(old), [], 0
    for match in PYTHON_FILE_RE.finditer(text):
        out.append(pattern.sub(new, text[last:match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(pattern.sub(new, text[last:]))
    return "".join(out)


def _remap(path: Path, moves: List[Tuple[Path, Path]]) -> Path:
    for old, new in moves:
        if path == old or old in path.parents:
            return new / path.relative_to(old)
    return path


class Reorganizer:
    def __init__(self, project_manager):
        self.pm = project_manager

    # -- the operations; each returns (ok, new path or error) ---------------------------------------------------------
    def rename_package(self, package: str, new_name: str):
        if not NAME_RE.match(new_name):
            return False, "Use letters, digits and _ (starting with a letter)."
        if new_name in self.pm.list_packages():
            return False, f"The package '{new_name}' already exists."
        old_dir = self.pm.package_dir(package).resolve()
        new_dir = old_dir.with_name(new_name)
        if new_dir.exists():
            return False, f"'{new_dir}' already exists."
        return self._run([(old_dir, new_dir)], sorted(old_dir.rglob("*.ttl")), new_dir, package=(package, new_name))

    def rename_folder(self, folder: Path, new_name: str):
        folder = Path(folder).resolve()
        if not NAME_RE.match(new_name):
            return False, "Use letters, digits and _ (starting with a letter)."
        new_dir = folder.with_name(new_name)
        if new_dir.exists():
            return False, f"'{new_name}' already exists in {folder.parent.name}."
        return self._run([(folder, new_dir)], sorted(folder.rglob("*.ttl")), new_dir)

    def move_folder(self, folder: Path, dest_package: str):
        folder = Path(folder).resolve()
        new_dir = self.pm.package_dir(dest_package).resolve() / folder.name
        if new_dir == folder:
            return False, "The folder is already in that package."
        if new_dir.exists():
            return False, f"'{folder.name}' already exists in {dest_package}."
        return self._run([(folder, new_dir)], sorted(folder.rglob("*.ttl")), new_dir)

    def rename_concept(self, ttl: Path, new_name: str):
        """Renames the .ttl/.py pair. A concept made from the template (its individual is named after the file) is renamed
        inside the files too: the individual, its function and its entry point."""
        ttl = Path(ttl).resolve()
        old_name = ttl.stem
        if not NAME_RE.match(new_name):
            return False, "Use letters, digits and _ (starting with a letter)."
        pairs = self._pair(ttl, lambda p: p.with_name(new_name + p.suffix))
        clash = next((new for _, new in pairs if new.exists()), None)
        if clash:
            return False, f"{clash.name} already exists in {clash.parent.name}."
        rewrite = f"{old_name}:{old_name}" in ttl.read_text(encoding="utf-8")

        def rewrite_files():
            for old, _ in pairs:
                old.write_text(_replace_identifiers(old.read_text(encoding="utf-8"), old_name, new_name), encoding="utf-8")
        name_tf = (lambda n: _identifier_re(old_name).sub(new_name, n)) if rewrite else (lambda n: n)
        return self._run(pairs, [ttl], pairs[0][1], name_tf=name_tf, prepare=rewrite_files if rewrite else None)

    def move_concept(self, ttl: Path, dest_package: str, dest_group: str):
        ttl = Path(ttl).resolve()
        if not NAME_RE.match(dest_group):
            return False, "Use letters, digits and _ (starting with a letter) for the folder."
        dest_dir = self.pm.package_dir(dest_package).resolve() / dest_group
        if dest_dir == ttl.parent:
            return False, "The concept is already in that folder."
        pairs = self._pair(ttl, lambda p: dest_dir / p.name)
        clash = next((new for _, new in pairs if new.exists()), None)
        if clash:
            return False, f"{clash.name} already exists in {dest_group}."
        return self._run(pairs, [ttl], pairs[0][1])

    # -- shared machinery -------------------------------------------------------------------------------------------
    @staticmethod
    def _pair(ttl: Path, target: Callable[[Path], Path]):
        """The .ttl and its .py of the same name, as (old, new) pairs; the .ttl is first."""
        return [(p, target(p)) for p in (ttl, ttl.with_suffix(".py")) if p.is_file()]

    def _package_dir_of(self, path: Path):
        return next((d for d in (self.pm.package_dir(p).resolve() for p in self.pm.list_packages())
                     if d == path or d in path.parents), None)

    def _concept_keys(self, ttls: List[Path]) -> dict:
        """{ttl: [Concept]} for the ontologies that can be parsed (the others have no concepts to follow)."""
        found = {}
        for ttl in ttls:
            package_dir = self._package_dir_of(ttl)
            try:
                found[ttl] = load_concepts(str(ttl), str(package_dir)) if package_dir else []
            except Exception:
                found[ttl] = []
        return found

    def _rewrite_python_files(self, ttl: Path, moves):
        """Points excode:hasPythonFile to where the files went (the path is relative to the folder of the package)."""
        package_dir = self._package_dir_of(ttl)
        if package_dir is None:
            return
        base = package_dir.parent
        text = ttl.read_text(encoding="utf-8")

        def fix(match):
            old = (base / match.group(2)).resolve()
            new = _remap(old, moves)
            try:
                return match.group(1) + "./" + new.relative_to(base).as_posix() + match.group(3) if new != old else match.group(0)
            except ValueError:
                return match.group(0)
        fixed = PYTHON_FILE_RE.sub(fix, text)
        if fixed != text:
            ttl.write_text(fixed, encoding="utf-8")

    def _run(self, moves, ttls, shown: Path, package=None, name_tf=lambda n: n, prepare=None):
        before = self._concept_keys(ttls)  # the keys the canvas knows, read before anything changes
        try:
            if prepare:
                prepare()
            for old, new in moves:
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old), str(new))
            if package:
                self.pm.rename_package_source(*package)
        except OSError as e:
            return False, f"Could not complete the operation: {e}"
        key_map = {}
        for old_ttl, concepts in before.items():
            new_ttl = _remap(old_ttl, moves)
            if not new_ttl.is_file():
                continue
            self._rewrite_python_files(new_ttl, moves)
            after = {c.name: c.key for c in self._concept_keys([new_ttl])[new_ttl]}
            for concept in concepts:
                new_key = after.get(name_tf(concept.name))
                if new_key and new_key != concept.key:
                    key_map[concept.key] = new_key
        self.pm.remap_concept_keys(key_map)
        return True, str(shown)
