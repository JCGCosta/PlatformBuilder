import json
import shutil
from pathlib import Path
from core.schemas.ProjectSchema import ProjectSchema

CONCEPTS_FOLDER = "concept_packages"  # inside the project folder

SETTINGS_FOLDER = Path(str(Path.cwd()) + '/settings/')

class ProjectManager():
    def __init__(self):
        self.proj_data = None
        self.proj_file_path = None
        self.session_data = None
        self.key_map = {}  # concept keys changed by renames/moves, to bring the canvas (not yet saved) up to date
        self.session_file = Path(str(SETTINGS_FOLDER) + '/session.json')
        
        if not self.session_file.is_file():
            SETTINGS_FOLDER.mkdir(parents=True, exist_ok=True)
            self._create_clear_session_file() 

    def _create_clear_session_file(self):
        with open(self.session_file, "w") as f:
            json.dump({
                "last_project": {
                    "name": "",
                    "dir_path": ""
                }
            }, f, indent=2)

    def _update_session_data(self, proj_name: str, proj_path: str):
        last = self.session_data["last_project"]
        if (last["name"], last["dir_path"]) != (proj_name, proj_path):
            last.pop("canvas_view", None)  # the canvas position belongs to the project it was saved for
        last["name"] = proj_name
        self.session_data["last_project"]["dir_path"] = proj_path
        with open(self.session_file, "w") as f:
            json.dump(self.session_data, f, indent=2)

    def get_canvas_view(self):
        """The (x, y) scroll position of the canvas when the project was last used, (0, 0) if unknown."""
        view = (self.session_data or {}).get("last_project", {}).get("canvas_view", {})
        try:
            return int(view.get("x", 0)), int(view.get("y", 0))
        except (TypeError, ValueError, AttributeError):
            return 0, 0

    def save_canvas_view(self, x: int, y: int):
        if self.session_data is None or not self.have_active_project():
            return
        self.session_data["last_project"]["canvas_view"] = {"x": x, "y": y}
        with open(self.session_file, "w") as f:
            json.dump(self.session_data, f, indent=2)

    def _load_project_data(self):
        try:
            with open(Path(self.proj_file_path)) as f:
                self.proj_data = json.load(f)
            return True
        except:
            return False

    def _update_proj_path_with_session_data(self):
        self.proj_file_path = Path(self.get_proj_dir_path() + f"/{self.get_proj_name().replace(' ', '_')}.pbproj")

    def have_active_project(self):
        if self.session_data["last_project"]["name"] != "":
            return True
        return False

    def get_proj_name(self):
        return self.session_data["last_project"]["name"]
    
    def get_proj_dir_path(self):
        return self.session_data["last_project"]["dir_path"]

    def get_proj_info(self):
        return self.proj_data

    def load_session(self):
        try:
            with open(Path(self.session_file)) as f:
                self.session_data = json.load(f)
            if not self.get_proj_name(): return True, ""
            self._update_proj_path_with_session_data()
            if not self._load_project_data():
                self._create_clear_session_file()
                return False, f"Error in loading project ({self.get_proj_name()}) info, from \"{self.get_proj_dir_path()}\", the project file (.pbproj) is missing!"
            self._migrate_concepts_sources()
            return True, self.session_data["last_project"]["name"]
        except:
            return False, ""

    def new_project(self, dir_path: str):
        proj_name = dir_path.split('/')[-1]
        self._update_session_data(proj_name=proj_name, proj_path=dir_path)
        self._update_proj_path_with_session_data()
        if not any(Path(dir_path).iterdir()):
            self.proj_data = {
                    "project_info": {
                        "name": self.get_proj_name(),
                        "dir_path": self.get_proj_dir_path()
                    },
                    "concepts_sources": [],
                    "active_concepts": [],
                    "connections": []
                }
            with open(self.proj_file_path, "w") as f:
                json.dump(self.proj_data, f, indent=2)
            return True, proj_name
        else:
            return False, "The folder must be empty to create a new project."

    def save_project(self, active_concepts: list, connections: list):
        """active_concepts: [{"key", "x", "y"}]; connections: [{"src", "out", "dst", "in"}] wired in the canvas."""
        if self.proj_data is None:
            return False, "There is no active project."
        self.proj_data["active_concepts"] = active_concepts
        self.proj_data["connections"] = connections
        if Path(self.proj_file_path).is_file():
            with open(Path(self.proj_file_path), "w") as f:
                json.dump(self.proj_data, f, indent=2)
        else:
            return False, f"The project file is missing!"
        return True, ""

    def load_project(self, pbproj_path: str):
        try:
            with open(Path(pbproj_path)) as f:
                self.proj_data = json.load(f)
                ProjectSchema.model_validate(self.proj_data)
        except Exception as e:
            return False, f"The project file is currupted or missing some critical information! ({e})"
        # The folder where the .pbproj is now is the project folder (the project may have been moved/copied)
        self.proj_data["project_info"]["dir_path"] = str(Path(pbproj_path).resolve().parent)
        self._update_session_data(self.proj_data["project_info"]["name"], self.proj_data["project_info"]["dir_path"])
        self._update_proj_path_with_session_data()
        self._load_project_data()
        self._migrate_concepts_sources()
        return True, self.get_proj_name()
    
    def _write_project_file(self):
        with open(self.proj_file_path, "w") as f:
            json.dump(self.proj_data, f, indent=2)

    def resolve_concepts_source(self, source: str) -> Path:
        """concepts_sources are relative to the project folder (absolute ones are kept for old projects)."""
        path = Path(source)
        return path if path.is_absolute() else Path(self.get_proj_dir_path()) / path

    def add_concepts_package(self, folder: str):
        """Copies the concept package folder into the project folder and registers it (relative path) in the .pbproj.
        Returns (ok, project_copy_path_or_error). Adding a package that is already in the project refreshes its copy."""
        if self.proj_data is None:
            return False, "There is no active project."
        try:
            proj_dir = Path(self.get_proj_dir_path()).resolve()
            src = Path(folder).resolve()
            if src == proj_dir or src in proj_dir.parents:
                return False, "The concept package folder cannot contain the project folder."
            if proj_dir in src.parents:  # already inside the project, nothing to copy
                dest = src
            else:
                dest = proj_dir / CONCEPTS_FOLDER / src.name
                shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            rel = dest.relative_to(proj_dir).as_posix()
            if rel not in self.proj_data["concepts_sources"]:
                self.proj_data["concepts_sources"].append(rel)
            self._write_project_file()
            return True, str(dest)
        except Exception as e:
            return False, f"Error in adding the concept package to the project: {e}"

    def create_package(self, name: str):
        """Creates an empty package inside the project and registers it.
        Returns (ok, package_path_or_error)."""
        if self.proj_data is None:
            return False, "There is no active project."
        package_dir = Path(self.get_proj_dir_path()) / CONCEPTS_FOLDER / name
        if package_dir.exists():
            return False, f"The package '{name}' already exists."
        try:
            package_dir.mkdir(parents=True)
            rel = package_dir.relative_to(self.get_proj_dir_path()).as_posix()
            if rel not in self.proj_data["concepts_sources"]:
                self.proj_data["concepts_sources"].append(rel)
            self._write_project_file()
            return True, str(package_dir)
        except Exception as e:
            return False, f"Error in creating the package: {e}"

    def rename_package_source(self, old: str, new: str):
        self.proj_data["concepts_sources"] = [Path(x).with_name(new).as_posix() if Path(x).name == old else x
                                              for x in self.proj_data["concepts_sources"]]
        self._write_project_file()

    def remap_concept_keys(self, key_map: dict):
        """Applies renamed/moved concept keys to the saved project and remembers them for the canvas in memory."""
        for old, new in self.key_map.items():  # a concept renamed again before the canvas was updated
            self.key_map[old] = key_map.get(new, new)
        self.key_map.update({k: v for k, v in key_map.items() if k not in self.key_map})
        self.proj_data["active_concepts"], self.proj_data["connections"] = self.translate_keys(
            self.proj_data.get("active_concepts", []), self.proj_data.get("connections", []), key_map)
        self._write_project_file()

    @staticmethod
    def translate_keys(placed: list, connections: list, key_map: dict):
        """The placed concepts and connections with their concept keys replaced according to key_map."""
        return ([{**p, "key": key_map.get(p.get("key"), p.get("key"))} for p in placed],
                [{**c, "src": key_map.get(c["src"], c["src"]), "dst": key_map.get(c["dst"], c["dst"])} for c in connections])

    def package_dir(self, package: str) -> Path:
        return next(self.resolve_concepts_source(x) for x in self.proj_data["concepts_sources"] if Path(x).name == package)

    def list_groups(self, package: str) -> list:
        """The subfolders of a package, which hold the concepts."""
        return sorted(d.name for d in self.package_dir(package).iterdir() if d.is_dir() and d.name != "__pycache__")

    def create_group(self, package: str, name: str):
        group_dir = self.package_dir(package) / name
        if group_dir.exists():
            return False, f"The folder '{name}' already exists in {package}."
        try:
            group_dir.mkdir(parents=True)
            return True, str(group_dir)
        except Exception as e:
            return False, f"Error in creating the folder: {e}"

    def remove_package(self, package: str):
        """Deletes the package folder from the project and unregisters it. Returns (ok, error)."""
        if self.proj_data is None:
            return False, "There is no active project."
        try:
            package_dir = self.package_dir(package).resolve()
            if Path(self.get_proj_dir_path()).resolve() in package_dir.parents:  # never delete outside the project
                shutil.rmtree(package_dir, ignore_errors=False)
            self.proj_data["concepts_sources"] = [x for x in self.proj_data["concepts_sources"] if Path(x).name != package]
            self._write_project_file()
            return True, ""
        except Exception as e:
            return False, f"Error in removing the package: {e}"

    def remove_folder(self, folder: str):
        """Deletes a folder inside a package of the project (the package itself is removed with remove_package)."""
        try:
            folder = Path(folder).resolve()
            proj_dir = Path(self.get_proj_dir_path()).resolve()
            packages = [self.resolve_concepts_source(x).resolve() for x in self.proj_data["concepts_sources"]]
            if proj_dir not in folder.parents or not any(p in folder.parents for p in packages):
                return False, "Only folders inside a package of the project can be removed."
            shutil.rmtree(folder)
            return True, ""
        except Exception as e:
            return False, f"Error in removing the folder: {e}"

    def list_packages(self) -> list:
        """Names of the packages registered in the project (folders that exist)."""
        return [Path(x).name for x in self.proj_data.get("concepts_sources", [])
                if self.resolve_concepts_source(x).is_dir()] if self.proj_data else []

    def _migrate_concepts_sources(self):
        """Old projects stored absolute paths to the packages; copy those into the project and store relative ones."""
        sources = self.proj_data.get("concepts_sources", [])
        if not any(Path(x).is_absolute() for x in sources):
            return
        self.proj_data["concepts_sources"] = []
        for source in sources:
            if not Path(source).is_absolute():
                self.proj_data["concepts_sources"].append(source)
            elif Path(source).is_dir():
                self.add_concepts_package(source)
            else:
                self.proj_data["concepts_sources"].append(source)  # missing, reported when the project is restored
        self._write_project_file()
