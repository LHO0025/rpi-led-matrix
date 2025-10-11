from bluezero import peripheral

# UUIDs can be arbitrary, but must be valid (use uuidgen if you want)
SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
CHAR_UUID = '12345678-1234-5678-1234-56789abcdef1'

def on_write(value, options):
    # Convert bytearray to string and print it
    print("Received:", value.decode('utf-8'))

# Define the characteristic
test_characteristic = {
    'uuid': CHAR_UUID,
    'flags': ['write'],       # Only writable
    'write': on_write,        # Callback when written
}

# Define the service
test_service = {
    'uuid': SERVICE_UUID,
    'characteristics': [test_characteristic],
}

# Create the peripheral
device = peripheral.Peripheral(
    adapter_addr='B8:27:EB:00:00:00',  # Replace with your Pi's Bluetooth MAC (use `bluetoothctl show`)
    local_name='BluezeroTest',
    services=[test_service],
)

print("BLE server running. Waiting for write requests...")
device.run()
