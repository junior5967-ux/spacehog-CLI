"""
SpaceHog Logger - Simple logging for SpaceHog CLI
Logs errors, scans, and cleanup actions to ~/.spacehog/spacehog.log
"""
import os
import json
from pathlib import Path
from datetime import datetime


LOG_DIR = Path.home() / ".spacehog"
LOG_FILE = LOG_DIR / "spacehog.log"
HISTORY_FILE = LOG_DIR / "history.json"


def ensure_log_dir():
    """Create log directory if it doesn't exist"""
    LOG_DIR.mkdir(exist_ok=True)


def log(message, level="INFO"):
    """Log a message with timestamp"""
    ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}\n"
    
    try:
        with open(LOG_FILE, "a") as f:
            f.write(log_line)
    except Exception as e:
        print(f"Logging error: {e}")


def log_error(message):
    """Log an error"""
    log(message, "ERROR")


def log_scan(path, file_count, total_size, duration):
    """Log a scan operation"""
    ensure_log_dir()
    entry = {
        "type": "scan",
        "timestamp": datetime.now().isoformat(),
        "path": path,
        "file_count": file_count,
        "total_size": total_size,
        "duration_seconds": duration
    }
    _append_history(entry)
    log(f"SCAN: {path} | {file_count:,} files | {total_size} bytes | {duration:.1f}s", "INFO")


def log_cleanup(category, files_deleted, bytes_freed):
    """Log a cleanup operation"""
    ensure_log_dir()
    entry = {
        "type": "cleanup",
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "files_deleted": files_deleted,
        "bytes_freed": bytes_freed
    }
    _append_history(entry)
    log(f"CLEANUP: {category} | {files_deleted} files | {bytes_freed} bytes freed", "INFO")


def log_error_action(action, error_msg):
    """Log an error during an action"""
    ensure_log_dir()
    entry = {
        "type": "error",
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "error": error_msg
    }
    _append_history(entry)
    log(f"ERROR during {action}: {error_msg}", "ERROR")


def _append_history(entry):
    """Append an entry to history.json"""
    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except:
            history = []
    
    history.append(entry)
    
    # Keep last 100 entries
    history = history[-100:]
    
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"History logging error: {e}")


def get_history(limit=20):
    """Get recent history entries"""
    if not HISTORY_FILE.exists():
        return []
    
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
        return history[-limit:]
    except:
        return []


def get_errors(limit=50):
    """Get recent errors"""
    history = get_history(100)
    errors = [e for e in history if e.get("type") == "error"]
    return errors[-limit:]


def format_size(size_bytes):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def print_recent_errors():
    """Print recent errors to console"""
    errors = get_errors()
    if not errors:
        print("\n✅ No errors logged recently.")
        return
    
    print("\n❌ Recent Errors:")
    print("-" * 50)
    for e in errors[-10:]:
        print(f"  [{e['timestamp'][:19]}] {e.get('action', 'Unknown')}")
        print(f"    {e.get('error', 'No message')[:60]}")


if __name__ == "__main__":
    # Test - print log file location and recent entries
    print(f"SpaceHog Log: {LOG_FILE}")
    print(f"SpaceHog History: {HISTORY_FILE}")
    print()
    print_recent_errors()
