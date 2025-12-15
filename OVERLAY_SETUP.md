# LED Matrix - Overlay Filesystem Protection Setup

## Problem
When running with overlay filesystem enabled, the entire root filesystem becomes read-only, preventing uploads and config changes from being saved.

## Solution
Store uploads and config in a separate writable location (`/data/matrix`) while keeping the system protected with overlay enabled.

## Setup Instructions

### 1. Create Writable Data Directory
```bash
chmod +x setup_writable_data.sh
sudo ./setup_writable_data.sh
```

This script will:
- Create `/data/matrix/images` and `/data/matrix/config`
- Copy existing images and config files
- Set proper permissions
- Configure mount point

### 2. Enable Overlay Filesystem
```bash
sudo raspi-config nonint do_overlayfs 0
```

### 3. Reboot
```bash
sudo reboot
```

## How It Works

### Path Configuration
The code automatically detects if `/data/matrix` exists:

**With /data/matrix (overlay enabled):**
- Images: `/data/matrix/images/`
- Config: `/data/matrix/config/config.ini`
- Auth: `/data/matrix/config/.auth`

**Without /data/matrix (overlay disabled):**
- Images: `./matrix_images/`
- Config: `./config.ini`
- Auth: `./.auth`

### Files Modified
- `server.py`: Updated paths to use `/data/matrix`
- `viewer.py`: Updated paths to use `/data/matrix`

## Benefits

1. **System Protection**: Root filesystem is read-only, preventing SD card corruption on power loss
2. **Real-time Uploads**: Images and config can still be uploaded without reboot
3. **Automatic Fallback**: Works with or without overlay enabled
4. **No Performance Impact**: Direct file access, no overlay overhead for data

## Storage Options

The setup script uses `tmpfs` (RAM) for `/data` by default. For persistent storage across reboots, you can:

### Option A: Use SD Card Partition
```bash
# Create partition and mount
sudo mkdir -p /data
echo "/dev/mmcblk0p3 /data ext4 defaults,noatime 0 2" | sudo tee -a /etc/fstab
```

### Option B: Use USB Drive
```bash
# Mount USB drive
sudo mkdir -p /data
echo "/dev/sda1 /data ext4 defaults,noatime 0 2" | sudo tee -a /etc/fstab
```

## Verification

Check if overlay is enabled:
```bash
curl http://your-pi-ip:5000/api/overlay/status
```

Check current paths being used:
```bash
sudo python3 server.py
# Look for "Using data directory: /data/matrix" in logs
```

## Reverting

To disable overlay protection:
```bash
sudo raspi-config nonint do_overlayfs 1
sudo reboot
```

The code will automatically use local directories again.
