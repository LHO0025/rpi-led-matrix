from bluezero import peripheral

# Called when the client writes a value
def on_write(value, options):
    print("Received:", value)
    if value == b'1':
        print("Action: Turn ON")
    elif value == b'0':
        print("Action: Turn OFF")

# GATT service/characteristic definition
led_service = {
    'uuid': '12345678-1234-5678-1234-56789abcdef0',
    'characteristics': [{
        'uuid': '12345678-1234-5678-1234-56789abcdef1',
        'flags': ['write'],
        'write': on_write
    }]
}

# Create a Peripheral (advertises a GATT service)
device = peripheral.Peripheral(adapter_addr=None, local_name='PiBLE')
device.add_service(led_service)

print("Starting BLE GATT server as 'PiBLE'...")
device.run()
