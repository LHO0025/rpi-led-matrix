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

local_api = "https://127.0.0.1:2999/liveclientdata/allgamedata"

is_running = True

while is_running:
    try:
        print("Running! 1")
        resp = requests.get(local_api, verify=False)
        print("Running! 2")
        
        player = next((x for x in resp.json()['allPlayers'] if x['riotIdGameName'] == "EcolsX"), None)
        champion_name = player['championName']
        skin_id = player['skinID']
        splash_art_data = requests.get("https://ddragon.leagueoflegends.com/cdn/img/champion/splash/" + champion_name + "_" + str(skin_id) + ".jpg", verify=False).content
        splash_art_img = Image.open(io.BytesIO(splash_art_data))
        splash_art_img.thumbnail((64, 64), Image.Resampling.LANCZOS)
        matrix.SetImage(splash_art_img.convert('RGB'))
    except:
        pass
    time.sleep(5)    
    

# try:
#     print("Press CTRL-C to stop.")
#     while True:
#         time.sleep(100)
# except KeyboardInterrupt:
#     sys.exit(0)