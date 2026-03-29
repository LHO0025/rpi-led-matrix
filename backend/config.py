"""Shared path and configuration logic for server and viewer."""

import os

# Project root is the parent of the backend/ directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Use /data/matrix for writable storage (overlay filesystem protection).
# Falls back to project root if /data/matrix doesn't exist.
_DATA_MATRIX = "/data/matrix"
DATA_DIR = _DATA_MATRIX if os.path.exists(_DATA_MATRIX) else PROJECT_ROOT

IMAGE_FOLDER = os.path.join(
    DATA_DIR, "images" if DATA_DIR == _DATA_MATRIX else "matrix_images"
)
CONFIG_DIR = os.path.join(
    DATA_DIR, "config" if DATA_DIR == _DATA_MATRIX else ""
)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.ini")
AUTH_FILE = os.path.join(CONFIG_DIR, ".auth")
ORDER_FILE = os.path.join(IMAGE_FOLDER, "order.json")

CTRL_SOCK = "/tmp/ledctl.sock"


def ensure_directories():
    """Create required directories, raising on failure."""
    for d in (IMAGE_FOLDER, CONFIG_DIR):
        if not d:
            continue
        os.makedirs(d, exist_ok=True)
    # Validate writability
    for d in (IMAGE_FOLDER, CONFIG_DIR):
        if not d:
            continue
        if not os.access(d, os.W_OK):
            raise RuntimeError(
                f"Directory {d} is not writable. "
                "If overlay filesystem is enabled, run scripts/setup_writable_data.sh first."
            )
