# SpaceHog CLI v0.0.1-alpha

Interactive disk space analyzer for Linux - like a text adventure!

## Installation

```bash
pip install send2trash
```

## Running

Just one command to start:

```bash
python spacehog.py
```

Then follow the menus!

## Features

- **🔍 Scan** - Find largest folders on any path
- **🧹 Clean** - Find and safely delete temp/cache files
- **💽 Drives** - See disk usage at a glance  
- **📋 History** - View past cleanup actions
- **❌ Errors** - View recent errors
- **❓ Help** - How to use

## Logging

SpaceHog automatically logs:
- All scans with file counts and sizes
- All cleanup actions
- Any errors encountered

Logs are stored in:
- `~/.spacehog/spacehog.log` - Human-readable log
- `~/.spacehog/history.json` - Structured history (last 100 entries)

## Files

- `spacehog.py` - Main interactive app (run this!)
- `spacehog-logger.py` - Logging module
- `scanner.py` - Disk scanning engine
- `cleaner.py` - Junk file finder & cleaner
- `requirements.txt` - Dependencies
- `VERSION` - Version number
- `CHANGELOG.md` - Change history

## Notes

- Files are moved to Trash, not deleted
- You can restore them from Trash if needed
- Python 3 only
