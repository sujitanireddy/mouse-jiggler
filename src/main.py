import time
import random
import threading

import pyautogui as pag
from pynput import mouse
import pystray
from PIL import Image, ImageDraw


# ---------------- Settings ----------------
DEFAULT_COUNT = 10**9          # effectively "run forever" until a user interrupts 
MOVE_DURATION = 0.15           # time it takes to move from one position to another
DELAY_BETWEEN_MOVES = 0.1
X_RANGE = (500, 1000)
Y_RANGE = (200, 600)

USER_MOVE_THRESHOLD_PX = 10
IGNORE_WINDOW_SEC = 0.35
# ------------------------------------------


class MouseJigglerApp:
    def __init__(self):
        self.stop_event = threading.Event()
        self.running = False
        self.worker_thread = None

        self.expected_position = {"x": None, "y": None}
        self.ignore_until = {"t": 0.0}

        self.listener = None
        self.icon = None

    # ---------- user-takeover detection ----------
    def request_stop(self, reason: str):
        if self.running:
            print(f"Stopping: {reason}")
        self.stop_event.set()
        self.running = False
        self.update_icon_title()

    def on_move(self, x, y):
        if self.stop_event.is_set():
            return False

        if time.time() < self.ignore_until["t"]:
            return

        ex, ey = self.expected_position["x"], self.expected_position["y"]
        if ex is None or ey is None:
            self.request_stop("Mouse moved by user.")
            return False

        if abs(x - ex) > USER_MOVE_THRESHOLD_PX or abs(y - ey) > USER_MOVE_THRESHOLD_PX:
            self.request_stop("Mouse moved by user.")
            return False

    def on_click(self, x, y, button, pressed):
        if pressed:
            self.request_stop(f"Mouse click detected: {button}")
            return False

    def on_scroll(self, x, y, dx, dy):
        self.request_stop("Mouse scroll detected.")
        return False

    def start_listener(self):
        if self.listener is None:
            self.listener = mouse.Listener(
                on_move=self.on_move,
                on_click=self.on_click,
                on_scroll=self.on_scroll,
            )
            self.listener.start()

    def stop_listener(self):
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None

    # ---------- jiggler worker ----------
    def jiggle_loop(self):
    
        self.start_listener()
        self.stop_event.clear()
        self.running = True
        self.update_icon_title()

        try:
            for _ in range(DEFAULT_COUNT):
                if self.stop_event.is_set():
                    break

                x = random.randint(*X_RANGE)
                y = random.randint(*Y_RANGE)

                self.expected_position["x"] = x
                self.expected_position["y"] = y

                self.ignore_until["t"] = time.time() + IGNORE_WINDOW_SEC
                pag.moveTo(x, y, duration=MOVE_DURATION)

                cx, cy = pag.position()
                self.expected_position["x"], self.expected_position["y"] = cx, cy

                if DELAY_BETWEEN_MOVES:
                    time.sleep(DELAY_BETWEEN_MOVES)

        except Exception as e:
            self.request_stop(f"Unknown reason: {e}")
            
        finally:
            self.running = False
            self.stop_event.set()
            self.stop_listener()
            self.update_icon_title()

    # ---------- tray actions ----------
    def start(self, _icon=None, _item=None):
        if self.running:
            return
        self.worker_thread = threading.Thread(target=self.jiggle_loop, daemon=True)
        self.worker_thread.start()

    def stop(self, _icon=None, _item=None):
        self.request_stop("Stopped from tray menu.")

    def quit(self, icon, _item=None):
        self.request_stop("Quitting app.")
        time.sleep(0.1)
        icon.stop()

    def update_icon_title(self):
        if self.icon is not None:
            self.icon.title = "Mouse Jiggler (Running)" if self.running else "Mouse Jiggler (Stopped)"

    # ---------- icon ----------
    @staticmethod
    def make_icon(size: int = 64):
        """
        Minimal white mouse with small jiggle lines.
        Transparent background, suitable for pystray.
        """
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Colors
        white = (255, 255, 255, 255)

        # --- Mouse body (simple rounded shape) ---
        # Main body
        body = (size*0.30, size*0.18, size*0.70, size*0.82)
        d.rounded_rectangle(body, radius=int(size*0.18), outline=white, width=int(size*0.09))

        # Scroll wheel line
        d.line(
            (size*0.50, size*0.28, size*0.50, size*0.42),
            fill=white,
            width=max(1, int(size*0.05))
        )

        # Button split line (subtle)
        d.line(
            (size*0.50, size*0.18, size*0.50, size*0.28),
            fill=white,
            width=max(1, int(size*0.03))
        )

        # --- Jiggle lines (minimal) ---
        w = max(1, int(size*0.05))
        # left jiggle
        d.arc((size*0.12, size*0.24, size*0.32, size*0.44), start=300, end=60, fill=white, width=w)
        d.arc((size*0.08, size*0.18, size*0.34, size*0.50), start=300, end=60, fill=white, width=w)

        # right jiggle
        d.arc((size*0.68, size*0.24, size*0.88, size*0.44), start=120, end=240, fill=white, width=w)
        d.arc((size*0.66, size*0.18, size*0.92, size*0.50), start=120, end=240, fill=white, width=w)

        return img
        

    def run_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Start", self.start),
            pystray.MenuItem("Stop", self.stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit),
        )
        self.icon = pystray.Icon("mouse-jiggler", self.make_icon(), "Mouse Jiggler (Stopped)", menu)
        self.icon.run()


if __name__ == "__main__":
    MouseJigglerApp().run_tray()