#!/usr/bin/env python3

import time
import sys
import logging
import shutil
import argparse
import threading
import json
import os
import subprocess
import ctypes
from pathlib import Path
from typing import List, Optional

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox, filedialog
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).parent / "log_deleter_config.json"


def launch_with_elevation(exe_path: Path, working_dir: Optional[Path] = None) -> bool:
    try:
        if working_dir is None:
            working_dir = exe_path.parent
        
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            str(exe_path),
            None,
            str(working_dir),
            1
        )
        if result > 32:
            return True
        else:
            logger.error(f"ShellExecuteW failed with code: {result}")
            return False
    except Exception as e:
        logger.error(f"Failed to launch with elevation: {e}")
        return False


def launch_normal(exe_path: Path, working_dir: Optional[Path] = None) -> bool:
    try:
        if working_dir is None:
            working_dir = exe_path.parent
        
        subprocess.Popen(
            [str(exe_path)],
            cwd=str(working_dir),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        return True
    except Exception as e:
        logger.error(f"Failed to launch normally: {e}")
        return False


def find_game_installation() -> Optional[Path]:
    search_paths = []
    import string
    for drive in string.ascii_uppercase:
        search_paths.extend([
            Path(f"{drive}:\\Program Files\\Duet Night Abyss"),
            Path(f"{drive}:\\Program Files (x86)\\Duet Night Abyss"),
        ])
    
    search_paths.extend([
        Path(r"C:\Program Files\Duet Night Abyss"),
        Path(r"C:\Program Files (x86)\Duet Night Abyss"),
    ])
    search_paths.extend([
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Duet Night Abyss"),
        Path(r"D:\Steam\steamapps\common\Duet Night Abyss"),
        Path(r"E:\Steam\steamapps\common\Duet Night Abyss"),
    ])
    
    for drive in string.ascii_uppercase:
        search_paths.append(Path(f"{drive}:\\Games\\Duet Night Abyss"))
    search_paths.extend([
        Path(r"C:\Games\Duet Night Abyss"),
        Path(r"D:\Games\Duet Night Abyss"),
        Path(r"E:\Games\Duet Night Abyss"),
        Path(r"F:\Games\Duet Night Abyss"),
        Path(r"G:\Games\Duet Night Abyss"),
    ])
    
    for game_path in search_paths:
        dna_game_path = game_path / "DNA Game" / "EM" / "Saved"
        if dna_game_path.exists():
            logger.info(f"Auto-detected game installation: {game_path}")
            return game_path
    
    return None


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
    return {}


def save_config(config: dict):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save config: {e}")


def find_game_exe() -> Optional[Path]:
    game_path = find_game_installation()
    if game_path:
        em_exe = game_path / "DNA Game" / "EM.exe"
        if em_exe.exists():
            return em_exe
    
    import string
    for drive in string.ascii_uppercase:
        for base in ["Program Files", "Program Files (x86)"]:
            test_path = Path(f"{drive}:\\{base}\\Duet Night Abyss\\DNA Game\\EM.exe")
            if test_path.exists():
                return test_path
        test_path = Path(f"{drive}:\\Games\\Duet Night Abyss\\DNA Game\\EM.exe")
        if test_path.exists():
            return test_path
    
    return None


def find_ok_dna_exe() -> Optional[Path]:
    local_appdata = os.getenv('LOCALAPPDATA')
    if local_appdata:
        test_path = Path(local_appdata) / "ok-dna" / "ok-dna.exe"
        if test_path.exists():
            return test_path
    users_dir = Path(r"C:\Users")
    if users_dir.exists():
        for user_dir in users_dir.iterdir():
            if user_dir.is_dir():
                test_path = user_dir / "AppData" / "Local" / "ok-dna" / "ok-dna.exe"
                if test_path.exists():
                    return test_path
    
    return None


def get_game_path() -> str:
    config = load_config()
    if 'game_path' in config:
        config_path = Path(config['game_path'])
        if (config_path / "DNA Game" / "EM" / "Saved").exists():
            return str(config_path)
    
    detected_path = find_game_installation()
    if detected_path:
        save_config({'game_path': str(detected_path)})
        return str(detected_path)
    return r"C:\Program Files\Duet Night Abyss"


def get_game_exe_path() -> str:
    config = load_config()
    if 'game_exe_path' in config:
        exe_path = Path(config['game_exe_path'])
        if exe_path.exists():
            return str(exe_path)
    
    detected_exe = find_game_exe()
    if detected_exe:
        save_config({**config, 'game_exe_path': str(detected_exe)})
        return str(detected_exe)
    return r"C:\Program Files\Duet Night Abyss\DNA Game\EM.exe"


def get_ok_dna_exe_path() -> str:
    config = load_config()
    if 'ok_dna_exe_path' in config:
        exe_path = Path(config['ok_dna_exe_path'])
        if exe_path.exists():
            return str(exe_path)
    
    detected_exe = find_ok_dna_exe()
    if detected_exe:
        save_config({**config, 'ok_dna_exe_path': str(detected_exe)})
        return str(detected_exe)
    
    local_appdata = os.getenv('LOCALAPPDATA')
    if local_appdata:
        return str(Path(local_appdata) / "ok-dna" / "ok-dna.exe")
    return r"C:\Users\USERNAME\AppData\Local\ok-dna\ok-dna.exe"


class LogDeleter:
    
    def __init__(self, game_path: Optional[str] = None):
        if game_path is None:
            game_path = get_game_path()
        
        self.game_path = Path(game_path)
        self.saved_path = self.game_path / "DNA Game" / "EM" / "Saved"
        
        if not self.saved_path.exists():
            raise ValueError(
                f"Game installation not found at: {self.game_path}\n"
                f"Expected path: {self.saved_path}\n"
                f"Please select the correct game installation folder."
            )
        
        self.folders_to_delete: List[Path] = [
            self.saved_path / "Logs",
            self.saved_path / "PcUsdk" / "log",
            self.saved_path / "Config" / "CrashReportClient",
        ]
        
        logger.info(f"Initialized log deleter for: {self.game_path}")
        logger.info(f"Saved path: {self.saved_path}")
    
    def update_path(self, new_path: str):
        self.game_path = Path(new_path)
        self.saved_path = self.game_path / "DNA Game" / "EM" / "Saved"
        
        if not self.saved_path.exists():
            raise ValueError(f"Invalid game path: {self.saved_path} does not exist")
        
        self.folders_to_delete = [
            self.saved_path / "Logs",
            self.saved_path / "PcUsdk" / "log",
            self.saved_path / "Config" / "CrashReportClient",
        ]
        
        logger.info(f"Updated game path to: {self.game_path}")
    
    def try_delete_folder(self, folder_path: Path) -> bool:
        try:
            if folder_path.exists() and folder_path.is_dir():
                shutil.rmtree(folder_path, ignore_errors=True)
                logger.info(f"[✓] Deleted: {folder_path}")
                return True
            return False
        except PermissionError as e:
            logger.debug(f"[!] Permission denied (folder in use): {folder_path}")
            return False
        except Exception as e:
            logger.error(f"[!] Failed to delete {folder_path}: {e}")
            return False
    
    def delete_all_logs(self):
        for folder in self.folders_to_delete:
            self.try_delete_folder(folder)
    
    def delete_once(self):
        logger.info("Deleting logs once (preventive deletion)...")
        logger.info("-" * 60)
        self.delete_all_logs()
        logger.info("Deletion complete. Safe to start game.")
    
    def run_continuous(self, interval: float = 0.1, stop_event: Optional[threading.Event] = None):
        logger.info("Starting continuous log deletion...")
        logger.info(f"Deletion interval: {interval * 1000:.0f}ms")
        logger.info("Press Ctrl+C to stop")
        logger.info("-" * 60)
        
        try:
            while True:
                if stop_event and stop_event.is_set():
                    logger.info("Stopped by user")
                    break
                self.delete_all_logs()
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("\nStopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    def run_periodic(self, interval_minutes: float = 5.0, stop_event: Optional[threading.Event] = None):
        interval_seconds = interval_minutes * 60
        logger.info(f"Starting periodic log deletion (every {interval_minutes} minutes)...")
        logger.info("Press Ctrl+C to stop")
        logger.info("-" * 60)
        
        try:
            while True:
                if stop_event and stop_event.is_set():
                    logger.info("Stopped by user")
                    break
                self.delete_all_logs()
                logger.info(f"Next deletion in {interval_minutes} minutes...")
                for _ in range(int(interval_seconds)):
                    if stop_event and stop_event.is_set():
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nStopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise


class LogDeleterGUI:
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Duet Night Abyss - Log Deleter")
        self.root.geometry("700x750")
        self.root.resizable(False, False)
        
        try:
            self.deleter = LogDeleter()
        except ValueError as e:
            logger.warning(f"Initial path invalid: {e}")
            self.deleter = None
            default_path = get_game_path()
            from pathlib import Path
            self._temp_path = Path(default_path)
        
        self.stop_event = None
        self.deletion_thread = None
        self.is_running = False
        
        self._create_widgets()
        self._setup_logging()
        
        if self.deleter:
            self._validate_path(str(self.deleter.game_path))
        else:
            self.path_var.set(str(self._temp_path))
            self._validate_path(str(self._temp_path))
    
    def _create_widgets(self):
        title_label = tk.Label(
            self.root,
            text="Log Deleter for Duet Night Abyss",
            font=("Arial", 14, "bold"),
            pady=10
        )
        title_label.pack()
        
        path_frame = tk.LabelFrame(self.root, text="Game Installation Path", padx=10, pady=10)
        path_frame.pack(pady=5, padx=10, fill="x")
        
        path_input_frame = tk.Frame(path_frame)
        path_input_frame.pack(fill="x")
        
        tk.Label(path_input_frame, text="Path:", font=("Arial", 9)).pack(side="left", padx=2)
        initial_path = str(self.deleter.game_path) if self.deleter else str(self._temp_path)
        self.path_var = tk.StringVar(value=initial_path)
        path_entry = tk.Entry(
            path_input_frame,
            textvariable=self.path_var,
            font=("Arial", 9),
            width=50
        )
        path_entry.pack(side="left", padx=5, fill="x", expand=True)
        path_entry.bind('<KeyRelease>', lambda e: self._validate_path(self.path_var.get()))
        
        browse_button = tk.Button(
            path_input_frame,
            text="Browse...",
            command=self._browse_game_path,
            font=("Arial", 9),
            width=10
        )
        browse_button.pack(side="left", padx=2)
        
        auto_detect_button = tk.Button(
            path_input_frame,
            text="Auto-Detect",
            command=self._auto_detect_path,
            font=("Arial", 9),
            width=10
        )
        auto_detect_button.pack(side="left", padx=2)
        
        self.path_status_label = tk.Label(
            path_frame,
            text="✓ Path validated",
            font=("Arial", 8),
            fg="green"
        )
        self.path_status_label.pack(anchor="w", pady=2)
        
        mode_frame = tk.LabelFrame(self.root, text="Deletion Mode", padx=10, pady=10)
        mode_frame.pack(pady=10, padx=10, fill="x")
        
        self.mode_var = tk.StringVar(value="once")
        
        tk.Radiobutton(
            mode_frame,
            text="Once (delete and exit) - Run BEFORE starting game",
            variable=self.mode_var,
            value="once",
            font=("Arial", 9)
        ).pack(anchor="w", pady=2)
        
        tk.Radiobutton(
            mode_frame,
            text="Continuous (every 100ms) - Maximum safety during gameplay",
            variable=self.mode_var,
            value="continuous",
            font=("Arial", 9)
        ).pack(anchor="w", pady=2)
        
        tk.Radiobutton(
            mode_frame,
            text="Periodic (every N minutes) - Balanced approach",
            variable=self.mode_var,
            value="periodic",
            font=("Arial", 9),
            command=self._on_periodic_selected
        ).pack(anchor="w", pady=2)
        
        # Interval input (for periodic mode)
        interval_frame = tk.Frame(mode_frame)
        interval_frame.pack(anchor="w", pady=5, padx=20)
        
        tk.Label(interval_frame, text="Interval (minutes):", font=("Arial", 9)).pack(side="left")
        self.interval_var = tk.StringVar(value="5.0")
        interval_entry = tk.Entry(interval_frame, textvariable=self.interval_var, width=10, font=("Arial", 9))
        interval_entry.pack(side="left", padx=5)
        interval_entry.config(state="disabled")
        self.interval_entry = interval_entry
        
        launch_frame = tk.LabelFrame(self.root, text="Auto-Launch Applications", padx=10, pady=10)
        launch_frame.pack(pady=10, padx=10, fill="x")
        
        config = load_config()
        launch_enabled = config.get('launch_enabled', True)
        self.launch_enabled_var = tk.BooleanVar(value=launch_enabled)
        launch_checkbox = tk.Checkbutton(
            launch_frame,
            text="Launch game and ok-dna.exe when starting deletion",
            variable=self.launch_enabled_var,
            font=("Arial", 9, "bold"),
            command=self._on_launch_checkbox_changed
        )
        launch_checkbox.pack(anchor="w", pady=5)
        
        game_exe_frame = tk.Frame(launch_frame)
        game_exe_frame.pack(fill="x", pady=2)
        tk.Label(game_exe_frame, text="Game EXE:", font=("Arial", 9)).pack(side="left", padx=2)
        self.game_exe_var = tk.StringVar(value=get_game_exe_path())
        game_exe_entry = tk.Entry(
            game_exe_frame,
            textvariable=self.game_exe_var,
            font=("Arial", 9),
            width=45
        )
        game_exe_entry.pack(side="left", padx=5, fill="x", expand=True)
        game_exe_entry.bind('<KeyRelease>', lambda e: self._validate_exe_path(self.game_exe_var.get(), 'game'))
        
        game_exe_browse = tk.Button(
            game_exe_frame,
            text="Browse...",
            command=lambda: self._browse_exe_path('game'),
            font=("Arial", 8),
            width=8
        )
        game_exe_browse.pack(side="left", padx=2)
        
        game_exe_auto = tk.Button(
            game_exe_frame,
            text="Auto",
            command=lambda: self._auto_detect_exe_path('game'),
            font=("Arial", 8),
            width=6
        )
        game_exe_auto.pack(side="left", padx=2)
        
        self.game_exe_status = tk.Label(
            launch_frame,
            text="",
            font=("Arial", 8),
            fg="green"
        )
        self.game_exe_status.pack(anchor="w", padx=20)
        
        ok_dna_exe_frame = tk.Frame(launch_frame)
        ok_dna_exe_frame.pack(fill="x", pady=2)
        tk.Label(ok_dna_exe_frame, text="ok-dna.exe:", font=("Arial", 9)).pack(side="left", padx=2)
        self.ok_dna_exe_var = tk.StringVar(value=get_ok_dna_exe_path())
        ok_dna_exe_entry = tk.Entry(
            ok_dna_exe_frame,
            textvariable=self.ok_dna_exe_var,
            font=("Arial", 9),
            width=45
        )
        ok_dna_exe_entry.pack(side="left", padx=5, fill="x", expand=True)
        ok_dna_exe_entry.bind('<KeyRelease>', lambda e: self._validate_exe_path(self.ok_dna_exe_var.get(), 'ok_dna'))
        
        ok_dna_exe_browse = tk.Button(
            ok_dna_exe_frame,
            text="Browse...",
            command=lambda: self._browse_exe_path('ok_dna'),
            font=("Arial", 8),
            width=8
        )
        ok_dna_exe_browse.pack(side="left", padx=2)
        
        ok_dna_exe_auto = tk.Button(
            ok_dna_exe_frame,
            text="Auto",
            command=lambda: self._auto_detect_exe_path('ok_dna'),
            font=("Arial", 8),
            width=6
        )
        ok_dna_exe_auto.pack(side="left", padx=2)
        
        self.ok_dna_exe_status = tk.Label(
            launch_frame,
            text="",
            font=("Arial", 8),
            fg="green"
        )
        self.ok_dna_exe_status.pack(anchor="w", padx=20)
        
        self._validate_exe_path(self.game_exe_var.get(), 'game')
        self._validate_exe_path(self.ok_dna_exe_var.get(), 'ok_dna')
        
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        self.start_button = tk.Button(
            button_frame,
            text="Start Deletion",
            command=self._start_deletion,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            width=15,
            height=2
        )
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = tk.Button(
            button_frame,
            text="Stop",
            command=self._stop_deletion,
            bg="#f44336",
            fg="white",
            font=("Arial", 10, "bold"),
            width=15,
            height=2,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)
        
        self.status_label = tk.Label(
            self.root,
            text="Ready",
            font=("Arial", 9),
            fg="green"
        )
        self.status_label.pack(pady=5)
        
        log_frame = tk.LabelFrame(self.root, text="Log Output", padx=5, pady=5)
        log_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            width=70,
            font=("Consolas", 8),
            wrap=tk.WORD
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(state="disabled")
    
    def _on_periodic_selected(self):
        if self.mode_var.get() == "periodic":
            self.interval_entry.config(state="normal")
        else:
            self.interval_entry.config(state="disabled")
    
    def _validate_path(self, path_str: str) -> bool:
        try:
            game_path = Path(path_str)
            saved_path = game_path / "DNA Game" / "EM" / "Saved"
            if saved_path.exists():
                self.path_status_label.config(text="✓ Path validated", fg="green")
                return True
            else:
                self.path_status_label.config(
                    text=f"✗ Invalid path (missing: {saved_path.name})",
                    fg="red"
                )
                return False
        except Exception as e:
            self.path_status_label.config(text=f"✗ Error: {e}", fg="red")
            return False
    
    def _browse_game_path(self):
        initial_dir = "C:\\"
        if self.deleter and self.deleter.game_path.exists():
            initial_dir = str(self.deleter.game_path.parent)
        elif hasattr(self, '_temp_path'):
            initial_dir = str(self._temp_path.parent) if self._temp_path.exists() else "C:\\"
        
        selected_path = filedialog.askdirectory(
            title="Select Duet Night Abyss Installation Folder",
            initialdir=initial_dir
        )
        
        if selected_path:
            self.path_var.set(selected_path)
            if self._validate_path(selected_path):
                try:
                    if not self.deleter:
                        self.deleter = LogDeleter(game_path=selected_path)
                    else:
                        self.deleter.update_path(selected_path)
                    config = load_config()
                    config['game_path'] = selected_path
                    save_config(config)
                    logger.info(f"Game path updated to: {selected_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update path: {e}")
    
    def _auto_detect_path(self):
        logger.info("Auto-detecting game installation...")
        detected_path = find_game_installation()
        
        if detected_path:
            self.path_var.set(str(detected_path))
            if self._validate_path(str(detected_path)):
                try:
                    self.deleter.update_path(str(detected_path))
                    config = load_config()
                    config['game_path'] = str(detected_path)
                    save_config(config)
                    logger.info(f"Auto-detected and saved path: {detected_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update path: {e}")
        else:
            messagebox.showwarning(
                "Not Found",
                "Could not auto-detect game installation.\n\n"
                "Please use 'Browse' to manually select the game folder.\n"
                "The folder should contain 'DNA Game' subfolder."
            )
            logger.warning("Game installation not auto-detected")
    
    def _validate_exe_path(self, path_str: str, exe_type: str) -> bool:
        try:
            exe_path = Path(path_str)
            if exe_path.exists() and exe_path.is_file() and exe_path.suffix.lower() == '.exe':
                status_label = self.game_exe_status if exe_type == 'game' else self.ok_dna_exe_status
                status_label.config(text="✓ Executable found", fg="green")
                return True
            else:
                status_label = self.game_exe_status if exe_type == 'game' else self.ok_dna_exe_status
                status_label.config(text="✗ Executable not found", fg="red")
                return False
        except Exception as e:
            status_label = self.game_exe_status if exe_type == 'game' else self.ok_dna_exe_status
            status_label.config(text=f"✗ Error: {e}", fg="red")
            return False
    
    def _browse_exe_path(self, exe_type: str):
        var = self.game_exe_var if exe_type == 'game' else self.ok_dna_exe_var
        current_path = var.get()
        initial_dir = str(Path(current_path).parent) if Path(current_path).exists() else "C:\\"
        
        selected_file = filedialog.askopenfilename(
            title=f"Select {exe_type.upper()} Executable",
            initialdir=initial_dir,
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        
        if selected_file:
            var.set(selected_file)
            if self._validate_exe_path(selected_file, exe_type):
                config = load_config()
                key = 'game_exe_path' if exe_type == 'game' else 'ok_dna_exe_path'
                config[key] = selected_file
                save_config(config)
                logger.info(f"{exe_type} executable path updated to: {selected_file}")
    
    def _auto_detect_exe_path(self, exe_type: str):
        logger.info(f"Auto-detecting {exe_type} executable...")
        
        if exe_type == 'game':
            detected_exe = find_game_exe()
            var = self.game_exe_var
            status_label = self.game_exe_status
        else:
            detected_exe = find_ok_dna_exe()
            var = self.ok_dna_exe_var
            status_label = self.ok_dna_exe_status
        
        if detected_exe:
            var.set(str(detected_exe))
            if self._validate_exe_path(str(detected_exe), exe_type):
                config = load_config()
                key = 'game_exe_path' if exe_type == 'game' else 'ok_dna_exe_path'
                config[key] = str(detected_exe)
                save_config(config)
                logger.info(f"Auto-detected and saved {exe_type} executable: {detected_exe}")
        else:
            messagebox.showwarning(
                "Not Found",
                f"Could not auto-detect {exe_type} executable.\n\n"
                f"Please use 'Browse' to manually select the executable file."
            )
            logger.warning(f"{exe_type} executable not auto-detected")
    
    def _on_launch_checkbox_changed(self):
        config = load_config()
        config['launch_enabled'] = self.launch_enabled_var.get()
        save_config(config)
        logger.info(f"Launch enabled: {self.launch_enabled_var.get()}")
    
    def _launch_executables(self):
        if not self.launch_enabled_var.get():
            return
        game_exe_path = Path(self.game_exe_var.get())
        if game_exe_path.exists():
            if not launch_normal(game_exe_path):
                logger.info("Normal launch failed, attempting with elevation...")
                if launch_with_elevation(game_exe_path):
                    logger.info(f"Launched game with elevation: {game_exe_path}")
                else:
                    logger.error(f"Failed to launch game: {game_exe_path}")
                    messagebox.showerror(
                        "Error",
                        f"Failed to launch game:\n{game_exe_path}\n\n"
                        "Please ensure you have permission to run this executable."
                    )
            else:
                logger.info(f"Launched game: {game_exe_path}")
        else:
            logger.warning(f"Game executable not found: {game_exe_path}")
            messagebox.showwarning("Warning", f"Game executable not found:\n{game_exe_path}")
        
        ok_dna_exe_path = Path(self.ok_dna_exe_var.get())
        if ok_dna_exe_path.exists():
            if not launch_normal(ok_dna_exe_path):
                logger.info("Normal launch failed, attempting with elevation...")
                if launch_with_elevation(ok_dna_exe_path):
                    logger.info(f"Launched ok-dna with elevation: {ok_dna_exe_path}")
                else:
                    logger.error(f"Failed to launch ok-dna: {ok_dna_exe_path}")
                    messagebox.showerror(
                        "Error",
                        f"Failed to launch ok-dna:\n{ok_dna_exe_path}\n\n"
                        "Please ensure you have permission to run this executable."
                    )
            else:
                logger.info(f"Launched ok-dna: {ok_dna_exe_path}")
        else:
            logger.warning(f"ok-dna executable not found: {ok_dna_exe_path}")
            messagebox.showwarning("Warning", f"ok-dna executable not found:\n{ok_dna_exe_path}")
    
    def _setup_logging(self):
        class GUILogHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
            
            def emit(self, record):
                msg = self.format(record)
                self.text_widget.config(state="normal")
                self.text_widget.insert(tk.END, msg + "\n")
                self.text_widget.see(tk.END)
                self.text_widget.config(state="disabled")
        
        gui_handler = GUILogHandler(self.log_text)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(gui_handler)
    
    def _start_deletion(self):
        if self.is_running:
            return
        current_path = self.path_var.get()
        if not self._validate_path(current_path):
            messagebox.showerror(
                "Invalid Path",
                f"Invalid game installation path:\n{current_path}\n\n"
                "Please select a valid game installation folder that contains 'DNA Game' subfolder."
            )
            return
        
        if not self.deleter or Path(current_path) != self.deleter.game_path:
            try:
                if not self.deleter:
                    self.deleter = LogDeleter(game_path=current_path)
                else:
                    self.deleter.update_path(current_path)
                config = load_config()
                config['game_path'] = current_path
                save_config(config)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update path: {e}")
                return
        
        if self.launch_enabled_var.get():
            self._launch_executables()
            time.sleep(1)
        
        mode = self.mode_var.get()
        self.is_running = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        
        if mode == "once":
            self.status_label.config(text="Deleting logs once...", fg="blue")
            self.deleter.delete_once()
            self.status_label.config(text="Deletion complete!", fg="green")
            self._reset_buttons()
        
        elif mode == "continuous":
            self.status_label.config(text="Running continuous deletion (100ms interval)...", fg="orange")
            self.stop_event = threading.Event()
            self.deletion_thread = threading.Thread(
                target=self.deleter.run_continuous,
                args=(0.1, self.stop_event),
                daemon=True
            )
            self.deletion_thread.start()
        
        elif mode == "periodic":
            try:
                interval = float(self.interval_var.get())
                if interval <= 0:
                    raise ValueError("Interval must be positive")
                self.status_label.config(
                    text=f"Running periodic deletion (every {interval} minutes)...",
                    fg="orange"
                )
                self.stop_event = threading.Event()
                self.deletion_thread = threading.Thread(
                    target=self.deleter.run_periodic,
                    args=(interval, self.stop_event),
                    daemon=True
                )
                self.deletion_thread.start()
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid interval: {e}")
                self._reset_buttons()
    
    def _stop_deletion(self):
        if self.stop_event:
            self.stop_event.set()
        self.status_label.config(text="Stopping...", fg="red")
        self._reset_buttons()
        logger.info("Stopped by user")
    
    def _reset_buttons(self):
        self.is_running = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
    
    def run(self):
        self.root.mainloop()


def main():
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description="Delete Duet Night Abyss log folders to prevent ban",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Deletion Strategies:
  once         - Delete logs once and exit (run BEFORE starting game)
                 Best for: Preventive deletion before game launch
  
  continuous   - Delete logs every 100ms (safest, most resource-intensive)
                 Best for: Maximum safety, catches logs as they're generated
                 Use when: You want absolute protection
  
  periodic     - Delete logs every N minutes (balanced approach)
                 Best for: Long gaming sessions with less CPU usage
                 Default: Every 5 minutes (adjust with --interval)

Recommendation:
  - Run 'once' mode BEFORE starting the game (preventive)
  - Run 'continuous' mode DURING gameplay for maximum safety
  - Or use 'periodic' mode (every 5-10 min) for balanced protection
            """
        )
        
        parser.add_argument(
            'mode',
            choices=['once', 'continuous', 'periodic'],
            help='Deletion mode: once (delete and exit), continuous (100ms interval), or periodic (every N minutes)'
        )
        
        parser.add_argument(
            '--game-path',
            type=str,
            default=None,
            help='Path to Duet Night Abyss installation (auto-detected if not specified)'
        )
        
        parser.add_argument(
            '--interval',
            type=float,
            default=5.0,
            help='Interval in minutes for periodic mode (default: 5.0)'
        )
        
        args = parser.parse_args()
        
        if args.game_path is None:
            game_path = get_game_path()
            logger.info(f"Using game path: {game_path}")
        else:
            game_path = args.game_path
        
        deleter = LogDeleter(game_path=game_path)
        
        if args.mode == 'once':
            deleter.delete_once()
        elif args.mode == 'continuous':
            deleter.run_continuous(interval=0.1)
        elif args.mode == 'periodic':
            deleter.run_periodic(interval_minutes=args.interval)
    else:
        if not GUI_AVAILABLE:
            print("GUI not available. Please install tkinter or use command-line mode.")
            print("Usage: python log_deleter.py [once|continuous|periodic]")
            return 1
        
        app = LogDeleterGUI()
        app.run()


if __name__ == "__main__":
    main()

