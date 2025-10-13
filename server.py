from flask import Flask, jsonify, send_from_directory, request
import os
from flask_cors import CORS, cross_origin
from werkzeug.utils import secure_filename
import socket

app = Flask(__name__)
cors = CORS(app) # allow CORS for all domains on all routes.
app.config['CORS_HEADERS'] = 'Content-Type'

IMAGE_FOLDER = os.path.join(os.getcwd(), "matrix_images")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def send_ctl(cmd: bytes):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    s.connect("/tmp/ledctl.sock")
    s.send(cmd)
    s.close()

@app.route("/images", methods=["GET"])
@cross_origin()
def list_images():
    """Return full image URLs so they’re clickable/visible in the browser."""
    image_files = [
        f for f in os.listdir(IMAGE_FOLDER)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
    ]

    image_urls = [f"{filename}" for filename in image_files]
    return jsonify({"images": image_urls})


@app.route("/images/<filename>", methods=["GET"])
@cross_origin()
def serve_image(filename):
    """Serve an individual image file."""
    return send_from_directory(IMAGE_FOLDER, filename)


@app.route("/delete_image", methods=["DELETE"])
@cross_origin()
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
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_image', methods=['POST'])
@cross_origin()
def upload_image():
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
    save_path = os.path.join("matrix_images", filename)
    file.save(save_path)

    # Return a public or relative URL
    return jsonify({
        'message': 'File uploaded successfully',
        'filename': filename,
        'url': f'/matrix_images/{filename}'
    }), 200

@app.route('/set_brightness', methods=['POST'])
@cross_origin()
def set_brightness():
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

    send_ctl(f"brightness:{brightness}".encode())

    return jsonify({'message': f'Brightness set to {brightness}'}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)