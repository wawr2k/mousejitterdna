# Mouse Jitter AFK Bypass

This mod adds a "Mouse Jitter" feature to prevent AFK detection in Duet Night Abyss. It works by periodically moving the mouse cursor slightly when the game is in the background or foreground.

## Features
- **Safe:** Uses human-like mouse movements (jitter) instead of memory injection.
- **Non-Disruptive:** Checks if the mouse is in the game window before jittering. If the mouse is outside, it centers it first.
- **Configurable:** You can enable/disable it and set the jitter interval in the task settings.

## Supported Tasks
- **Auto Commission (CommissionsTask)**
- **Auto Skill (AutoSkill)**
- **Auto Dungeon (ImportTask)**
- **Auto Defence (AutoDefence)**
- **Auto 70jjb (Auto70jjbTask)**

## Installation
1. Copy all the `.py` files from this folder to your `ok-dna/src/tasks/` directory (and subdirectories as appropriate).
   - `CommissionsTask.py` -> `src/tasks/`
   - `AutoSkill.py` -> `src/tasks/`
   - `AutoDefence.py` -> `src/tasks/`
   - `ImportTask.py` -> `src/tasks/fullauto/`
   - `Auto70jjbTask.py` -> `src/tasks/fullauto/`

2. Restart `ok-dna`.

## Configuration
1. Find "Enable External Movement Logic" and toggle it **ON**.
3. (Optional) Adjust "External Movement Min/Max Delay" to change how often the mouse jitters.

## Files Included
- `CommissionsTask.py`: Core logic for mouse jitter.
- `AutoSkill.py`: Adds support for Auto Skill task.
- `AutoDefence.py`: Adds support for Auto Defence task.
- `ImportTask.py`: Adds support for Auto Dungeon (ImportTask).
- `Auto70jjbTask.py`: Adds support for Level 70 Shell Credit Dungeon.

