import time
import sys
import requests
import io
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'  
matrix = RGBMatrix(options = options)

api_url = "https://api.nasa.gov/planetary/apod"
api_key = "EIxtZ1OCPmcjO7GYbuoro79wIvvGyq5mIJXKJHdS"
resp = requests.get(api_url + "?api_key=" + api_key)
img_url = resp.json()['url']

img_data = requests.get(img_url).content
image = Image.open(io.BytesIO(img_data))



width, height = image.size

if width > height:
    new_width = new_height = height
    left = (width - height) // 2
    top = 0
else:
    new_width = new_height = width
    left = 0
    top = (height - width) // 2

right = left + new_width
bottom = top + new_height

cropped_image = image.crop((left, top, right, bottom))
cropped_image.thumbnail((matrix.width, matrix.height), Image.Resampling.LANCZOS)
matrix.SetImage(cropped_image.convert('RGB'))

try:
    print("Press CTRL-C to stop.")
    while True:
        time.sleep(100)
except KeyboardInterrupt:
    sys.exit(0)