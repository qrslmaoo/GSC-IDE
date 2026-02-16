# GSC IDE - Python Edition

A modern, standalone IDE for writing and deploying GSC (Game Script) scripts to Call of Duty games via the Plutonium launcher.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- 🎨 Modern Dark Theme UI
- 📝 Syntax highlighting for GSC
- 🚀 One-click deployment to Plutonium (where applicable)
- 🎮 Multi-game support: T6, T5, T4, IW5
- 🗂️ Multi-tab editor (edit multiple scripts at once)
- 💾 Autosave & crash-recovery (experimental): unsaved edits are periodically written to a temp folder for recovery
- 🐞 Simple linter with clickable errors and editor underlines

## Installation

1. Install Python 3.10+ (from python.org)

2. Clone the repository:

```bash
git clone https://github.com/yourusername/gsc-ide-python.git
cd gsc-ide-python
```

3. (Recommended) Create a virtual environment and install dependencies:

```bash
python -m venv .venv
\.venv\Scripts\activate      
pip install -r requirements.txt
```

4. Run the app:

```bash
python main.py
```

### Notes
- On Windows the app attempts to detect Plutonium in the expected %localappdata%\Plutonium\storage path. You can override paths via Preferences.
- Autosave files are written to your system temp directory under a `gscide_autosave` folder. The recovery feature is experimental.

If you want changes or a more detailed CONTRIBUTING section, tell me what to add.


