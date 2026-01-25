# Changelog

All notable changes to this project will be documented in this file.

The format is based on "Keep a Changelog" and adheres to Semantic Versioning.

## [Unreleased]

### Fixed

- Fix crash when opening the Find/Replace UI or clicking the Find icon by implementing `find_next()` and `show_find()` in [main.py](main.py). This prevents an AttributeError that caused the whole application to exit when the Find widget was invoked.
- Ensure the Replace button is wired safely to `replace_one()` and the Find widget can be opened via menu/toolbar shortcuts without crashing.

### Audited

- Scanned signal handlers and UI callback connections across the codebase to catch other missing handlers; no additional missing callbacks were found.
- Performed a quick static check on `main.py` to verify there are no syntax errors after the fix.

### Notes

- Low-risk change. Recommended follow-up: commit the change, add this entry to the release notes for the next tag (e.g. `v1.0.1`), and create a GitHub release.


## [1.0.0] - 2025-xx-xx

- Initial public release.

### Details (what changed)

- Files modified:
	- `main.py` — added `find_next()` and `show_find()`; hardened calls to `InjectionManager` and filesystem operations to avoid uncaught exceptions (functions: `update_game_status`, `update_plutonium_path`, `deploy_script`, `open_scripts_folder`).
	- `CHANGELOG.md` — this file (updated Unreleased section).

### Verification

- Ran a quick static check on `main.py` (no syntax errors reported).
- Manually reviewed signal connections in `main.py` that refer to `self.*` handlers to ensure implementations exist.

### Release draft text (copy for GitHub release)

Fixed crash when invoking Find/Replace

This release fixes a bug where clicking the Find icon or opening the Find/Replace widget could crash the application due to missing handler methods. The update adds safe implementations for `find_next()` and `show_find()`, and hardens several external calls (injection and filesystem) against exceptions so the UI won't crash on unexpected errors.

Files changed: `main.py`, `CHANGELOG.md`.

Suggested tag: `v1.0.1` — small bugfix release.

