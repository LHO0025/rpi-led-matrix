"""Peripheral device/GATT Server that also prints written values"""
import logging
import random

from bluezero import async_tools
from bluezero import adapter
from bluezero import peripheral

# constants
CPU_TMP_SRVC = '12341000-1234-1234-1234-123456789abc'
CPU_TMP_CHRC = '2A6E'   # reusing same char; now also writable for the demo
CPU_FMT_DSCP = '2904'


def read_value():
    cpu_value = random.randrange(3200, 5310, 10) / 100
    return list(int(cpu_value * 100).to_bytes(2, byteorder='little', signed=True))


def update_value(characteristic):
    new_value = read_value()
    characteristic.set_value(new_value)
    return characteristic.is_notifying


def notify_callback(notifying, characteristic):
    if notifying:
        async_tools.add_timer_seconds(2, update_value, characteristic)


def write_callback(value, options):
    """
    Called when a client writes to the characteristic.
    `value` is a list of uint8. `options` is a dict from BlueZ.
    """
    try:
        # Try to decode as UTF-8 text (common for simple tests)
        text = bytes(value).decode('utf-8')
    except Exception:
        text = None

    print("[GATT] Write received:")
    print(f"  raw bytes: {value}")
    if text is not None:
        print(f"  utf-8 text: '{text}'")

    # (Optional) echo last written value into the characteristic
    # so a read right after shows what was written:
    try:
        characteristic = options.get('characteristic')  # may not always be present
    except Exception:
        characteristic = None
    if characteristic:
        characteristic.set_value(value)

    # You can trigger side effects here (toggle GPIO, log, etc.)
    return True  # indicate success


def main(adapter_address):
    logger = logging.getLogger('localGATT')
    logger.setLevel(logging.DEBUG)

    print('CPU temperature is {}\u00B0C'.format(
        int.from_bytes(read_value(), byteorder='little', signed=True)/100))

    cpu_monitor = peripheral.Peripheral(adapter_address,
                                        local_name='CPU Monitor',
                                        appearance=1344)

    cpu_monitor.add_service(srv_id=1, uuid=CPU_TMP_SRVC, primary=True)

    cpu_monitor.add_characteristic(
        srv_id=1,
        chr_id=1,
        uuid=CPU_TMP_CHRC,
        value=[],
        notifying=False,
        # ← add write permissions so clients can write
        flags=['read', 'notify', 'write', 'write-without-response'],
        read_callback=read_value,
        write_callback=write_callback,
        notify_callback=notify_callback
    )

    cpu_monitor.add_descriptor(
        srv_id=1,
        chr_id=1,
        dsc_id=1,
        uuid=CPU_FMT_DSCP,
        value=[0x0E, 0xFE, 0x2F, 0x27, 0x01, 0x00, 0x00],
        flags=['read']
    )

    cpu_monitor.publish()


if __name__ == '__main__':
    main(list(adapter.Adapter.available())[0].address)
