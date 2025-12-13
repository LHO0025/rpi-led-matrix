from flask import Flask, jsonify, send_from_directory, request
import os
import subprocess
import logging
from flask_cors import CORS, cross_origin
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import socket
import configparser
import jwt
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_FOLDER = os.path.join(BASE_DIR, "matrix_images")
WEB_APP_FOLDER = os.path.join(BASE_DIR, "my-app", "dist")
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")
AUTH_FILE = os.path.join(BASE_DIR, ".auth")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', os.urandom(32).hex())
JWT_EXPIRATION_HOURS = 24

# Ensure required directories exist
os.makedirs(IMAGE_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder=WEB_APP_FOLDER, static_url_path='')
cors = CORS(app)  # allow CORS for all domains on all routes.
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size


def send_ctl(cmd: bytes):
    """Send command to LED control socket."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.connect("/tmp/ledctl.sock")
        s.send(cmd)
        s.close()
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

    with open(CONFIG_FILE, "w") as f:
        config.write(f)
    logger.info(f"Config saved: brightness={brightness}, hold_seconds={hold_seconds}")


# =============================================================================
# Authentication Functions
# =============================================================================

def load_password_hash():
    """Load the password hash from file."""
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r') as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to load password hash: {e}")
    return None


def save_password_hash(password: str):
    """Save a new password hash."""
    try:
        hash_val = generate_password_hash(password)
        with open(AUTH_FILE, 'w') as f:
            f.write(hash_val)
        os.chmod(AUTH_FILE, 0o600)  # Secure file permissions
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
        
        # Check for token in Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
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
        # Returns 0 if overlay is enabled, 1 if disabled
        return result.stdout.strip() == "0"
    except Exception as e:
        logger.error(f"Failed to check overlay status: {e}")
        return None


def set_overlay(enable: bool):
    """
    Enable or disable the overlay filesystem.
    Note: Changes require a reboot to take effect.
    """
    try:
        # Set overlay configuration
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
    
    # Check if token is provided and valid
    token_valid = False
    if 'Authorization' in request.headers:
        try:
            token = request.headers['Authorization'].split(' ')[1]
            token_valid = verify_token(token) is not None
        except:
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
    # Fallback to index.html for client-side routing
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


@app.route("/delete_image", methods=["DELETE"])
@cross_origin()
@token_required
def delete_images():
    """
    Delete one or more image files by filename.
    Accepts JSON: { "filenames": ["file1.jpg", "file2.png"] }
    """
    data = request.get_json()
    if not data or "filenames" not in data:
        return jsonify({"error": "Missing 'filenames' in request body"}), 400

    filenames = data["filenames"]
    if not isinstance(filenames, list) or not filenames:
        return jsonify({"error": "'filenames' must be a non-empty list"}), 400

    deleted = []
    errors = {}

    for filename in filenames:
        file_path = os.path.join(IMAGE_FOLDER, filename)

        # Prevent directory traversal
        if not os.path.abspath(file_path).startswith(IMAGE_FOLDER):
            errors[filename] = "Invalid filename"
            continue

        if not os.path.exists(file_path):
            errors[filename] = "File not found"
            continue

        try:
            os.remove(file_path)
            deleted.append(filename)
        except Exception as e:
            errors[filename] = str(e)

    return jsonify({"deleted": deleted, "errors": errors}), 200



def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload_image', methods=['POST'])
@cross_origin()
@token_required
def upload_image():
    """
    Upload a new image file.
    Note: If overlay filesystem is enabled, this will fail silently.
    Consider disabling overlay before uploading.
    """
    # Check if any file is in the request
    if 'image' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    # Sanitize filename
    filename = secure_filename(file.filename)
    save_path = os.path.join(IMAGE_FOLDER, filename)
    
    try:
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

    if not send_ctl(f"brightness:{brightness}".encode()):
        logger.warning("Could not send brightness command to LED controller")
    
    save_config(brightness=brightness)
    
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

    if not send_ctl(f"hold:{hold_seconds}".encode()):
        logger.warning("Could not send hold command to LED controller")
    
    save_config(hold_seconds=hold_seconds)
    
    return jsonify({'message': f'Hold seconds set to {hold_seconds}', 'hold_seconds': hold_seconds}), 200


@app.route('/apply_changes', methods=['POST'])
@cross_origin()
@token_required
def apply_changes():
    """
    Apply all pending changes at once:
    - brightness
    - hold_seconds
    - deleted images
    - uploaded images (already on disk)
    Then send reload command to viewer.
    """
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    errors = []
    
    # Apply brightness if provided
    if 'brightness' in data:
        try:
            brightness = int(data['brightness'])
            if 1 <= brightness <= 100:
                send_ctl(f"brightness:{brightness}".encode())
                save_config(brightness=brightness)
            else:
                errors.append("Brightness must be between 1 and 100")
        except (ValueError, TypeError):
            errors.append("Invalid brightness value")
    
    # Apply hold_seconds if provided
    if 'hold_seconds' in data:
        try:
            hold_seconds = int(data['hold_seconds'])
            if 1 <= hold_seconds <= 3600:
                send_ctl(f"hold:{hold_seconds}".encode())
                save_config(hold_seconds=hold_seconds)
            else:
                errors.append("hold_seconds must be between 1 and 3600")
        except (ValueError, TypeError):
            errors.append("Invalid hold_seconds value")
    
    # Delete images if provided
    deleted = []
    if 'delete_images' in data and isinstance(data['delete_images'], list):
        for filename in data['delete_images']:
            file_path = os.path.join(IMAGE_FOLDER, filename)
            if os.path.abspath(file_path).startswith(IMAGE_FOLDER) and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    deleted.append(filename)
                except Exception as e:
                    errors.append(f"Failed to delete {filename}: {str(e)}")
    
    # Send reload command to viewer to reload images and restart display
    send_ctl(b"reload")
    
    return jsonify({
        'message': 'Changes applied',
        'deleted': deleted,
        'errors': errors if errors else None
    }), 200


@app.route("/turn_on", methods=["POST", "GET"])
@cross_origin()
@token_required
def turn_on():
    """Turn on the LED display."""
    success = send_ctl(b"on")
    if success:
        return jsonify({"status": "success", "action": "on"}), 200
    return jsonify({"status": "warning", "action": "on", "message": "Command sent but controller may not be running"}), 200


@app.route("/turn_off", methods=["POST", "GET"])
@cross_origin()
@token_required
def turn_off():
    """Turn off the LED display."""
    success = send_ctl(b"off")
    if success:
        return jsonify({"status": "success", "action": "off"}), 200
    return jsonify({"status": "warning", "action": "off", "message": "Command sent but controller may not be running"}), 200


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
    """
    Disable overlay filesystem to allow writes.
    Requires reboot to take effect.
    """
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
    """
    Enable overlay filesystem for read-only protection.
    Requires reboot to take effect.
    """
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
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    logger.info(f"Starting LED Matrix Server...")
    logger.info(f"Image folder: {IMAGE_FOLDER}")
    logger.info(f"Web app folder: {WEB_APP_FOLDER}")
    logger.info(f"Config file: {CONFIG_FILE}")
    
    # Set default password if none exists
    if not is_password_set():
        default_password = "jakipz123"
        save_password_hash(default_password)
        logger.info(f"Default password set: {default_password}")
    
    # Load and log current config
    config = load_config()
    logger.info(f"Current config: {config}")
    
    # Check overlay status
    overlay = is_overlay_enabled()
    if overlay is not None:
        logger.info(f"Overlay filesystem: {'enabled' if overlay else 'disabled'}")
    
    # Run server
    app.run(host="0.0.0.0", port=5000, threaded=True)