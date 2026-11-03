import importlib.util
import os
import shlex
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional

from core.catalog import Concept, ComposedBusinessModel
from core.ui_generator import UIGenerator

PLATFORM_ROOT = Path(__file__).resolve().parents[2]
ENGINE_UI_DIR = PLATFORM_ROOT / "OntologyToUI"

# The UI runs in the browser at another origin and calls every endpoint of a pipeline from there, so the API allows it
RUN_API_TEMPLATE = '''
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from OntologyToAPI.core.APIGenerator import APIGenerator

if __name__ == "__main__":
    APIGen = APIGenerator(showLogs=False)
    APIGen.load_ontologies(paths={paths!r})
    APIGen.serialize_ontologies()
    api_app = APIGen.generate_api_routes()
    api_app.add_middleware(CORSMiddleware, allow_origins={origins!r}, allow_methods=["*"], allow_headers=["*"])
    uvicorn.run(api_app, host={host!r}, port={port})
'''


class EngineIntegration:
    def __init__(self, output_dir=PLATFORM_ROOT / "src" / "generated"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.api_process: Optional[subprocess.Popen] = None
        self.ui_process: Optional[subprocess.Popen] = None

    @staticmethod
    def _alive(process: Optional[subprocess.Popen]) -> bool:
        return process is not None and process.poll() is None

    def is_running(self) -> bool:
        return self._alive(self.api_process) or self._alive(self.ui_process)

    @staticmethod
    def _terminate(process: Optional[subprocess.Popen]):
        if not EngineIntegration._alive(process):
            return
        if os.name == "posix" and os.getpgid(process.pid) == process.pid:
            os.killpg(process.pid, signal.SIGTERM)  # the UI runs in its own session (a shell with npm and node under it)
        elif os.name == "posix":
            process.terminate()
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
        process.wait()

    def stop(self):
        self._terminate(self.api_process)
        self._terminate(self.ui_process)
        self.api_process = self.ui_process = None

    def _copy_concept_files(self, concept: Concept) -> str:
        """Copies the concept's .ttl and .py as they are into the output dir, keeping the paths the .ttl refers to
        (OntologyToAPI resolves hasPythonFile against the working directory). Returns the copied .ttl path (relative)."""
        package_dir = Path(concept.package_dir)
        python_rel = Path(concept.python_file)
        for base in (package_dir.parent, package_dir, Path(concept.ttl_path).parent):
            if (base / python_rel).is_file():
                dest = self.output_dir / python_rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(base / python_rel, dest)
                break
        else:
            raise FileNotFoundError(f"{concept.name}: python file '{concept.python_file}' not found")
        ttl_rel = Path(concept.ttl_path).relative_to(package_dir.parent)
        (self.output_dir / ttl_rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(concept.ttl_path, self.output_dir / ttl_rel)
        return f"./{ttl_rel.as_posix()}"

    def run_engines(self, business_models: List[ComposedBusinessModel], log_callback: Callable = print,
                    api_host: str = "127.0.0.1", api_port: int = 5000, ui_host: str = "127.0.0.1", ui_port: int = 3000,
                    ui_settings: Optional[dict] = None) -> bool:
        concepts = {c.key: c for bm in business_models for c in bm.concepts}
        if not concepts:
            log_callback("There are no concepts in the canvas.")
            return False

        # 1. OntologyToAPI: one endpoint per concept, straight from the package's own .ttl/.py
        try:
            ttl_paths = sorted({self._copy_concept_files(c) for c in concepts.values()})
        except FileNotFoundError as e:
            log_callback(str(e))
            return False
        run_api = self.output_dir / "runAPI.py"
        origins = sorted({f"http://{h}:{ui_port}" for h in (ui_host, "localhost", "127.0.0.1")})
        run_api.write_text(RUN_API_TEMPLATE.format(paths=ttl_paths, origins=origins, host=api_host, port=api_port))
        log_callback(f"API runner written to {run_api}")
        if importlib.util.find_spec("OntologyToAPI") is None:
            log_callback("The 'ontologytoapi' package is not installed (pip install ontologytoapi); run the runner manually after installing it.")
        else:
            self.stop()
            self.api_process = subprocess.Popen([sys.executable, str(run_api)], cwd=self.output_dir)
            log_callback(f"API started at http://{api_host}:{api_port}/docs")

        # 2. OntologyToUI: one view per business model, run as a sequence of calls to the endpoints above
        api_url = f"http://{'127.0.0.1' if api_host in ('0.0.0.0', '') else api_host}:{api_port}"
        return self._run_ui(business_models, api_url, log_callback, ui_host, ui_port, ui_settings)

    def _run_ui(self, business_models: List[ComposedBusinessModel], api_url: str, log_callback: Callable,
                ui_host: str, ui_port: int, ui_settings: Optional[dict] = None) -> bool:
        ui_dir = self.output_dir / "ui"
        try:
            views = UIGenerator(ui_dir, ENGINE_UI_DIR).generate(business_models, api_url, ui_settings)
        except FileNotFoundError as e:
            log_callback(str(e))
            return False
        log_callback(f"UI generated at {ui_dir} with {len(views)} view(s): {', '.join(views)}")
        npm = shutil.which("npm")
        if npm is None:
            log_callback("npm was not found; install Node.js and run 'npm install && npm run dev' in the UI folder.")
            return True
        # npm install only runs when something is missing, and in the background (the first run downloads packages)
        steps = []
        if not (ENGINE_UI_DIR / "node_modules").is_dir():
            steps.append([npm, "--prefix", str(ENGINE_UI_DIR), "install", "--no-audit", "--no-fund"])
        if not (ui_dir / "node_modules" / ".package-lock.json").is_file() or \
                (ui_dir / "package.json").stat().st_mtime > (ui_dir / "node_modules" / ".package-lock.json").stat().st_mtime:
            steps.append([npm, "install", "--no-audit", "--no-fund"])
        steps.append([npm, "run", "dev", "--", "--host", ui_host, "--port", str(ui_port), "--strictPort"])
        command = " && ".join(shlex.join(step) if os.name == "posix" else subprocess.list2cmdline(step) for step in steps)
        self._terminate(self.ui_process)
        log_file = open(ui_dir / "ui.log", "w")
        self.ui_process = subprocess.Popen(command, shell=True, cwd=ui_dir, stdout=log_file, stderr=subprocess.STDOUT,
                                           start_new_session=os.name == "posix")
        log_callback(f"UI starting at http://{ui_host}:{ui_port} (progress in {ui_dir / 'ui.log'})")
        return True
