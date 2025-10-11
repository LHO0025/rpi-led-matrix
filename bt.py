from bluezero import peripheral

# Action to perform when a BLE client writes a value
def on_write(value):
    print("Received value:", value)
    if value == b'1':
        print("Turning LED ON")
        # Here you can perform an action (e.g., GPIO output)
    elif value == b'0':
        print("Turning LED OFF")

# Define a simple characteristic
my_service_uuid = '12345678-1234-5678-1234-56789abcdef0'
my_char_uuid = '12345678-1234-5678-1234-56789abcdef1'

my_service = peripheral.Service(my_service_uuid)
my_char = peripheral.Characteristic(
    my_char_uuid,
    ['write'],             # allows remote app to write
    value=None,
    write_callback=on_write
)

# Add characteristic to the service
my_service.add_characteristic(my_char)

# Create and advertise the peripheral
my_device = peripheral.Peripheral([my_service],
                                  local_name='PiBLE')

print("Starting GATT server... (visible as 'PiBLE')")
my_device.run()
