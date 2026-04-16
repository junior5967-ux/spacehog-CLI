#!/usr/bin/env python3
"""
SpaceHog - Disk Space Analyzer TUI
Full curses-based terminal user interface
Run with: python spacehog.py
"""
VERSION = "0.1.1"

import os
import sys
import curses
import threading
import time
import importlib.util
import traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from scanner import DiskScanner
from cleaner import SafeCleaner

# Import logger via importlib to handle the hyphenated filename
def _import_logger():
    path = os.path.join(SCRIPT_DIR, "spacehog-logger.py")
    spec = importlib.util.spec_from_file_location("spacehog_logger", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

try:
    _logger = _import_logger()
    log            = _logger.log
    log_scan       = _logger.log_scan
    log_cleanup    = _logger.log_cleanup
    log_error_action = _logger.log_error_action
    get_errors     = _logger.get_errors
except Exception:
    def log(*a, **kw): pass
    def log_scan(*a, **kw): pass
    def log_cleanup(*a, **kw): pass
    def log_error_action(*a, **kw): pass
    def get_errors(*a, **kw): return []

# Color pair IDs
CP_DEFAULT  = 1
CP_HEADER   = 2
CP_SUCCESS  = 3
CP_WARN     = 4
CP_ERROR    = 5
CP_ACCENT   = 6
CP_SELECTED = 7
CP_DIM      = 8


def format_size(b):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} PB"


class SpaceHogTUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.height, self.width = stdscr.getmaxyx()
        self.screen = "main_menu"
        self.sel = 0
        self.scroll = 0
        self.message = ""
        self.message_color = CP_SUCCESS

        self.menu_items = [
            ("Scan",    "Find the largest folders",     "scan_config"),
            ("Cleanup", "Find & remove junk files",     "cleanup_config"),
            ("Drives",  "Disk usage per mount point",   "drives"),
            ("History", "Past cleanup actions",         "history"),
            ("Errors",  "View recent error log",        "errors"),
            ("Help",    "How to use SpaceHog",          "help"),
            ("Exit",    "Quit SpaceHog",                "exit"),
        ]

        # Scan state
        self.scan_path   = os.path.expanduser("~")
        self.scan_top    = 15
        self.scan_result = None
        self.scanner     = None
        self.scan_progress = {"path": "", "folders": 0, "size": 0, "done": False, "error": None}

        # Cleanup state
        self.cleanup_targets  = []
        self.cleanup_selected = set()
        self.cleanup_scanning = False

        # Drives/history/errors cache
        self.drives_data   = []
        self.history_items = []
        self.error_items   = []

        self._init_colors()
        curses.curs_set(0)

    # ── Colors ──────────────────────────────────────────────────────────────

    def _init_colors(self):
        if not curses.has_colors():
            return
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(CP_DEFAULT,  curses.COLOR_WHITE,   -1)
        curses.init_pair(CP_HEADER,   curses.COLOR_CYAN,    -1)
        curses.init_pair(CP_SUCCESS,  curses.COLOR_GREEN,   -1)
        curses.init_pair(CP_WARN,     curses.COLOR_YELLOW,  -1)
        curses.init_pair(CP_ERROR,    curses.COLOR_RED,     -1)
        curses.init_pair(CP_ACCENT,   curses.COLOR_MAGENTA, -1)
        curses.init_pair(CP_SELECTED, curses.COLOR_BLACK,   curses.COLOR_CYAN)
        curses.init_pair(CP_DIM,      curses.COLOR_WHITE,   -1)

    def cp(self, pair):
        if curses.has_colors():
            return curses.color_pair(pair)
        return 0

    # ── Safe drawing ─────────────────────────────────────────────────────────

    def safe_addstr(self, y, x, text, attr=0):
        if y < 0 or y >= self.height - 1 or x >= self.width or x < 0:
            return
        avail = self.width - x - 1
        if avail <= 0:
            return
        try:
            self.stdscr.addstr(y, x, text[:avail], attr)
        except curses.error:
            pass

    def fill_line(self, y, attr=0):
        self.safe_addstr(y, 0, " " * (self.width - 1), attr)

    # ── Shared chrome ────────────────────────────────────────────────────────

    def draw_header(self):
        attr = self.cp(CP_HEADER) | curses.A_BOLD
        self.fill_line(0, self.cp(CP_HEADER))
        self.safe_addstr(0, 1, "  SPACEHOG  -  Disk Space Analyzer", attr)
        ver = f"v{VERSION}  "
        self.safe_addstr(0, max(1, self.width - len(ver) - 1), ver, self.cp(CP_HEADER))

    def draw_status_bar(self, hints=""):
        sy = self.height - 1
        self.fill_line(sy, self.cp(CP_HEADER))
        if hints:
            self.safe_addstr(sy, 1, hints, self.cp(CP_HEADER) | curses.A_BOLD)

    def draw_message(self, msg, color=None):
        if not msg:
            return
        c = color if color is not None else self.message_color
        my = self.height - 2
        self.fill_line(my)
        mx = max(1, (self.width - len(msg)) // 2)
        self.safe_addstr(my, mx, msg, self.cp(c) | curses.A_BOLD)

    def draw_section_title(self, title):
        self.safe_addstr(2, 2, title, self.cp(CP_HEADER) | curses.A_BOLD)
        self.safe_addstr(3, 2, "─" * min(len(title) + 10, self.width - 4), self.cp(CP_DIM))

    def draw_border_box(self, y, x, h, w, title=""):
        try:
            self.safe_addstr(y,       x, "╔" + "═" * (w - 2) + "╗", self.cp(CP_HEADER))
            self.safe_addstr(y + h-1, x, "╚" + "═" * (w - 2) + "╝", self.cp(CP_HEADER))
            for i in range(1, h - 1):
                self.safe_addstr(y + i, x,     "║", self.cp(CP_HEADER))
                self.safe_addstr(y + i, x+w-1, "║", self.cp(CP_HEADER))
            if title:
                t = f" {title} "
                tx = x + max(1, (w - len(t)) // 2)
                self.safe_addstr(y, tx, t, self.cp(CP_HEADER) | curses.A_BOLD)
        except curses.error:
            pass

    # ── Text input widget ────────────────────────────────────────────────────

    def get_input(self, prompt, default="", y=8, x=4):
        """Blocking single-line text input. Returns the entered string."""
        curses.echo()
        curses.curs_set(1)
        px = x
        self.safe_addstr(y, px, f"{prompt}: ", self.cp(CP_ACCENT) | curses.A_BOLD)
        px += len(prompt) + 2
        iw = min(55, self.width - px - 2)
        self.safe_addstr(y, px, " " * iw, self.cp(CP_DEFAULT) | curses.A_UNDERLINE)
        self.stdscr.move(y, px)
        self.stdscr.refresh()
        try:
            raw = self.stdscr.getstr(y, px, iw).decode("utf-8", errors="replace").strip()
        except Exception:
            raw = ""
        curses.noecho()
        curses.curs_set(0)
        return raw if raw else default

    # ── State transitions (called each loop tick before drawing) ─────────────

    def _update_state(self):
        if self.screen == "scanning":
            p = self.scan_progress
            if p["done"]:
                if p["error"]:
                    self.message = f"Scan error: {p['error']}"
                    self.message_color = CP_ERROR
                    self.screen = "scan_config"
                elif self.scan_result and self.scan_result.total_size > 0:
                    self.screen = "scan_results"
                    self.sel = 0
                    self.scroll = 0
                else:
                    self.message = "No files found or scan cancelled."
                    self.message_color = CP_WARN
                    self.screen = "scan_config"

        elif self.screen == "cleanup_scanning":
            if not self.cleanup_scanning:
                self.screen = "cleanup_view"
                self.sel = 0
                self.scroll = 0

    # ════════════════════════════════════════════════════════════════════════
    # MAIN MENU
    # ════════════════════════════════════════════════════════════════════════

    def draw_main_menu(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()

        # Banner
        banner = [
            " ____                      _   _",
            "/ ___| _ __   __ _  ___ ___| | | | ___   __ _",
            r"\\___ \\| '_ \\ / _` |/ __/ _ \\ |_| |/ _ \\ / _` |",
            " ___) | |_) | (_| | (_|  __/  _  | (_) | (_| |",
            "|____/| .__/ \\__,_|\\___\\___|_| |_|\\___/ \\__, |",
            "      |_|                                |___/ ",
        ]
        by = 2
        for i, line in enumerate(banner):
            if by + i < self.height - 12:
                self.safe_addstr(by + i, 4, line, self.cp(CP_ACCENT) | curses.A_DIM)

        menu_y = by + len(banner) + 1
        col_w  = min(52, self.width - 6)

        for i, (name, desc, _) in enumerate(self.menu_items):
            y = menu_y + i
            if y >= self.height - 3:
                break
            num = str(i + 1)
            if i == self.sel:
                self.safe_addstr(y, 3, " " * col_w, self.cp(CP_SELECTED))
                self.safe_addstr(y, 3, f"  [{num}]  {name:<10} {desc}", self.cp(CP_SELECTED) | curses.A_BOLD)
            else:
                self.safe_addstr(y, 3, f"   {num}   {name:<10} {desc}", self.cp(CP_DEFAULT))

        self.draw_message(self.message)
        self.draw_status_bar("↑↓: Navigate   Enter: Select   1-7: Quick select   Q: Quit")

    def handle_main_menu(self, key):
        n = len(self.menu_items)
        if key == curses.KEY_UP:
            self.sel = (self.sel - 1) % n
        elif key == curses.KEY_DOWN:
            self.sel = (self.sel + 1) % n
        elif key in [curses.KEY_ENTER, 10, 13]:
            return self._menu_select(self.sel)
        elif key in [ord('q'), ord('Q'), 27]:
            return False
        elif ord('1') <= key <= ord('7'):
            return self._menu_select(key - ord('1'))
        return True

    def _menu_select(self, idx):
        if idx >= len(self.menu_items):
            return True
        _, _, target = self.menu_items[idx]
        if target == "exit":
            return False
        self.message = ""
        self.sel = 0
        self.scroll = 0
        self.screen = target
        if target == "drives":
            self._load_drives()
        elif target == "history":
            self._load_history()
        elif target == "errors":
            self._load_errors()
        return True

    # ════════════════════════════════════════════════════════════════════════
    # SCAN CONFIG
    # ════════════════════════════════════════════════════════════════════════

    def draw_scan_config(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("SCAN FOR DISK USAGE")

        self.safe_addstr(5, 4, "Scan the largest folders on disk.", self.cp(CP_DIM))

        self.safe_addstr(7, 4, "Path to scan:    ", self.cp(CP_DIM))
        self.safe_addstr(7, 21, self.scan_path, self.cp(CP_DEFAULT) | curses.A_BOLD)

        self.safe_addstr(8, 4, "Results to show: ", self.cp(CP_DIM))
        self.safe_addstr(8, 21, str(self.scan_top), self.cp(CP_DEFAULT) | curses.A_BOLD)

        self.safe_addstr(10, 4, "[S]  Start scan",          self.cp(CP_SUCCESS) | curses.A_BOLD)
        self.safe_addstr(11, 4, "[P]  Change path",         self.cp(CP_DEFAULT))
        self.safe_addstr(12, 4, "[N]  Change result count", self.cp(CP_DEFAULT))
        self.safe_addstr(13, 4, "[Esc] Back to menu",       self.cp(CP_DIM))

        self.draw_message(self.message)
        self.draw_status_bar("S: Start   P: Path   N: Count   Esc: Back")

    def handle_scan_config(self, key):
        if key in [27]:
            self.screen = "main_menu"
            self.sel = 0
        elif key in [ord('s'), ord('S'), curses.KEY_ENTER, 10, 13]:
            self._start_scan()
        elif key in [ord('p'), ord('P')]:
            self._prompt_scan_path()
        elif key in [ord('n'), ord('N')]:
            self._prompt_scan_top()
        return True

    def _prompt_scan_path(self):
        self.stdscr.erase()
        self.draw_header()
        self.draw_section_title("CHANGE SCAN PATH")
        self.safe_addstr(5, 4, f"Current: {self.scan_path}", self.cp(CP_DIM))
        self.safe_addstr(6, 4, "Press Enter to keep current.", self.cp(CP_DIM))
        self.stdscr.refresh()
        val = self.get_input("New path", default=self.scan_path, y=8, x=4)
        val = os.path.expanduser(val.strip()) if val.strip() else self.scan_path
        if os.path.isdir(val):
            self.scan_path = val
            self.message = f"Path set: {val}"
            self.message_color = CP_SUCCESS
        else:
            self.message = f"Not a valid directory: {val}"
            self.message_color = CP_ERROR

    def _prompt_scan_top(self):
        self.stdscr.erase()
        self.draw_header()
        self.draw_section_title("NUMBER OF RESULTS")
        self.safe_addstr(5, 4, f"Current: {self.scan_top}  (range 5-50)", self.cp(CP_DIM))
        self.stdscr.refresh()
        val = self.get_input("Results", default=str(self.scan_top), y=7, x=4)
        try:
            self.scan_top = max(5, min(50, int(val)))
            self.message = f"Will show top {self.scan_top} results"
            self.message_color = CP_SUCCESS
        except ValueError:
            self.message = "Invalid number, keeping current."
            self.message_color = CP_WARN

    def _start_scan(self):
        self.scan_result = None
        self.scan_progress = {"path": "", "folders": 0, "size": 0, "done": False, "error": None}
        self.scanner = DiskScanner()
        self.screen = "scanning"

        def run():
            def progress(cur, folders, size):
                self.scan_progress["path"]    = cur
                self.scan_progress["folders"] = folders
                self.scan_progress["size"]    = size
            try:
                result = self.scanner.scan(self.scan_path, progress_callback=progress)
                self.scan_result = result
                if result.total_size > 0:
                    log_scan(self.scan_path, result.file_count, result.total_size, result.scan_time)
            except Exception as e:
                self.scan_progress["error"] = str(e)
            finally:
                self.scan_progress["done"] = True

        threading.Thread(target=run, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════════
    # SCANNING (progress)
    # ════════════════════════════════════════════════════════════════════════

    def draw_scanning(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("SCANNING...")

        p = self.scan_progress
        spinner = r"|/-\\"[int(time.time() * 5) % 4]

        self.safe_addstr(5, 4, f"Path:    {self.scan_path}", self.cp(CP_DEFAULT))
        self.safe_addstr(7, 4, f"Folders: {p['folders']:,}", self.cp(CP_SUCCESS))
        self.safe_addstr(8, 4, f"Size:    {format_size(p['size'])}", self.cp(CP_SUCCESS))

        cur = p["path"]
        max_cur = self.width - 14
        if len(cur) > max_cur:
            cur = "..." + cur[-(max_cur - 3):]
        self.safe_addstr(10, 4, "Scanning:", self.cp(CP_DIM))
        self.safe_addstr(11, 4, cur, self.cp(CP_DIM))

        self.safe_addstr(13, 4, f" {spinner}  Working... (press C to cancel)", self.cp(CP_WARN))
        self.draw_status_bar("C: Cancel")

    def handle_scanning(self, key):
        if key in [ord('c'), ord('C')]:
            if self.scanner:
                self.scanner.cancel()
        return True

    # ════════════════════════════════════════════════════════════════════════
    # SCAN RESULTS
    # ════════════════════════════════════════════════════════════════════════

    def draw_scan_results(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("SCAN RESULTS")

        r = self.scan_result
        if not r:
            self.screen = "main_menu"
            return

        summary = f"{r.file_count:,} files  |  {format_size(r.total_size)}  |  {r.scan_time:.1f}s"
        self.safe_addstr(4, 4, summary, self.cp(CP_SUCCESS))

        top = r.get_top_folders(self.scan_top)
        max_size = top[0][1] if top else 1
        bar_w = min(24, self.width // 4)
        bar_colors = [CP_SUCCESS, CP_HEADER, CP_ACCENT, CP_WARN, CP_ERROR]

        list_y = 6
        visible = self.height - list_y - 3

        for i, (folder, size) in enumerate(top):
            if i < self.scroll:
                continue
            row = list_y + (i - self.scroll)
            if row >= self.height - 3:
                break

            pct     = size / max_size if max_size else 0
            filled  = int(pct * bar_w)
            bar     = "█" * filled + "░" * (bar_w - filled)
            sz_str  = format_size(size)
            max_fp  = self.width - bar_w - 18
            fdisp   = folder if len(folder) <= max_fp else "..." + folder[-(max_fp - 3):]
            color   = bar_colors[i % len(bar_colors)]

            if i == self.sel:
                self.safe_addstr(row, 2, " " * (self.width - 3), self.cp(CP_SELECTED))
                self.safe_addstr(row, 2, bar, self.cp(CP_SELECTED) | curses.A_BOLD)
                self.safe_addstr(row, 2 + bar_w + 1, f"{sz_str:>10}  {fdisp}", self.cp(CP_SELECTED) | curses.A_BOLD)
            else:
                self.safe_addstr(row, 2, bar, self.cp(color))
                self.safe_addstr(row, 2 + bar_w + 1, f"{sz_str:>10}  {fdisp}", self.cp(CP_DEFAULT))

        self.draw_message(self.message)
        self.draw_status_bar("↑↓: Scroll   S: Save to file   Esc: Back")

    def handle_scan_results(self, key):
        if not self.scan_result:
            return True
        top = self.scan_result.get_top_folders(self.scan_top)
        n   = len(top)
        vis = self.height - 9

        if key == curses.KEY_UP:
            if self.sel > 0:
                self.sel -= 1
                if self.sel < self.scroll:
                    self.scroll = self.sel
        elif key == curses.KEY_DOWN:
            if self.sel < n - 1:
                self.sel += 1
                if self.sel >= self.scroll + vis:
                    self.scroll = self.sel - vis + 1
        elif key in [ord('s'), ord('S')]:
            self._save_scan_results()
        elif key in [27]:
            self.screen = "main_menu"
            self.sel = 0
        return True

    def _save_scan_results(self):
        save_path = os.path.join(os.getcwd(), "spacehog-scan.txt")
        try:
            with open(save_path, 'w') as f:
                f.write(f"SpaceHog Scan - {self.scan_path}\n")
                f.write(f"Total: {self.scan_result.file_count:,} files | {format_size(self.scan_result.total_size)}\n")
                f.write("=" * 50 + "\n")
                for folder, size in self.scan_result.get_top_folders(100):
                    f.write(f"{format_size(size):>12}  {folder}\n")
            self.message = f"Saved: {save_path}"
            self.message_color = CP_SUCCESS
        except Exception as e:
            self.message = f"Save failed: {e}"
            self.message_color = CP_ERROR

    # ════════════════════════════════════════════════════════════════════════
    # CLEANUP CONFIG
    # ════════════════════════════════════════════════════════════════════════

    def draw_cleanup_config(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("FIND & CLEAN JUNK FILES")

        self.safe_addstr(5, 4, "Scans for temp files, caches, and old downloads.", self.cp(CP_DIM))
        self.safe_addstr(6, 4, "Files are moved to Trash — fully recoverable.", self.cp(CP_SUCCESS))

        self.safe_addstr(8, 4, "Scan path:  ", self.cp(CP_DIM))
        self.safe_addstr(8, 16, self.scan_path, self.cp(CP_DEFAULT) | curses.A_BOLD)

        self.safe_addstr(10, 4, "[S]  Start cleanup scan", self.cp(CP_SUCCESS) | curses.A_BOLD)
        self.safe_addstr(11, 4, "[P]  Change path",        self.cp(CP_DEFAULT))
        self.safe_addstr(12, 4, "[Esc] Back to menu",      self.cp(CP_DIM))

        self.draw_message(self.message)
        self.draw_status_bar("S: Start   P: Path   Esc: Back")

    def handle_cleanup_config(self, key):
        if key in [27]:
            self.screen = "main_menu"
            self.sel = 0
        elif key in [ord('s'), ord('S'), curses.KEY_ENTER, 10, 13]:
            self._start_cleanup_scan()
        elif key in [ord('p'), ord('P')]:
            self._prompt_scan_path()
        return True

    def _start_cleanup_scan(self):
        self.cleanup_targets  = []
        self.cleanup_selected = set()
        self.cleanup_scanning = True
        self.screen = "cleanup_scanning"

        def run():
            try:
                scanner = DiskScanner()
                cleaner = SafeCleaner()
                result  = scanner.scan(self.scan_path)
                self.cleanup_targets = cleaner.scan_for_cleanup(result)
            except Exception as e:
                log_error_action("cleanup_scan", str(e))
            finally:
                self.cleanup_scanning = False

        threading.Thread(target=run, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════════
    # CLEANUP SCANNING (progress)
    # ════════════════════════════════════════════════════════════════════════

    def draw_cleanup_scanning(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("SCANNING FOR JUNK FILES...")

        spinner = r"|/-\\"[int(time.time() * 5) % 4]
        self.safe_addstr(6, 4, f" {spinner}  Analyzing {self.scan_path} ...", self.cp(CP_WARN))
        self.safe_addstr(8, 4, "Please wait.", self.cp(CP_DIM))
        self.draw_status_bar("")

    def handle_cleanup_scanning(self, key):
        return True

    # ════════════════════════════════════════════════════════════════════════
    # CLEANUP VIEW
    # ════════════════════════════════════════════════════════════════════════

    def draw_cleanup_view(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("CLEANUP TARGETS")

        targets = self.cleanup_targets

        if not targets:
            self.safe_addstr(5, 4, "No cleanup targets found.", self.cp(CP_SUCCESS) | curses.A_BOLD)
            self.safe_addstr(6, 4, "Your system looks clean!", self.cp(CP_SUCCESS))
            self.draw_status_bar("Esc: Back")
            return

        total    = sum(t.size for t in targets)
        sel_size = sum(targets[i].size for i in self.cleanup_selected if i < len(targets))

        self.safe_addstr(4, 3, f"{len(targets)} targets  |  {format_size(total)} reclaimable", self.cp(CP_WARN))

        list_y  = 6
        visible = self.height - list_y - 4

        for i, t in enumerate(targets):
            if i < self.scroll:
                continue
            row = list_y + (i - self.scroll)
            if row >= self.height - 4:
                break

            chk   = "[X]" if i in self.cleanup_selected else "[ ]"
            sz    = format_size(t.size)
            cat   = t.category[:28]
            pshort = t.path
            max_p = self.width - 54
            if len(pshort) > max_p:
                pshort = "..." + pshort[-(max_p - 3):]

            line = f" {chk} {sz:>10}  {cat:<28}  {pshort}"

            if i == self.sel:
                attr = self.cp(CP_SELECTED) | curses.A_BOLD
            elif i in self.cleanup_selected:
                attr = self.cp(CP_SUCCESS)
            else:
                attr = self.cp(CP_DEFAULT)

            self.safe_addstr(row, 2, " " * (self.width - 4), attr)
            self.safe_addstr(row, 2, line, attr)

        if self.cleanup_selected:
            sumline = f"  {len(self.cleanup_selected)} selected  |  {format_size(sel_size)} to free  |  Press D to delete"
            self.safe_addstr(self.height - 4, 2, sumline, self.cp(CP_SUCCESS) | curses.A_BOLD)

        self.draw_message(self.message)
        self.draw_status_bar("↑↓: Navigate   Space: Toggle   A: All/None   D: Delete selected   Esc: Back")

    def handle_cleanup_view(self, key):
        targets = self.cleanup_targets
        n = len(targets)

        if n == 0:
            if key in [27, curses.KEY_ENTER, 10, 13]:
                self.screen = "main_menu"
                self.sel = 0
            return True

        vis = self.height - 11

        if key == curses.KEY_UP:
            if self.sel > 0:
                self.sel -= 1
                if self.sel < self.scroll:
                    self.scroll = self.sel
        elif key == curses.KEY_DOWN:
            if self.sel < n - 1:
                self.sel += 1
                if self.sel >= self.scroll + vis:
                    self.scroll = self.sel - vis + 1
        elif key == ord(' '):
            if self.sel in self.cleanup_selected:
                self.cleanup_selected.discard(self.sel)
            else:
                self.cleanup_selected.add(self.sel)
        elif key in [ord('a'), ord('A')]:
            if len(self.cleanup_selected) == n:
                self.cleanup_selected.clear()
            else:
                self.cleanup_selected = set(range(n))
        elif key in [ord('d'), ord('D')]:
            if self.cleanup_selected:
                self._do_cleanup()
        elif key in [27]:
            self.screen = "main_menu"
            self.sel = 0

        return True

    def _do_cleanup(self):
        selected = sorted(self.cleanup_selected)
        targets  = [self.cleanup_targets[i] for i in selected if i < len(self.cleanup_targets)]
        total_sz = sum(t.size for t in targets)

        # Confirmation dialog
        dw = min(62, self.width - 4)
        dh = 10
        dy = (self.height - dh) // 2
        dx = (self.width  - dw) // 2

        self.stdscr.erase()
        self.draw_header()
        self.draw_border_box(dy, dx, dh, dw, "CONFIRM DELETION")
        self.safe_addstr(dy + 2, dx + 3, f"About to delete {len(targets)} item(s):", self.cp(CP_WARN) | curses.A_BOLD)
        self.safe_addstr(dy + 3, dx + 3, f"Total size: {format_size(total_sz)}",      self.cp(CP_WARN))
        self.safe_addstr(dy + 5, dx + 3, "Files will be moved to Trash (recoverable).", self.cp(CP_SUCCESS))
        self.safe_addstr(dy + 7, dx + 3, "[Y] Confirm       [N] Cancel", self.cp(CP_DEFAULT) | curses.A_BOLD)
        self.stdscr.refresh()

        while True:
            k = self.stdscr.getch()
            if k in [ord('y'), ord('Y')]:
                break
            if k in [ord('n'), ord('N'), 27]:
                self.message = "Cancelled."
                self.message_color = CP_WARN
                return

        # Perform deletion
        cleaner       = SafeCleaner()
        total_deleted = 0
        total_freed   = 0

        for t in targets:
            try:
                deleted, freed, _ = cleaner.delete_target(t)
                total_deleted += deleted
                total_freed   += freed
                log_cleanup(t.category, deleted, freed)
            except Exception as e:
                log_error_action(f"cleanup:{t.category}", str(e))

        # Remove cleaned targets from the list
        for i in sorted(selected, reverse=True):
            if i < len(self.cleanup_targets):
                self.cleanup_targets.pop(i)

        self.cleanup_selected.clear()
        self.sel = min(self.sel, max(0, len(self.cleanup_targets) - 1))

        self.message = f"Done! {total_deleted} files deleted  |  {format_size(total_freed)} freed"
        self.message_color = CP_SUCCESS

    # ════════════════════════════════════════════════════════════════════════
    # DRIVES
    # ════════════════════════════════════════════════════════════════════════

    def _load_drives(self):
        self.drives_data = []
        candidates = ["/", "/home", "/boot", "/var", "/tmp", "/mnt", "/opt"]
        seen = set()
        for mount in candidates:
            if not os.path.exists(mount):
                continue
            try:
                st = os.statvfs(mount)
                dev_id = st.f_fsid
                if dev_id in seen:
                    continue
                seen.add(dev_id)
                total = st.f_blocks * st.f_frsize
                used  = (st.f_blocks - st.f_bavail) * st.f_frsize
                free  = st.f_bavail * st.f_frsize
                pct   = (used / total * 100) if total > 0 else 0
                self.drives_data.append({"mount": mount, "total": total, "used": used, "free": free, "pct": pct})
            except Exception:
                pass

    def draw_drives(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("DISK USAGE OVERVIEW")

        bar_w = min(30, self.width // 3)
        y = 5

        if not self.drives_data:
            self.safe_addstr(y, 4, "No drives found.", self.cp(CP_WARN))
        else:
            # Column headers
            self.safe_addstr(y, 2, f"{'Mount':<15}", self.cp(CP_DIM))
            self.safe_addstr(y, 17, f"{'Usage':<{bar_w}}  {'%':>6}  {'Free':>10}  {'Total':>10}", self.cp(CP_DIM))
            y += 1
            self.safe_addstr(y, 2, "─" * min(self.width - 4, 70), self.cp(CP_DIM))
            y += 1

            for d in self.drives_data:
                if y >= self.height - 3:
                    break
                pct    = d["pct"]
                filled = int(pct / 100 * bar_w)
                bar    = "█" * filled + "░" * (bar_w - filled)
                color  = CP_SUCCESS if pct < 70 else CP_WARN if pct < 90 else CP_ERROR

                self.safe_addstr(y, 2,  f"{d['mount']:<15}",  self.cp(CP_DEFAULT) | curses.A_BOLD)
                self.safe_addstr(y, 17, bar,                   self.cp(color) | curses.A_BOLD)
                self.safe_addstr(y, 17 + bar_w + 2, f"{pct:5.1f}%  {format_size(d['free']):>10}  {format_size(d['total']):>10}", self.cp(color))
                y += 2

        self.draw_status_bar("R: Refresh   Esc: Back")

    def handle_drives(self, key):
        if key in [27]:
            self.screen = "main_menu"
            self.sel = 0
        elif key in [ord('r'), ord('R')]:
            self._load_drives()
        return True

    # ════════════════════════════════════════════════════════════════════════
    # HISTORY
    # ════════════════════════════════════════════════════════════════════════

    def _load_history(self):
        try:
            cleaner = SafeCleaner()
            self.history_items = cleaner.get_history(20)
        except Exception:
            self.history_items = []

    def draw_history(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("CLEANUP HISTORY")

        items = self.history_items
        if not items:
            self.safe_addstr(5, 4, "No cleanup history yet.", self.cp(CP_DIM))
            self.safe_addstr(6, 4, "Run Cleanup to start freeing space!", self.cp(CP_DIM))
        else:
            y = 5
            for action in items:
                if y >= self.height - 3:
                    break
                ts      = action.timestamp[:19] if len(action.timestamp) >= 19 else action.timestamp
                undone  = "  [UNDONE]" if action.undone else ""
                freed   = format_size(action.bytes_freed)
                dim_attr = curses.A_DIM if action.undone else 0

                self.safe_addstr(y,   4, ts,                               self.cp(CP_ACCENT))
                self.safe_addstr(y,   25, f"{action.category}{undone}",   self.cp(CP_DEFAULT) | dim_attr)
                self.safe_addstr(y+1, 4, f"{action.files_deleted} files  |  {freed} freed", self.cp(CP_SUCCESS) | dim_attr)
                y += 3

        self.draw_status_bar("Esc: Back")

    def handle_history(self, key):
        if key in [27]:
            self.screen = "main_menu"
            self.sel = 0
        return True

    # ════════════════════════════════════════════════════════════════════════
    # ERRORS
    # ════════════════════════════════════════════════════════════════════════

    def _load_errors(self):
        try:
            self.error_items = get_errors(20)
        except Exception:
            self.error_items = []

    def draw_errors(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("RECENT ERRORS")

        items = self.error_items
        if not items:
            self.safe_addstr(5, 4, "No errors logged recently.", self.cp(CP_SUCCESS) | curses.A_BOLD)
        else:
            y = 5
            for e in reversed(items[-15:]):
                if y >= self.height - 3:
                    break
                ts     = e.get("timestamp", "")[:19]
                action = e.get("action", "Unknown")
                err    = e.get("error", "")
                avail  = self.width - 10
                if len(err) > avail:
                    err = err[:avail - 3] + "..."

                self.safe_addstr(y,   4, f"[{ts}]  {action}", self.cp(CP_ERROR) | curses.A_BOLD)
                self.safe_addstr(y+1, 6, err, self.cp(CP_DIM))
                y += 3

        self.draw_status_bar("Esc: Back")

    def handle_errors(self, key):
        if key in [27]:
            self.screen = "main_menu"
            self.sel = 0
        return True

    # ════════════════════════════════════════════════════════════════════════
    # HELP
    # ════════════════════════════════════════════════════════════════════════

    def draw_help(self):
        self.stdscr.erase()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_header()
        self.draw_section_title("HELP")

        lines = [
            ("SpaceHog finds and cleans disk space hogs.", CP_DEFAULT, False),
            ("Files are moved to Trash — never permanently deleted.", CP_SUCCESS, False),
            ("", CP_DEFAULT, False),
            ("Navigation", CP_ACCENT, True),
            ("  ↑ / ↓         Navigate lists", CP_DEFAULT, False),
            ("  Enter          Select / confirm", CP_DEFAULT, False),
            ("  Esc            Go back", CP_DEFAULT, False),
            ("  Q              Quit (from main menu)", CP_DEFAULT, False),
            ("  1-7            Jump to menu item directly", CP_DEFAULT, False),
            ("", CP_DEFAULT, False),
            ("Scan screen", CP_ACCENT, True),
            ("  S              Start scan", CP_DEFAULT, False),
            ("  P              Change scan path", CP_DEFAULT, False),
            ("  N              Change result count", CP_DEFAULT, False),
            ("  S (results)    Save results to file", CP_DEFAULT, False),
            ("", CP_DEFAULT, False),
            ("Cleanup screen", CP_ACCENT, True),
            ("  Space          Toggle item selection", CP_DEFAULT, False),
            ("  A              Select / deselect all", CP_DEFAULT, False),
            ("  D              Delete selected items", CP_DEFAULT, False),
            ("", CP_DEFAULT, False),
            ("Drives screen", CP_ACCENT, True),
            ("  R              Refresh drive data", CP_DEFAULT, False),
        ]

        y = 5
        for text, color, bold in lines:
            if y >= self.height - 3:
                break
            attr = self.cp(color)
            if bold:
                attr |= curses.A_BOLD
            self.safe_addstr(y, 4, text, attr)
            y += 1

        self.draw_status_bar("Esc: Back")

    def handle_help(self, key):
        if key in [27]:
            self.screen = "main_menu"
            self.sel = 0
        return True

    # ════════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ════════════════════════════════════════════════════════════════════════

    def run(self):
        self.stdscr.keypad(True)

        screens = {
            "main_menu":        (self.draw_main_menu,       self.handle_main_menu),
            "scan_config":      (self.draw_scan_config,     self.handle_scan_config),
            "scanning":         (self.draw_scanning,        self.handle_scanning),
            "scan_results":     (self.draw_scan_results,    self.handle_scan_results),
            "cleanup_config":   (self.draw_cleanup_config,  self.handle_cleanup_config),
            "cleanup_scanning": (self.draw_cleanup_scanning,self.handle_cleanup_scanning),
            "cleanup_view":     (self.draw_cleanup_view,    self.handle_cleanup_view),
            "drives":           (self.draw_drives,          self.handle_drives),
            "history":          (self.draw_history,         self.handle_history),
            "errors":           (self.draw_errors,          self.handle_errors),
            "help":             (self.draw_help,            self.handle_help),
        }

        animated = {"scanning", "cleanup_scanning"}

        while True:
            try:
                # Auto-transitions for background screens
                self._update_state()

                draw_fn, handle_fn = screens.get(
                    self.screen,
                    (self.draw_main_menu, self.handle_main_menu)
                )

                draw_fn()
                self.stdscr.refresh()

                if self.screen in animated:
                    self.stdscr.nodelay(True)
                    key = self.stdscr.getch()
                    if key == curses.KEY_RESIZE:
                        self.height, self.width = self.stdscr.getmaxyx()
                        continue
                    if key == -1:
                        time.sleep(0.08)
                        continue
                else:
                    self.stdscr.nodelay(False)
                    key = self.stdscr.getch()
                    if key == curses.KEY_RESIZE:
                        self.height, self.width = self.stdscr.getmaxyx()
                        continue

                cont = handle_fn(key)
                if not cont:
                    break

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.message = f"Error: {e}"
                self.message_color = CP_ERROR
                self.screen = "main_menu"
                self.sel = 0


# ── Entry point ──────────────────────────────────────────────────────────────

def main(stdscr):
    app = SpaceHogTUI(stdscr)
    app.run()


if __name__ == "__main__":
    if os.name == 'nt':
        try:
            import windows_curses  # noqa: F401
        except ImportError:
            print("Windows requires windows-curses: pip install windows-curses")
            sys.exit(1)
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nFatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\nGoodbye!\n")
