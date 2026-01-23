import os
from pathlib import Path
from enum import IntEnum
import psutil


class TargetGame(IntEnum):
    PLUTONIUM_T6 = 0
    PLUTONIUM_T5 = 1
    PLUTONIUM_T4 = 2
    PLUTONIUM_IW5 = 3


class InjectionMethod(IntEnum):
    PLUTONIUM_SCRIPTS = 0
    DIRECT_MEMORY = 1
    NETWORK = 2


class GameMode(IntEnum):
    MULTIPLAYER = 0
    ZOMBIES = 1
    BOTH = 2


class InjectionManager:
    def __init__(self):
        self.plutonium_path = self.get_plutonium_path()
        # optional overrides provided by UI (map TargetGame -> base path)
        self.custom_paths = {}

    def set_custom_paths(self, overrides: dict):
        """Provide custom base paths per TargetGame.

        overrides: dict where keys are TargetGame members and values are string paths.
        """
        if not overrides:
            self.custom_paths = {}
            return
        self.custom_paths = {}
        for k, v in overrides.items():
            try:
                self.custom_paths[int(k)] = str(v) if v else None
            except Exception:
                # allow passing TargetGame directly
                try:
                    self.custom_paths[k] = str(v) if v else None
                except Exception:
                    pass
    
    def get_plutonium_path(self):
        """Get Plutonium installation path from %localappdata%"""
        localappdata = os.getenv('LOCALAPPDATA')
        if not localappdata:
            return None
        
        plut_path = Path(localappdata) / "Plutonium" / "storage"
        if plut_path.exists():
            return str(plut_path)
        return None
    
    def get_script_path(self, game: TargetGame, mode: GameMode):
        """Get the scripts folder path for the given game and mode"""
        if not self.plutonium_path:
            return None
        # if overrides exist for this game, prefer them
        base = Path(self.plutonium_path) if self.plutonium_path else None
        override = None
        try:
            override = self.custom_paths.get(game)
        except Exception:
            override = None
        if override:
            # if override path is absolute, use it as base; otherwise try relative to plutonium_path
            ov = Path(override)
            if ov.is_absolute():
                base = ov
            else:
                if base:
                    base = base / ov
                else:
                    base = ov
        if not base:
            return None

        # Map each game to its mode-specific script folder structure
        paths = {
            TargetGame.PLUTONIUM_T6: {
                GameMode.MULTIPLAYER: base / "t6" / "scripts" / "mp",
                GameMode.ZOMBIES: base / "t6" / "scripts" / "zm",
                GameMode.BOTH: base / "t6" / "scripts",
            },
            # BO1 (t5) uses the 'raw/scripts' layout
            TargetGame.PLUTONIUM_T5: {
                GameMode.MULTIPLAYER: base / "t5" / "raw" / "scripts" / "mp",
                GameMode.ZOMBIES: base / "t5" / "raw" / "scripts" / "zm",
                GameMode.BOTH: base / "t5" / "raw" / "scripts",
            },
            TargetGame.PLUTONIUM_T4: {
                GameMode.MULTIPLAYER: base / "t4" / "scripts" / "mp",
                GameMode.ZOMBIES: base / "t4" / "scripts" / "zm",
                GameMode.BOTH: base / "t4" / "scripts",
            },
            TargetGame.PLUTONIUM_IW5: {
                GameMode.MULTIPLAYER: base / "iw5" / "scripts" / "mp",
                GameMode.ZOMBIES: base / "iw5" / "scripts" / "zm",
                GameMode.BOTH: base / "iw5" / "scripts",
            },
        }

        game_paths = paths.get(game)
        if not game_paths:
            return None

        target_path = game_paths.get(mode, game_paths.get(GameMode.BOTH))

        try:
            target_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            # If creation fails return string path anyway
            return str(target_path)

        return str(target_path)
    
    def inject_script(self, script: str, game: TargetGame, method: InjectionMethod, 
                     mode: GameMode, script_name: str):
        """Deploy script to Plutonium"""
        if method == InjectionMethod.PLUTONIUM_SCRIPTS:
            return self._inject_plutonium(script, game, mode, script_name)
        elif method == InjectionMethod.DIRECT_MEMORY:
            return False, "Direct memory injection not recommended for Plutonium. Use Scripts method."
        elif method == InjectionMethod.NETWORK:
            return False, "Network injection coming soon for console modding."
        else:
            return False, "Unknown injection method"
    
    def _inject_plutonium(self, script: str, game: TargetGame, mode: GameMode, script_name: str):
        """Write script to Plutonium scripts folder"""
        script_path = self.get_script_path(game, mode)
        
        if not script_path:
            return False, "Plutonium not found. Install Plutonium first."
        
        # Ensure .gsc extension
        if not script_name.endswith('.gsc'):
            script_name += '.gsc'
        
        full_path = Path(script_path) / script_name
        
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(script)
            return True, f"Script deployed successfully to:\n{full_path}"
        except Exception as e:
            return False, f"Failed to write script: {str(e)}"
    
    def is_game_running(self, game: TargetGame):
        """Check if the game is currently running"""
        process_names = {
            TargetGame.PLUTONIUM_T6: ["plutonium-bootstrapper-win32.exe", "t6mp.exe", "t6zm.exe"],
            TargetGame.PLUTONIUM_T5: ["plutonium-bootstrapper-win32.exe", "t5mp.exe", "t5zm.exe"],
            TargetGame.PLUTONIUM_T4: ["plutonium-bootstrapper-win32.exe", "t4mp.exe", "t4zm.exe"],
            TargetGame.PLUTONIUM_IW5: ["plutonium-bootstrapper-win32.exe", "iw5mp.exe"]
        }
        
        target_processes = process_names.get(game, [])
        running_processes = [p.name() for p in psutil.process_iter(['name'])]
        
        return any(proc in running_processes for proc in target_processes)
