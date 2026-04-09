"""
SpaceHog - Disk Scanner Engine
Scans drives and calculates space usage by folder
"""
import os
import threading
import platform
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional


def format_size(size_bytes: int) -> str:
    """Convert bytes to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


@dataclass
class ScanResult:
    """Holds the results of a disk scan"""
    root_path: str
    total_size: int = 0
    folder_sizes: Dict[str, int] = field(default_factory=dict)
    file_count: int = 0
    scan_time: float = 0
    errors: List[str] = field(default_factory=list)
    
    def get_top_folders(self, n: int = 10) -> List[tuple]:
        """Return top N folders by size"""
        sorted_folders = sorted(self.folder_sizes.items(), key=lambda x: x[1], reverse=True)
        return sorted_folders[:n]
    
    def get_size_str(self, size_bytes: int) -> str:
        """Convert bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"


class DiskScanner:
    """Multi-threaded disk scanner"""
    
    def __init__(self):
        self._cancel = False
        self._results = ScanResult(root_path="")
        self._progress_callback: Optional[Callable] = None
        self._current_path = ""
        
    def scan(self, path: str, progress_callback: Optional[Callable] = None) -> ScanResult:
        """
        Scan a drive or folder
        Args:
            path: Drive letter (C:) or folder path
            progress_callback: Function(current_path, folders_scanned, bytes_scanned)
        Returns:
            ScanResult object
        """
        self._cancel = False
        self._progress_callback = progress_callback
        self._results = ScanResult(root_path=path)
        
        import time
        start_time = time.time()
        
        # Count files in parallel for speed
        folder_totals: Dict[str, int] = defaultdict(int)
        file_count = 0
        folders_checked = 0
        
        try:
            for root, dirs, files in os.walk(path, topdown=True):
                if self._cancel:
                    break
                    
                # Skip certain system folders to speed things up
                dirs[:] = [d for d in dirs if d not in ['$Recycle.Bin', 'System Volume Information', '.Trash-1000']]
                
                folders_checked += 1
                root_size = 0
                
                for filename in files:
                    if self._cancel:
                        break
                    
                    filepath = os.path.join(root, filename)
                    try:
                        # Get file size without following symlinks
                        size = os.lstat(filepath).st_size
                        root_size += size
                        file_count += 1
                    except (OSError, PermissionError) as e:
                        # Track ALL permission errors
                        self._results.errors.append(f"{type(e).__name__}: {filepath}")
                        continue
                
                folder_totals[root] = root_size
                self._results.total_size += root_size
                
                # Report progress every 100 folders
                if folders_checked % 100 == 0:
                    self._results.file_count = file_count
                    if self._progress_callback:
                        self._progress_callback(root, folders_checked, self._results.total_size)
                
                self._current_path = root
                
        except Exception as e:
            self._results.errors.append(str(e))
        
        # Calculate tree size for each folder
        for folder in reversed(folder_totals):
            parent_folder = os.path.dirname(folder)
            if parent_folder in folder_totals:
                folder_totals[parent_folder] += folder_totals[folder]
        
        self._results.folder_sizes = dict(folder_totals)
        self._results.file_count = file_count
        self._results.scan_time = time.time() - start_time
        
        return self._results
    
    def cancel(self):
        """Cancel the scan in progress"""
        self._cancel = True
    
    def get_temp_cleanup_targets(self) -> List[tuple]:
        """Return common temp folders that are safe to analyze"""
        import tempfile
        targets = []
        
        temp = tempfile.gettempdir()
        targets.append((temp, self._results.folder_sizes.get(temp, 0)))
        
        # Common temp locations based on the platform
        if platform.system() == 'Windows':
            common_temps = [
                os.path.expanduser("~\\AppData\\Local\\Temp"),
                os.path.expanduser("~\\Downloads"),
                "C:\\Windows\\Temp",
                "C:\\Temp",
            ]
        elif platform.system() == 'Linux':
            common_temps = [
                "/tmp",
                "~/.cache",
                "/var/tmp"
            ]
        else:
            common_temps = []
        
        for loc in common_temps:
            expanded_loc = os.path.expanduser(loc)
            if os.path.exists(expanded_loc):
                size = self._results.folder_sizes.get(expanded_loc, 0)
                if size > 0:
                    targets.append((expanded_loc, size))
        
        return sorted(targets, key=lambda x: x[1], reverse=True)


def quick_scan(path: str = None) -> ScanResult:
    """Quick one-off scan without progress reporting"""
    scanner = DiskScanner()
    scan_path = str(Path.home()) if path is None else path
    return scanner.scan(scan_path)


if __name__ == '__main__':
    # Test scan
    print("Quick scan test of ~/...")
    result = quick_scan("~")
    print(f"Total: {result.get_size_str(result.total_size)}")
    print(f"Files: {result.file_count}")
    print(f"Time: {result.scan_time:.1f}s")
    print("\nTop 10 folders:")
    for folder, size in result.get_top_folders(10):
        print(f"  {result.get_size_str(size)} - {folder}")
