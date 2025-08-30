from rgbmatrix import RGBMatrix, RGBMatrixOptions
import time
from PIL import Image

# Setup matrix
options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'
options.brightness = 80  # initial brightness (max 80)

matrix = RGBMatrix(options=options)

# Load images
images = [Image.open("image1.png"), Image.open("image2.png")]

def show_image(image):
    matrix.SetImage(image.convert("RGB"))

def breathe_transition(old_img, new_img, steps=20, delay=0.05, max_brightness=80):
    # Fade out old image
    for b in reversed(range(0, max_brightness+1, int(max_brightness/steps))):
        matrix.brightness = b
        show_image(old_img)
        time.sleep(delay)

    # Fade in new image
    for b in range(0, max_brightness+1, int(max_brightness/steps)):
        matrix.brightness = b
        show_image(new_img)
        time.sleep(delay)

# Example usage
current = images[0]
show_image(current)
time.sleep(2)

next_img = images[1]
breathe_transition(current, next_img, max_brightness=80)
current = next_img
