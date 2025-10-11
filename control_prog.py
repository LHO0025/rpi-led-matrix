import socket
def send_ctl(cmd: bytes):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    s.connect("/tmp/ledctl.sock")
    s.send(cmd)
    s.close()

def led_off(): send_ctl(b"off")
def led_on():  send_ctl(b"on")



led_off()