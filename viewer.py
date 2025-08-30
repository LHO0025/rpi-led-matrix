#!/usr/bin/env python
import time
import sys
import os
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageEnhance

# ---------- Settings ----------
IMAGE_FOLDER = "matrix_images"
HOLD_SECONDS = 15           # time each image is fully shown (no fade)
FADE_STEPS = 30             # more steps = smoother fade
FADE_DELAY = 0.03           # delay between fade frames (seconds)
# ------------------------------

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
            # Scale to fit, keep aspect, then center on canvas if needed
            img.thumbnail(target_size, Image.LANCZOS)
            canvas = Image.new("RGB", target_size, (0, 0, 0))
            x = (target_size[0] - img.width) // 2
            y = (target_size[1] - img.height) // 2
            canvas.paste(img, (x, y))
            imgs.append((p, canvas))
        except Exception as e:
            print(f"Skipping {p}: {e}")
    if not imgs:
        sys.exit("No valid images after loading")
    return imgs

def fade_out(matrix, img, steps=FADE_STEPS, delay=FADE_DELAY):
    enhancer = ImageEnhance.Brightness(img)
    for i in range(steps, -1, -1):
        alpha = i / float(steps)
        frame = enhancer.enhance(alpha)
        matrix.SetImage(frame)
        time.sleep(delay)

def fade_in(matrix, img, steps=FADE_STEPS, delay=FADE_DELAY):
    enhancer = ImageEnhance.Brightness(img)
    for i in range(0, steps + 1):
        alpha = i / float(steps)
        frame = enhancer.enhance(alpha)
        matrix.SetImage(frame)
        time.sleep(delay)

# ----- Matrix config -----
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'
options.brightness = 75
matrix = RGBMatrix(options=options)

# Preload & prepare images
images = load_images(IMAGE_FOLDER, (matrix.width, matrix.height))

try:
    print("Press CTRL-C to stop.")
    # Start by fading in the first image from black
    idx = 0
    path, current_img = images[idx]
    print(f"Displaying {path}")
    fade_in(matrix, current_img)
    start = time.time()

    while True:
        # Hold the current image
        while time.time() - start < HOLD_SECONDS:
            time.sleep(0.05)

        # Next image index
        idx = (idx + 1) % len(images)
        next_path, next_img = images[idx]

        # Fade out current, fade in next
        fade_out(matrix, current_img)
        print(f"Displaying {next_path}")
        fade_in(matrix, next_img)

        # Advance
        current_img = next_img
        start = time.time()

except KeyboardInterrupt:
    pass
finally:
    matrix.Clear()
    sys.exit(0)
