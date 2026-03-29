#!/usr/bin/env python3
import time
import sys
import os
import socket
import threading
import configparser
import json

import numpy as np
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

from config import (
    PROJECT_ROOT, DATA_DIR, IMAGE_FOLDER, CONFIG_DIR,
    CONFIG_FILE, ORDER_FILE, CTRL_SOCK,
)

# =============================================================================
# Configuration Constants
# =============================================================================

# Maximum hardware brightness (100% UI = MAX_BRIGHTNESS% hardware)
MAX_BRIGHTNESS = 75

# CPU affinity: cores for the viewer process (leave core 0 for server)
VIEWER_CPU_CORES = [1, 2, 3]

# Fade transition settings — tune these for Pi Zero W 2 performance
FADE_STEPS = 40
FADE_FPS = 30
BLACK_PAUSE_S = 0.05

GAMMA = 2.2


def set_cpu_affinity():
    """Set CPU affinity to specific cores (Linux only)."""
    if VIEWER_CPU_CORES is None:
        return
    try:
        os.sched_setaffinity(0, VIEWER_CPU_CORES)
        print(f"CPU affinity set to cores: {VIEWER_CPU_CORES}")
    except (AttributeError, OSError) as e:
        print(f"Could not set CPU affinity: {e}")


# Set CPU affinity early
set_cpu_affinity()


def scale_brightness(ui_value: int) -> int:
    """Scale UI brightness (1-100) to hardware brightness (1-MAX_BRIGHTNESS)."""
    return max(1, int(ui_value * MAX_BRIGHTNESS / 100))


def load_config():
    brightness = 75
    hold_seconds = 30
    config = configparser.ConfigParser()
    if not os.path.isfile(CONFIG_FILE):
        print(f"Config file '{CONFIG_FILE}' not found. Using defaults.")
        return brightness, hold_seconds

    try:
        config.read(CONFIG_FILE)
        if "display" in config:
            if "brightness" in config["display"]:
                try:
                    b = int(config["display"]["brightness"])
                    if 1 <= b <= 100:
                        brightness = b
                    else:
                        print(f"Brightness in config out of range (1-100), using default {brightness}")
                except ValueError:
                    print(f"Invalid brightness in config, using default {brightness}")

            if "hold_seconds" in config["display"]:
                try:
                    s = int(config["display"]["hold_seconds"])
                    if s > 0:
                        hold_seconds = s
                    else:
                        print(f"hold_seconds must be > 0, using default {hold_seconds}")
                except ValueError:
                    print(f"Invalid hold_seconds in config, using default {hold_seconds}")

    except Exception as e:
        print(f"Error reading config file: {e}. Using defaults.")

    return brightness, hold_seconds


# =============================================================================
# Thread-safe state
# =============================================================================

isRunning = True
lock = threading.Lock()
hold_seconds_lock = threading.Lock()
current_hold_seconds = 30
reload_requested = False
reload_lock = threading.Lock()


def get_hold_seconds():
    with hold_seconds_lock:
        return current_hold_seconds


def set_hold_seconds_value(value):
    global current_hold_seconds
    with hold_seconds_lock:
        current_hold_seconds = value
    print(f"Hold seconds updated to {value}")


def request_reload():
    global reload_requested
    with reload_lock:
        reload_requested = True
    print("Reload requested")


def should_reload():
    global reload_requested
    with reload_lock:
        if reload_requested:
            reload_requested = False
            return True
        return False


def peek_reload():
    """Check if reload is requested without consuming the flag."""
    with reload_lock:
        return reload_requested


def handle_off():
    global isRunning
    with lock:
        isRunning = False
    print("Turning off display")


def handle_on():
    global isRunning
    with lock:
        isRunning = True
    print("Turning on display")


def getIsRunning():
    with lock:
        return isRunning


# =============================================================================
# Control socket
# =============================================================================

try:
    os.unlink(CTRL_SOCK)
except FileNotFoundError:
    pass
except OSError as e:
    print(f"Warning: could not remove old socket {CTRL_SOCK}: {e}")

sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
sock.bind(CTRL_SOCK)

last_brightness_update = 0
BRIGHTNESS_RATE_LIMIT_S = 0.2


def handle_set_brightness(value):
    """Set brightness with scaling (100% UI = MAX_BRIGHTNESS% hardware)."""
    if 1 <= value <= 100:
        hw_brightness = scale_brightness(value)
        matrix.brightness = hw_brightness
        print(f"Set brightness to {value}% (hardware: {hw_brightness}%)")
    else:
        print(f"Invalid brightness value: {value} (must be 1-100)")


def try_update_brightness(value):
    global last_brightness_update
    now = time.monotonic()
    if now - last_brightness_update >= BRIGHTNESS_RATE_LIMIT_S:
        handle_set_brightness(value)
        last_brightness_update = now


def control_thread():
    """Listen for commands on the Unix socket. Restarts on errors."""
    while True:
        try:
            msg, _ = sock.recvfrom(256)
            msg = msg.decode("utf-8").strip()
            if msg == "off":
                handle_off()
            elif msg == "on":
                handle_on()
            elif msg == "reload":
                request_reload()
            elif msg.startswith("brightness:"):
                try:
                    value = int(msg.split(":")[1])
                    if 1 <= value <= 100:
                        try_update_brightness(value)
                    else:
                        print(f"Invalid brightness value: {value} (must be 1-100)")
                except ValueError:
                    print(f"Invalid brightness format: {msg}")
            elif msg.startswith("hold:"):
                try:
                    value = int(msg.split(":")[1])
                    if 1 <= value <= 3600:
                        set_hold_seconds_value(value)
                    else:
                        print(f"Invalid hold_seconds value: {value} (must be 1-3600)")
                except ValueError:
                    print(f"Invalid hold format: {msg}")
            else:
                print(f"Unknown command: {msg}")
        except Exception as e:
            print(f"Error in control thread: {e}")
            time.sleep(0.5)


threading.Thread(target=control_thread, daemon=True).start()


# =============================================================================
# Image loading — lazy: only decode images when needed for display
# =============================================================================

def load_order():
    """Load image order from order.json if it exists."""
    if os.path.isfile(ORDER_FILE):
        try:
            with open(ORDER_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading order.json: {e}")
    return None


def get_sorted_image_paths(folder):
    """Return sorted list of image file paths without loading pixel data."""
    if not os.path.isdir(folder):
        return []

    files = [f for f in os.listdir(folder)
             if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"))]

    if not files:
        return []

    order = load_order()
    if order:
        order_map = {name: idx for idx, name in enumerate(order)}
        def sort_key(f):
            if f in order_map:
                return (0, order_map[f], f)
            return (1, 0, f)
        files = sorted(files, key=sort_key)
    else:
        files = sorted(files)

    return [os.path.join(folder, f) for f in files]


def load_single_image(path, target_size):
    """
    Load and decode a single image on demand.
    Returns (numpy_array_or_frames, durations_or_none) or None on error.
    """
    try:
        img = Image.open(path)
        is_animated_gif = getattr(img, "is_animated", False) and path.lower().endswith('.gif')

        if is_animated_gif:
            frames = []
            durations = []
            try:
                while True:
                    duration = img.info.get('duration', 100)
                    durations.append(duration)
                    frame = img.convert("RGB")
                    frame.thumbnail(target_size, Image.LANCZOS)
                    canvas = Image.new("RGB", target_size, (0, 0, 0))
                    x = (target_size[0] - frame.width) // 2
                    y = (target_size[1] - frame.height) // 2
                    canvas.paste(frame, (x, y))
                    frames.append(np.asarray(canvas, dtype=np.uint8))
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
            finally:
                img.close()
            if frames:
                return frames, durations
            return None
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail(target_size, Image.LANCZOS)
            canvas = Image.new("RGB", target_size, (0, 0, 0))
            x = (target_size[0] - img.width) // 2
            y = (target_size[1] - img.height) // 2
            canvas.paste(img, (x, y))
            arr = np.asarray(canvas, dtype=np.uint8)
            img.close()
            return arr, None
    except Exception as e:
        print(f"Skipping {path}: {e}")
        return None


# =============================================================================
# Rendering helpers
# =============================================================================

def make_gamma_tables(gamma=GAMMA):
    x = np.arange(256, dtype=np.float32) / 255.0
    to_gamma = np.clip((x ** gamma) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    to_linear = np.clip((x ** (1.0 / gamma)) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return to_gamma, to_linear


_TO_GAMMA, _TO_LINEAR = make_gamma_tables(GAMMA)


def scale_perceptual(img_u8, scale01):
    lin = _TO_LINEAR[img_u8]
    s = int(scale01 * 256 + 0.5)
    out = (lin.astype(np.uint16) * s) >> 8
    return _TO_GAMMA[out.astype(np.uint8)]


def blit(matrix, off, frame_u8):
    """Blit a numpy frame to the matrix."""
    if isinstance(frame_u8, np.ndarray):
        pil_img = Image.fromarray(frame_u8, mode="RGB")
    elif isinstance(frame_u8, Image.Image):
        pil_img = frame_u8
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
    else:
        pil_img = Image.fromarray(np.array(frame_u8, dtype=np.uint8), mode="RGB")

    matrix.SetImage(pil_img)
    return off


def smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def fade_to_level(matrix, off, img, start_level, end_level, steps=FADE_STEPS, fps=FADE_FPS):
    frame_time = 1.0 / float(fps)
    start = time.perf_counter()
    for i in range(steps + 1):
        t = i / float(steps)
        s = smoothstep(t)
        level = start_level + (end_level - start_level) * s
        frame = scale_perceptual(img, level)
        off = blit(matrix, off, frame)
        next_time = start + (i + 1) * frame_time
        remain = next_time - time.perf_counter()
        if remain > 0:
            time.sleep(remain)
    return off


def fade_out_to_black(matrix, off, img):
    off = fade_to_level(matrix, off, img, start_level=1.0, end_level=0.0)
    off = blit(matrix, off, np.zeros_like(img, dtype=np.uint8))
    return off


def fade_in_from_black(matrix, off, img):
    return fade_to_level(matrix, off, img, start_level=0.0, end_level=1.0)


def show_still(matrix, off, img, seconds):
    """Display a static image for the specified duration."""
    start = time.time()
    end = start + seconds

    while time.time() < end:
        if not getIsRunning():
            break
        if peek_reload():
            return off, True
        off = blit(matrix, off, img)
        time.sleep(0.1)

    return off, False


def show_gif(matrix, off, frames, durations, total_seconds):
    """Play an animated GIF in a loop until total_seconds have elapsed."""
    start = time.time()
    end = start + total_seconds
    frame_idx = 0
    num_frames = len(frames)

    while time.time() < end:
        if not getIsRunning():
            break
        if peek_reload():
            return off, True

        off = blit(matrix, off, frames[frame_idx])

        frame_duration = durations[frame_idx] / 1000.0
        frame_start = time.time()
        while time.time() - frame_start < frame_duration:
            if not getIsRunning():
                return off, False
            if peek_reload():
                return off, True
            time.sleep(min(0.05, frame_duration / 2))

        frame_idx = (frame_idx + 1) % num_frames

    return off, False


# =============================================================================
# Matrix setup
# =============================================================================

print("Starting viewer...")

BRIGHTNESS, HOLD_SECONDS = load_config()
current_hold_seconds = HOLD_SECONDS

options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'
options.brightness = scale_brightness(BRIGHTNESS)
options.pwm_bits = 8
options.pwm_lsb_nanoseconds = 130
options.gpio_slowdown = 2

matrix = RGBMatrix(options=options)
offscreen = matrix.CreateFrameCanvas()

# =============================================================================
# Main display loop — lazy image loading
# =============================================================================

# current_paths: ordered list of image file paths
# current_data: decoded pixel data for the currently-displayed image (loaded on demand)
# current_img: the first frame (numpy array) of current_data, used for fade transitions
current_paths = get_sorted_image_paths(IMAGE_FOLDER)
if not current_paths:
    sys.exit("No image files found in " + IMAGE_FOLDER)

idx = 0
result = load_single_image(current_paths[idx], (matrix.width, matrix.height))
while result is None and idx < len(current_paths) - 1:
    idx += 1
    result = load_single_image(current_paths[idx], (matrix.width, matrix.height))
if result is None:
    sys.exit("No valid images could be loaded")

current_data_pixels, current_durations = result
current_img = current_data_pixels[0] if current_durations is not None else current_data_pixels

prev_running = False

try:
    print("Press CTRL-C to stop.")
    print(f"Found {len(current_paths)} images")
    print(f"Display is {'ON' if isRunning else 'OFF'}")

    if isRunning:
        print("Performing initial fade-in...")
        offscreen = fade_in_from_black(matrix, offscreen, current_img)
        prev_running = True

    while True:
        # Handle reload
        if should_reload():
            print("Reloading images...")
            _, new_hold = load_config()
            set_hold_seconds_value(new_hold)

            new_paths = get_sorted_image_paths(IMAGE_FOLDER)
            if new_paths:
                current_paths = new_paths
                idx = 0
                result = load_single_image(current_paths[idx], (matrix.width, matrix.height))
                if result is not None:
                    new_pixels, new_durations = result
                    new_img = new_pixels[0] if new_durations is not None else new_pixels
                    print(f"Reloaded {len(current_paths)} images")
                    if getIsRunning():
                        offscreen = fade_out_to_black(matrix, offscreen, current_img)
                        offscreen = fade_in_from_black(matrix, offscreen, new_img)
                    current_data_pixels, current_durations = new_pixels, new_durations
                    current_img = new_img
            else:
                print("No images found after reload, keeping current state")

        now_running = getIsRunning()

        # OFF transition
        if prev_running and not now_running:
            offscreen = fade_out_to_black(matrix, offscreen, current_img)
            matrix.Clear()

        # ON transition
        if not prev_running and now_running:
            offscreen = fade_in_from_black(matrix, offscreen, current_img)

        prev_running = now_running

        if now_running:
            # Single image mode
            if len(current_paths) == 1:
                if current_durations is not None:
                    offscreen, _ = show_gif(matrix, offscreen, current_data_pixels, current_durations, get_hold_seconds())
                else:
                    offscreen, _ = show_still(matrix, offscreen, current_img, 5)
                continue

            # Multiple images: show current, then advance
            if current_durations is not None:
                offscreen, reload_triggered = show_gif(matrix, offscreen, current_data_pixels, current_durations, get_hold_seconds())
            else:
                offscreen, reload_triggered = show_still(matrix, offscreen, current_img, get_hold_seconds())

            if reload_triggered:
                continue

            # Advance to next image (lazy load)
            if getIsRunning():
                next_idx = (idx + 1) % len(current_paths)
                result = load_single_image(current_paths[next_idx], (matrix.width, matrix.height))
                if result is None:
                    # Skip broken images
                    print(f"Skipping broken image: {current_paths[next_idx]}")
                    idx = next_idx
                    continue

                next_pixels, next_durations = result
                next_img = next_pixels[0] if next_durations is not None else next_pixels

                offscreen = fade_out_to_black(matrix, offscreen, current_img)
                if BLACK_PAUSE_S > 0:
                    time.sleep(BLACK_PAUSE_S)
                offscreen = fade_in_from_black(matrix, offscreen, next_img)

                # Free previous image data
                current_data_pixels = next_pixels
                current_durations = next_durations
                current_img = next_img
                idx = next_idx
        else:
            time.sleep(0.2)

except KeyboardInterrupt:
    pass
finally:
    matrix.Clear()
    try:
        os.unlink(CTRL_SOCK)
    except OSError:
        pass
    print("Exiting...")
    sys.exit(0)
