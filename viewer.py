#!/usr/bin/env python
import time
import sys
import os
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

# ---------- Settings ----------
IMAGE_FOLDER = "matrix_images"
HOLD_SECONDS = 15      # time each image is fully shown
FADE_DELAY = 0.03      # seconds between brightness steps
BRIGHTNESS = 75        # max brightness (0-100)
FADE_STEPS = BRIGHTNESS  # number of steps (0 → BRIGHTNESS)
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
            img.thumbnail(target_size, Image.LANCZOS)
            canvas = Image.new("RGB", target_size, (0, 0, 0))
            x = (target_size[0] - img.width) // 2
            y = (target_size[1] - img.height) // 2
            canvas.paste(img, (x, y))
            imgs.append((p, canvas))
        except Exception as e:
            print(f"Skipping {p}: {e}")
    return imgs

def fade_out(matrix, steps=FADE_STEPS, delay=FADE_DELAY):
    for b in range(steps, -1, -1):
        matrix.brightness = b
        time.sleep(delay)

def fade_in(matrix, steps=FADE_STEPS, delay=FADE_DELAY):
    for b in range(0, steps + 1):
        matrix.brightness = b
        time.sleep(delay)

# ----- Matrix config -----
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'
options.brightness = BRIGHTNESS
matrix = RGBMatrix(options=options)

images = load_images(IMAGE_FOLDER, (matrix.width, matrix.height))

try:
    print("Press CTRL-C to stop.")
    idx = 0
    path, img = images[idx]
    print(f"Displaying {path}")
    matrix.SetImage(img)
    fade_in(matrix)  # fade up the first image
    start = time.time()

    while True:
        # Hold
        while time.time() - start < HOLD_SECONDS:
            time.sleep(0.05)

        # Next image
        idx = (idx + 1) % len(images)
        next_path, next_img = images[idx]

        fade_out(matrix)            # fade current out
        print(f"Displaying {next_path}")
        matrix.SetImage(next_img)   # swap while dark
        fade_in(matrix)             # fade next in

        start = time.time()

except KeyboardInterrupt:
    pass
finally:
    matrix.Clear()
    sys.exit(0)
