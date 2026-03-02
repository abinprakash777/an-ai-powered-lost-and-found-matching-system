from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from flask_socketio import SocketIO
from supabase import create_client
from skimage.metrics import structural_similarity as ssim
import cv2
import os
import uuid
import numpy as np

app = Flask(__name__)
CORS(app)

# =========================
# SOCKET IO
# =========================
socketio = SocketIO(app, cors_allowed_origins="*")

# =========================
# ENV VARIABLES (IMPORTANT)
# =========================
DATABASE_URL = os.environ.get("DATABASE_URL")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")

# =========================
# DATABASE CONFIG (Supabase PostgreSQL)
# =========================
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# SUPABASE STORAGE
# =========================
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# EMAIL CONFIG
# =========================
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = EMAIL_USER
app.config["MAIL_PASSWORD"] = EMAIL_PASS
app.config["MAIL_DEFAULT_SENDER"] = EMAIL_USER

mail = Mail(app)

# =========================
# MODELS
# =========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.String(500))
    status = db.Column(db.String(20))
    user_id = db.Column(db.Integer)
    image_filename = db.Column(db.String(500))
    matched = db.Column(db.Boolean, default=False)

# =========================
# IMAGE SIMILARITY (SSIM)
# =========================
def calculate_image_similarity(file1_bytes, file2_url):

    try:
        # Read uploaded image
        nparr1 = np.frombuffer(file1_bytes, np.uint8)
        img1 = cv2.imdecode(nparr1, cv2.IMREAD_COLOR)

        # Download second image
        import requests
        response = requests.get(file2_url)
        nparr2 = np.frombuffer(response.content, np.uint8)
        img2 = cv2.imdecode(nparr2, cv2.IMREAD_COLOR)

        img1 = cv2.resize(img1, (300, 300))
        img2 = cv2.resize(img2, (300, 300))

        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        score, _ = ssim(gray1, gray2, full=True)
        return score

    except:
        return 0

# =========================
# HOME
# =========================
@app.route("/")
def home():
    return "Campus Found-It AI Running 🚀"

# =========================
# REGISTER
# =========================
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"message": "Email already exists"}), 400

    user = User(
        name=data["name"],
        email=data["email"],
        password=generate_password_hash(data["password"])
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "Registered successfully"})

# =========================
# LOGIN
# =========================
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    user = User.query.filter_by(email=data["email"]).first()

    if not user:
        return jsonify({"message": "User not found"}), 404

    if not check_password_hash(user.password, data["password"]):
        return jsonify({"message": "Incorrect password"}), 401

    return jsonify({
        "message": "Login successful",
        "user_id": user.id,
        "name": user.name,
        "email": user.email
    })

# =========================
# UPLOAD + MATCH
# =========================
@app.route("/upload", methods=["POST"])
def upload_item():

    title = request.form.get("title")
    description = request.form.get("description")
    status = request.form.get("status")
    user_id = int(request.form.get("user_id"))
    image = request.files.get("image")

    if not image:
        return jsonify({"error": "Image required"}), 400

    unique_name = str(uuid.uuid4()) + "_" + secure_filename(image.filename)
    file_bytes = image.read()

    # Upload to Supabase Storage
    supabase.storage.from_("item-images").upload(
        path=unique_name,
        file=file_bytes,
        file_options={"content-type": image.content_type}
    )

    public_url = supabase.storage.from_("item-images").get_public_url(unique_name)

    new_item = Item(
        title=title,
        description=description,
        status=status,
        user_id=user_id,
        image_filename=public_url,
        matched=False
    )

    db.session.add(new_item)
    db.session.commit()

    opposite_status = "found" if status == "lost" else "lost"

    candidates = Item.query.filter_by(
        status=opposite_status,
        matched=False
    ).all()

    for item in candidates:

        if item.user_id == user_id:
            continue

        similarity = calculate_image_similarity(file_bytes, item.image_filename)

        if similarity >= 0.85:

            new_item.matched = True
            item.matched = True
            db.session.commit()

            socketio.emit("match_found", {
                "message": "🔥 MATCH FOUND!"
            })

            return jsonify({
                "message": "🔥 MATCH FOUND!",
                "similarity": round(similarity * 100, 2)
            })

    return jsonify({"message": "Item uploaded successfully"})

# =========================
# MY ITEMS
# =========================
@app.route("/my-items/<int:user_id>")
def my_items(user_id):

    items = Item.query.filter_by(user_id=user_id).all()

    result = [{
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "status": item.status,
        "matched": item.matched,
        "image_url": item.image_filename
    } for item in items]

    return jsonify(result)

# =========================
# DELETE
# =========================
@app.route("/delete/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):

    item = db.session.get(Item, item_id)

    if not item:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(item)
    db.session.commit()

    return jsonify({"message": "Deleted successfully"})

# =========================
# RUN
# =========================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    socketio.run(app, host="0.0.0.0", port=10000)
