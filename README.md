# GSC IDE

A standalone PyQt6 editor for writing, linting, navigating, and deploying GSC scripts for Plutonium-supported Call of Duty titles.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Overview

GSC IDE is built for fast Plutonium script work: open multiple scripts, jump through functions, insert common GSC patterns, lint as you type, and deploy the active tab into the correct Plutonium scripts folder.

It is intentionally a desktop tool, not a web app. The UI stays close to a traditional IDE: menu bar, toolbar, tabs, line numbers, symbol navigation, output console, and deployment controls.

## Features

- Multi-tab GSC editor with line numbers and syntax highlighting.
- Live linter for bracket, string, suspicious token, and control-character issues.
- Clickable lint output that jumps directly to the problem line and column.
- Symbols panel for `#include` entries and function declarations.
- One-click symbol navigation with double-click or Enter.
- 80+ built-in GSC snippets for lifecycle hooks, threads, HUD, dvars, weapons, FX, triggers, arrays, debug helpers, and utility patterns.
- Find and replace with wraparound search.
- Autosave and crash recovery for unsaved tabs.
- Recent files menu.
- Active-tab aware edit actions for undo, redo, cut, copy, paste, save, and close.
- Plutonium install detection.
- One-click deployment to Plutonium script folders.
- Per-game custom script path overrides from Preferences.
- Game running status indicators.

## Supported Games

The deployment panel supports these Plutonium targets:

- T6 - Call of Duty: Black Ops II
- T5 - Call of Duty: Black Ops
- T4 - Call of Duty: World at War
- IW5 - Call of Duty: Modern Warfare 3

The app writes scripts into the expected Plutonium storage layout under:

```text
%LOCALAPPDATA%\Plutonium\storage
```

You can override script paths per game from Preferences.

<<<<<<< HEAD
## Screenshots

Add screenshots before publishing the repository:

```text
docs/screenshots/editor.png
docs/screenshots/symbols-and-snippets.png
docs/screenshots/deploy-panel.png
```

Recommended first screenshot: editor open with the Symbols panel, Snippets dropdown, lint output, and deployment panel visible.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- Plutonium installed, if you want automatic deployment

Python dependencies:

```text
PyQt6>=6.6.0
psutil>=5.9.0
```

## Install From Source

Clone the repository:

```powershell
git clone <your-repo-url>
cd GSC-IDE
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
=======
## Screenshots

<img width="1480" height="1195" alt="image" src="https://github.com/user-attachments/assets/22b09270-1afe-4020-b75a-2e85b194610b" />

<img width="401" height="368" alt="image" src="https://github.com/user-attachments/assets/72f1c7bd-55ef-4b93-aec3-6beb9a16c4ca" />

<img width="406" height="464" alt="image" src="https://github.com/user-attachments/assets/7d9600a3-00e2-4395-aa2d-f9f860131695" />

<img width="363" height="206" alt="image" src="https://github.com/user-attachments/assets/13dd9bed-eac6-4715-8f40-8e6dffdc0ab3" />


## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- Plutonium installed, if you want automatic deployment

Python dependencies:

```text
PyQt6>=6.6.0
psutil>=5.9.0
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
>>>>>>> bed577f58a426bfc84e6b7f415338b2fd685298d
pip install -r requirements.txt
```

Run the app:

```powershell
python main.py
```

## Build A Windows EXE

Install PyInstaller:

```powershell
pip install pyinstaller
```

Build with the included spec file:

```powershell
pyinstaller GSC-IDE.spec
```

The built executable will be created under:

```text
dist\GSC-IDE.exe
```

## Basic Use

1. Open or create a `.gsc` file.
2. Use the Symbols panel to jump between includes and functions.
3. Insert common patterns from the Snippet dropdown.
4. Fix any lint issues shown in the lower output panel.
5. Select the target game, deployment method, and game mode.
6. Set the script name.
7. Click Deploy Script or press F5.

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+N` | New script |
| `Ctrl+O` | Open script |
| `Ctrl+S` | Save |
| `Ctrl+Shift+S` | Save as |
| `Ctrl+F` | Find |
| `Ctrl+H` | Replace |
| `Shift+F3` | Find previous |
| `Ctrl+W` | Close tab |
| `F5` | Deploy active script |
| `Ctrl+,` | Preferences |
| `Ctrl+Alt+O` | Refresh symbols |
| `Ctrl+Shift+I` | Toggle deployment panel |
| `Ctrl+Shift+O` | Toggle output panel |

## Project Layout

```text
.
|-- main.py                # PyQt6 application, editor, UI, linting, snippets
|-- injection_manager.py   # Plutonium path detection and script deployment
|-- gsc_highlighter.py     # Standalone syntax highlighter module
|-- requirements.txt       # Runtime dependencies
|-- GSC-IDE.spec           # PyInstaller build spec
|-- assets/                # App icon assets
`-- CHANGELOG.md
```

## Notes

- Direct memory injection and network injection are present as method choices, but the supported deployment path is the Plutonium scripts folder method.
- Autosave recovery files are stored in your system temp directory under `gscide_autosave`.
- This project is not affiliated with Plutonium, Activision, Treyarch, Infinity Ward, or Sledgehammer Games.

## Roadmap

- Project folder explorer.
- Better GSC completion and call tips.
- Snippet search and categories.
- Configurable formatter rules.
- Theme preferences.
- Release builds with signed Windows binaries.

## Contributing

Issues and pull requests are welcome. Keep changes focused, test the app before submitting, and avoid broad rewrites unless they remove real complexity.

Before opening a pull request:

```powershell
python -m py_compile main.py injection_manager.py gsc_highlighter.py
```

## License

MIT. See [LICENSE](LICENSE).
