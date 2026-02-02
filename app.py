from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import zipfile
import shutil
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///student_projects.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size for zip files
ALLOWED_EXTENSIONS = {'html', 'zip', 'css', 'js', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'json', 'txt', 'ico'}
ALLOWED_ZIP_EXTENSIONS = {'zip'}

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
    file_path = db.Column(db.String(255))  # For single HTML file (backward compatibility)
    project_dir = db.Column(db.String(255))  # For multi-file projects (directory path)
    main_file = db.Column(db.String(255))  # Main entry point (index.html, etc.)
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

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_zip_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_ZIP_EXTENSIONS

def extract_zip_project(zip_path, extract_to):
    # Extract zip file and maintain directory structure
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    # Find main HTML file (index.html, main.html, or first .html file)
    html_files = []
    for root, dirs, files in os.walk(extract_to):
        for file in files:
            if file.endswith('.html'):
                rel_path = os.path.relpath(os.path.join(root, file), extract_to)
                html_files.append(rel_path)
    # Prefer index.html, then main.html, then first HTML file
    main_file = None
    for preferred in ['index.html', 'main.html', 'home.html']:
        if preferred in html_files:
            main_file = preferred
            break
    if not main_file and html_files:
        main_file = html_files[0]
    return main_file

def get_project_files(project_dir):
    # Get all files in project directory with their relative paths
    files = []
    if not os.path.exists(project_dir):
        return files
    for root, dirs, filenames in os.walk(project_dir):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, project_dir)
            file_size = os.path.getsize(file_path)
            files.append({
                'path': rel_path.replace('\\', '/'),
                'name': filename,
                'size': file_size,
                'is_html': filename.endswith('.html')
            })
    return sorted(files, key=lambda x: (not x['is_html'], x['path']))

def teacher_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'teacher':
            flash('Access denied. Teacher privileges required.')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'student':
            flash('Access denied. Student privileges required.')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

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
            upload_type = request.form.get('upload_type', 'single')  # single, zip, or multiple
            
            if upload_type == 'zip':
                # Handle zip file upload
                if 'zip_file' not in request.files:
                    flash('No zip file uploaded')
                    return redirect(url_for('upload_project'))
                
                zip_file = request.files['zip_file']
                if zip_file.filename == '':
                    flash('No zip file selected')
                    return redirect(url_for('upload_project'))
                
                if zip_file and allowed_zip_file(zip_file.filename):
                    # Create project directory
                    project_dir_name = f"project_{current_user.id}_{int(datetime.now().timestamp())}"
                    project_dir_path = os.path.join(app.config['UPLOAD_FOLDER'], project_dir_name)
                    os.makedirs(project_dir_path, exist_ok=True)
                    
                    # Save and extract zip
                    zip_filename = secure_filename(zip_file.filename)
                    zip_path = os.path.join(project_dir_path, zip_filename)
                    zip_file.save(zip_path)
                    
                    # Extract zip file
                    main_file = extract_zip_project(zip_path, project_dir_path)
                    
                    # Clean up zip file after extraction
                    os.remove(zip_path)
                    
                    if main_file:
                        project.project_dir = project_dir_name
                        project.main_file = main_file
                    else:
                        flash('No HTML files found in zip archive')
                        shutil.rmtree(project_dir_path)
                        return redirect(url_for('upload_project'))
                else:
                    flash('Invalid file type. Please upload a ZIP file.')
                    return redirect(url_for('upload_project'))
            
            elif upload_type == 'multiple':
                # Handle multiple file upload
                files = request.files.getlist('files[]')
                if not files or all(f.filename == '' for f in files):
                    flash('No files selected')
                    return redirect(url_for('upload_project'))
                
                # Create project directory
                project_dir_name = f"project_{current_user.id}_{int(datetime.now().timestamp())}"
                project_dir_path = os.path.join(app.config['UPLOAD_FOLDER'], project_dir_name)
                os.makedirs(project_dir_path, exist_ok=True)
                
                html_files = []
                for file in files:
                    if file.filename and allowed_file(file.filename):
                        # Maintain original filename
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(project_dir_path, filename)
                        file.save(filepath)
                        if filename.endswith('.html'):
                            html_files.append(filename)
                
                if html_files:
                    # Use first HTML file as main, or prefer index.html
                    if 'index.html' in html_files:
                        main_file = 'index.html'
                    else:
                        main_file = html_files[0]
                    project.project_dir = project_dir_name
                    project.main_file = main_file
                else:
                    flash('No HTML files found in upload')
                    shutil.rmtree(project_dir_path)
                    return redirect(url_for('upload_project'))
            
            else:
                # Handle single file upload (backward compatibility)
                if 'file' not in request.files:
                    flash('No file uploaded')
                    return redirect(url_for('upload_project'))
                
                file = request.files['file']
                if file.filename == '':
                    flash('No file selected')
                    return redirect(url_for('upload_project'))
                
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{current_user.id}_{datetime.now().timestamp()}_{file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    project.file_path = filename
                else:
                    flash('Invalid file type. Allowed: HTML, CSS, JS, images, and other web assets.')
                    return redirect(url_for('upload_project'))
        
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
    
    # Get project files if it's a multi-file project
    project_files = []
    if project.project_dir:
        project_dir_path = os.path.join(app.config['UPLOAD_FOLDER'], project.project_dir)
        project_files = get_project_files(project_dir_path)
    
    return render_template('view_project.html', project=project, project_files=project_files)

@app.route('/project/<int:project_id>/file/<path:file_path>')
@login_required
def project_file(project_id, file_path):
    # Serve files from project directory
    project = Project.query.get_or_404(project_id)
    
    # Check access
    if current_user.role == 'teacher':
        if project.classroom.teacher_id != current_user.id:
            abort(403)
    else:
        enrollment = ClassroomStudent.query.filter_by(
            classroom_id=project.classroom_id,
            student_id=current_user.id
        ).first()
        if not enrollment:
            abort(403)
    
    if not project.project_dir:
        abort(404)
    
    project_dir_path = os.path.join(app.config['UPLOAD_FOLDER'], project.project_dir)
    # Security: prevent directory traversal
    safe_path = os.path.normpath(file_path).lstrip('/')
    if '..' in safe_path or safe_path.startswith('/'):
        abort(403)
    
    file_full_path = os.path.join(project_dir_path, safe_path)
    if not os.path.exists(file_full_path) or not os.path.isfile(file_full_path):
        abort(404)
    
    # Ensure file is within project directory
    if not os.path.commonpath([project_dir_path, file_full_path]) == project_dir_path:
        abort(403)
    
    return send_from_directory(project_dir_path, safe_path)

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

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_code=404, error_message='Page not found'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', error_code=500, error_message='Internal server error'), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template('error.html', error_code=413, error_message='File too large. Maximum size is 16MB.'), 413

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")
        print("Starting server on http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
