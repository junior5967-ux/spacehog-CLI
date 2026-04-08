"""
SpaceHog - Safe File Cleaner
Identifies and safely removes temp files, caches, and duplicates
"""
import os
import json
import send2trash  # Safely moves to trash instead of deleting
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional
from datetime import datetime
import hashlib


@dataclass
class CleanupTarget:
    """Represents a folder/file that can be cleaned"""
    path: str
    size: int
    category: str  # 'temp', 'cache', 'download', 'duplicate'
    safe_to_delete: bool = True
    files: List[str] = None
    
    def __post_init__(self):
        if self.files is None:
            self.files = []


@dataclass
class CleanupAction:
    """Records a cleanup action for undo"""
    timestamp: str
    category: str
    files_deleted: int
    bytes_freed: int
    file_list: List[str]  # List of files that were deleted
    undone: bool = False


class SafeCleaner:
    """Identifies and safely cleans up space-wasting files"""
    
    # Common temp and cache locations on Windows
    TEMP_LOCATIONS = [
        # User temp
        ("%TEMP%", "User Temp Files"),
        ("%LOCALAPPDATA%\\Temp", "Local Temp Files"),
        # System temp
        ("C:\\Windows\\Temp", "Windows Temp"),
        ("C:\\Temp", "Temp"),
        # Browser caches
        ("%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default\\Cache", "Chrome Cache"),
        ("%LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\Default\\Cache", "Edge Cache"),
        ("%APPDATA%\\Mozilla\\Firefox\\Profiles\\*\\cache2", "Firefox Cache"),
    ]
    
    def __init__(self):
        self.targets: List[CleanupTarget] = []
        self.cleanup_history: List[CleanupAction] = []
        self.history_file = os.path.join(
            os.path.expanduser("~"),
            ".spacehog_history.json"
        )
        self._load_history()
    
    def _load_history(self):
        """Load cleanup history from file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self.cleanup_history = [CleanupAction(**a) for a in data]
            except Exception:
                self.cleanup_history = []
    
    def _save_history(self):
        """Save cleanup history to file"""
        try:
            with open(self.history_file, 'w') as f:
                # Only keep last 20 actions
                data = [asdict(a) for a in self.cleanup_history[-20:]]
                json.dump(data, f, indent=2)
        except Exception:
            pass
    
    def get_history(self, limit: int = 10) -> List[CleanupAction]:
        """Get recent cleanup actions"""
        return self.cleanup_history[-limit:][::-1]  # Most recent first
    
    def undo_last(self) -> Tuple[int, int]:
        """
        Restore files from the last cleanup action
        Returns: (files_restored, bytes_restored)
        """
        # Find last non-undone action
        for action in reversed(self.cleanup_history):
            if not action.undone:
                restored = 0
                bytes_restored = 0
                for filepath in action.file_list:
                    try:
                        # Files in trash need to be restored manually
                        # send2trash puts them in Recycle Bin
                        # We can't programmatically restore from there
                        # But we can tell the user
                        if os.path.exists(filepath):
                            bytes_restored += os.path.getsize(filepath)
                            restored += 1
                    except Exception:
                        pass
                
                action.undone = True
                self._save_history()
                return restored, bytes_restored, len(action.file_list)
        
        return 0, 0, 0
    
    def get_trash_info(self) -> Tuple[int, int]:
        """
        Get info about files in Recycle Bin
        Returns: (file_count, total_size)
        """
        # This is platform-specific
        # On Windows, we'd need to use Win32 API or shell
        # For now, return placeholder
        return 0, 0
    
    def scan_for_cleanup(self, scan_result) -> List[CleanupTarget]:
        """Scan for cleanup targets based on scan results"""
        self.targets = []
        
        # Check common temp locations
        for pattern, category in self.TEMP_LOCATIONS:
            path = os.path.expandvars(pattern)
            if os.path.exists(path):
                try:
                    size = self._get_folder_size(path)
                    if size > 100_000_000:  # Only report if > 100MB
                        self.targets.append(CleanupTarget(
                            path=path,
                            size=size,
                            category=category,
                            safe_to_delete=True
                        ))
                except PermissionError:
                    pass
        
        # Check Downloads folder
        downloads = os.path.expanduser("~\\Downloads")
        if os.path.exists(downloads):
            old_files = self._get_old_files(downloads, days=180)
            if old_files:
                size = sum(os.path.getsize(f) for f in old_files if os.path.exists(f))
                self.targets.append(CleanupTarget(
                    path=downloads,
                    size=size,
                    category="Old Downloads (180+ days)",
                    safe_to_delete=True,
                    files=old_files[:50]  # Limit to first 50
                ))
        
        # Sort by size descending
        self.targets.sort(key=lambda x: x.size, reverse=True)
        return self.targets
    
    def _get_folder_size(self, path: str) -> int:
        """Get total size of a folder"""
        total = 0
        try:
            for root, dirs, files in os.walk(path):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except (OSError, PermissionError):
                        pass
        except Exception:
            pass
        return total
    
    def _get_old_files(self, folder: str, days: int = 180) -> List[str]:
        """Get files older than N days"""
        import time
        cutoff = time.time() - (days * 24 * 60 * 60)
        old_files = []
        
        try:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    filepath = os.path.join(root, f)
                    try:
                        if os.path.getmtime(filepath) < cutoff:
                            old_files.append(filepath)
                    except OSError:
                        pass
        except Exception:
            pass
        
        return old_files
    
    def delete_target(self, target: CleanupTarget) -> Tuple[int, int, List[str]]:
        """
        Safely delete files in a cleanup target
        Returns: (files_deleted, bytes_freed, list_of_deleted_files)
        """
        if not target.safe_to_delete:
            return 0, 0, []
        
        deleted_files = []
        deleted = 0
        freed = 0
        
        if target.files:
            # Delete specific files
            for filepath in target.files:
                try:
                    size = os.path.getsize(filepath)
                    send2trash(filepath)
                    deleted += 1
                    freed += size
                    deleted_files.append(filepath)
                except Exception:
                    pass
        else:
            # Delete entire folder contents
            try:
                for root, dirs, files in os.walk(target.path):
                    for f in files:
                        filepath = os.path.join(root, f)
                        try:
                            size = os.path.getsize(filepath)
                            send2trash(filepath)
                            deleted += 1
                            freed += size
                            deleted_files.append(filepath)
                        except Exception:
                            pass
            except Exception:
                pass
        
        # Record this action
        if deleted > 0:
            action = CleanupAction(
                timestamp=datetime.now().isoformat(),
                category=target.category,
                files_deleted=deleted,
                bytes_freed=freed,
                file_list=deleted_files
            )
            self.cleanup_history.append(action)
            self._save_history()
        
        return deleted, freed, deleted_files
    
    def find_duplicates(self, scan_result, min_size: int = 10_000_000) -> List[Tuple[str, str, int]]:
        """
        Find duplicate files based on size and hash
        Returns: List of (file1, file2, size) tuples
        """
        # Group by size first
        size_groups = {}
        for folder, size in scan_result.folder_sizes.items():
            if size >= min_size:
                if size not in size_groups:
                    size_groups[size] = []
                size_groups[size].append(folder)
        
        # Find duplicates by hash
        duplicates = []
        for size, paths in size_groups.items():
            if len(paths) > 1:
                hashes = {}
                for path in paths:
                    try:
                        h = self._hash_file(path)
                        if h in hashes:
                            duplicates.append((hashes[h], path, size))
                        else:
                            hashes[h] = path
                    except Exception:
                        pass
        
        return duplicates
    
    def _hash_file(self, filepath: str, chunk_size: int = 65536) -> str:
        """Get hash of first chunk of file"""
        h = hashlib.md5()
        with open(filepath, 'rb') as f:
            h.update(f.read(chunk_size))
        return h.hexdigest()
    
    def format_size(self, size_bytes: int) -> str:
        """Convert bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
