from bluezero import peripheral
import subprocess

SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
CHAR_UUID = '12345678-1234-5678-1234-56789abcdef1'

def write_callback(value, options):
    message = value.decode('utf-8')
    print(f"Received BLE message: {message}")

    if message.strip().upper() == "START":
        print("Starting service...")
        subprocess.run(["sudo", "systemctl", "start", "myservice"])  # replace with your service
    elif message.strip().upper() == "STOP":
        print("Stopping service...")
        subprocess.run(["sudo", "systemctl", "stop", "myservice"])

my_characteristic = peripheral.Characteristic(
    uuid=CHAR_UUID,
    flags=['write'],
    write_callback=write_callback
)

my_service = peripheral.Service(
    uuid=SERVICE_UUID,
    primary=True
)
my_service.add_characteristic(my_characteristic)

app = peripheral.Application()
app.add_service(my_service)

advert = peripheral.Advertisement("MyPiTrigger", ["1234"])
advert.register()

print("Advertising as BLE peripheral…")
app.run()