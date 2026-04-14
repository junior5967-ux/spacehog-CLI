#!/usr/bin/env python3
"""
SpaceHog TUI - Minimal Terminal User Interface
Curses-based interface with arrow key navigation
"""
import os
import sys
import curses
import traceback

# Add script directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

VERSION = "0.1.1"

class SpaceHogTUI:
    """Minimal TUI controller"""
    
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.height, self.width = stdscr.getmaxyx()
        self.current_screen = "main_menu"
        self.selected_index = 0
        self.message = ""
        
        # Main menu items
        self.main_menu_items = [
            "🔍 Scan for Disk Usage",
            "🧹 Find & Clean Junk Files",
            "💽 View Disk Usage Overview",
            "📋 View Cleanup History",
            "❌ View Recent Errors",
            "❓ Help",
            "🚪 Exit"
        ]
        
        # Initialize colors if available
        self.init_colors()
    
    def init_colors(self):
        """Initialize color pairs"""
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            curses.init_pair(5, curses.COLOR_RED, curses.COLOR_BLACK)
    
    def clear_screen(self):
        """Clear the screen"""
        self.stdscr.clear()
        self.height, self.width = self.stdscr.getmaxyx()
    
    def draw_header(self):
        """Draw application header"""
        title = "🐷 SPACEHOG - Disk Space Analyzer"
        version = f"v{VERSION}"
        
        title_x = max(0, (self.width - len(title)) // 2)
        version_x = max(0, (self.width - len(version)) // 2)
        
        if curses.has_colors():
            self.stdscr.attron(curses.color_pair(2))
        
        self.stdscr.addstr(1, title_x, title)
        self.stdscr.addstr(2, version_x, version)
        
        if curses.has_colors():
            self.stdscr.attroff(curses.color_pair(2))
        
        # Separator
        self.stdscr.addstr(3, 0, "═" * self.width)
    
    def draw_status_bar(self):
        """Draw status bar at bottom"""
        status_y = self.height - 2
        
        # Clear status area
        self.stdscr.addstr(status_y, 0, " " * self.width)
        self.stdscr.addstr(status_y + 1, 0, " " * self.width)
        
        # Keyboard hints
        hints = "↑↓: Navigate | Enter: Select | Q/Esc: Exit"
        hints_x = max(0, (self.width - len(hints)) // 2)
        self.stdscr.addstr(status_y + 1, hints_x, hints)
    
    def draw_main_menu(self):
        """Draw main menu screen"""
        self.clear_screen()
        self.draw_header()
        
        # Menu title
        title = "MAIN MENU"
        title_x = max(0, (self.width - len(title)) // 2)
        self.stdscr.addstr(5, title_x, title)
        self.stdscr.addstr(6, 0, "─" * self.width)
        
        # Draw menu items
        menu_start_y = 8
        max_items = min(len(self.main_menu_items), self.height - menu_start_y - 5)
        
        for i in range(max_items):
            y = menu_start_y + i
            item = self.main_menu_items[i]
            
            # Highlight selected item
            if i == self.selected_index:
                if curses.has_colors():
                    self.stdscr.attron(curses.color_pair(2))
                self.stdscr.addstr(y, 2, f"> {item}")
                if curses.has_colors():
                    self.stdscr.attroff(curses.color_pair(2))
            else:
                self.stdscr.addstr(y, 4, item)
        
        # Draw message if any
        if self.message:
            msg_y = self.height - 6
            msg_x = max(0, (self.width - len(self.message)) // 2)
            self.stdscr.addstr(msg_y, msg_x, self.message)
        
        self.draw_status_bar()
    
    def handle_main_menu_input(self, key):
        """Handle input on main menu"""
        if key == curses.KEY_UP:
            self.selected_index = (self.selected_index - 1) % len(self.main_menu_items)
            return True
        elif key == curses.KEY_DOWN:
            self.selected_index = (self.selected_index + 1) % len(self.main_menu_items)
            return True
        elif key in [curses.KEY_ENTER, 10, 13]:  # Enter
            if self.selected_index == 0:
                self.message = "Scan functionality coming soon..."
            elif self.selected_index == 1:
                self.message = "Cleanup functionality coming soon..."
            elif self.selected_index == 2:
                self.message = "Drives functionality coming soon..."
            elif self.selected_index == 3:
                self.message = "History functionality coming soon..."
            elif self.selected_index == 4:
                self.message = "Errors functionality coming soon..."
            elif self.selected_index == 5:
                self.message = "Help functionality coming soon..."
            elif self.selected_index == 6:  # Exit
                raise SystemExit(0)
            return True
        elif key in [27, ord('q'), ord('Q')]:  # ESC or Q
            raise SystemExit(0)
        
        return False
    
    def run(self):
        """Main application loop"""
        self.stdscr.nodelay(False)
        curses.curs_set(0)  # Hide cursor
        
        while True:
            try:
                if self.current_screen == "main_menu":
                    self.draw_main_menu()
                
                self.stdscr.refresh()
                
                # Get input
                key = self.stdscr.getch()
                
                # Handle input
                handled = False
                if self.current_screen == "main_menu":
                    handled = self.handle_main_menu_input(key)
                
                # Clear message after a while if no action
                if not handled:
                    self.message = ""
                
            except SystemExit:
                break
            except Exception as e:
                self.message = f"Error: {str(e)}"

def main(stdscr):
    """Main entry point"""
    app = SpaceHogTUI(stdscr)
    app.run()

if __name__ == "__main__":
    try:
        # Check for Windows
        if os.name == 'nt':
            try:
                import curses
            except ImportError:
                print("Windows detected but curses not available.")
                print("Please install windows-curses: pip install windows-curses")
                sys.exit(1)
        
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        sys.exit(1)