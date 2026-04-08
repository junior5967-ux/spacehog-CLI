# Changelog - SpaceHog CLI (Linux)

All notable changes to SpaceHog CLI will be documented here.

## [0.0.1-alpha] - 2026-04-07

### Added
- Interactive text-adventure style menu interface
- Disk scanning with progress display
- Cleanup target discovery (temp files, caches, old downloads)
- Safe deletion to Trash (recoverable)
- Cleanup history tracking
- Drive/partition overview
- Error logging to ~/.spacehog/
- Help system

### Features
- Single command startup: `python spacehog.py`
- Menu navigation with number keys
- Scans with visual progress
- Multiple cleanup targets
- Dry-run capable
- Color-coded output

### Dependencies
- Python 3
- send2trash (for safe deletion)
