# Changelog - SpaceHog CLI

All notable changes to SpaceHog CLI will be documented here.

## [0.1.1] — 2026-04-14

### Fixed
- Mount point exclusion when scanning root on Linux (st_dev comparison)
- Replace clear() with erase() for better screen updates in TUI

### Changed
- Version bumped to 0.1.1

## [0.1.0] - 2026-04-13

### Added
- Full curses-based TUI with arrow key navigation
- Dark theme with colored ASCII bars
- Animated scanning with real-time spinner
- Threaded background operations (no UI freezing)
- Scan results with visual folder breakdown
- Threaded cleanup scanning and deletion
- Drive info screen with usage bars
- Cleanup history with file count and bytes freed
- Errors screen to view permission issues
- In-app help with keyboard shortcuts

### Features
- Navigate menus with ↑↓ arrows, Enter to select
- Press A to select all cleanup targets
- Press D to delete selected targets
- Color-coded size bars in scan results
- Scannable folder list with sizes
- Status bar with keyboard hints on every screen

### Technical
- Scanner total_size calculation fix
- Proper threading with QThread pattern
- Windows curses support (windows-curses)

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
