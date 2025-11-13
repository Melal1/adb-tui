import curses
import os
import select
import subprocess
from curses import wrapper

START_DIR_DEFAULT = "/sdcard/"


SELECTED_COLOR = 1  # Yellow on Blue
HIGHLIGHT_COLOR = 2  # White on Red (cursor + selected)
NORMAL_COLOR = 3  # Default


def init_colors():
    curses.start_color()
    curses.init_pair(SELECTED_COLOR, curses.COLOR_YELLOW, curses.COLOR_BLUE)
    curses.init_pair(HIGHLIGHT_COLOR, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(NORMAL_COLOR, curses.COLOR_WHITE, curses.COLOR_BLACK)


class FileBrowser:
    def __init__(self, start_dir: str = START_DIR_DEFAULT):
        self.current_dir = start_dir
        self.dirs: list[str] = []
        self.files: list[str] = []
        self.all_items: list[str] = []
        self.highlighted_idx: int = 0
        self.start_idx: int = 0
        self.selected_set: set[int] = set()
        self._ls_cmd = ["adb", "shell", "ls", "-p", self.current_dir]
        self.reload_dir(reset_cursor=True, reset_scroll=True, max_height=None)

    # -------- Directory handling --------

    def _run_ls(self) -> list[str]:
        self._ls_cmd[-1] = self.current_dir
        out = (
            subprocess.run(self._ls_cmd, capture_output=True, text=True)
            .stdout.strip()
            .splitlines()
        )
        return out

    def reload_dir(
        self, reset_cursor: bool, reset_scroll: bool, max_height: int | None
    ):
        out = self._run_ls()
        self.files = [f for f in out if not f.endswith("/")]
        self.dirs = [f for f in out if f.endswith("/")]
        self.all_items = self.dirs + self.files

        if reset_cursor:
            self.highlighted_idx = 0
        else:
            self.highlighted_idx = min(
                self.highlighted_idx, max(len(self.all_items) - 1, 0)
            )

        if reset_scroll:
            self.start_idx = 0
        else:
            if max_height is not None:
                self.start_idx = max(0, self.start_idx - (max_height - 2))

        self.selected_set.clear()

    def go_up_directory(self, max_height: int):
        if self.current_dir in ["/", START_DIR_DEFAULT]:
            return
        new_dir = os.path.dirname(self.current_dir.rstrip("/")) + "/"
        self.current_dir = new_dir
        self.reload_dir(reset_cursor=False, reset_scroll=False, max_height=max_height)

    def go_home(self, max_height: int):
        self.current_dir = START_DIR_DEFAULT
        self.reload_dir(reset_cursor=True, reset_scroll=True, max_height=max_height)

    def enter_directory_under_cursor(self, max_height: int):
        if not self.all_items:
            return
        item = self.all_items[self.highlighted_idx]
        if item.endswith("/"):
            self.current_dir += item
            self.reload_dir(reset_cursor=True, reset_scroll=True, max_height=max_height)

    # -------- Navigation & selection --------

    def move_down(self, max_height: int):
        if self.highlighted_idx < len(self.all_items) - 1:
            self.highlighted_idx += 1
            if self.highlighted_idx >= self.start_idx + max_height - 2:
                self.start_idx += 1 # scroll

    def move_up(self):
        if self.highlighted_idx > 0:
            self.highlighted_idx -= 1
            if self.highlighted_idx < self.start_idx:
                self.start_idx -= 1

    def toggle_select_current(self,max_height: int | None):
        if self.highlighted_idx < len(self.dirs):
            return
        if self.highlighted_idx in self.selected_set:
            self.selected_set.remove(self.highlighted_idx)
        else:
            self.selected_set.add(self.highlighted_idx)
            if max_height is not None:
              self.move_down(max_height)


    def clear_selection(self):
        self.selected_set.clear()

    def draw(self, stdscr: curses.window, max_height: int, max_width: int):
        stdscr.clear()
        end = min(self.start_idx + max_height - 2, len(self.all_items))

        for idx, item in enumerate(self.all_items[self.start_idx : end]):
            global_idx = idx + self.start_idx
            display_item = item
            if len(display_item) > max_width - 1:
                display_item = display_item[: max_width - 4] + "..."

            attr = curses.color_pair(NORMAL_COLOR)

            if global_idx in self.selected_set:
                attr = curses.color_pair(SELECTED_COLOR)

            if global_idx == self.highlighted_idx:
                if global_idx in self.selected_set:
                    attr = curses.color_pair(HIGHLIGHT_COLOR)
                else:
                    attr |= curses.A_REVERSE

            stdscr.addstr(idx, 0, display_item, attr)

        status = f"Dir: {self.current_dir} | Sel: {len(self.selected_set)} | q:quit h:up =:home"
        help_text = "TAB:select  j/k:move  c:clear  s:show  o:copy"

        stdscr.addstr(max_height - 2, 0, status[: max_width - 1], curses.A_BOLD)
        stdscr.addstr(max_height - 1, 0, help_text[: max_width - 1])
        stdscr.refresh()

    def has_items(self) -> bool:
        return bool(self.all_items)

    def get_targets_for_copy(self) -> list[str]:
        if self.selected_set:
            return [self.all_items[i] for i in self.selected_set]
        if not self.all_items: # If the list is empty 
            return []
        return [self.all_items[self.highlighted_idx]]

    def get_all_items(self) -> list[str]:
        return self.all_items

    def get_selected_files_for_notify(self) -> list[str]:
        return [self.all_items[i] for i in self.selected_set]


class LogTerminal:
    def __init__(self):
        self.lines: list[str] = []

    def _draw_live_tail(self, stdscr: curses.window):
        max_h, max_w = stdscr.getmaxyx()
        visible_height = max_h - 1  # 1 header line

        stdscr.clear()
        header = "Output log (live) – history kept. After copy: scrollable viewer."
        stdscr.addstr(0, 0, header[: max_w - 1], curses.A_BOLD)

        if visible_height <= 0:
            stdscr.refresh()
            return

        start = max(0, len(self.lines) - visible_height)
        row = 1
        for line in self.lines[start : start + visible_height]:
            if row >= max_h:
                break
            stdscr.addstr(row, 0, line[: max_w - 1])
            row += 1

        stdscr.refresh()

    def append_command_output(self, cmd: list[str], stdscr: curses.window):
        self.lines.append(f"$ {' '.join(cmd)}")
        self._draw_live_tail(stdscr)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        streams = []
        if proc.stdout is not None:
            streams.append(proc.stdout)
        if proc.stderr is not None:
            streams.append(proc.stderr)

        while streams:
            rlist, _, _ = select.select(streams, [], [], 0.1)

            if not rlist:
                if proc.poll() is not None:
                    break
                continue

            closed = []
            for s in rlist:
                line = s.readline()
                if line == "":
                    closed.append(s)
                    continue

                self.lines.append(line.rstrip("\n"))
                self._draw_live_tail(stdscr)

            for s in closed:
                if s in streams:
                    streams.remove(s)

    def view(self, stdscr: curses.window):
        max_h, max_w = stdscr.getmaxyx()
        visible_height = max_h - 1  # 1 header line
        if visible_height <= 0:
            return

        scroll = max(0, len(self.lines) - visible_height)

        while True:
            stdscr.clear()
            header = "Log viewer – j/k:up/down  d/u:half  g/G:top/bottom  q:back"
            stdscr.addstr(0, 0, header[: max_w - 1], curses.A_BOLD)

            row = 1
            end = min(scroll + visible_height, len(self.lines))
            for line in self.lines[scroll:end]:
                if row >= max_h:
                    break
                stdscr.addstr(row, 0, line[: max_w - 1])
                row += 1

            stdscr.refresh()

            ch = stdscr.getch()
            if ch == ord("q"):
                break
            elif ch == ord("j"):
                if scroll < max(0, len(self.lines) - visible_height):
                    scroll += 1
            elif ch == ord("k"):
                if scroll > 0:
                    scroll -= 1
            elif ch == ord("d"):
                scroll = min(
                    scroll + visible_height // 2,
                    max(0, len(self.lines) - visible_height),
                )
            elif ch == ord("u"):
                scroll = max(scroll - visible_height // 2, 0)
            elif ch == ord("g"):
                scroll = 0
            elif ch == ord("G"):
                scroll = max(0, len(self.lines) - visible_height)


class CopyManager:
    def __init__(self, browser: FileBrowser, terminal: LogTerminal):
        self.browser = browser
        self.terminal = terminal

    def run_copy_flow(self, stdscr: curses.window):
        stdscr.clear()
        _, max_w = stdscr.getmaxyx()
        prompt = "COPY MODE: press 'c' to copy selected/file-under-cursor, any other key to cancel."
        stdscr.addstr(0, 0, prompt[: max_w - 1])
        stdscr.refresh()

        key = stdscr.getch()
        if key != ord("c"):
            return

        if not self.browser.has_items():
            return

        targets = self.browser.get_targets_for_copy()
        if not targets:
            return

        for name in targets:
            src = self.browser.current_dir + name
            cmd = ["adb", "pull", src]
            self.terminal.append_command_output(cmd, stdscr)

        self.terminal.view(stdscr)



def main(stdscr: curses.window):
    curses.curs_set(0)
    stdscr.nodelay(False)
    init_colors()

    MAX_HEIGHT, MAX_WIDTH = stdscr.getmaxyx()

    browser = FileBrowser(start_dir=START_DIR_DEFAULT)
    terminal = LogTerminal()
    copy_manager = CopyManager(browser, terminal)

    while True:
        browser.draw(stdscr, MAX_HEIGHT, MAX_WIDTH)
        key = stdscr.getch()

        if key == ord("q"):
            break

        elif key == ord("j"):
            browser.move_down(MAX_HEIGHT)

        elif key == ord("k"):
            browser.move_up()

        elif key in (9, ord("\t")):
            browser.toggle_select_current(MAX_HEIGHT)

        elif key == ord("h"):
            browser.go_up_directory(MAX_HEIGHT)

        elif key == ord("l"):
            browser.enter_directory_under_cursor(MAX_HEIGHT)

        elif key == ord("="):
            browser.go_home(MAX_HEIGHT)

        elif key == ord("c"):
            browser.clear_selection()

        elif key == ord("s"):
            if browser.selected_set:
                selected_files = browser.get_selected_files_for_notify()
                msg = ", ".join(selected_files)
                os.system(f'notify-send "Selected ({len(selected_files)})" "{msg}"')
            else:
                os.system('notify-send "No files selected"')

        elif key == ord("o"):
            copy_manager.run_copy_flow(stdscr)
            browser.clear_selection()



wrapper(main)
