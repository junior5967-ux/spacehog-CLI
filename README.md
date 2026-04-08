# SpaceHog CLI

Interactive disk space analyzer for Linux - like a text adventure!

## Installation

1. Download the latest release from https://github.com/junior5967-ux/spacehog/releases

2. Extract the zip file:
```bash
unzip SpaceHog-CLI.zip
cd SpaceHog-CLI
```

3. Install the dependency:
```bash
pip install send2trash
```

4. Run:
```bash
python spacehog.py
```

## Features

- 🔍 **Scan** - Find largest folders on any path
- 🧹 **Clean** - Find and safely delete temp/cache files  
- 💽 **Drives** - See disk usage at a glance
- 📋 **History** - View past cleanup actions
- ❌ **Errors** - View recent errors
- ❓ **Help** - How to use

## Usage

Just run `python spacehog.py` and follow the menu prompts!

## Requirements

- Python 3
- send2trash (`pip install send2trash`)

## Notes

- Files are moved to Trash, not deleted - you can restore them
- Logs are saved to `~/.spacehog/`

## License

MIT
