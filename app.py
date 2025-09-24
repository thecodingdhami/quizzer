from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import hashlib
import smtplib, ssl, random, os
from werkzeug.utils import secure_filename
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = '9866109958'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'quizzer.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------- FILE UPLOAD CONFIG ----------------
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- EMAIL CONFIG ----------------
EMAIL_SENDER = "quizzer1pro@gmail.com"
EMAIL_PASSWORD = "qkdk onns awhj fnuz"  # <-- Replace with Google App Password
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

def send_otp(receiver_email, otp):
    subject = "Your OTP Code"
    body = f"Your OTP code is: {otp}\n\nUse this to complete your registration or reset."

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, receiver_email, msg.as_string())

# ---------------- DATABASE MODELS ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    username = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(256))
    role = db.Column(db.String(10))
    profile_pic = db.Column(db.String(100), nullable=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faculty = db.Column(db.String(50))
    course = db.Column(db.String(50))
    semester = db.Column(db.String(10))
    level = db.Column(db.String(20))
    question = db.Column(db.String(500))
    choice1 = db.Column(db.String(200))
    choice2 = db.Column(db.String(200))
    choice3 = db.Column(db.String(200))
    choice4 = db.Column(db.String(200))
    correct_index = db.Column(db.Integer)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(50))
    score = db.Column(db.Integer)
    submitted_at = db.Column(db.DateTime, default=db.func.current_timestamp())

# Create DB tables
with app.app_context():
    db.create_all()

# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template('main_homepage.html')

# ---------------- REGISTER ----------------
@app.route('/register', methods=['POST'])
def register():
    first_name = request.form['first_name'].strip()
    last_name = request.form['last_name'].strip()
    username = request.form['username'].strip().lower()
    email = request.form['email'].strip().lower()
    password = request.form['password']
    confirm_password = request.form['confirm_password']

    if password != confirm_password:
        flash('Passwords do not match!', 'error')
        return render_template('login.html', show_register=True, old_data=request.form)

    existing_user = User.query.filter((db.func.lower(User.email)==email)|(db.func.lower(User.username)==username)).first()
    if existing_user:
        flash('Email or Username already exists! Please login.', 'error')
        return render_template('login.html', show_register=True, old_data=request.form)

    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['temp_user'] = {
        'first_name': first_name,
        'last_name': last_name,
        'username': username,
        'email': email,
        'password': hashed_password
    }

    try:
        send_otp(email, otp)
    except Exception as e:
        flash(f"Error sending OTP: {e}", "error")
        return render_template('login.html', show_register=True, old_data=request.form)

    return redirect(url_for('verify_otp'))

# ---------------- VERIFY OTP ----------------
@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        data = request.get_json()
        entered_otp = data.get('otp') if data else None

        real_otp = session.get('otp')
        user_data = session.get('temp_user')

        if entered_otp == real_otp and user_data:
            new_user = User(
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password'],
                role='user'
            )
            db.session.add(new_user)
            db.session.commit()

            session.pop('otp', None)
            session.pop('temp_user', None)

            return jsonify({"ok": True, "msg": "OTP verified! Registration successful."})
        else:
            return jsonify({"ok": False, "msg": "OTP mismatch!"})

    return render_template('verify.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip().lower()
        password_input = request.form['password'].strip()
        hashed_password = hashlib.sha256(password_input.encode()).hexdigest()

        user = User.query.filter(db.func.lower(User.email) == identifier).first() \
               or User.query.filter(db.func.lower(User.username) == identifier).first()

        if not user:
            flash("User doesn't exist", "error")
        elif user.password != hashed_password:
            flash("Incorrect password", "error")
        else:
            session['loggedin'] = True
            session['id'] = user.id
            session['first_name'] = user.first_name
            session['last_name'] = user.last_name
            session['username'] = user.username
            session['role'] = user.role
            session['profile_pic'] = user.profile_pic
            return redirect('/admin' if user.role=='admin' else '/student_dashboard')

    return render_template('login.html')

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- STUDENT DASHBOARD ----------------
@app.route('/student_dashboard')
def student_dashboard():
    if 'loggedin' in session and session['role']=='user':
        user = User.query.get(session['id'])
        profile_pic = url_for('static', filename='uploads/' + user.profile_pic) if user.profile_pic else url_for('static', filename='img/default_avatar.png')
        return render_template('student_dashboard.html', username=session['username'], profile_pic_url=profile_pic)
    return redirect(url_for('login'))

# ---------------- USER PROFILE ----------------
@app.route('/userprofile', methods=['GET', 'POST'])
def userprofile():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['id'])

    if request.method == 'POST':
        action = request.form.get("action")

        if action == "update_pic" and 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                user.profile_pic = filename
                db.session.commit()
                session['profile_pic'] = filename
                return jsonify({"ok": True, "filename": filename})

            return jsonify({"ok": False, "error": "Invalid file type."})

        elif action == "change_password":
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not password or not confirm_password:
                return jsonify({"ok": False, "msg": "Password fields cannot be empty."})
            if password != confirm_password:
                return jsonify({"ok": False, "msg": "Passwords do not match!"})

            user.password = hashlib.sha256(password.encode()).hexdigest()
            db.session.commit()
            return jsonify({"ok": True, "msg": "Password updated successfully!"})

        elif action == "update_name":
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            user.first_name = first_name
            user.last_name = last_name
            db.session.commit()
            session['first_name'] = first_name
            session['last_name'] = last_name
            flash("Profile updated successfully!", "success")
            return redirect(url_for('userprofile'))

    profile_pic_url = url_for('static', filename='uploads/' + user.profile_pic) if user.profile_pic else url_for('static', filename='img/default_avatar.png')
    return render_template("user_profile.html", user=user, profile_pic_url=profile_pic_url, current_year=2025)

# ---------------- ADMIN DASHBOARD ----------------
@app.route('/admin')
def admin():
    if 'loggedin' in session and session['role']=='admin':
        users = User.query.all()
        reports = Report.query.order_by(Report.submitted_at.desc()).all()
        return render_template('admin_users.html', users=users, reports=reports)
    return redirect(url_for('login'))

# ---------------- FORGOT PASSWORD ----------------
@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    if request.method=='POST':
        email = request.form['email'].strip().lower()
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if not user:
            flash("Email not registered!", "error")
            return redirect(url_for('forgot_password'))

        otp = str(random.randint(100000,999999))
        session['reset_otp'] = otp
        session['reset_email'] = email

        try:
            send_otp(email, otp)
            flash("OTP sent to your email!", "success")
            return redirect(url_for('verify_reset_otp'))
        except Exception as e:
            flash(f"Failed to send OTP: {e}", "error")
            return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

# ---------------- VERIFY RESET OTP ----------------
@app.route('/verify-reset-otp', methods=['GET','POST'])
def verify_reset_otp():
    if 'reset_email' not in session:
        flash("Unauthorized access.", "error")
        return redirect(url_for('forgot_password'))

    if request.method=='POST':
        entered_otp = request.form['otp'].strip()
        otp = session.get('reset_otp')

        if entered_otp != otp:
            flash("Incorrect OTP!", "error")
            return redirect(url_for('verify_reset_otp'))

        flash("OTP verified! Enter your new password.", "success")
        return redirect(url_for('reset_password'))

    return render_template('verify_reset_otp.html')

# ---------------- RESET PASSWORD ----------------
@app.route('/reset-password', methods=['GET','POST'])
def reset_password():
    if 'reset_email' not in session:
        flash("Unauthorized access.", "error")
        return redirect(url_for('forgot_password'))

    if request.method=='POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password or not confirm_password:
            flash("Please fill out both fields!", "error")
            return redirect(url_for('reset_password'))
        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for('reset_password'))

        user = User.query.filter(db.func.lower(User.email) == session['reset_email']).first()
        user.password = hashlib.sha256(password.encode()).hexdigest()
        db.session.commit()

        session.pop('reset_email',None)
        session.pop('reset_otp',None)
        flash("Password changed successfully! Redirecting to login...", "success")
        return render_template('reset_password.html', redirect_login=True)

    return render_template('reset_password.html', redirect_login=False)

# ---------------- ADD QUESTION ----------------
@app.route('/add_question', methods=['GET','POST'])
def add_question():
    if 'loggedin' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method=='POST':
        faculty = request.form['faculty']
        course = request.form['course']
        semester = request.form['semester']
        level = request.form['quizLevel']
        question = request.form['questionText']
        choice1 = request.form['choice1']
        choice2 = request.form['choice2']
        choice3 = request.form['choice3']
        choice4 = request.form['choice4']
        correct = request.form['correctAnswer']
        correct_index = {"choice1":0,"choice2":1,"choice3":2,"choice4":3}[correct]

        new_question = Question(
            faculty=faculty, course=course, semester=semester, level=level,
            question=question, choice1=choice1, choice2=choice2, choice3=choice3, choice4=choice4,
            correct_index=correct_index
        )
        db.session.add(new_question)
        db.session.commit()
        return redirect(url_for('add_question'))

    return render_template('add_question.html')

# ---------------- QUIZ ----------------
@app.route('/quiz')
def quiz():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    faculty = request.args.get('faculty')
    course = request.args.get('course')
    semester = request.args.get('semester')
    level = request.args.get('level')

    if not all([faculty, course, semester, level]):
        return "Invalid quiz selection.", 400

    questions = Question.query.filter_by(faculty=faculty, course=course, semester=semester, level=level).all()
    return render_template('quiz.html', questions=questions, username=session['username'])

# ---------------- SUBMIT QUIZ ----------------
@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    score = int(request.form.get('score',0))
    new_report = Report(user_id=session['id'], username=session['username'], score=score)
    db.session.add(new_report)
    db.session.commit()
    return render_template('result.html', score=score, username=session['username'])

# ---------------- ADMIN REPORTS ----------------
@app.route('/admin/reports')
def admin_reports():
    if 'loggedin' in session and session['role']=='admin':
        reports = Report.query.order_by(Report.submitted_at.desc()).all()
        return render_template('reports.html', reports=reports)
    return redirect(url_for('login'))

# ---------------- STATIC PAGES ----------------
@app.route('/becomputer')
def be_computer():
    return render_template('becomputer.html')

# ---------------- RESEND OTP ----------------
@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    user_data = session.get('temp_user')
    if not user_data:
        return jsonify({"ok": False, "msg": "No user data found. Please register again."})

    otp = str(random.randint(100000, 999999))
    session['otp'] = otp

    try:
        send_otp(user_data['email'], otp)
        return jsonify({"ok": True, "msg": f"OTP resent to {user_data['email']}"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Failed to resend OTP: {e}"})

# ---------------- CHANGE OTP EMAIL ----------------
@app.route('/change_otp_email', methods=['POST'])
def change_otp_email():
    data = request.get_json()
    new_email = data.get('email')
    if not new_email:
        return jsonify({"ok": False, "msg": "Email cannot be empty!"})

    user_data = session.get('temp_user')
    if not user_data:
        return jsonify({"ok": False, "msg": "No user data found. Please register again."})

    user_data['email'] = new_email.strip().lower()
    session['temp_user'] = user_data

    otp = str(random.randint(100000, 999999))
    session['otp'] = otp

    try:
        send_otp(new_email, otp)
        return jsonify({"ok": True, "msg": f"OTP sent to new email: {new_email}"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Failed to send OTP to new email: {e}"})

@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session and session['role']=='user':
        return render_template('dashboard.html', username=session['username'])
    return redirect(url_for('login'))

# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(debug=False)
