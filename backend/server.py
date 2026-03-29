from flask import Flask, jsonify, send_from_directory, request
import os
import sys
import subprocess
import logging
from flask_cors import CORS, cross_origin
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import socket
import configparser
import threading
import time
import re
import jwt
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv

from config import (
    PROJECT_ROOT, DATA_DIR, IMAGE_FOLDER, CONFIG_DIR,
    CONFIG_FILE, AUTH_FILE, ORDER_FILE, CTRL_SOCK,
    ensure_directories,
)

# Load environment variables from project root
_env_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(_env_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WEB_APP_FOLDER = os.path.join(PROJECT_ROOT, "frontend", "dist")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    logger.warning(
        "JWT_SECRET_KEY not found in environment. "
        "Tokens will be invalidated on every restart. "
        "Run scripts/deploy.sh or create a .env file with JWT_SECRET_KEY."
    )
    JWT_SECRET_KEY = os.urandom(32).hex()
JWT_EXPIRATION_HOURS = 24

# Ensure required directories exist and are writable
try:
    ensure_directories()
except RuntimeError as e:
    logger.error(str(e))
    sys.exit(1)

# 4MB max upload — images are displayed on a 64x64 matrix, anything larger is wasteful
app = Flask(__name__, static_folder=WEB_APP_FOLDER, static_url_path='')
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024

# Thumbnail cache directory
THUMB_DIR = os.path.join(IMAGE_FOLDER, ".thumbs")
os.makedirs(THUMB_DIR, exist_ok=True)


def send_ctl(cmd: bytes):
    """Send command to LED control socket. Returns True on success."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.settimeout(2.0)
            s.connect(CTRL_SOCK)
            s.send(cmd)
        logger.info(f"Sent control command: {cmd.decode()}")
        return True
    except socket.error as e:
        logger.error(f"Failed to send control command: {e}")
        return False


def load_config():
    """Load configuration from file."""
    config = configparser.ConfigParser()
    defaults = {
        "brightness": 50,
        "hold_seconds": 20
    }

    if os.path.isfile(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if "display" in config:
            return {
                "brightness": config.getint("display", "brightness", fallback=defaults["brightness"]),
                "hold_seconds": config.getint("display", "hold_seconds", fallback=defaults["hold_seconds"])
            }
    return defaults


def save_config(brightness=None, hold_seconds=None):
    """Save configuration to file."""
    config = configparser.ConfigParser()

    if os.path.isfile(CONFIG_FILE):
        config.read(CONFIG_FILE)

    if "display" not in config:
        config["display"] = {}

    if brightness is not None:
        config["display"]["brightness"] = str(brightness)

    if hold_seconds is not None:
        config["display"]["hold_seconds"] = str(hold_seconds)

    try:
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
        logger.info(f"Config saved: brightness={brightness}, hold_seconds={hold_seconds}")
    except OSError as e:
        logger.error(f"Failed to save config: {e}")


# =============================================================================
# Schedule Functions
# =============================================================================

_TIME_RE = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')

# Scheduler state — updated by API, read by scheduler thread
_schedule_lock = threading.Lock()
_schedule = {"enabled": False, "on_time": "08:00", "off_time": "23:00"}


def load_schedule():
    """Load schedule from config file."""
    config = configparser.ConfigParser()
    if os.path.isfile(CONFIG_FILE):
        config.read(CONFIG_FILE)
    result = {
        "enabled": config.getboolean("schedule", "enabled", fallback=False),
        "on_time": config.get("schedule", "on_time", fallback="08:00"),
        "off_time": config.get("schedule", "off_time", fallback="23:00"),
    }
    with _schedule_lock:
        _schedule.update(result)
    return result


def save_schedule(enabled=None, on_time=None, off_time=None):
    """Save schedule to config file and update running scheduler."""
    config = configparser.ConfigParser()
    if os.path.isfile(CONFIG_FILE):
        config.read(CONFIG_FILE)

    if "schedule" not in config:
        config["schedule"] = {}

    if enabled is not None:
        config["schedule"]["enabled"] = str(enabled).lower()
    if on_time is not None:
        config["schedule"]["on_time"] = on_time
    if off_time is not None:
        config["schedule"]["off_time"] = off_time

    try:
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
    except OSError as e:
        logger.error(f"Failed to save schedule: {e}")
        return

    # Update in-memory schedule for the running thread
    with _schedule_lock:
        if enabled is not None:
            _schedule["enabled"] = enabled
        if on_time is not None:
            _schedule["on_time"] = on_time
        if off_time is not None:
            _schedule["off_time"] = off_time

    logger.info(f"Schedule saved: enabled={enabled}, on={on_time}, off={off_time}")


def _time_to_minutes(t: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _should_be_on(now_minutes: int, on_minutes: int, off_minutes: int) -> bool:
    """Determine if display should be on, handling overnight schedules."""
    if on_minutes < off_minutes:
        # Normal: e.g., on=08:00, off=23:00
        return on_minutes <= now_minutes < off_minutes
    elif on_minutes > off_minutes:
        # Overnight: e.g., on=22:00, off=06:00
        return now_minutes >= on_minutes or now_minutes < off_minutes
    else:
        # on == off means always on
        return True


def schedule_thread():
    """Background thread that sends on/off commands based on schedule."""
    last_action = None

    while True:
        time.sleep(30)
        try:
            with _schedule_lock:
                enabled = _schedule["enabled"]
                on_time = _schedule["on_time"]
                off_time = _schedule["off_time"]

            if not enabled:
                last_action = None
                continue

            now = datetime.now()
            now_minutes = now.hour * 60 + now.minute
            on_minutes = _time_to_minutes(on_time)
            off_minutes = _time_to_minutes(off_time)

            should_on = _should_be_on(now_minutes, on_minutes, off_minutes)
            action = "on" if should_on else "off"

            if action != last_action:
                send_ctl(action.encode())
                logger.info(f"Schedule: sent '{action}' (now={now.strftime('%H:%M')}, on={on_time}, off={off_time})")
                last_action = action

        except Exception as e:
            logger.error(f"Schedule thread error: {e}")


# =============================================================================
# Authentication Functions
# =============================================================================

def load_password_hash():
    """Load the password hash from file."""
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r') as f:
                return f.read().strip()
        except OSError as e:
            logger.error(f"Failed to load password hash: {e}")
    return None


def save_password_hash(password: str):
    """Save a new password hash with secure permissions."""
    try:
        hash_val = generate_password_hash(password)
        # Use os.open with explicit mode to avoid permission race
        fd = os.open(AUTH_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(hash_val)
        logger.info("Password hash saved successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to save password hash: {e}")
        return False


def verify_password(password: str) -> bool:
    """Verify a password against the stored hash."""
    hash_val = load_password_hash()
    if not hash_val:
        return False
    return check_password_hash(hash_val, password)


def generate_token(username: str = "admin") -> str:
    """Generate a JWT token."""
    payload = {
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        return None


def token_required(f):
    """Decorator to require valid JWT token for routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            parts = auth_header.split(' ')
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
            else:
                return jsonify({'error': 'Invalid token format'}), 401

        if not token:
            return jsonify({'error': 'Authentication required'}), 401

        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        return f(*args, **kwargs)

    return decorated


def is_password_set() -> bool:
    """Check if a password has been set."""
    return load_password_hash() is not None


# =============================================================================
# Overlay Filesystem Management (for Raspberry Pi)
# =============================================================================

def is_overlay_enabled():
    """Check if overlay filesystem is currently enabled."""
    try:
        result = subprocess.run(
            ["sudo", "raspi-config", "nonint", "get_overlay_now"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() == "0"
    except Exception as e:
        logger.error(f"Failed to check overlay status: {e}")
        return None


def set_overlay(enable: bool):
    """Enable or disable the overlay filesystem. Changes require a reboot."""
    try:
        overlay_cmd = ["sudo", "raspi-config", "nonint", "do_overlayfs", "0" if enable else "1"]
        result = subprocess.run(overlay_cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            logger.error(f"Failed to set overlay: {result.stderr}")
            return False, result.stderr

        logger.info(f"Overlay filesystem {'enabled' if enable else 'disabled'} (reboot required)")
        return True, "Reboot required for changes to take effect"
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        logger.error(f"Failed to set overlay: {e}")
        return False, str(e)


def reboot_system():
    """Reboot the Raspberry Pi."""
    try:
        subprocess.Popen(["sudo", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.error(f"Failed to reboot: {e}")
        return False


# =============================================================================
# Web App Routes (Serve React frontend)
# =============================================================================

@app.route('/')
def serve_index():
    """Serve the main React app."""
    return send_from_directory(WEB_APP_FOLDER, 'index.html')


# =============================================================================
# Authentication Endpoints
# =============================================================================

@app.route("/api/auth/status", methods=["GET"])
@cross_origin()
def auth_status():
    """Check if password is set and if provided token is valid."""
    password_is_set = is_password_set()

    token_valid = False
    if 'Authorization' in request.headers:
        try:
            parts = request.headers['Authorization'].split(' ')
            if len(parts) == 2:
                token_valid = verify_token(parts[1]) is not None
        except (IndexError, ValueError):
            pass

    return jsonify({
        "password_set": password_is_set,
        "authenticated": token_valid
    }), 200


@app.route("/api/auth/setup", methods=["POST"])
@cross_origin()
def setup_password():
    """Set up initial password (only works if no password exists)."""
    if is_password_set():
        return jsonify({"error": "Password already set"}), 400

    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    password = data.get('password')

    if not password or len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    if save_password_hash(password):
        token = generate_token()
        return jsonify({
            'message': 'Password set successfully',
            'token': token
        }), 200

    return jsonify({'error': 'Failed to save password'}), 500


@app.route("/api/auth/login", methods=["POST"])
@cross_origin()
def login():
    """Authenticate and receive JWT token."""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    password = data.get('password')

    if not password:
        return jsonify({'error': 'Password required'}), 400

    if verify_password(password):
        token = generate_token()
        logger.info("Successful login")
        return jsonify({
            'message': 'Login successful',
            'token': token
        }), 200

    logger.warning("Failed login attempt")
    return jsonify({'error': 'Invalid password'}), 401


@app.route("/api/auth/verify", methods=["GET"])
@cross_origin()
@token_required
def verify_auth():
    """Verify that the current token is valid."""
    return jsonify({'message': 'Token is valid'}), 200


@app.route("/api/auth/change-password", methods=["POST"])
@cross_origin()
@token_required
def change_password():
    """Change password (requires authentication)."""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({'error': 'Both old and new passwords required'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    if not verify_password(old_password):
        return jsonify({'error': 'Current password is incorrect'}), 401

    if save_password_hash(new_password):
        token = generate_token()
        return jsonify({
            'message': 'Password changed successfully',
            'token': token
        }), 200

    return jsonify({'error': 'Failed to change password'}), 500


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files, fallback to index.html for SPA routing."""
    file_path = os.path.join(WEB_APP_FOLDER, path)
    if os.path.isfile(file_path):
        return send_from_directory(WEB_APP_FOLDER, path)
    return send_from_directory(WEB_APP_FOLDER, 'index.html')


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.route("/api/health", methods=["GET"])
@cross_origin()
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({"status": "healthy", "service": "led-matrix-server"}), 200


@app.route("/api/config", methods=["GET"])
@cross_origin()
def get_config():
    """Get current configuration."""
    config = load_config()
    return jsonify(config), 200


@app.route("/api/status", methods=["GET"])
@cross_origin()
def get_status():
    """Get system status including overlay state."""
    overlay_status = is_overlay_enabled()
    config = load_config()
    return jsonify({
        "config": config,
        "overlay_enabled": overlay_status,
        "overlay_check_available": overlay_status is not None
    }), 200


# =============================================================================
# Image Management Endpoints
# =============================================================================

@app.route("/images", methods=["GET"])
@cross_origin()
def list_images():
    """Return list of image filenames."""
    try:
        image_files = [
            f for f in os.listdir(IMAGE_FOLDER)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
        ]
        return jsonify({"images": image_files})
    except Exception as e:
        logger.error(f"Failed to list images: {e}")
        return jsonify({"error": "Failed to list images", "images": []}), 500


@app.route("/images/<filename>", methods=["GET"])
@cross_origin()
def serve_image(filename):
    """Serve an individual image file."""
    return send_from_directory(IMAGE_FOLDER, filename)


def _invalidate_thumbnail(filename):
    """Remove cached thumbnail for a file."""
    thumb_path = os.path.join(THUMB_DIR, filename + ".png")
    try:
        os.unlink(thumb_path)
    except FileNotFoundError:
        pass


@app.route("/images/thumb/<filename>", methods=["GET"])
@cross_origin()
def serve_thumbnail(filename):
    """Serve a cached thumbnail (150x150). Generates on first request."""
    from PIL import Image
    from io import BytesIO
    from flask import send_file
    import urllib.parse

    try:
        decoded_filename = urllib.parse.unquote(filename)
        file_path = os.path.join(IMAGE_FOLDER, decoded_filename)

        # Security check
        if not os.path.abspath(file_path).startswith(os.path.abspath(IMAGE_FOLDER)):
            raise ValueError("Invalid filename")

        # Case-insensitive match fallback
        if not os.path.exists(file_path):
            files = os.listdir(IMAGE_FOLDER)
            match = next((f for f in files if f.lower() == decoded_filename.lower()), None)
            if match:
                file_path = os.path.join(IMAGE_FOLDER, match)
                decoded_filename = match
            else:
                raise FileNotFoundError(f"File not found: {decoded_filename}")

        # Check thumbnail cache
        thumb_path = os.path.join(THUMB_DIR, decoded_filename + ".png")
        if os.path.exists(thumb_path):
            src_mtime = os.path.getmtime(file_path)
            thumb_mtime = os.path.getmtime(thumb_path)
            if thumb_mtime >= src_mtime:
                return send_file(thumb_path, mimetype='image/png', max_age=3600)

        # Generate thumbnail
        with Image.open(file_path) as img:
            img.thumbnail((150, 150), Image.LANCZOS)
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA')
            img.save(thumb_path, format='PNG', optimize=True)

        return send_file(thumb_path, mimetype='image/png', max_age=3600)
    except Exception as e:
        logger.error(f"Failed to generate thumbnail for '{filename}': {e}")
        # Return a 1x1 transparent pixel on error
        from io import BytesIO as _BytesIO
        from PIL import Image as _PILImage
        error_img = _PILImage.new('RGBA', (1, 1), (0, 0, 0, 0))
        buf = _BytesIO()
        error_img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')


@app.route("/delete_image", methods=["DELETE"])
@cross_origin()
@token_required
def delete_images():
    """Delete one or more image files by filename."""
    data = request.get_json()
    if not data or "filenames" not in data:
        return jsonify({"error": "Missing 'filenames' in request body"}), 400

    filenames = data["filenames"]
    if not isinstance(filenames, list) or not filenames:
        return jsonify({"error": "'filenames' must be a non-empty list"}), 400

    deleted = []
    errors = {}

    abs_image_folder = os.path.abspath(IMAGE_FOLDER)
    for filename in filenames:
        file_path = os.path.join(IMAGE_FOLDER, filename)

        if not os.path.abspath(file_path).startswith(abs_image_folder):
            errors[filename] = "Invalid filename"
            continue

        if not os.path.exists(file_path):
            errors[filename] = "File not found"
            continue

        try:
            os.remove(file_path)
            _invalidate_thumbnail(filename)
            deleted.append(filename)
        except Exception as e:
            errors[filename] = str(e)

    return jsonify({"deleted": deleted, "errors": errors}), 200


@app.route("/images/order", methods=["GET"])
@cross_origin()
def get_image_order():
    """Get the current image display order."""
    import json
    try:
        if os.path.exists(ORDER_FILE):
            with open(ORDER_FILE, 'r') as f:
                order = json.load(f)
            return jsonify({"order": order}), 200
        else:
            image_files = sorted([
                f for f in os.listdir(IMAGE_FOLDER)
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ])
            return jsonify({"order": image_files}), 200
    except Exception as e:
        logger.error(f"Failed to get image order: {e}")
        return jsonify({"error": "Failed to get image order"}), 500


@app.route("/images/order", methods=["POST"])
@cross_origin()
@token_required
def set_image_order():
    """Set the image display order."""
    import json

    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    if 'order' not in data:
        return jsonify({'error': 'Missing order array'}), 400

    order = data['order']
    if not isinstance(order, list):
        return jsonify({'error': 'Order must be an array of filenames'}), 400

    existing_files = set(
        f for f in os.listdir(IMAGE_FOLDER)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
    )

    invalid_files = [f for f in order if f not in existing_files]
    if invalid_files:
        logger.warning(f"Order contains non-existent files: {invalid_files}")

    valid_order = [f for f in order if f in existing_files]

    for f in existing_files:
        if f not in valid_order:
            valid_order.append(f)

    try:
        with open(ORDER_FILE, 'w') as f:
            json.dump(valid_order, f, indent=2)
        logger.info(f"Image order saved: {len(valid_order)} images")

        send_ctl(b"reload")

        return jsonify({
            'message': 'Order saved successfully',
            'order': valid_order
        }), 200
    except Exception as e:
        logger.error(f"Failed to save image order: {e}")
        return jsonify({'error': 'Failed to save order. Filesystem may be read-only.'}), 500


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload_image', methods=['POST'])
@cross_origin()
@token_required
def upload_image():
    """Upload a new image file. WebP files are auto-converted to PNG."""
    from PIL import Image

    if 'image' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    filename = secure_filename(file.filename)

    try:
        if filename.lower().endswith('.webp'):
            img = Image.open(file)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGBA')
            else:
                img = img.convert('RGB')

            filename = filename.rsplit('.', 1)[0] + '.png'
            save_path = os.path.join(IMAGE_FOLDER, filename)
            img.save(save_path, 'PNG', optimize=True)
            logger.info(f"WebP converted to PNG and saved: {filename}")
        else:
            save_path = os.path.join(IMAGE_FOLDER, filename)
            file.save(save_path)
            logger.info(f"Image uploaded: {filename}")

        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename,
            'url': f'/images/{filename}'
        }), 200
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        return jsonify({'error': 'Failed to save file. Filesystem may be read-only (overlay enabled).'}), 500


# =============================================================================
# Display Control Endpoints
# =============================================================================

@app.route('/set_brightness', methods=['POST'])
@cross_origin()
@token_required
def set_brightness():
    """Set display brightness (1-100)."""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    if 'brightness' not in data:
        return jsonify({'error': 'Missing brightness value'}), 400

    try:
        brightness = int(data['brightness'])
        if not (1 <= brightness <= 100):
            return jsonify({'error': 'Brightness must be between 1 and 100'}), 400
    except ValueError:
        return jsonify({'error': 'Brightness must be an integer'}), 400

    success = send_ctl(f"brightness:{brightness}".encode())
    save_config(brightness=brightness)

    if not success:
        return jsonify({'error': 'Config saved but viewer may not be running'}), 503

    return jsonify({'message': f'Brightness set to {brightness}', 'brightness': brightness}), 200


@app.route('/set_hold_seconds', methods=['POST'])
@cross_origin()
@token_required
def set_hold_seconds():
    """Set how long each image is displayed (in seconds)."""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    if 'hold_seconds' not in data:
        return jsonify({'error': 'Missing hold_seconds value'}), 400

    try:
        hold_seconds = int(data['hold_seconds'])
        if not (1 <= hold_seconds <= 3600):
            return jsonify({'error': 'hold_seconds must be between 1 and 3600'}), 400
    except ValueError:
        return jsonify({'error': 'hold_seconds must be an integer'}), 400

    success = send_ctl(f"hold:{hold_seconds}".encode())
    save_config(hold_seconds=hold_seconds)

    if not success:
        return jsonify({'error': 'Config saved but viewer may not be running'}), 503

    return jsonify({'message': f'Hold seconds set to {hold_seconds}', 'hold_seconds': hold_seconds}), 200


@app.route('/apply_changes', methods=['POST'])
@cross_origin()
@token_required
def apply_changes():
    """Apply all pending changes (brightness, hold_seconds, deletions) then reload viewer."""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    errors = []
    viewer_unreachable = False

    if 'brightness' in data:
        try:
            brightness = int(data['brightness'])
            if 1 <= brightness <= 100:
                if not send_ctl(f"brightness:{brightness}".encode()):
                    viewer_unreachable = True
                save_config(brightness=brightness)
            else:
                errors.append("Brightness must be between 1 and 100")
        except (ValueError, TypeError):
            errors.append("Invalid brightness value")

    if 'hold_seconds' in data:
        try:
            hold_seconds = int(data['hold_seconds'])
            if 1 <= hold_seconds <= 3600:
                if not send_ctl(f"hold:{hold_seconds}".encode()):
                    viewer_unreachable = True
                save_config(hold_seconds=hold_seconds)
            else:
                errors.append("hold_seconds must be between 1 and 3600")
        except (ValueError, TypeError):
            errors.append("Invalid hold_seconds value")

    deleted = []
    abs_image_folder = os.path.abspath(IMAGE_FOLDER)
    if 'delete_images' in data and isinstance(data['delete_images'], list):
        for filename in data['delete_images']:
            file_path = os.path.join(IMAGE_FOLDER, filename)
            if os.path.abspath(file_path).startswith(abs_image_folder) and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    _invalidate_thumbnail(filename)
                    deleted.append(filename)
                except Exception as e:
                    errors.append(f"Failed to delete {filename}: {str(e)}")

    if not send_ctl(b"reload"):
        viewer_unreachable = True

    status_code = 200
    result = {
        'message': 'Changes applied',
        'deleted': deleted,
        'errors': errors if errors else None
    }
    if viewer_unreachable:
        result['warning'] = 'Viewer may not be running — config saved but display not updated'
        status_code = 207  # Multi-Status

    return jsonify(result), status_code


@app.route("/turn_on", methods=["POST", "GET"])
@cross_origin()
@token_required
def turn_on():
    """Turn on the LED display."""
    success = send_ctl(b"on")
    if success:
        return jsonify({"status": "success", "action": "on"}), 200
    return jsonify({"status": "error", "action": "on", "message": "Viewer may not be running"}), 503


@app.route("/turn_off", methods=["POST", "GET"])
@cross_origin()
@token_required
def turn_off():
    """Turn off the LED display."""
    success = send_ctl(b"off")
    if success:
        return jsonify({"status": "success", "action": "off"}), 200
    return jsonify({"status": "error", "action": "off", "message": "Viewer may not be running"}), 503


# =============================================================================
# Overlay Filesystem Endpoints
# =============================================================================

@app.route("/api/overlay/status", methods=["GET"])
@cross_origin()
def overlay_status():
    """Check if overlay filesystem is enabled."""
    enabled = is_overlay_enabled()
    if enabled is None:
        return jsonify({"error": "Could not determine overlay status", "available": False}), 200
    return jsonify({"enabled": enabled, "available": True}), 200


@app.route("/api/overlay/disable", methods=["POST"])
@cross_origin()
@token_required
def disable_overlay():
    """Disable overlay filesystem to allow writes. Requires reboot."""
    success, message = set_overlay(False)
    if success:
        return jsonify({
            "status": "success",
            "message": message,
            "action": "Overlay will be disabled after reboot"
        }), 200
    return jsonify({"status": "error", "message": message}), 500


@app.route("/api/overlay/enable", methods=["POST"])
@cross_origin()
@token_required
def enable_overlay():
    """Enable overlay filesystem for read-only protection. Requires reboot."""
    success, message = set_overlay(True)
    if success:
        return jsonify({
            "status": "success",
            "message": message,
            "action": "Overlay will be enabled after reboot"
        }), 200
    return jsonify({"status": "error", "message": message}), 500


@app.route("/api/reboot", methods=["POST"])
@cross_origin()
@token_required
def reboot():
    """Reboot the Raspberry Pi."""
    if reboot_system():
        return jsonify({"status": "success", "message": "System is rebooting..."}), 200
    return jsonify({"status": "error", "message": "Failed to initiate reboot"}), 500


# =============================================================================
# Schedule Endpoints
# =============================================================================

@app.route("/api/schedule", methods=["GET"])
@cross_origin()
def get_schedule():
    """Get current schedule configuration."""
    sched = load_schedule()
    return jsonify(sched), 200


@app.route("/api/schedule", methods=["POST"])
@cross_origin()
@token_required
def set_schedule():
    """Update schedule configuration."""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    enabled = data.get('enabled')
    on_time = data.get('on_time')
    off_time = data.get('off_time')

    if enabled is not None and not isinstance(enabled, bool):
        return jsonify({'error': 'enabled must be a boolean'}), 400
    if on_time is not None and not _TIME_RE.match(on_time):
        return jsonify({'error': 'on_time must be in HH:MM format'}), 400
    if off_time is not None and not _TIME_RE.match(off_time):
        return jsonify({'error': 'off_time must be in HH:MM format'}), 400

    save_schedule(enabled=enabled, on_time=on_time, off_time=off_time)

    return jsonify({
        'message': 'Schedule updated',
        'schedule': {
            'enabled': enabled if enabled is not None else _schedule['enabled'],
            'on_time': on_time if on_time is not None else _schedule['on_time'],
            'off_time': off_time if off_time is not None else _schedule['off_time'],
        }
    }), 200


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    # Set CPU affinity to core 0 only (leave cores 1-3 for viewer)
    try:
        os.sched_setaffinity(0, {0})
        logger.info("Server CPU affinity set to core 0")
    except (AttributeError, OSError) as e:
        logger.warning(f"Could not set CPU affinity: {e}")

    logger.info("Starting LED Matrix Server...")
    logger.info(f"Image folder: {IMAGE_FOLDER}")
    logger.info(f"Web app folder: {WEB_APP_FOLDER}")
    logger.info(f"Config file: {CONFIG_FILE}")

    # Check for --reset-password flag
    if "--reset-password" in sys.argv:
        import secrets
        new_pw = secrets.token_urlsafe(12)
        save_password_hash(new_pw)
        logger.info("Password has been reset")
        print(f"✓ Password reset to: {new_pw}")
        sys.exit(0)

    # Set default password if none exists
    if not is_password_set():
        default_password = "hello123"
        save_password_hash(default_password)
        logger.info(f"Default password set: {default_password}")

    config = load_config()
    logger.info(f"Current config: {config}")
    logger.info(f"Using data directory: {DATA_DIR}")

    # Load and start schedule
    sched = load_schedule()
    logger.info(f"Schedule: {sched}")
    threading.Thread(target=schedule_thread, daemon=True).start()

    # Check overlay status
    overlay = is_overlay_enabled()
    if overlay is not None:
        logger.info(f"Overlay filesystem: {'enabled' if overlay else 'disabled'}")
        if overlay and DATA_DIR == PROJECT_ROOT:
            logger.warning("Overlay is enabled but using local directories - uploads may not persist!")
            logger.warning("Run scripts/setup_writable_data.sh to create /data/matrix for writable storage")

    app.run(host="0.0.0.0", port=5000, threaded=True)
