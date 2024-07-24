import time
import sys
import requests
import io
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image
from flask import Flask
import threading

options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'  
matrix = RGBMatrix(options = options)

while True:
    try:
        resp = requests.get("http://192.168.88.178:81/splash_art_url")        
        splash_art_data = requests.get(resp.raw, verify=False).content
        splash_art_img = Image.open(io.BytesIO(splash_art_data))
        splash_art_img.thumbnail((64, 64), Image.Resampling.LANCZOS)
        matrix.SetImage(splash_art_img.convert('RGB'))
    except:
        pass
    time.sleep(1)  