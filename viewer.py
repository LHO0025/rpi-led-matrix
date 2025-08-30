#!/usr/bin/env python
import time
import sys
import os
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

# Folder containing images
image_folder = "matrix_images"

# Load all image paths
if not os.path.isdir(image_folder):
    sys.exit(f"Folder '{image_folder}' not found")

image_files = [os.path.join(image_folder, f) for f in os.listdir(image_folder)
               if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))]

if not image_files:
    sys.exit("No image files found in folder")

# Configuration for the matrix
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'

matrix = RGBMatrix(options=options)

try:
    print("Press CTRL-C to stop.")
    while True:
        for image_file in image_files:
            print(f"Displaying {image_file}")
            image = Image.open(image_file)
            image.thumbnail((matrix.width, matrix.height), Image.ANTIALIAS)
            matrix.SetImage(image.convert('RGB'))
            time.sleep(15)  # show each image for 15 seconds
except KeyboardInterrupt:
    sys.exit(0)
