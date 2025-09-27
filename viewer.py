#!/usr/bin/env python3
import time, sys, os
import numpy as np
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image
import random

# ---------- Settings ----------
IMAGE_FOLDER = "matrix_images"
HOLD_SECONDS = 30

FADE_STEPS = 40          # increase for longer fades (e.g., 48)
FADE_FPS   = 30          # lower = longer fades (e.g., 28)

BLACK_PAUSE_S = 0.05     # small dramatic pause at black; set 0.0 to disable

GAMMA = 2.2
BRIGHTNESS = 80
# -----------------------------

def load_images(folder, target_size):
    if not os.path.isdir(folder):
        sys.exit(f"Folder '{folder}' not found")
    paths = [os.path.join(folder, f) for f in os.listdir(folder)
             if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))]
    if not paths:
        sys.exit("No image files found in folder")

    imgs = []
    for p in sorted(paths):
        try:
            img = Image.open(p).convert("RGB")
            img.thumbnail(target_size, Image.LANCZOS)
            canvas = Image.new("RGB", target_size, (0, 0, 0))
            x = (target_size[0] - img.width) // 2
            y = (target_size[1] - img.height) // 2
            canvas.paste(img, (x, y))
            arr = np.asarray(canvas, dtype=np.uint8)
            imgs.append((p, arr))
        except Exception as e:
            print(f"Skipping {p}: {e}")
    if not imgs:
        sys.exit("No valid images after loading")
    random.shuffle(imgs)
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
    pil_frame = Image.fromarray(frame_u8, mode="RGB")
    off.SetImage(pil_frame, 0, 0)
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

def show_still(matrix, off, img, seconds):
    pil_frame = Image.fromarray(img, mode="RGB")
    off.SetImage(pil_frame, 0, 0)
    off = matrix.SwapOnVSync(off)
    time.sleep(seconds)
    return off

# ----- Matrix config -----
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'
options.brightness = BRIGHTNESS
options.gpio_slowdown = 1
# options.pwm_bits = 9
# options.limit_refresh_rate_hz = 100

matrix = RGBMatrix(options=options)
offscreen = matrix.CreateFrameCanvas()

images = load_images(IMAGE_FOLDER, (matrix.width, matrix.height))

try:
    print("Press CTRL-C to stop.")
    idx = 0
    path, current_img = images[idx]

    offscreen = fade_in_from_black(matrix, offscreen, current_img)

    while True:
        offscreen = show_still(matrix, offscreen, current_img, HOLD_SECONDS)

        idx = (idx + 1) % len(images)
        next_path, next_img = images[idx]

        offscreen = fade_out_to_black(matrix, offscreen, current_img)
        if BLACK_PAUSE_S > 0:
            time.sleep(BLACK_PAUSE_S)
        offscreen = fade_in_from_black(matrix, offscreen, next_img)

        current_img = next_img

except KeyboardInterrupt:
    pass
finally:
    matrix.Clear()
    sys.exit(0)
