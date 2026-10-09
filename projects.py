import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


APP_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "CodePCommand"
SETTINGS_FILE = APP_DIR / "settings.json"
VERSION_RE = re.compile(r"^v(\d+)$", re.IGNORECASE)
EXCLUDED_DIRS = {".venv", "venv", "__pycache__", "node_modules", ".git"}
EXCLUDED_FILES = {".ds_store", "thumbs.db"}

# Project names become folder names AND end up in command lines, so keep them boring:
# letters, digits, space, dot, underscore, hyphen; must start/end with a letter, digit, _ or -.
NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9 _.\-]{0,62}[A-Za-z0-9_\-])?$")
WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
TEMP_SUFFIX = ".bench-tmp"


class BenchError(Exception):
    pass


@dataclass
class Settings:
    workspace: str = ""

    @classmethod
    def load(cls):
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        workspace = data.get("workspace", "") if isinstance(data, dict) else ""
        return cls(workspace=workspace if isinstance(workspace, str) else "")

    def save(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        temp = SETTINGS_FILE.with_suffix(".json.tmp")
        temp.write_text(json.dumps({"workspace": self.workspace}, indent=2), encoding="utf-8")
        temp.replace(SETTINGS_FILE)


def ensure_workspace(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def validate_name(name):
    if not name or not NAME_RE.match(name):
        raise BenchError(
            "Invalid project name. Use letters, digits, spaces, '.', '_' or '-' "
            "(max 64 chars, must start with a letter or digit)."
        )
    if name.lower().endswith(TEMP_SUFFIX):
        raise BenchError(f"Project names may not end with '{TEMP_SUFFIX}'.")
    if name.split(".")[0].strip().lower() in WINDOWS_RESERVED:
        raise BenchError(f"'{name}' is a reserved Windows device name.")


def workspace_path(settings):
    if not settings.workspace:
        raise BenchError("No workspace is configured.")
    path = Path(settings.workspace).expanduser().resolve()
    if not path.is_dir():
        raise BenchError("The configured workspace does not exist.")
    return path


def safe_project_path(settings, name):
    validate_name(name)
    root = workspace_path(settings)
    candidate = (root / name).resolve()
    if candidate.parent != root:
        raise BenchError("Project path must remain inside the workspace.")
    return candidate


def create_project(settings, name):
    project = safe_project_path(settings, name)
    if project.exists():
        raise BenchError(f"Project already exists: {name}")
    # Build in a temporary sibling and rename on success to avoid half-created projects.
    # Names ending in TEMP_SUFFIX are rejected, so this can never be a user's folder.
    temp = project.with_name(project.name + TEMP_SUFFIX)
    if temp.exists():
        shutil.rmtree(temp, ignore_errors=True)
    try:
        (temp / "versions" / "v1").mkdir(parents=True)
        (temp / "project.json").write_text(
            json.dumps({"active_version": "v1"}, indent=2), encoding="utf-8"
        )
        temp.rename(project)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return project / "versions" / "v1"


def read_project_config(project):
    config_path = project / "project.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BenchError(f"Cannot read project.json for {project.name}: {exc}")
    if not isinstance(config, dict):
        raise BenchError("project.json must contain a JSON object.")
    return config


def write_project_config(project, config):
    config_path = project / "project.json"
    temp = config_path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temp.replace(config_path)


def get_versions(project):
    versions_dir = project / "versions"
    if not versions_dir.is_dir():
        raise BenchError(f"Project has no versions directory: {project.name}")
    found = []
    for child in versions_dir.iterdir():
        match = VERSION_RE.match(child.name)
        if match and child.is_dir() and not child.is_symlink():
            found.append((int(match.group(1)), child))
    return sorted(found, key=lambda item: item[0])


def active_version(project):
    name = str(read_project_config(project).get("active_version", "v1"))
    # Validate the name BEFORE touching the filesystem with it (no "../" tricks via project.json).
    if VERSION_RE.match(name):
        candidate = project / "versions" / name
        if candidate.is_dir():
            return candidate
    versions = get_versions(project)
    if not versions:
        raise BenchError(f"No valid versions found for {project.name}.")
    return versions[-1][1]


def resolve_project(settings, name, active=False):
    project = safe_project_path(settings, name)
    if not project.is_dir():
        raise BenchError(f"Project not found: {name}")
    # A folder created outside Bench is not silently adopted.
    if not (project / "project.json").is_file():
        raise BenchError(f"{name} is not a CodeP Bench project.")
    if active:
        return active_version(project)
    return project


def copy_version(source: Path, destination: Path):
    def ignore(directory, names):
        ignored = []
        for name in names:
            p = Path(directory) / name
            if p.is_symlink():
                # Symlinks/junctions could escape the project or loop forever; skip them.
                ignored.append(name)
            elif p.is_dir() and name.lower() in EXCLUDED_DIRS:
                ignored.append(name)
            elif p.is_file() and name.lower() in EXCLUDED_FILES:
                ignored.append(name)
        return ignored
    shutil.copytree(source, destination, ignore=ignore)


def create_version(settings, name):
    project = resolve_project(settings, name)
    versions = get_versions(project)
    if not versions:
        raise BenchError(f"No versions found for {name}.")
    active = active_version(project)
    version_name = f"v{max(n for n, _ in versions) + 1}"
    destination = project / "versions" / version_name
    if destination.exists():
        raise BenchError(f"Version already exists: {version_name}")
    temp = project / "versions" / f".{version_name}{TEMP_SUFFIX}"
    shutil.rmtree(temp, ignore_errors=True)
    renamed = False
    try:
        copy_version(active, temp)
        temp.rename(destination)
        renamed = True
        config = read_project_config(project)
        config["active_version"] = version_name
        write_project_config(project, config)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        if renamed:
            # Config was not switched, so the new folder would be an orphan; remove it.
            shutil.rmtree(destination, ignore_errors=True)
        raise
    return project, version_name, destination


def list_versions(settings, name):
    project = resolve_project(settings, name)
    # Use the same resolution as `open`/`run` so the [ACTIVE] marker never disagrees with them.
    active = active_version(project).name
    return [(path.name, path, path.name == active) for _, path in get_versions(project)]


def open_project(path: Path):
    path = Path(path).resolve()
    # On Windows the VS Code launcher is code.cmd, which CreateProcess cannot find as plain "code".
    code = shutil.which("code.cmd") or shutil.which("code")
    if not code:
        raise BenchError(
            "VS Code command 'code' was not found. In VS Code, enable the 'code' command in PATH."
        )
    try:
        subprocess.Popen(
            [code, str(path)],
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise BenchError(f"Could not start VS Code: {exc}")
