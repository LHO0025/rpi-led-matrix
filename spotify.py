import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import time
import sys
import requests
import io
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
from PIL import Image
import threading

options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'regular'  
matrix = RGBMatrix(options = options)


sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="72dfcbd58ae646a08e3a4e2dfa10d610",
                                               client_secret="eff663d28afb4f298f230c9f6e7857f6",
                                               redirect_uri="http://127.0.0.1:8888/callback",
                                               scope="user-read-currently-playing"))

prev_img_url = ""

def thread_function(matrix):
    pass
    # offscreen_canvas = matrix.CreateFrameCanvas()
    # font = graphics.Font()
    # font.LoadFont("../../../fonts/7x13.bdf")
    # textColor = graphics.Color(255, 255, 0)
    # pos = offscreen_canvas.width
    # my_text = "asdashdjkashkdahksjd"

    # while True:
    #     offscreen_canvas.Clear()
    #     len = graphics.DrawText(offscreen_canvas, font, pos, 10, textColor, my_text)
    #     pos -= 1
    #     if (pos + len < 0):
    #         pos = offscreen_canvas.width

    #     time.sleep(0.05)
    #     offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)

x = threading.Thread(target=thread_function, args=[matrix])
x.start()

while True:
    try:
        result = sp.current_user_playing_track()
        if result is not None and prev_img_url != result["item"]["album"]["images"][0]["url"]:
            prev_img_url = result["item"]["album"]["images"][0]["url"]
            imageURL = result["item"]["album"]["images"][0]["url"]
            img_data = requests.get(imageURL).content
            image = Image.open(io.BytesIO(img_data))
            image.thumbnail((matrix.width, matrix.height), Image.Resampling.LANCZOS)
            matrix.SetImage(image.convert('RGB'))
    except:
        print("there was an error")
    
    time.sleep(1)


# result = sp.current_user_playing_track()
# song = result["item"]["name"]
# imageURL = result["item"]["album"]["images"][0]["url"]
# img_data = requests.get(imageURL).content
# image = Image.open(io.BytesIO(img_data))
# image.thumbnail((matrix.width, matrix.height), Image.Resampling.LANCZOS)
# matrix.SetImage(image.convert('RGB'))