# CodeP Bench

**Projects. Versions. Local runs.**

CodeP Bench is a lightweight, command-driven desktop workspace manager
for developers. Built with Python and PySide6, it helps you create
projects, keep numbered local snapshots, open the active version in
Visual Studio Code, run Python files, and preview web projects through a
local HTTP server.

> **Platform:** Windows-first. HTTP preview is supported; HTTPS is not
> enabled in the current build.

## Contents

-   [Features](#features)
-   [Requirements](#requirements)
-   [Installation](#installation)
-   [First launch](#first-launch)
-   [Commands](#commands)
-   [Project and version model](#project-and-version-model)
-   [Settings](#settings)
-   [Troubleshooting](#troubleshooting)
-   [Limitations](#limitations)
-   [Project structure](#project-structure)
-   [Contributing](#contributing)

## Features

-   Command-driven workflow with quick-action buttons.
-   Global `Ctrl + Alt + Space` shortcut on Windows.
-   System tray menu to reopen the dashboard, open the workspace, or
    exit.
-   Numbered versions (`v1`, `v2`, `v3`, ...) with active-version
    tracking.
-   Visual Studio Code integration.
-   Python execution in a separate console, keeping output and errors
    visible.
-   Local HTTP server for browser previews.
-   Project-name validation and checks that run targets stay inside the
    active version.
-   Excludes common generated folders from version copies, including
    `.venv`, `venv`, `__pycache__`, `node_modules`, and `.git`.

## Requirements

-   Windows 10 or Windows 11 recommended.
-   Python 3.9 or newer.
-   `pip`.
-   Visual Studio Code for the editor-opening commands.
-   A web browser for HTML previews.

Make sure Python is available in your terminal. When installing Python
on Windows, enable its PATH option if offered.

## Installation

### 1. Get the source

Clone your published repository (replace the example URL if your
repository URL differs):

``` powershell
git clone https://github.com/PratyayCodes/Bench.git
cd Bench
```

Alternatively, download the repository as a ZIP and extract it.

### 2. Create a virtual environment

``` powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt:

``` bat
.venv\Scripts\activate.bat
```

### 3. Install dependencies

``` powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

CodeP Bench uses **PySide6** for its desktop UI. If `requirements.txt`
is not included in your checkout yet, install it directly:

``` powershell
python -m pip install PySide6
```

### 4. Launch

``` powershell
python main.py
```

On first launch, select a workspace folder. For example:

``` text
C:\Users\YourUser\Workspace
```

This is where Bench-managed projects will be stored. Keep the workspace
separate from the application source directory if you want to update or
clone the application without touching your projects.

## First launch

1.  Run `python main.py`.
2.  Choose a workspace directory when prompted.
3.  Open the dashboard with `Ctrl + Alt + Space` or from the system
    tray.
4.  Enter `Help` to display supported commands.
5.  Try `Create DemoProject`.

If the shortcut cannot be registered, another application may already
use it. You can still open Bench from its tray icon.

## Commands

Commands are case-insensitive. Put double quotes around project names
containing spaces, such as `Create "My Web Project"`.

  -----------------------------------------------------------------------
  Command                             What it does
  ----------------------------------- -----------------------------------
  `Help`                              Lists available commands.

  `Create <name>`                     Creates a project with `v1` and
                                      attempts to open it in VS Code.

  `Version <name>`                    Copies the active version into the
                                      next numbered version.

  `Versions <name>`                   Lists versions, paths, and the
                                      active version.

  `Open <name>`                       Opens the active version in VS
                                      Code.

  `Run <name> <file.py>`              Runs a Python file in a separate
                                      console.

  `Run <name> http <file.html>`       Serves the active version over
                                      local HTTP and opens the page.

  `Run <name> https <file.html>`      Not enabled in the current build.

  `Stop <name>`                       Stops the process tracked for that
                                      project.
  -----------------------------------------------------------------------

### Examples

**Create a project**

``` text
Create NomadFS
```

Bench creates a project folder, a `versions/v1/` directory, and
`project.json`. If VS Code is available, it attempts to open `v1`.

**Create a new version**

``` text
Version NomadFS
```

Bench copies the current active version into the next unused numbered
version and updates the active-version setting only after the copy
succeeds. Common generated folders and files are skipped, including
`.venv`, `venv`, `__pycache__`, `node_modules`, `.git`, `.DS_Store`, and
`Thumbs.db`. Symbolic links are skipped.

**List or open versions**

``` text
Versions NomadFS
Open NomadFS
```

**Run Python**

``` text
Run NomadFS main.py
Run NomadFS src\main.py
```

The target path is relative to the active version. The Python console
stays open after the script exits so you can inspect its output and exit
code.

**Preview a website over HTTP**

``` text
Run NomadFS http index.html
Run NomadFS http pages\index.html
```

Bench starts a local server bound to `127.0.0.1` and opens the requested
page in your browser. This is intended for local development, not public
hosting.

**Open HTML directly**

``` text
Run NomadFS index.html
```

Without an explicit server mode, HTML opens directly in the browser
using a `file://` URL. Some browser APIs may require HTTP instead.

**Stop a process**

``` text
Stop NomadFS
```

Use this to stop a Python process or HTTP server started and tracked by
Bench.

### Window and tray behavior

-   Clicking the dashboard's close button hides it; the tray application
    remains running.
-   Press `Esc` to hide the dashboard.
-   Use `Ctrl + Alt + Space` or the tray menu to reopen it.
-   Choose **Open Workspace** from the tray menu to open the configured
    folder.
-   Choose **Exit** to quit. If Bench-tracked processes are still
    running, it asks whether to stop them first.

## Project and version model

A typical project looks like this:

``` text
CodePWorkspace/
└── NomadFS/
    ├── project.json
    └── versions/
        ├── v1/
        ├── v2/
        └── v3/
```

`project.json` stores which version is active:

``` json
{
  "active_version": "v1"
}
```

The version folders contain the actual project files. Bench discovers
numbered version folders from disk and uses the active-version value
when opening or running the project.

**Important:** a version is a local copy, not a Git commit. Creating a
version copies the active version; it does not merge changes from older
versions. Earlier version folders remain in place, but this is not a
substitute for an independent backup or source control.

## Settings

On Windows, Bench stores its workspace setting at:

``` text
%LOCALAPPDATA%\CodePCommand\settings.json
```

Projects are stored in the workspace you select. A lock file in the
application settings directory helps prevent multiple Bench instances
from running at once.

## Troubleshooting

### `No module named PySide6`

Activate the virtual environment and install dependencies:

``` powershell
python -m pip install -r requirements.txt
```

Or install PySide6 directly:

``` powershell
python -m pip install PySide6
```

### The global shortcut does not work

Try the tray icon. Another application may already have registered
`Ctrl + Alt + Space`; check the dashboard output for a registration
warning.

### VS Code does not open

In a new terminal, run:

``` powershell
where.exe code
```

If Windows cannot find the command, enable VS Code's command-line/PATH
integration, restart Bench, and try again.

### A project cannot be created

Check that the workspace exists and is writable, the name follows the
naming rules, and a folder with that name does not already exist. Bench
does not overwrite existing projects.

### A file cannot be run

Confirm the file exists inside the active version and use a relative
path. Supported targets are Python files and HTML files; use explicit
`http` mode for local hosting.

### The browser preview does not load

Check the dashboard output for the local URL and server status. Refresh
if the server was slow to respond. If the server exited or the port
could not be used, try the command again.

### Bench reports that another instance is running

First confirm that no Bench process is still running. Only then consider
removing a stale `bench.lock` file from `%LOCALAPPDATA%\CodePCommand`.

## Limitations

-   Windows is the primary target; the global shortcut is Windows-only.
-   HTTPS mode is intentionally not implemented yet because it requires
    certificate/key handling.
-   Bench tracks only processes it launches during the current run; it
    is not a general-purpose process manager.
-   Version folders are local copies, not Git branches or commits.
-   VS Code commands depend on its command-line launcher being available
    on `PATH`.
-   Bench runs Python using the interpreter that launched Bench; it does
    not automatically create or select a separate environment for each
    project.

## Project structure

``` text
CodeP-Bench/
├── main.py           # Startup, tray menu, global shortcut, single-instance lock
├── dashboard.py      # Dashboard UI and command dispatch
├── branding.py       # Shared colours and generated app icon
├── projects.py       # Workspace settings, validation, version management, VS Code launch
├── servers.py        # Python execution, HTTP preview, process tracking
├── requirements.txt  # Python dependencies
└── README.md         # Project documentation
```

## Contributing

Bug reports and focused improvements are welcome.

1.  Describe the issue or proposal clearly.
2.  Keep changes consistent with the project's lightweight,
    command-driven approach.
3.  Test on Windows, especially global hotkeys, tray behavior,
    subprocess handling, and paths containing spaces.
4.  Include reproduction steps for bugs and screenshots for UI changes
    when useful.

Before submitting a change, test project creation, version creation,
version listing, opening in VS Code, running Python, HTTP preview,
stopping processes, and exiting from the tray.
