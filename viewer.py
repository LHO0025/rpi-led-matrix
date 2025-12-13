#!/usr/bin/env python3
import time, sys, os
import numpy as np
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image
import random
import os, socket, threading
import configparser

CONFIG_FILE = "config.ini"

def load_config():
    brightness = 75  # defaults from script
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
                        print(f"Brightness in config out of range (1–100), using default {brightness}")
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

isRunning = True
lock = threading.Lock()
hold_seconds_lock = threading.Lock()
CTRL_SOCK = "/tmp/ledctl.sock"
try: os.unlink(CTRL_SOCK)
except FileNotFoundError: pass

sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
sock.bind(CTRL_SOCK)

# Global hold_seconds that can be updated dynamically
current_hold_seconds = 30
reload_requested = False
reload_lock = threading.Lock()

def get_hold_seconds():
    with hold_seconds_lock:
        return current_hold_seconds

def set_hold_seconds(value):
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

def control_thread():
    while True:
        msg, _ = sock.recvfrom(64)
        msg = msg.decode("utf-8") 
        if msg == "off":
            handle_off(None, None)
        elif msg == "on":
            handle_on(None, None)
        elif msg == "reload":
            request_reload()
        elif msg.startswith("brightness:"):
            try:
                value = int(msg.split(":")[1])
                if 1 <= value <= 100:
                    try_update_brightness(value)
                else:
                    print(f"Invalid brightness value: {value} (must be 1–100)")
            except ValueError:
                print(f"Invalid brightness format: {msg}")
        elif msg.startswith("hold:"):
            try:
                value = int(msg.split(":")[1])
                if 1 <= value <= 3600:
                    set_hold_seconds(value)
                else:
                    print(f"Invalid hold_seconds value: {value} (must be 1–3600)")
            except ValueError:
                print(f"Invalid hold format: {msg}")
        else:
            print(f"Unknown command: {msg}")
            

threading.Thread(target=control_thread, daemon=True).start()


print("Starting viewer...")


# ---------- Settings ----------
IMAGE_FOLDER = "matrix_images"
BRIGHTNESS, HOLD_SECONDS = load_config()
current_hold_seconds = HOLD_SECONDS  # Initialize the global variable

FADE_STEPS = 40          # increase for longer fades (e.g., 48)
FADE_FPS   = 30          # lower = longer fades (e.g., 28)

BLACK_PAUSE_S = 0.05     # small dramatic pause at black; set 0.0 to disable

GAMMA = 2.2

# -----------------------------

ORDER_FILE = os.path.join(IMAGE_FOLDER, "order.json")

def load_order():
    """Load image order from order.json if it exists."""
    import json
    if os.path.isfile(ORDER_FILE):
        try:
            with open(ORDER_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading order.json: {e}")
    return None

def load_images(folder, target_size, allow_empty=False):
    """
    Load images from folder. Returns list of tuples:
    - For static images: (path, numpy_array, None)
    - For GIFs: (path, list_of_numpy_frames, list_of_durations_ms)
    """
    if not os.path.isdir(folder):
        if allow_empty:
            print(f"Folder '{folder}' not found")
            return []
        sys.exit(f"Folder '{folder}' not found")
    
    files = [f for f in os.listdir(folder)
             if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"))]
    
    if not files:
        if allow_empty:
            print("No image files found in folder")
            return []
        sys.exit("No image files found in folder")

    # Sort by order.json if available, otherwise alphabetically
    order = load_order()
    if order:
        # Create a map of filename -> position
        order_map = {name: idx for idx, name in enumerate(order)}
        # Sort files: ordered files first (by their order), then unordered files alphabetically
        def sort_key(f):
            if f in order_map:
                return (0, order_map[f], f)
            return (1, 0, f)
        files = sorted(files, key=sort_key)
    else:
        files = sorted(files)
    
    paths = [os.path.join(folder, f) for f in files]

    imgs = []
    for p in paths:
        try:
            img = Image.open(p)
            
            # Check if it's an animated GIF
            is_animated = getattr(img, "is_animated", False) and p.lower().endswith('.gif')
            
            if is_animated:
                # Load all frames of the GIF
                frames = []
                durations = []
                try:
                    while True:
                        # Get frame duration (default 100ms if not specified)
                        duration = img.info.get('duration', 100)
                        durations.append(duration)
                        
                        # Convert frame to RGB and resize
                        frame = img.convert("RGB")
                        frame.thumbnail(target_size, Image.LANCZOS)
                        canvas = Image.new("RGB", target_size, (0, 0, 0))
                        x = (target_size[0] - frame.width) // 2
                        y = (target_size[1] - frame.height) // 2
                        canvas.paste(frame, (x, y))
                        frames.append(np.asarray(canvas, dtype=np.uint8))
                        
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass  # End of frames
                
                if frames:
                    imgs.append((p, frames, durations))
                    print(f"Loaded animated GIF: {p} ({len(frames)} frames)")
            else:
                # Static image
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.thumbnail(target_size, Image.LANCZOS)
                canvas = Image.new("RGB", target_size, (0, 0, 0))
                x = (target_size[0] - img.width) // 2
                y = (target_size[1] - img.height) // 2
                canvas.paste(img, (x, y))
                arr = np.asarray(canvas, dtype=np.uint8)
                imgs.append((p, arr, None))
        except Exception as e:
            print(f"Skipping {p}: {e}")
    
    if not imgs:
        if allow_empty:
            print("No valid images after loading")
            return []
        sys.exit("No valid images after loading")
    
    return imgs

def make_gamma_tables(gamma=GAMMA):
    x = np.arange(256, dtype=np.float32) / 255.0
    to_gamma  = np.clip((x ** gamma)        * 255.0 + 0.5, 0, 255).astype(np.uint8)
    to_linear = np.clip((x ** (1.0 / gamma)) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return to_gamma, to_linear

_TO_GAMMA, _TO_LINEAR = make_gamma_tables(GAMMA)

def scale_perceptual(img_u8, scale01):
    lin = _TO_LINEAR[img_u8]
    s = int(scale01 * 256 + 0.5)
    out = (lin.astype(np.uint16) * s) >> 8
    return _TO_GAMMA[out.astype(np.uint8)]

def blit(matrix, off, frame_u8):
    import numpy as np
    from PIL import Image as PILImage
    # If frame_u8 is a PIL.Image.Image, convert to numpy array
    if isinstance(frame_u8, PILImage.Image):
        frame_u8 = np.array(frame_u8)
    # Ensure frame_u8 is uint8 numpy array
    if not (isinstance(frame_u8, np.ndarray) and frame_u8.dtype == np.uint8):
        frame_u8 = np.array(frame_u8, dtype=np.uint8)
    
    # Use pixel-by-pixel setting instead of SetImage to avoid PIL version issues
    height, width = frame_u8.shape[:2]
    for y in range(height):
        for x in range(width):
            r, g, b = frame_u8[y, x]
            off.SetPixel(x, y, r, g, b)
    
    return matrix.SwapOnVSync(off)

def smoothstep(t):
    # S-curve: slow at start & end, symmetric
    return t * t * (3.0 - 2.0 * t)

def fade_to_level(matrix, off, img, start_level, end_level, steps=FADE_STEPS, fps=FADE_FPS):
    frame_time = 1.0 / float(fps)
    start = time.perf_counter()
    for i in range(steps + 1):
        t = i / float(steps)
        s = smoothstep(t)
        level = start_level + (end_level - start_level) * s  # 0..1
        frame = scale_perceptual(img, level)
        off = blit(matrix, off, frame)

        next_time = start + (i + 1) * frame_time
        remain = next_time - time.perf_counter()
        if remain > 0:
            time.sleep(remain)
    return off

def fade_out_to_black(matrix, off, img):
    off = fade_to_level(matrix, off, img, start_level=1.0, end_level=0.0)
    # Ensure true black
    off = blit(matrix, off, np.zeros_like(img, dtype=np.uint8))
    return off

def fade_in_from_black(matrix, off, img):
    return fade_to_level(matrix, off, img, start_level=0.0, end_level=1.0)

def peek_reload():
    """Check if reload is requested without resetting the flag."""
    global reload_requested
    with reload_lock:
        return reload_requested


def show_still(matrix, off, img, seconds):
    """Display a static image for the specified duration."""
    start = time.time()
    end = start + seconds

    while time.time() < end:
        if not getIsRunning():
            break
        if peek_reload():
            # Return early to allow reload processing (don't consume the flag here)
            return off, True
        # Use blit instead of SetImage to avoid PIL issues
        off = blit(matrix, off, img)
        time.sleep(0.1)  # lower interval for more responsive brightness updates

    return off, False


def show_gif(matrix, off, frames, durations, total_seconds):
    """
    Play an animated GIF in a loop until total_seconds have elapsed.
    Returns (offscreen, reload_requested).
    """
    start = time.time()
    end = start + total_seconds
    frame_idx = 0
    num_frames = len(frames)
    
    while time.time() < end:
        if not getIsRunning():
            break
        if peek_reload():
            return off, True
        
        # Display current frame
        off = blit(matrix, off, frames[frame_idx])
        
        # Wait for frame duration (convert ms to seconds)
        frame_duration = durations[frame_idx] / 1000.0
        frame_start = time.time()
        while time.time() - frame_start < frame_duration:
            if not getIsRunning():
                return off, False
            if peek_reload():
                return off, True
            # Check more frequently for responsiveness
            time.sleep(min(0.05, frame_duration / 2))
        
        # Advance to next frame (loop)
        frame_idx = (frame_idx + 1) % num_frames
    
    return off, False


def get_display_frame(image_data):
    """
    Get the first frame for display (for fading).
    image_data is (path, frames_or_array, durations_or_none)
    """
    path, data, durations = image_data
    if durations is not None:
        # Animated GIF - return first frame
        return data[0]
    else:
        # Static image
        return data


def is_animated(image_data):
    """Check if image_data represents an animated GIF."""
    return image_data[2] is not None

# ----- Matrix config -----
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'
options.brightness = BRIGHTNESS

options.pwm_bits = 8            
options.pwm_lsb_nanoseconds = 130 
options.gpio_slowdown = 2 
# options.pwm_bits = 9
# options.limit_refresh_rate_hz = 100

matrix = RGBMatrix(options=options)
offscreen = matrix.CreateFrameCanvas()

idx = 0
images = load_images(IMAGE_FOLDER, (matrix.width, matrix.height))
path, data, durations = images[idx]
current_img = get_display_frame(images[idx])

def handle_off(event, value):
    with lock:
        global isRunning
        isRunning = False
    print("Turning off display")

def handle_on(event, value):
    with lock:
        global isRunning
        isRunning = True
    print("Turning on display")

def getIsRunning():
    global isRunning
    with lock:
        return isRunning
    
last_brightness_update = 0
BRIGHTNESS_RATE_LIMIT_S = 0.2  # 200 ms

def handle_set_brightness(value):
    if 1 <= value <= 100:
        matrix.brightness = value
        print(f"Set brightness to {value}")
    else:
        print(f"Invalid brightness value: {value} (must be 1–100)")

def try_update_brightness(value):
    global last_brightness_update
    now = time.monotonic()

    # enforce 200ms cooldown
    if now - last_brightness_update >= BRIGHTNESS_RATE_LIMIT_S:
        handle_set_brightness(value)
        last_brightness_update = now
    else:
        # optional: silently ignore or print
        print("Brightness update skipped (rate-limited)")

    
prev_running = False

try:
    print("Press CTRL-C to stop.")
    print(f"Loaded {len(images)} images")
    print(f"Display is {'ON' if isRunning else 'OFF'}")
    # Initial fade-in if display is on
    if isRunning:
        print("Performing initial fade-in...")
        offscreen = fade_in_from_black(matrix, offscreen, current_img)
        prev_running = True

    while True:
        # Check if reload was requested
        if should_reload():
            print("Reloading images...")
            # Reload config
            _, new_hold = load_config()
            set_hold_seconds(new_hold)
            # Reload images (allow_empty=True to prevent crash if all images deleted)
            new_images = load_images(IMAGE_FOLDER, (matrix.width, matrix.height), allow_empty=True)
            if new_images:
                images = new_images
                idx = 0
                new_img = get_display_frame(images[idx])
                print(f"Reloaded {len(images)} images")
                # Fade transition if display is on
                if getIsRunning():
                    offscreen = fade_out_to_black(matrix, offscreen, current_img)
                    offscreen = fade_in_from_black(matrix, offscreen, new_img)
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
            # Check if current image is animated GIF
            current_data = images[idx]
            if is_animated(current_data):
                # Play GIF animation for hold_seconds
                path, frames, durations = current_data
                offscreen, reload_triggered = show_gif(matrix, offscreen, frames, durations, get_hold_seconds())
            else:
                # Show static image
                offscreen, reload_triggered = show_still(matrix, offscreen, current_img, get_hold_seconds())
            
            # If reload was triggered during display, continue to process it
            if reload_triggered:
                continue
            
            # Advance to next image only if still on
            if getIsRunning():
                idx = (idx + 1) % len(images)
                next_img = get_display_frame(images[idx])
                offscreen = fade_out_to_black(matrix, offscreen, current_img)
                if BLACK_PAUSE_S > 0:
                    time.sleep(BLACK_PAUSE_S)
                offscreen = fade_in_from_black(matrix, offscreen, next_img)
                current_img = next_img
        else:
            time.sleep(0.2)

except KeyboardInterrupt:
    pass
finally:
    import traceback
    matrix.Clear()
    print("Exiting...")
    traceback.print_exc()
    sys.exit(0)
