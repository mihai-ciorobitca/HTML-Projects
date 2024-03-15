from flask import (
    Flask,
    redirect,
    session,
    render_template,
    request,
    jsonify,
)
from requests import post
from uuid import uuid4
from werkzeug.security import check_password_hash, generate_password_hash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from os.path import expanduser, join
from os import getenv

project_folder = expanduser('~/website')
load_dotenv(join(project_folder, '.env'))

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = getenv("URI")
app.secret_key = getenv("SECRET_KEY")

db = SQLAlchemy(app)

class Users(db.Model):

    username = db.Column(db.String(20),  nullable = False, primary_key = True)
    password = db.Column(db.String(200), nullable = False)

    def __init__(self, username, password):
        self.username = username
        self.password = generate_password_hash(password)

class Tickets(db.Model):
    token       = db.Column(db.String(36), primary_key=True, unique=True)
    subject     = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    date        = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    status      = db.Column(db.String(10), nullable=False, default="unread")
    name        = db.Column(db.String(20), nullable=False)

    username = db.Column(db.String(20), db.ForeignKey('users.username'), nullable=False)
    user     = db.relationship('Users', backref=db.backref('tickets', lazy=True))

    def __init__(self, name, subject, description, username):
        self.name        = name
        self.subject     = subject
        self.description = description
        self.username    = username
        self.token       = str(uuid4())

@app.route("/")
def index():
    return redirect("/home")

@app.route("/home")
def home():
    if session.get("user", False):
        username = session["user"]
        tickets = Tickets.query.filter_by(username=username)
        return render_template("home.html", tickets=tickets)
    return redirect("/login")

@app.route("/home/ticket", methods=["POST"])
def home_tiket():
    token  = request.form["token"]
    ticket = Tickets.query.filter_by(token=token).first()
    return render_template("ticket.html", ticket=ticket, admin=False)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if (username, password) == (getenv("ADMIN_PASSWORD"), getenv("ADMIN_USERNAME")):
            session["admin"] = True
            return jsonify({"status": "success", "route": "/admin", "message": "logged in as admin"})
        user = Users.query.filter_by(username = username).first()
        if user:
            if check_password_hash(user.password, password):
                session["user"] = username
                return jsonify({"status": "success", "route": "/home", "message": "logged in"})
            return jsonify({"status": "fail", "message": "wrong username or password"})
        return jsonify({"status": "fail", "message": "user not exists"})
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        recaptcha = request.form["g-recaptcha-response"]
        if recaptcha:
            private_key = getenv("PRIVATE_KEY")
            response = post(
                'https://www.google.com/recaptcha/api/siteverify',
                data={
                    'secret': private_key,
                    'response': recaptcha
                }
            )
            result = response.json()
            if result['success']:
                username = request.form["username"]
                password = request.form["password"]
                user = Users.query.filter_by(username = username).first()
                if not user:
                    new_user = Users(username, password)
                    db.session.add(new_user)
                    db.session.commit()
                    return jsonify({"status": "success", "route": "/login", "message": "registered"})
                return jsonify({"status": "fail", "message": "user already exists"})
            return jsonify({"status": "fail", "message": "reCAPTCHA verification failed"})
        return jsonify({"status": "fail", "message": "reCAPTCHA not filled"})
    return render_template("register.html", site_key=getenv("SITE_KEY"))

@app.route("/new-ticket", methods=["POST"])
def ticket():
    name        = request.form["name"]
    subject     = request.form["subject"]
    description = request.form["description"]
    username    = session.get("user")
    new_ticket  = Tickets(name, subject, description, username)
    db.session.add(new_ticket)
    db.session.commit()
    return jsonify({"status": "success", "message": "ticket created"})

@app.route("/admin")
def admin():
    if session.get("admin", False):
        users = Users.query.all()
        tickets = Tickets.query.all()
        return render_template("admin.html", users=users, tickets=tickets)
    return redirect("/login")

@app.route("/admin/tickets/username", methods=["POST"])
def admin_tickets_username():
    session["username"] = request.form["username"]
    return redirect("/admin/tickets")

@app.route("/admin/tickets")
def admin_tickets():
    if session.get("username", False):
        username = session["username"]
        tickets = Tickets.query.filter_by(username=username).all()
        session.pop("username", None)
        return render_template("tickets.html", tickets=tickets, username=username)
    return redirect("/admin")

@app.route("/admin/ticket", methods=["POST"])
def admin_tiket():
    token  = request.form["token"]
    ticket = Tickets.query.filter_by(token=token).first()
    username = ticket.username
    session["username"] = username
    return render_template("ticket.html", ticket=ticket, admin=True)

@app.route("/admin/ticket/update", methods=["POST"])
def admin_update_ticket():
    token   = request.form["token"]
    status  = request.form["status"]
    ticket = Tickets.query.filter_by(token=token).first()
    ticket.status = status
    db.session.commit()
    session["username"]=ticket.username
    return redirect("/admin/tickets")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run()
