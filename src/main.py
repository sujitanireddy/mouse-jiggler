import time
import random
import threading

import pyautogui as pag
from pynput import mouse
import pystray
from PIL import Image, ImageDraw


# ---------------- Settings ----------------
MOVE_DURATION = 0.15
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

        self.expected_position = {"x": None, "y": None}
        self.ignore_until_t = 0.0

        self.listener = None
        self.icon = None

        # Pre-render icons (faster, no redraw needed later)
        self.icon_stopped = self.make_icon(size=64, jiggling=False)
        self.icon_running = self.make_icon(size=64, jiggling=True)

    # ---------- stop / user takeover ----------
    def request_stop(self, reason: str):
        if self.running:
            print(f"Stopping: {reason}")
        self.stop_event.set()
        self.running = False
        self.refresh_tray()

    def on_move(self, x, y):
        if self.stop_event.is_set():
            return False

        if time.time() < self.ignore_until_t:
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

    # ---------- tray icon refresh ----------
    def refresh_tray(self):
        if self.icon is None:
            return

        self.icon.title = "Mouse Jiggler (Running)" if self.running else "Mouse Jiggler (Stopped)"
        self.icon.icon = self.icon_running if self.running else self.icon_stopped

        # Some platforms need a visibility toggle to force refresh
        try:
            self.icon.visible = False
            self.icon.visible = True
        except Exception:
            pass

    # ---------- worker ----------
    def jiggle_loop(self):
        self.start_listener()
        self.stop_event.clear()
        self.running = True
        self.refresh_tray()

        try:
            while not self.stop_event.is_set():
                x = random.randint(*X_RANGE)
                y = random.randint(*Y_RANGE)

                self.expected_position["x"] = x
                self.expected_position["y"] = y

                self.ignore_until_t = time.time() + IGNORE_WINDOW_SEC
                pag.moveTo(x, y, duration=MOVE_DURATION)

                cx, cy = pag.position()
                self.expected_position["x"], self.expected_position["y"] = cx, cy

                if DELAY_BETWEEN_MOVES:
                    time.sleep(DELAY_BETWEEN_MOVES)

        except Exception as e:
            self.request_stop(f"Error: {e}")

        finally:
            self.running = False
            self.stop_event.set()
            self.stop_listener()
            self.refresh_tray()

    # ---------- tray actions ----------
    def start(self, _icon=None, _item=None):
        if self.running:
            return
        threading.Thread(target=self.jiggle_loop, daemon=True).start()

    def quit(self, icon, _item=None):
        self.request_stop("Quitting app.")
        time.sleep(0.1)
        icon.stop()

    # ---------- icon drawing ----------
    @staticmethod
    def make_icon(size: int = 64, jiggling: bool = False) -> Image.Image:
        """
        Thick-outline mouse icon; optional subtle jiggle arcs when running.
        Transparent background, suitable for pystray.
        """
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        white = (255, 255, 255, 255)

        stroke = max(2, int(size * 0.06))
        thin = max(2, int(size * 0.06))

        def I(x): return int(round(x))

        # Outer body
        left, top, right, bottom = size * 0.18, size * 0.18, size * 0.82, size * 0.92
        body_bbox = (I(left), I(top), I(right), I(bottom))
        radius = I(size * 0.34)
        d.rounded_rectangle(body_bbox, radius=radius, outline=white, width=stroke)

        # Inner arch
        pad = size * 0.09
        arch_bbox = (
            I(left + pad),
            I(top + pad * 0.55),
            I(right - pad),
            I(top + (bottom - top) * 0.55),
        )
        d.arc(arch_bbox, start=180, end=0, fill=white, width=thin)

        arch_left_x, arch_right_x = arch_bbox[0], arch_bbox[2]
        arch_base_y = arch_bbox[3]
        mid_y = I(top + (bottom - top) * 0.52)

        d.line((arch_left_x, arch_base_y, arch_left_x, mid_y), fill=white, width=thin)
        d.line((arch_right_x, arch_base_y, arch_right_x, mid_y), fill=white, width=thin)

        # Middle divider
        d.line((I(left + pad * 0.55), mid_y, I(right - pad * 0.55), mid_y), fill=white, width=stroke)

        # Center stem + wheel capsule
        cx = size * 0.50
        stem_top = top + size * 0.05
        stem_bottom = top + (bottom - top) * 0.50
        d.line((I(cx), I(stem_top), I(cx), I(stem_bottom)), fill=white, width=stroke)

        wheel_w = size * 0.12
        wheel_h = size * 0.22
        wheel_bbox = (
            I(cx - wheel_w / 2),
            I(top + (bottom - top) * 0.24),
            I(cx + wheel_w / 2),
            I(top + (bottom - top) * 0.24 + wheel_h),
        )
        d.rounded_rectangle(wheel_bbox, radius=I(wheel_w * 0.45), outline=white, width=thin)

        # Jiggle arcs (only when running)
        if jiggling:
            w = max(2, int(size * 0.05))
            # Left arcs
            d.arc((I(size*0.06), I(size*0.30), I(size*0.28), I(size*0.52)), start=300, end=60, fill=white, width=w)
            d.arc((I(size*0.02), I(size*0.24), I(size*0.32), I(size*0.58)), start=300, end=60, fill=white, width=w)
            # Right arcs
            d.arc((I(size*0.72), I(size*0.30), I(size*0.94), I(size*0.52)), start=120, end=240, fill=white, width=w)
            d.arc((I(size*0.68), I(size*0.24), I(size*0.98), I(size*0.58)), start=120, end=240, fill=white, width=w)

        return img

    def run_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Start", self.start),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit),
        )
        self.icon = pystray.Icon("mouse-jiggler", self.icon_stopped, "Mouse Jiggler (Stopped)", menu)
        self.icon.run()


if __name__ == "__main__":
    MouseJigglerApp().run_tray()