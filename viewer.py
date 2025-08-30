#!/usr/bin/env python3
import time, sys, os
import numpy as np
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

# ---------- Settings ----------
IMAGE_FOLDER = "matrix_images"
HOLD_SECONDS = 5

# Separate timings for OUT and IN so you can exaggerate the “dim then light up” feel
FADE_OUT_STEPS = 28      # more steps = slower/smoother
FADE_IN_STEPS  = 32
FADE_OUT_FPS   = 40      # lower FPS = slower fade
FADE_IN_FPS    = 40

GAMMA = 2.2
BRIGHTNESS = 70
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
    return imgs

def make_gamma_tables(gamma=GAMMA):
    x = np.arange(256, dtype=np.float32) / 255.0
    to_gamma = np.clip((x ** gamma) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    to_linear = np.clip((x ** (1.0/gamma)) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return to_gamma, to_linear

_TO_GAMMA, _TO_LINEAR = make_gamma_tables(GAMMA)

def scale_perceptual(img_u8, scale01):
    """
    Perceptual fade: linearize -> scale -> re-apply gamma.
    img_u8: HxWx3 uint8 (gamma-ish)
    scale01: 0..1
    """
    lin = _TO_LINEAR[img_u8]                   # linearize
    s = int(scale01 * 256 + 0.5)
    out = (lin.astype(np.uint16) * s) >> 8     # scale
    return _TO_GAMMA[out.astype(np.uint8)]     # back to gamma

def blit(matrix, off, frame_u8):
    pil_frame = Image.fromarray(frame_u8, mode="RGB")
    off.SetImage(pil_frame, 0, 0)
    return matrix.SwapOnVSync(off)

def fade_out_to_black(matrix, off, img, steps=FADE_OUT_STEPS, fps=FADE_OUT_FPS):
    frame_time = 1.0 / float(fps)
    start = time.perf_counter()
    # 1.0 -> 0.0
    for i in range(steps + 1):
        t = i / float(steps)
        # OPTIONAL easing (slower at the start, quicker at end); try t*t or smoothstep
        a = 1.0 - t*t
        frame = scale_perceptual(img, max(a, 0.0))
        off = blit(matrix, off, frame)

        next_time = start + (i + 1) * frame_time
        remain = next_time - time.perf_counter()
        if remain > 0:
            time.sleep(remain)
    # ensure true black at the end
    off = blit(matrix, off, np.zeros_like(img, dtype=np.uint8))
    return off

def fade_in_from_black(matrix, off, img, steps=FADE_IN_STEPS, fps=FADE_IN_FPS):
    frame_time = 1.0 / float(fps)
    start = time.perf_counter()
    # 0.0 -> 1.0
    for i in range(steps + 1):
        t = i / float(steps)
        # OPTIONAL easing (gentle start): use t*t or smoothstep
        b = t*t
        frame = scale_perceptual(img, min(max(b, 0.0), 1.0))
        off = blit(matrix, off, frame)

        next_time = start + (i + 1) * frame_time
        remain = next_time - time.perf_counter()
        if remain > 0:
            time.sleep(remain)
    return off

def show_still(matrix, off, img, seconds):
    end = time.perf_counter() + seconds
    pil = Image.fromarray(img, mode="RGB")
    while True:
        off.SetImage(pil, 0, 0)
        off = matrix.SwapOnVSync(off)
        if time.perf_counter() >= end:
            return off
        time.sleep(0.02)

# ----- Matrix config -----
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'
options.brightness = BRIGHTNESS
options.gpio_slowdown = 3     # Zero 2 W often likes 3; try 2–4 if needed
# options.pwm_bits = 9
# options.limit_refresh_rate_hz = 100

matrix = RGBMatrix(options=options)
offscreen = matrix.CreateFrameCanvas()

# Preload & prepare images
images = load_images(IMAGE_FOLDER, (matrix.width, matrix.height))

try:
    print("Press CTRL-C to stop.")
    idx = 0
    path, current_img = images[idx]
    print(f"Displaying {path}")

    # Fade in first image from black (nice intro)
    offscreen = fade_in_from_black(matrix, offscreen, current_img)

    while True:
        offscreen = show_still(matrix, offscreen, current_img, HOLD_SECONDS)

        idx = (idx + 1) % len(images)
        next_path, next_img = images[idx]
        print(f"Transition to {next_path}")

        # NEW transition style: dim to black, then light up the new one
        offscreen = fade_out_to_black(matrix, offscreen, current_img)
        offscreen = fade_in_from_black(matrix, offscreen, next_img)

        current_img = next_img

except KeyboardInterrupt:
    pass
finally:
    matrix.Clear()
    sys.exit(0)
