import os
import uuid
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy

# ---------------------------------------------------------------------------
# App & config
# ---------------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_IMAGE = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_VIDEO = {"mp4", "webm", "mov"}
ALLOWED_EXT = ALLOWED_IMAGE | ALLOWED_VIDEO
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "instance", "memoria.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memories = db.relationship("Memory", backref="author", lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


class Memory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(10), nullable=False)  # 'image' or 'video'
    caption = db.Column(db.Text, default="")
    location = db.Column(db.String(120), default="")
    memory_date = db.Column(db.String(20), default="")  # free-text date the memory happened
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    likes = db.relationship("Like", backref="memory", lazy=True, cascade="all, delete-orphan")
    comments = db.relationship(
        "Comment", backref="memory", lazy=True,
        cascade="all, delete-orphan", order_by="Comment.created_at.asc()"
    )

    def like_count(self):
        return len(self.likes)

    def liked_by(self, user_id):
        return any(l.user_id == user_id for l in self.likes)


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    memory_id = db.Column(db.Integer, db.ForeignKey("memory.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "memory_id", name="unique_like"),)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    memory_id = db.Column(db.Integer, db.ForeignKey("memory.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return db.session.get(User, uid)


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def media_kind(filename):
    ext = filename.rsplit(".", 1)[1].lower()
    return "video" if ext in ALLOWED_VIDEO else "image"


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


# ---------------------------------------------------------------------------
# Routes - auth
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("feed"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm:
            flash("Passwords don't match.", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username is already taken.", "error")
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            flash(f"Welcome, {username}! Your account is ready.", "success")
            return redirect(url_for("feed"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("feed"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            flash(f"Welcome back, {username}.", "success")
            nxt = request.args.get("next")
            return redirect(nxt or url_for("feed"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You've been logged out.", "success")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Routes - core
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def feed():
    q = request.args.get("q", "").strip()
    query = Memory.query
    if q:
        query = query.filter(Memory.caption.ilike(f"%{q}%"))
    memories = query.order_by(Memory.created_at.desc()).all()
    return render_template("feed.html", memories=memories, q=q)


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("media")
        caption = request.form.get("caption", "").strip()
        location = request.form.get("location", "").strip()
        memory_date = request.form.get("memory_date", "").strip()

        if not file or file.filename == "":
            flash("Please choose a photo or video.", "error")
            return render_template("upload.html")

        if not allowed_file(file.filename):
            flash("Unsupported file type. Use jpg, png, gif, webp, mp4, webm or mov.", "error")
            return render_template("upload.html")

        ext = file.filename.rsplit(".", 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))

        memory = Memory(
            user_id=current_user().id,
            filename=stored_name,
            media_type=media_kind(file.filename),
            caption=caption,
            location=location,
            memory_date=memory_date,
        )
        db.session.add(memory)
        db.session.commit()
        flash("Memory saved.", "success")
        return redirect(url_for("feed"))

    return render_template("upload.html")


@app.route("/memory/<int:memory_id>")
@login_required
def memory_detail(memory_id):
    memory = db.session.get(Memory, memory_id) or abort(404)
    return render_template("memory_detail.html", memory=memory)


@app.route("/memory/<int:memory_id>/delete", methods=["POST"])
@login_required
def delete_memory(memory_id):
    memory = db.session.get(Memory, memory_id) or abort(404)
    if memory.user_id != current_user().id:
        abort(403)
    path = os.path.join(app.config["UPLOAD_FOLDER"], memory.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(memory)
    db.session.commit()
    flash("Memory deleted.", "success")
    return redirect(url_for("profile", username=current_user().username))


@app.route("/memory/<int:memory_id>/like", methods=["POST"])
@login_required
def like_memory(memory_id):
    memory = db.session.get(Memory, memory_id) or abort(404)
    user = current_user()
    existing = Like.query.filter_by(user_id=user.id, memory_id=memory.id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(Like(user_id=user.id, memory_id=memory.id))
        liked = True
    db.session.commit()
    return jsonify({"liked": liked, "count": memory.like_count()})


@app.route("/memory/<int:memory_id>/comment", methods=["POST"])
@login_required
def add_comment(memory_id):
    memory = db.session.get(Memory, memory_id) or abort(404)
    body = request.form.get("body", "").strip()
    if body:
        comment = Comment(user_id=current_user().id, memory_id=memory.id, body=body)
        db.session.add(comment)
        db.session.commit()
    else:
        flash("Comment can't be empty.", "error")
    return redirect(url_for("memory_detail", memory_id=memory.id))


@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id) or abort(404)
    user = current_user()
    if comment.user_id != user.id and comment.memory.user_id != user.id:
        abort(403)
    memory_id = comment.memory_id
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for("memory_detail", memory_id=memory_id))


@app.route("/u/<username>")
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first() or abort(404)
    memories = Memory.query.filter_by(user_id=user.id).order_by(Memory.created_at.desc()).all()
    return render_template("profile.html", profile_user=user, memories=memories)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
