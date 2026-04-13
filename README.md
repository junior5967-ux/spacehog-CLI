# SpaceHog CLI

A full-featured disk space analyzer with a gorgeous curses-based TUI. Navigate with arrow keys, see real-time scanning progress, and clean up temp files safely.

## Installation

1. Download the latest release from https://github.com/junior5967-ux/spacehog-CLI/releases
2. Extract the zip and run:
```bash
pip install send2trash
python spacehog.py
```

## Features

- 🖥️ **Full TUI Interface** - Arrow key navigation, dark theme, colored bars
- 🔍 **Fast Scanner** - Scans drives and ranks folders by size
- 🧹 **Safe Cleanup** - Find and delete temp/cache files safely
- 💽 **Drive Info** - See all mounted drives and usage at a glance
- 📋 **History** - View past cleanup actions with stats
- 📊 **Colored Bars** - Visual representation of folder sizes
- ⏳ **Animated Scanning** - Real-time progress with spinner
- ❌ **Errors** - View skipped folders due to permissions
- ❓ **Help** - In-app help screen

## Controls

- **↑/↓** - Navigate menu
- **Enter** - Select option
- **A** - Select all (in cleanup)
- **D** - Delete selected (in cleanup)

## Requirements

- Python 3
- `send2trash` (`pip install send2trash`)
- `windows-curses` on Windows (`pip install windows-curses`)

## Notes

- Files are moved to Trash, not permanently deleted - you can restore them
- Logs saved to `~/.spacehog/`
- Requires terminal support for best experience

## License

MIT
