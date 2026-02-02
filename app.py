from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///student_projects.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='student')  # student or teacher
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    classrooms = db.relationship('Classroom', backref='teacher', lazy=True)
    projects = db.relationship('Project', backref='student', lazy=True)
    challenge_submissions = db.relationship('ChallengeSubmission', backref='student', lazy=True)

class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    students = db.relationship('ClassroomStudent', backref='classroom', lazy=True, cascade='all, delete-orphan')
    projects = db.relationship('Project', backref='classroom', lazy=True)
    challenges = db.relationship('Challenge', backref='classroom', lazy=True)

class ClassroomStudent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    points = db.Column(db.Integer, default=0)
    student = db.relationship('User', backref='enrollments')
    db.UniqueConstraint('classroom_id', 'student_id')

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    project_type = db.Column(db.String(20), nullable=False)  # html or scratch
    file_path = db.Column(db.String(255))  # For HTML uploads
    scratch_link = db.Column(db.String(500))  # For Scratch links
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)

class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, default=10)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submissions = db.relationship('ChallengeSubmission', backref='challenge', lazy=True)

class ChallengeSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    points_awarded = db.Column(db.Integer, default=0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'teacher':
        classrooms = Classroom.query.filter_by(teacher_id=current_user.id).all()
        return render_template('teacher_dashboard.html', classrooms=classrooms)
    else:
        # Get classrooms student is enrolled in
        enrollments = ClassroomStudent.query.filter_by(student_id=current_user.id).all()
        classroom_ids = [e.classroom_id for e in enrollments]
        classrooms = Classroom.query.filter(Classroom.id.in_(classroom_ids)).all()
        projects = Project.query.filter_by(student_id=current_user.id).all()
        return render_template('student_dashboard.html', classrooms=classrooms, projects=projects)

@app.route('/classroom/create', methods=['GET', 'POST'])
@login_required
def create_classroom():
    if current_user.role != 'teacher':
        flash('Only teachers can create classrooms')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        
        if Classroom.query.filter_by(code=code).first():
            flash('Classroom code already exists')
            return redirect(url_for('create_classroom'))
        
        classroom = Classroom(name=name, code=code, teacher_id=current_user.id)
        db.session.add(classroom)
        db.session.commit()
        flash('Classroom created successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('create_classroom.html')

@app.route('/classroom/join', methods=['POST'])
@login_required
def join_classroom():
    if current_user.role == 'teacher':
        flash('Teachers cannot join classrooms')
        return redirect(url_for('dashboard'))
    
    code = request.form.get('code')
    classroom = Classroom.query.filter_by(code=code).first()
    
    if not classroom:
        flash('Invalid classroom code')
        return redirect(url_for('dashboard'))
    
    # Check if already enrolled
    existing = ClassroomStudent.query.filter_by(
        classroom_id=classroom.id,
        student_id=current_user.id
    ).first()
    
    if existing:
        flash('You are already in this classroom')
        return redirect(url_for('dashboard'))
    
    enrollment = ClassroomStudent(classroom_id=classroom.id, student_id=current_user.id)
    db.session.add(enrollment)
    db.session.commit()
    flash(f'Joined classroom: {classroom.name}')
    return redirect(url_for('classroom_view', classroom_id=classroom.id))

@app.route('/classroom/<int:classroom_id>')
@login_required
def classroom_view(classroom_id):
    classroom = Classroom.query.get_or_404(classroom_id)
    
    # Check access
    if current_user.role == 'teacher':
        if classroom.teacher_id != current_user.id:
            flash('You do not have access to this classroom')
            return redirect(url_for('dashboard'))
    else:
        enrollment = ClassroomStudent.query.filter_by(
            classroom_id=classroom_id,
            student_id=current_user.id
        ).first()
        if not enrollment:
            flash('You are not enrolled in this classroom')
            return redirect(url_for('dashboard'))
    
    projects = Project.query.filter_by(classroom_id=classroom_id).order_by(Project.created_at.desc()).all()
    challenges = Challenge.query.filter_by(classroom_id=classroom_id).all()
    
    # Get leaderboard
    enrollments = ClassroomStudent.query.filter_by(classroom_id=classroom_id).order_by(ClassroomStudent.points.desc()).limit(10).all()
    leaderboard = []
    for e in enrollments:
        student = User.query.get(e.student_id)
        leaderboard.append({'username': student.username, 'points': e.points})
    
    return render_template('classroom.html', classroom=classroom, projects=projects, challenges=challenges, leaderboard=leaderboard)

@app.route('/project/upload', methods=['GET', 'POST'])
@login_required
def upload_project():
    if current_user.role == 'teacher':
        flash('Teachers cannot upload projects')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        project_type = request.form.get('project_type')
        classroom_id = request.form.get('classroom_id')
        
        # Verify classroom access
        enrollment = ClassroomStudent.query.filter_by(
            classroom_id=classroom_id,
            student_id=current_user.id
        ).first()
        if not enrollment:
            flash('You are not enrolled in this classroom')
            return redirect(url_for('dashboard'))
        
        project = Project(
            title=title,
            description=description,
            project_type=project_type,
            student_id=current_user.id,
            classroom_id=classroom_id
        )
        
        if project_type == 'html':
            if 'file' not in request.files:
                flash('No file uploaded')
                return redirect(url_for('upload_project'))
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected')
                return redirect(url_for('upload_project'))
            
            if file and file.filename.endswith('.html'):
                filename = secure_filename(f"{current_user.id}_{datetime.now().timestamp()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                project.file_path = filename
        
        elif project_type == 'scratch':
            scratch_link = request.form.get('scratch_link')
            if not scratch_link:
                flash('Scratch link is required')
                return redirect(url_for('upload_project'))
            project.scratch_link = scratch_link
        
        db.session.add(project)
        db.session.commit()
        flash('Project uploaded successfully!')
        return redirect(url_for('classroom_view', classroom_id=classroom_id))
    
    # Get student's classrooms
    enrollments = ClassroomStudent.query.filter_by(student_id=current_user.id).all()
    classroom_ids = [e.classroom_id for e in enrollments]
    classrooms = Classroom.query.filter(Classroom.id.in_(classroom_ids)).all()
    return render_template('upload_project.html', classrooms=classrooms)

@app.route('/project/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    project.views += 1
    db.session.commit()
    
    # Check access
    if current_user.role == 'teacher':
        if project.classroom.teacher_id != current_user.id:
            flash('You do not have access to this project')
            return redirect(url_for('dashboard'))
    else:
        enrollment = ClassroomStudent.query.filter_by(
            classroom_id=project.classroom_id,
            student_id=current_user.id
        ).first()
        if not enrollment:
            flash('You are not enrolled in this classroom')
            return redirect(url_for('dashboard'))
    
    return render_template('view_project.html', project=project)

@app.route('/project/<int:project_id>/like', methods=['POST'])
@login_required
def like_project(project_id):
    project = Project.query.get_or_404(project_id)
    project.likes += 1
    db.session.commit()
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/challenge/create', methods=['GET', 'POST'])
@login_required
def create_challenge():
    if current_user.role != 'teacher':
        flash('Only teachers can create challenges')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        points = int(request.form.get('points', 10))
        classroom_id = request.form.get('classroom_id')
        
        classroom = Classroom.query.get(classroom_id)
        if not classroom or classroom.teacher_id != current_user.id:
            flash('Invalid classroom')
            return redirect(url_for('dashboard'))
        
        challenge = Challenge(
            title=title,
            description=description,
            points=points,
            classroom_id=classroom_id
        )
        db.session.add(challenge)
        db.session.commit()
        flash('Challenge created successfully!')
        return redirect(url_for('classroom_view', classroom_id=classroom_id))
    
    classrooms = Classroom.query.filter_by(teacher_id=current_user.id).all()
    return render_template('create_challenge.html', classrooms=classrooms)

@app.route('/challenge/<int:challenge_id>/submit', methods=['POST'])
@login_required
def submit_challenge(challenge_id):
    if current_user.role == 'teacher':
        flash('Teachers cannot submit challenges')
        return redirect(url_for('dashboard'))
    
    challenge = Challenge.query.get_or_404(challenge_id)
    project_id = request.form.get('project_id')
    
    # Verify project belongs to student and is in same classroom
    project = Project.query.get(project_id)
    if not project or project.student_id != current_user.id or project.classroom_id != challenge.classroom_id:
        flash('Invalid project')
        return redirect(url_for('dashboard'))
    
    # Check if already submitted
    existing = ChallengeSubmission.query.filter_by(
        challenge_id=challenge_id,
        student_id=current_user.id
    ).first()
    
    if existing:
        flash('You have already submitted this challenge')
        return redirect(url_for('classroom_view', classroom_id=challenge.classroom_id))
    
    submission = ChallengeSubmission(
        challenge_id=challenge_id,
        student_id=current_user.id,
        project_id=project_id,
        points_awarded=challenge.points
    )
    
    # Award points
    enrollment = ClassroomStudent.query.filter_by(
        classroom_id=challenge.classroom_id,
        student_id=current_user.id
    ).first()
    if enrollment:
        enrollment.points += challenge.points
    
    db.session.add(submission)
    db.session.commit()
    flash(f'Challenge submitted! You earned {challenge.points} points!')
    return redirect(url_for('classroom_view', classroom_id=challenge.classroom_id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
