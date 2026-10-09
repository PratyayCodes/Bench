import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote

from projects import BenchError

NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Runs the script, then waits so errors/output don't vanish when the console closes.
LAUNCHER = (
    "import subprocess, sys; "
    "code = subprocess.call([sys.executable] + sys.argv[1:]); "
    "input('\\n[Bench] Exited with code %d. Press Enter to close...' % code)"
)


class ServerManager:
    def __init__(self, output):
        self.output = output
        # lower-cased project name -> subprocess.Popen (Windows paths are case-insensitive)
        self.processes = {}

    @staticmethod
    def free_port(start=8000):
        for port in range(start, start + 1000):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise BenchError("No free local port found in the range 8000-8999.")

    @staticmethod
    def wait_for_port(port, proc, timeout=5.0):
        """Return 'ready', 'exited' or 'timeout'."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return "exited"
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return "ready"
            except OSError:
                time.sleep(0.1)
        return "timeout"

    @staticmethod
    def kill_tree(proc):
        """Kill the process and anything it spawned."""
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True, creationflags=NO_WINDOW,
            )
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            pass

    def run(self, project_name, version_path: Path, args):
        key = project_name.lower()
        existing = self.processes.get(key)
        if existing is not None:
            if existing.poll() is None:
                self.output(f"{project_name} already has a process running. Use Stop {project_name} first.")
                return
            self.processes.pop(key, None)

        args = list(args)  # never mutate the caller's list
        mode = None
        if args and args[0].lower() in {"http", "https"}:
            mode = args.pop(0).lower()
        if not args:
            raise BenchError("Specify a file. Example: Run NomadFS main.py")
        if len(args) > 1:
            raise BenchError("Run takes a single target file; extra arguments are not supported.")

        root = version_path.resolve()
        target_path = (root / args[0]).resolve()
        if not target_path.is_relative_to(root):
            raise BenchError("Run target must be inside the active version.")
        if not target_path.is_file():
            raise BenchError(f"File not found in active version: {args[0]}")

        if mode == "https":
            raise BenchError(
                "HTTPS is not enabled in this initial build. It needs a local certificate/key setup; "
                "HTTP is available with: Run <project> http <file>."
            )

        if mode == "http":
            port = self.free_port()
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                    cwd=str(root), creationflags=NEW_CONSOLE,
                )
            except OSError as exc:
                raise BenchError(f"Could not start the HTTP server: {exc}")
            state = self.wait_for_port(port, proc)
            if state == "exited":
                raise BenchError("The HTTP server exited immediately; nothing was started.")
            self.processes[key] = proc
            rel = quote(target_path.relative_to(root).as_posix())
            url = f"http://127.0.0.1:{port}/{rel}"
            self.output(f"HTTP server started for {project_name}: {url} (PID {proc.pid})")
            if state == "timeout":
                self.output("Server is slow to respond; the page may need a refresh.")
            webbrowser.open(url)
            return

        suffix = target_path.suffix.lower()
        if suffix == ".py":
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-c", LAUNCHER, str(target_path)],
                    cwd=str(root), creationflags=NEW_CONSOLE,
                )
            except OSError as exc:
                raise BenchError(f"Could not start Python: {exc}")
            self.processes[key] = proc
            self.output(f"Python process started: {target_path} (PID {proc.pid})")
            return

        if suffix in {".html", ".htm"}:
            webbrowser.open(target_path.as_uri())
            self.output(f"Opened file in browser: {target_path}")
            return

        raise BenchError(
            "Supported targets: .py files, HTML files, or explicit http mode for local hosting."
        )

    def stop(self, project_name):
        key = project_name.lower()
        proc = self.processes.get(key)
        if proc is None:
            raise BenchError(f"No process tracked for {project_name}.")
        self.processes.pop(key, None)
        if proc.poll() is not None:
            self.output(f"{project_name} is already stopped.")
            return
        self.kill_tree(proc)
        self.output(f"Stopped {project_name} (PID {proc.pid}).")

    def running_projects(self):
        return [name for name, proc in self.processes.items() if proc.poll() is None]

    def stop_all(self):
        for key in list(self.processes):
            proc = self.processes.pop(key)
            if proc.poll() is None:
                self.kill_tree(proc)
