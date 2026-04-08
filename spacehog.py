#!/usr/bin/env python3
"""
SpaceHog CLI - Interactive Disk Space Analyzer
Run with: python spacehog.py
"""
VERSION = "0.0.1-alpha"

import os
import sys
import traceback

# Add script directory to path so modules can be found
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from scanner import DiskScanner
from cleaner import SafeCleaner
from spacehog_logger import log, log_scan, log_cleanup, log_error_action, print_recent_errors


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    print()
    print("=" * 50)
    print("       🐷  SPACEHOG  -  Disk Space Analyzer")
    print(f"                      v{VERSION}")
    print("=" * 50)
    print()


def print_menu(title, options):
    print(f"\n{title}")
    print("-" * 40)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print()


def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def ask_path():
    print("\n📁 Enter path to scan (press Enter for /home):")
    path = input("  > ").strip()
    if not path:
        path = os.path.expanduser("~/")
    return path


def ask_int(prompt, default, min_val=1, max_val=99):
    print(f"\n{prompt} (default: {default})")
    choice = input("  > ").strip()
    if not choice:
        return default
    try:
        val = int(choice)
        return max(min_val, min(max_val, val))
    except:
        return default


def do_scan():
    clear()
    print_header()
    print("🔍 SCAN FOR DISK USAGE")
    print()
    
    scanner = DiskScanner()
    path = ask_path()
    top = ask_int("How many results to show", 15, 5, 50)
    
    print(f"\n📊 Scanning {path}...")
    print("(Press Ctrl+C to cancel)\n")
    
    def progress(current_path, folders, size):
        short = current_path[:55] + "..." if len(current_path) > 55 else current_path
        print(f"\r  📁 {folders:,} folders | {format_size(size)} | {short}", end="", flush=True)
    
    result = scanner.scan(path, progress_callback=progress)
    print("\n")
    
    if not result or result.total_size == 0:
        print("❌ Scan cancelled or no files found.")
        log_error_action("scan", f"Scan cancelled or no files at {path}")
        input("\nPress Enter to continue...")
        return
    
    # Log the scan
    log_scan(path, result.file_count, result.total_size, result.scan_time)
    
    print(f"✅ Scan complete in {result.scan_time:.1f}s")
    print(f"   📊 Total: {result.file_count:,} files | {format_size(result.total_size)}\n")
    
    print("📁 Top Space Hogs:")
    print("-" * 50)
    top_folders = result.get_top_folders(top)
    colors = ["\033[92m", "\033[94m", "\033[95m", "\033[91m", "\033[93m", "\033[96m"]
    reset = "\033[0m"
    
    max_size = top_folders[0][1] if top_folders else 1
    bar_max = 25
    
    for i, (folder, size) in enumerate(top_folders):
        pct = size / max_size
        bar_len = int(pct * bar_max)
        color = colors[i % len(colors)]
        bar = "█" * bar_len
        size_str = format_size(size)
        name = folder if len(folder) < 35 else "..." + folder[-32:]
        print(f"{color}  {bar:<{bar_max}} {reset}{size_str:>10}  {name}")
    
    print()
    
    # Save option
    print("\n💾 Save results to file?")
    print("  1. Yes (save top 100)")
    print("  2. No")
    choice = input("  > ").strip()
    
    if choice == "1":
        save_path = os.path.expanduser("~/spacehog-scan.txt")
        try:
            with open(save_path, 'w') as f:
                f.write(f"SpaceHog Scan - {path}\n")
                f.write(f"Total: {result.file_count:,} files | {format_size(result.total_size)}\n")
                f.write("=" * 50 + "\n")
                for folder, size in result.get_top_folders(100):
                    f.write(f"{format_size(size):>12}  {folder}\n")
            print(f"\n✅ Saved to {save_path}")
        except Exception as e:
            print(f"\n❌ Could not save: {e}")
    
    input("\nPress Enter to continue...")


def do_cleanup():
    clear()
    print_header()
    print("🧹 FIND & CLEAN JUNK FILES")
    print()
    print("⚠️  Files are moved to Trash, not deleted!")
    print()
    
    cleaner = SafeCleaner()
    scanner = DiskScanner()
    
    path = ask_path()
    
    print(f"\n🔍 Scanning {path} for cleanup targets...")
    result = scanner.scan(path)
    targets = cleaner.scan_for_cleanup(result)
    
    if not targets:
        print("\n✅ No cleanup targets found. Your system looks clean!")
        input("\nPress Enter to continue...")
        return
    
    print(f"\n📋 Found {len(targets)} cleanup targets:\n")
    total_size = 0
    for i, target in enumerate(targets, 1):
        total_size += target.size
        print(f"  {i}. {target.category}")
        print(f"     {format_size(target.size)}")
        path_short = target.path[:50] + "..." if len(target.path) > 50 else target.path
        print(f"     📂 {path_short}")
        print()
    
    print(f"  {'─' * 40}")
    print(f"  Total reclaimable: {format_size(total_size)}\n")
    
    print("🎯 What would you like to do?")
    print("  1. Clean all targets")
    print("  2. Select individual targets")
    print("  3. View target details")
    print("  4. Go back")
    choice = input("  > ").strip()
    
    if choice == "1":
        confirm = input("\n❓ Delete ALL listed items? Type 'yes' to confirm: ").strip().lower()
        if confirm != 'yes':
            print("Cancelled.")
            input("\nPress Enter to continue...")
            return
        
        print("\n🗑️  Cleaning...\n")
        total_deleted = 0
        total_freed = 0
        
        for target in targets:
            try:
                deleted, freed, files = cleaner.delete_target(target)
                total_deleted += deleted
                total_freed += freed
                log_cleanup(target.category, deleted, freed)
                print(f"  ✅ {target.category}: {deleted} files | {format_size(freed)}")
            except Exception as e:
                log_error_action(f"cleanup:{target.category}", str(e))
                print(f"  ❌ {target.category}: Error - {e}")
        
        print(f"\n✨ Total: {total_deleted} files | {format_size(total_freed)} freed")
        print("   Files are in your Trash - you can restore them!")
        
    elif choice == "2":
        print("\nEnter numbers of targets to clean (comma separated, e.g. 1,3,5):")
        nums = input("  > ").strip()
        try:
            indices = [int(n.strip()) - 1 for n in nums.split(",")]
            selected = [targets[i] for i in indices if 0 <= i < len(targets)]
            
            confirm = input(f"\n❓ Delete {len(selected)} targets? Type 'yes': ").strip().lower()
            if confirm != 'yes':
                print("Cancelled.")
                input("\nPress Enter to continue...")
                return
            
            for target in selected:
                try:
                    deleted, freed, files = cleaner.delete_target(target)
                    log_cleanup(target.category, deleted, freed)
                    print(f"  ✅ {target.category}: {deleted} files | {format_size(freed)}")
                except Exception as e:
                    log_error_action(f"cleanup:{target.category}", str(e))
                    print(f"  ❌ {target.category}: Error - {e}")
            print("\n✨ Done!")
        except:
            print("Invalid selection.")
    
    elif choice == "3":
        print("\nEnter number of target to view details:")
        try:
            num = int(input("  > ").strip()) - 1
            if 0 <= num < len(targets):
                t = targets[num]
                print(f"\n📂 {t.category}")
                print(f"   Path: {t.path}")
                print(f"   Size: {format_size(t.size)}")
                print(f"   Files: {len(t.files) if t.files else 'All files in path'}")
        except:
            print("Invalid selection.")
    
    input("\nPress Enter to continue...")


def do_drives():
    clear()
    print_header()
    print("💽 DISK USAGE OVERVIEW")
    print()
    
    # Check common mounts
    mounts = ["/", "/home", "/mnt", "/var", "/tmp"]
    
    print("📊 Mount Points:\n")
    for mount in mounts:
        if os.path.exists(mount):
            try:
                stat = os.statvfs(mount)
                total = stat.f_blocks * stat.f_frsize
                used = (stat.f_blocks - stat.f_bavail) * stat.f_frsize
                free = stat.f_bavail * stat.f_frsize
                pct = (used / total) * 100 if total > 0 else 0
                
                bar_len = 20
                filled = int(pct / 100 * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)
                
                color = "\033[92m" if pct < 70 else "\033[93m" if pct < 90 else "\033[91m"
                reset = "\033[0m"
                
                print(f"  {mount:<15} {color}{bar}{reset} {format_size(free)} free / {format_size(total)}")
            except:
                pass
    
    print()
    input("\nPress Enter to continue...")


def do_history():
    clear()
    print_header()
    print("📋 CLEANUP HISTORY")
    print()
    
    cleaner = SafeCleaner()
    history = cleaner.get_history(20)
    
    if not history:
        print("  No cleanup history yet.")
        print("  Run 'Find & Clean Junk' to start cleaning!")
    else:
        for action in history:
            undone = " \033[91m[UNDONE]\033[0m" if action.undone else ""
            print(f"  📅 {action.timestamp}{undone}")
            print(f"     Category: {action.category}")
            print(f"     Files: {action.files_deleted} | Freed: {format_size(action.bytes_freed)}")
            print()
    
    print()
    input("\nPress Enter to continue...")


def do_help():
    clear()
    print_header()
    print("📖 HELP")
    print()
    print("  SpaceHog helps you find and clean disk space hogs.")
    print("  It safely moves files to your Trash, so you can restore them.")
    print()
    print("  Commands:")
    print("    1. Scan         - Find largest folders")
    print("    2. Find & Clean - Find temp/junk files to clean")
    print("    3. Drives       - Show disk usage overview")
    print("    4. History      - View past cleanup actions")
    print("    5. Errors       - View recent errors")
    print("    6. Help         - Show this help")
    print("    7. Exit         - Quit SpaceHog")
    print()
    input("\nPress Enter to continue...")


def do_errors():
    clear()
    print_header()
    print("❌ RECENT ERRORS")
    print()
    print_recent_errors()
    print()
    input("\nPress Enter to continue...")


def main():
    while True:
        clear()
        print_header()
        print_menu("MAIN MENU", [
            "🔍 Scan for Disk Usage",
            "🧹 Find & Clean Junk Files", 
            "💽 View Disk Usage Overview",
            "📋 View Cleanup History",
            "❌ View Recent Errors",
            "❓ Help",
            "🚪 Exit"
        ])
        
        choice = input("  Enter choice (0-7): ").strip()
        
        if choice == "1" or choice.lower() == "scan":
            do_scan()
        elif choice == "2" or choice.lower() == "clean":
            do_cleanup()
        elif choice == "3" or choice.lower() == "drives":
            do_drives()
        elif choice == "4" or choice.lower() == "history":
            do_history()
        elif choice == "5" or choice.lower() == "errors":
            do_errors()
        elif choice == "6" or choice.lower() == "help":
            do_help()
        elif choice in ["0", "7"] or choice.lower() in ["exit", "quit", "q"]:
            clear()
            print("\n🐷 Thanks for using SpaceHog!\n")
            break
        else:
            print("\n❌ Invalid choice. Press Enter to try again...")
            input()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)