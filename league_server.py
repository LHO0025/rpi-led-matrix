import time
import sys
import requests
import io
# from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image
from flask import Flask
import threading

# options = RGBMatrixOptions()
# options.rows = 64
# options.cols = 64
# options.chain_length = 1
# options.parallel = 1
# options.hardware_mapping = 'regular'  
# matrix = RGBMatrix(options = options)
current_splash_art_url = ""

def fetch_thread():
    global current_splash_art_url
    local_api = "https://127.0.0.1:2999/liveclientdata/allgamedata"
    is_running = True
    while is_running:
        try:
            print("Running! 1")
            resp = requests.get(local_api, verify=False)
            print("Running! 2")
            
            player = next((x for x in resp.json()['allPlayers'] if x['riotIdGameName'] == "EcolsX"), None)
            if player:
                champion_name = player['championName']
                skin_id = player['skinID']
                current_splash_art_url = f"https://ddragon.leagueoflegends.com/cdn/img/champion/loading/{champion_name}_{skin_id}.jpg"
                print(f"Updated current_splash_art_url to: {current_splash_art_url}")
            else:
                print("Player not found")
            # splash_art_data = requests.get( + ".jpg", verify=False).content
            # splash_art_img = Image.open(io.BytesIO(splash_art_data))
            # splash_art_img.thumbnail((64, 64), Image.Resampling.LANCZOS)
            # splash_art_img.show()
            

            # matrix.SetImage(splash_art_img.convert('RGB'))
        except Exception as error:
            print("An exception occurred:", error)
        time.sleep(1)    
        
x = threading.Thread(target=fetch_thread)
x.start()

test = "asdasdasdass"
 
app = Flask(__name__)
@app.route('/splash_art_url')
def index():
    return current_splash_art_url

app.run(host='0.0.0.0', port=81)
