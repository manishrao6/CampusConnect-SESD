from datetime import datetime
from functools import wraps
import os
import re

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient, ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017/")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "campusconnect")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[MONGO_DB_NAME]
events_collection = db["events"]
registrations_collection = db["registrations"]
counters_collection = db["counters"]


def next_event_id():
    counter = counters_collection.find_one_and_update(
        {"_id": "event_id"},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return counter["value"]


def init_db():
    # Confirm that the MongoDB server is reachable.
    client.admin.command("ping")

    # A student can register only once for the same event.
    registrations_collection.create_index(
        [("event_id", ASCENDING), ("student_email", ASCENDING)],
        unique=True
    )
    events_collection.create_index([("event_date", ASCENDING), ("event_time", ASCENDING)])

    if events_collection.count_documents({}) == 0:
        sample_events = [
            {"id": 1, "title": "CodeSprint 2026", "category": "Technical",
             "event_date": "2026-11-18", "event_time": "10:00",
             "venue": "CSE Seminar Hall", "organizer": "CSE Association",
             "description": "A friendly coding contest to test problem-solving, algorithms, and teamwork. Open to students from all departments.",
             "capacity": 120},
            {"id": 2, "title": "InnovateX Project Expo", "category": "Technical",
             "event_date": "2026-11-22", "event_time": "09:30",
             "venue": "Main Auditorium", "organizer": "Innovation Cell",
             "description": "Showcase your ideas, prototypes, and student projects. Teams can present software, hardware, and social-impact solutions.",
             "capacity": 200},
            {"id": 3, "title": "Rhythm & Colors", "category": "Cultural",
             "event_date": "2026-11-27", "event_time": "16:00",
             "venue": "Open-Air Stage", "organizer": "Cultural Club",
             "description": "An evening of music, dance, art, and performances celebrating campus creativity.",
             "capacity": 300},
            {"id": 4, "title": "Campus Green Day", "category": "Social",
             "event_date": "2026-12-02", "event_time": "08:30",
             "venue": "College Garden", "organizer": "Eco Club",
             "description": "Join a campus clean-up and tree-planting drive. Bring reusable water bottles and comfortable shoes.",
             "capacity": 80},
        ]
        events_collection.insert_many(sample_events)
        counters_collection.update_one(
            {"_id": "event_id"}, {"$max": {"value": 4}}, upsert=True
        )


def get_event(event_id):
    event = events_collection.find_one({"id": event_id}, {"_id": 0})
    if event:
        event["registered"] = registrations_collection.count_documents({"event_id": event_id})
    return event


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Please sign in as an administrator first.", "warning")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    query = {}
    if search:
        pattern = re.escape(search)
        query["$or"] = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"venue": {"$regex": pattern, "$options": "i"}},
            {"organizer": {"$regex": pattern, "$options": "i"}}
        ]
    if category:
        query["category"] = category

    events = list(events_collection.find(query, {"_id": 0}).sort(
        [("event_date", ASCENDING), ("event_time", ASCENDING)]
    ))
    for event in events:
        event["registered"] = registrations_collection.count_documents({"event_id": event["id"]})

    categories = [{"category": value} for value in events_collection.distinct("category")]
    categories.sort(key=lambda item: item["category"])
    total = events_collection.count_documents({})
    registrations = registrations_collection.count_documents({})
    return render_template("index.html", events=events, categories=categories, search=search,
                           selected_category=category, total=total, registrations=registrations)


@app.route("/events/<int:event_id>")
def event_detail(event_id):
    event = get_event(event_id)
    if event is None:
        flash("That event could not be found.", "danger")
        return redirect(url_for("index"))
    return render_template("event_detail.html", event=event)


@app.route("/events/<int:event_id>/register", methods=["POST"])
def register(event_id):
    event = get_event(event_id)
    if event is None:
        flash("That event could not be found.", "danger")
        return redirect(url_for("index"))

    name = request.form.get("student_name", "").strip()
    email = request.form.get("student_email", "").strip().lower()
    department = request.form.get("department", "").strip()

    if not name or not email or not department:
        flash("Please complete all registration fields.", "danger")
    elif "@" not in email or "." not in email.split("@")[-1]:
        flash("Enter a valid email address.", "danger")
    elif event["registered"] >= event["capacity"]:
        flash("Sorry, this event has reached its registration limit.", "danger")
    else:
        try:
            registrations_collection.insert_one({
                "event_id": event_id,
                "student_name": name,
                "student_email": email,
                "department": department,
                "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            flash("Registration successful! You are on the attendee list.", "success")
        except DuplicateKeyError:
            flash("This email is already registered for the event.", "warning")
    return redirect(url_for("event_detail", event_id=event_id))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Welcome back, administrator.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect username or password.", "danger")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    events = list(events_collection.find({}, {"_id": 0}).sort(
        [("event_date", ASCENDING), ("event_time", ASCENDING)]
    ))
    for event in events:
        event["registered"] = registrations_collection.count_documents({"event_id": event["id"]})
    total_registrations = registrations_collection.count_documents({})
    return render_template("admin_dashboard.html", events=events,
                           total_registrations=total_registrations)


@app.route("/admin/events/new", methods=["GET", "POST"])
@admin_required
def create_event():
    if request.method == "POST":
        data = event_form_data()
        error = validate_event(data)
        if error:
            flash(error, "danger")
        else:
            data["id"] = next_event_id()
            events_collection.insert_one(data)
            flash("Event created successfully.", "success")
            return redirect(url_for("admin_dashboard"))
    else:
        data = default_event_data()
    return render_template("event_form.html", event=data, page_title="Create event",
                           submit_label="Create event")


@app.route("/admin/events/<int:event_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_event(event_id):
    existing = events_collection.find_one({"id": event_id}, {"_id": 0})
    if existing is None:
        flash("Event not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        data = event_form_data()
        error = validate_event(data)
        if error:
            flash(error, "danger")
        else:
            events_collection.update_one({"id": event_id}, {"$set": data})
            flash("Event updated successfully.", "success")
            return redirect(url_for("admin_dashboard"))
    else:
        data = existing
    return render_template("event_form.html", event=data, page_title="Edit event",
                           submit_label="Save changes")


@app.route("/admin/events/<int:event_id>/delete", methods=["POST"])
@admin_required
def delete_event(event_id):
    events_collection.delete_one({"id": event_id})
    registrations_collection.delete_many({"event_id": event_id})
    flash("Event and its registrations have been deleted.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/events/<int:event_id>/attendees")
@admin_required
def attendees(event_id):
    event = events_collection.find_one({"id": event_id}, {"_id": 0})
    if event is None:
        flash("Event not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    people = list(registrations_collection.find(
        {"event_id": event_id}, {"_id": 0}
    ).sort("registered_at", -1))
    return render_template("attendees.html", event=event, people=people)


def default_event_data():
    return {"title": "", "category": "Technical", "event_date": "", "event_time": "10:00",
            "venue": "", "organizer": "", "description": "", "capacity": 100}


def event_form_data():
    try:
        capacity = int(request.form.get("capacity", "100"))
    except ValueError:
        capacity = 0
    return {
        "title": request.form.get("title", "").strip(),
        "category": request.form.get("category", "").strip(),
        "event_date": request.form.get("event_date", "").strip(),
        "event_time": request.form.get("event_time", "").strip(),
        "venue": request.form.get("venue", "").strip(),
        "organizer": request.form.get("organizer", "").strip(),
        "description": request.form.get("description", "").strip(),
        "capacity": capacity
    }


def validate_event(data):
    required = ["title", "category", "event_date", "event_time", "venue", "organizer", "description"]
    if any(not data[field] for field in required):
        return "Please fill in every required field."
    try:
        datetime.strptime(data["event_date"], "%Y-%m-%d")
        datetime.strptime(data["event_time"], "%H:%M")
    except ValueError:
        return "Please enter a valid date and time."
    if data["capacity"] < 1:
        return "Capacity must be at least 1."
    return None


try:
    init_db()
    print(f"Connected to MongoDB database: {MONGO_DB_NAME}")
except ServerSelectionTimeoutError as exc:
    raise RuntimeError(
        "Could not connect to MongoDB. Start the MongoDB Server service and try again. "
        "Default address: mongodb://127.0.0.1:27017/"
    ) from exc


if __name__ == "__main__":
    app.run(debug=True)
