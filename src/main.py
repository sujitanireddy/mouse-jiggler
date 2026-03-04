import time
import random
import threading

import pyautogui as pag
from pynput import mouse

# -------- behavior tuning --------
USER_MOVE_THRESHOLD_PX = 10      # how far mouse must deviate to be considered "user"
IGNORE_WINDOW_SEC = 0.35         # window after our move where movement is expected
# ---------------------------------

stop_event = threading.Event()
expected_position = {"x": None, "y": None}
ignore_until = {"t": 0.0}


def request_stop(reason: str):
    if not stop_event.is_set():
        print(f"\nStopping: {reason}")
        stop_event.set()


def on_move(x, y):
    if stop_event.is_set():
        return False

    # If we just moved the mouse ourselves, ignore movement events briefly
    if time.time() < ignore_until["t"]:
        return

    ex, ey = expected_position["x"], expected_position["y"]
    if ex is None or ey is None:
        # If we haven't set an expected position yet, treat any move as user input
        request_stop("Mouse moved by user.")
        return False

    # If cursor deviates from where we expect by more than threshold, user took over
    if abs(x - ex) > USER_MOVE_THRESHOLD_PX or abs(y - ey) > USER_MOVE_THRESHOLD_PX:
        request_stop("Mouse moved by user.")
        return False


def on_click(x, y, button, pressed):
    if pressed:
        request_stop(f"Mouse click detected: {button}")
        return False


def on_scroll(x, y, dx, dy):
    request_stop("Mouse scroll detected.")
    return False


def start_mouse_listener():
    listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
    listener.start()
    return listener


def main():
    # Extra safety: slam mouse to a corner to stop (PyAutoGUI throws exception)
    pag.FAILSAFE = True

    listener = start_mouse_listener()

    try:
        for _ in range(1000):
            if stop_event.is_set():
                break

            x = random.randint(500, 1000)
            y = random.randint(200, 600)

            # Set what position we *expect* to be at after our move
            expected_position["x"] = x
            expected_position["y"] = y

            # Ignore listener events caused by our move for a brief window
            ignore_until["t"] = time.time() + IGNORE_WINDOW_SEC

            pag.moveTo(x, y, duration=0.2)

            # After move, refresh expected to current (sometimes OS slightly adjusts)
            cx, cy = pag.position()
            expected_position["x"], expected_position["y"] = cx, cy

    except pag.FailSafeException:
        request_stop("PyAutoGUI fail-safe triggered (moved to screen corner).")
    finally:
        stop_event.set()
        listener.stop()


if __name__ == "__main__":
    main()