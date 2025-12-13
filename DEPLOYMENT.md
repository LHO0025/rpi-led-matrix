# LED Matrix Control System

A complete system for controlling RGB LED matrix displays on Raspberry Pi with a web-based GUI.

## Features

- **Web GUI**: Modern React-based interface for controlling the display
- **Authentication**: Secure JWT-based authentication system
- **Image Management**: Upload, delete, and display images
- **Display Controls**: Adjust brightness and image hold time
- **Power Management**: Turn display on/off remotely
- **Overlay Filesystem Support**: Protection against SD card corruption
- **Auto-start**: Systemd service for automatic startup on boot

## Requirements

- Raspberry Pi (Zero W 2 or better)
- RGB LED Matrix display
- Python 3.7+
- Node.js 14+ (for building web app)

## Installation

### Quick Setup (Recommended)

On your Raspberry Pi, run these commands:

```bash
# Clone the repository
git clone https://github.com/LHO0025/rpi-led-matrix.git
cd rpi-led-matrix

# Make deploy script executable and run it
chmod +x deploy.sh
sudo ./deploy.sh
```

That's it! The script will:
- Install all system dependencies (Python, Node.js, build tools)
- Create Python virtual environment
- Install Python packages
- Install RGB Matrix library
- Build the React web application
- Generate security keys
- Set up systemd service for auto-start
- Start the system

The entire process takes 10-20 minutes depending on your Pi and internet speed.

### Manual Setup (Advanced)

1. Open your browser and navigate to: `http://<raspberry-pi-ip>:5000`
2. You'll be prompted to create a password (minimum 6 characters)
3. After setting the password, you'll be automatically logged in

## Manual Control

### Start the system:
```bash
sudo ./start.sh
```

### Stop the system:
```bash
sudo ./stop.sh
```

### View logs:
```bash
# Combined logs
sudo journalctl -u led-matrix-system -f

# Individual service logs
sudo tail -f /var/log/led-matrix-viewer.log
sudo tail -f /var/log/led-matrix-server.log
```

### Service management:
```bash
# Check status
sudo systemctl status led-matrix-system

# Restart
sudo systemctl restart led-matrix-system

# Disable auto-start
sudo systemctl disable led-matrix-system
```

## API Endpoints

### Authentication
- `GET /api/auth/status` - Check if password is set and token validity
- `POST /api/auth/setup` - Set initial password (only works once)
- `POST /api/auth/login` - Login and receive JWT token
- `GET /api/auth/verify` - Verify current token
- `POST /api/auth/change-password` - Change password (requires authentication)

### Display Control (requires authentication)
- `POST /set_brightness` - Set brightness (1-100)
- `POST /set_hold_seconds` - Set image display duration (10-300 seconds)
- `POST /turn_on` - Turn display on
- `POST /turn_off` - Turn display off

### Image Management (requires authentication)
- `GET /images` - List all images
- `GET /images/<filename>` - Get specific image
- `POST /upload_image` - Upload new image
- `DELETE /delete_image` - Delete images

### System Status
- `GET /api/health` - Health check
- `GET /api/config` - Get current configuration
- `GET /api/status` - Full system status

### Overlay Filesystem (requires authentication)
- `GET /api/overlay/status` - Check overlay status
- `POST /api/overlay/enable` - Enable overlay (requires reboot)
- `POST /api/overlay/disable` - Disable overlay (requires reboot)
- `POST /api/reboot` - Reboot system

## Configuration Files

- `config.ini` - Display settings (brightness, hold_seconds)
- `.env` - JWT secret key (generated automatically)
- `.auth` - Password hash (created on first login)

## Security

- All sensitive endpoints require JWT authentication
- Passwords are hashed using Werkzeug's secure password hashing
- JWT tokens expire after 24 hours
- File uploads are validated and sanitized
- Directory traversal attacks are prevented

## Overlay Filesystem

The system supports Raspberry Pi's overlay filesystem for SD card protection:

1. **Enable overlay** - Makes filesystem read-only to prevent corruption
2. **Disable overlay** - Allows file writes (for uploading images)
3. Both require a reboot to take effect

Recommended workflow:
- Keep overlay enabled during normal operation
- Disable only when uploading new images
- Re-enable after uploads complete

## Troubleshooting

### Service won't start
```bash
sudo journalctl -u led-matrix-system -n 50
```

### Display shows nothing
- Check viewer logs: `sudo tail -f /var/log/led-matrix-viewer.log`
- Verify images exist in `matrix_images/` folder
- Check matrix hardware connections

### Cannot access web GUI
- Verify server is running: `sudo systemctl status led-matrix-system`
- Check server logs: `sudo tail -f /var/log/led-matrix-server.log`
- Ensure port 5000 is not blocked by firewall

### Forgot password
Delete the auth file and restart:
```bash
sudo rm .auth
sudo systemctl restart led-matrix-system
```

## Development

### Rebuild web app:
```bash
cd my-app
npm install
npm run build
```

### Run in development mode:
```bash
# Terminal 1 - Backend
source venv/bin/activate
python3 server.py

# Terminal 2 - Frontend
cd my-app
npm run dev
```

## License

[Your License Here]
