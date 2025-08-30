#!/usr/bin/env python3
import time, sys, os
import numpy as np
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

# ---------- Settings ----------
IMAGE_FOLDER = "matrix_images"
HOLD_SECONDS = 12        # shorter holds reduce chance of drift on tiny CPU
FADE_STEPS = 24          # 20–32 is a good sweet spot on Zero 2 W
TARGET_FPS = 50          # 45–60 works; lower if you still see jitter
GAMMA = 2.2              # basic gamma for LED panels
BRIGHTNESS = 70          # keep PWM load reasonable
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
            # Preconvert to numpy uint8 for fast LUT application
            arr = np.asarray(canvas, dtype=np.uint8)
            imgs.append((p, arr))
        except Exception as e:
            print(f"Skipping {p}: {e}")
    if not imgs:
        sys.exit("No valid images after loading")
    return imgs

def make_gamma_table(gamma=2.2):
    # Map linear [0..255] -> gamma space [0..255]
    x = np.arange(256, dtype=np.float32) / 255.0
    y = np.clip(np.power(x, gamma) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    # And inverse (panel expects gamma-ish input; we want fades to be perceptually smooth)
    inv = np.clip(np.power(x, 1.0/gamma) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return y, inv

def apply_brightness_lut(img_u8, scale01, inv_gamma_lut):
    """
    img_u8: HxWx3 uint8 in (roughly) gamma space
    scale01: 0..1
    inv_gamma_lut: LUT to linearize before scaling (optional simple model)
    """
    # 1) linearize via inverse gamma LUT
    lin = inv_gamma_lut[img_u8]
    # 2) scale in linear space (uint16 math for speed/precision)
    #    (val * scale) ~ (val * (scale*256)) >> 8
    s = int(scale01 * 256 + 0.5)
    out = (lin.astype(np.uint16) * s) >> 8
    # 3) back to gamma space quickly with a power approx using a small LUT
    # Build once (cached) for all possible 0..255 values after scaling
    # Here we reuse the same gamma LUT path by converting through floats once.
    # For speed on Zero 2 W, make a single static gamma table:
    if not hasattr(apply_brightness_lut, "_gamma_table"):
        g, _ = make_gamma_table(GAMMA)
        apply_brightness_lut._gamma_table = g
    gtab = apply_brightness_lut._gamma_table
    return gtab[out.astype(np.uint8)]

def fade_between(matrix, off, img_from, img_to, steps=FADE_STEPS, fps=TARGET_FPS):
    """
    Crossfade: img_from -> img_to with perceptual scaling in linear domain.
    """
    frame_time = 1.0 / float(fps)
    start = time.perf_counter()

    # Pre-LUTs once
    _, inv = make_gamma_table(GAMMA)

    for i in range(steps + 1):
        t = i / float(steps)
        # Compute two brightnesses that sum to ~1 with slight easing (optional)
        a = (1.0 - t)
        b = t

        # Compute frames
        fA = apply_brightness_lut(img_from, a, inv)
        fB = apply_brightness_lut(img_to,   b, inv)
        frame = np.clip(fA.astype(np.uint16) + fB.astype(np.uint16), 0, 255).astype(np.uint8)

        # Push via offscreen canvas + SwapOnVSync
        # Convert numpy -> PIL Image without copying when possible
        pil_frame = Image.fromarray(frame, mode="RGB")
        off.SetImage(pil_frame, 0, 0)
        off = matrix.SwapOnVSync(off)

        # Fixed timestep pacing
        next_time = start + (i + 1) * frame_time
        remaining = next_time - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
    return off

def show_still(matrix, off, img, seconds):
    end = time.perf_counter() + seconds
    pil = Image.fromarray(img, mode="RGB")
    while True:
        off.SetImage(pil, 0, 0)
        off = matrix.SwapOnVSync(off)
        if time.perf_counter() >= end:
            return off
        # Small nap to avoid busy loop; vsync swap already paces nicely
        time.sleep(0.02)

# ----- Matrix config -----
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'   # change to your HAT if needed
options.brightness = BRIGHTNESS

# Pi Zero 2 W friendly knobs:
options.gpio_slowdown = 3     # try 2..4; higher if flicker/judder
# If your build supports it, consider:
# options.pwm_bits = 9        # 8–10 can reduce CPU
# options.limit_refresh_rate_hz = 100  # try 80–120 if available

matrix = RGBMatrix(options=options)
offscreen = matrix.CreateFrameCanvas()

# Preload & prepare images
images = load_images(IMAGE_FOLDER, (matrix.width, matrix.height))

try:
    print("Press CTRL-C to stop.")
    idx = 0
    path, current_img = images[idx]
    print(f"Displaying {path}")

    # Fade in from black by crossfading with a zero image
    black = np.zeros_like(current_img, dtype=np.uint8)
    offscreen = fade_between(matrix, offscreen, black, current_img)

    while True:
        offscreen = show_still(matrix, offscreen, current_img, HOLD_SECONDS)
        idx = (idx + 1) % len(images)
        next_path, next_img = images[idx]
        print(f"Displaying {next_path}")
        offscreen = fade_between(matrix, offscreen, current_img, next_img)
        current_img = next_img

except KeyboardInterrupt:
    pass
finally:
    matrix.Clear()
    sys.exit(0)
