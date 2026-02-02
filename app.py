from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
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
app.config['SCREENSHOT_FOLDER'] = 'static/screenshots'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size for zip files

# Email configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@studentprojects.com')
ALLOWED_EXTENSIONS = {'html', 'zip', 'css', 'js', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'json', 'txt', 'ico'}
ALLOWED_ZIP_EXTENSIONS = {'zip'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
mail = Mail(app)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SCREENSHOT_FOLDER'], exist_ok=True)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='student')  # student, teacher, staff, parent, or admin
    parent_email = db.Column(db.String(120), nullable=True)  # Parent email for students (required for students)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    classrooms = db.relationship('Classroom', backref='teacher', lazy=True)
    projects = db.relationship('Project', foreign_keys='Project.student_id', backref='student', lazy=True)
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
    subjects = db.relationship('Subject', backref='classroom', lazy=True, cascade='all, delete-orphan')

class ClassroomStudent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    points = db.Column(db.Integer, default=0)
    student = db.relationship('User', backref='enrollments')
    db.UniqueConstraint('classroom_id', 'student_id')

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='taught_subjects')
    assignments = db.relationship('Assignment', backref='subject', lazy=True, cascade='all, delete-orphan')

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='created_assignments')
    submissions = db.relationship('Project', backref='assignment', lazy=True, foreign_keys='Project.assignment_id')

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    project_type = db.Column(db.String(20), nullable=False)  # html or scratch
    file_path = db.Column(db.String(255))  # For single HTML file (backward compatibility)
    project_dir = db.Column(db.String(255))  # For multi-file projects (directory path)
    main_file = db.Column(db.String(255))  # Main entry point (index.html, etc.)
    scratch_link = db.Column(db.String(500))  # For Scratch links
    screenshot_path = db.Column(db.String(255))  # Screenshot image of the project
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)  # Optional: link to subject
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=True)  # If this is a submission for an assignment
    tagged_teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Teacher tagged to project
    visibility = db.Column(db.String(20), default='classroom')  # classroom, public, private, parents
    is_student_created = db.Column(db.Boolean, default=True)  # True if student created, False if assignment submission
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)  # When student submitted (for assignments)
    likes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    tagged_teacher = db.relationship('User', foreign_keys=[tagged_teacher_id], backref='tagged_projects')
    subject = db.relationship('Subject', backref='projects')

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

class ProjectShare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    share_type = db.Column(db.String(20), default='parents')
    share_code = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    project = db.relationship('Project', backref='shares')
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='shared_projects')

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_email = db.Column(db.String(120), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='sent')  # sent, failed
    project = db.relationship('Project', backref='email_logs')
    teacher = db.relationship('User', foreign_keys=[teacher_id])

class ParentNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    share_code = db.Column(db.String(20), nullable=True)
    viewed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    project = db.relationship('Project', backref='parent_notifications')
    parent = db.relationship('User', foreign_keys=[parent_id], backref='notifications')
    teacher = db.relationship('User', foreign_keys=[teacher_id])
    student = db.relationship('User', foreign_keys=[student_id])

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
        if current_user.role not in ['teacher', 'staff', 'admin']:
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

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def generate_share_code():
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

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
        
        parent_email = request.form.get('parent_email', '').strip() if role == 'student' else None
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            parent_email=parent_email if parent_email else None
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
        
        if not user:
            # Try email instead
            user = User.query.filter_by(email=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username/email or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'parent':
        return redirect(url_for('parent_dashboard'))
    elif current_user.role in ['teacher', 'staff']:
        classrooms = Classroom.query.filter_by(teacher_id=current_user.id).all()
        return render_template('teacher_dashboard.html', classrooms=classrooms)
    else:
        # Enforce that students must belong to a class
        enrollments = ClassroomStudent.query.filter_by(student_id=current_user.id).all()
        if not enrollments:
            flash('You must be enrolled in a classroom. Please contact your teacher or admin.', 'warning')
            return render_template('student_dashboard.html', classrooms=[], projects=[], no_classroom=True)
        
        classroom_ids = [e.classroom_id for e in enrollments]
        classrooms = Classroom.query.filter(Classroom.id.in_(classroom_ids)).all()
        projects = Project.query.filter_by(student_id=current_user.id).all()
        return render_template('student_dashboard.html', classrooms=classrooms, projects=projects, no_classroom=False)

@app.route('/classroom/create', methods=['GET', 'POST'])
@admin_required
def create_classroom():
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        teacher_id = request.form.get('teacher_id')
        
        if not teacher_id:
            flash('Please select a teacher for this classroom')
            return redirect(url_for('create_classroom'))
        
        teacher = User.query.get(teacher_id)
        if not teacher or teacher.role != 'teacher':
            flash('Invalid teacher selected')
            return redirect(url_for('create_classroom'))
        
        if Classroom.query.filter_by(code=code).first():
            flash('Classroom code already exists')
            return redirect(url_for('create_classroom'))
        
        classroom = Classroom(name=name, code=code, teacher_id=teacher_id)
        db.session.add(classroom)
        db.session.commit()
        flash('Classroom created successfully!')
        return redirect(url_for('admin_dashboard'))
    
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('create_classroom.html', teachers=teachers)

# Admin/Teacher route to add student to classroom
@app.route('/classroom/<int:classroom_id>/add-student', methods=['GET', 'POST'])
@login_required
def add_student_to_classroom(classroom_id):
    classroom = Classroom.query.get_or_404(classroom_id)
    
    # Only admin or the classroom teacher can add students
    if current_user.role != 'admin' and classroom.teacher_id != current_user.id:
        flash('You do not have permission to add students to this classroom')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        if not student_id:
            flash('Please select a student')
            return redirect(url_for('add_student_to_classroom', classroom_id=classroom_id))
        
        student = User.query.get(student_id)
        if not student or student.role != 'student':
            flash('Invalid student selected')
            return redirect(url_for('add_student_to_classroom', classroom_id=classroom_id))
        
        # Check if already enrolled
        existing = ClassroomStudent.query.filter_by(
            classroom_id=classroom_id,
            student_id=student_id
        ).first()
        
        if existing:
            flash(f'{student.username} is already in this classroom')
            return redirect(url_for('add_student_to_classroom', classroom_id=classroom_id))
        
        enrollment = ClassroomStudent(classroom_id=classroom_id, student_id=student_id)
        db.session.add(enrollment)
        db.session.commit()
        flash(f'Student {student.username} added to classroom successfully!')
        return redirect(url_for('classroom_view', classroom_id=classroom_id))
    
    # Get all students not yet in this classroom
    enrolled_student_ids = [e.student_id for e in ClassroomStudent.query.filter_by(classroom_id=classroom_id).all()]
    all_students = User.query.filter_by(role='student').all()
    available_students = [s for s in all_students if s.id not in enrolled_student_ids]
    
    return render_template('add_student_to_classroom.html', classroom=classroom, students=available_students)

# Remove student from classroom
@app.route('/classroom/<int:classroom_id>/remove-student/<int:student_id>', methods=['POST'])
@login_required
def remove_student_from_classroom(classroom_id, student_id):
    classroom = Classroom.query.get_or_404(classroom_id)
    
    # Only admin or the classroom teacher can remove students
    if current_user.role != 'admin' and classroom.teacher_id != current_user.id:
        flash('You do not have permission to remove students from this classroom')
        return redirect(url_for('dashboard'))
    
    enrollment = ClassroomStudent.query.filter_by(
        classroom_id=classroom_id,
        student_id=student_id
    ).first_or_404()
    
    student = User.query.get(student_id)
    db.session.delete(enrollment)
    db.session.commit()
    flash(f'Student {student.username} removed from classroom')
    return redirect(url_for('classroom_view', classroom_id=classroom_id))

@app.route('/classroom/<int:classroom_id>')
@login_required
def classroom_view(classroom_id):
    classroom = Classroom.query.get_or_404(classroom_id)
    
    # Check access
    if current_user.role in ['teacher', 'staff', 'admin']:
        if classroom.teacher_id != current_user.id and current_user.role != 'admin':
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
    subjects = Subject.query.filter_by(classroom_id=classroom_id).all()
    
    # Get leaderboard
    enrollments = ClassroomStudent.query.filter_by(classroom_id=classroom_id).order_by(ClassroomStudent.points.desc()).limit(10).all()
    leaderboard = []
    for e in enrollments:
        student = User.query.get(e.student_id)
        leaderboard.append({'username': student.username, 'points': e.points})
    
    return render_template('classroom.html', classroom=classroom, projects=projects, challenges=challenges, subjects=subjects, leaderboard=leaderboard)

@app.route('/project/upload', methods=['GET', 'POST'])
@login_required
def upload_project():
    if current_user.role in ['teacher', 'staff', 'admin']:
        flash('Teachers and staff cannot upload projects')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        project_type = request.form.get('project_type')
        assignment_id = request.form.get('assignment_id')
        classroom_id = request.form.get('classroom_id')
        
        # Determine classroom and subject from assignment or direct selection
        if assignment_id:
            assignment = Assignment.query.get(assignment_id)
            if not assignment:
                flash('Invalid assignment')
                return redirect(url_for('upload_project'))
            classroom_id = assignment.subject.classroom_id
            subject_id = assignment.subject_id
        else:
            subject_id = None
        
        # Verify classroom access
        enrollment = ClassroomStudent.query.filter_by(
            classroom_id=classroom_id,
            student_id=current_user.id
        ).first()
        if not enrollment:
            flash('You are not enrolled in this classroom')
            return redirect(url_for('dashboard'))
        
        # Get tagged teacher from classroom
        classroom = Classroom.query.get(classroom_id)
        tagged_teacher_id = classroom.teacher_id if classroom else None
        
        project = Project(
            title=title,
            description=description,
            project_type=project_type,
            student_id=current_user.id,
            classroom_id=classroom_id,
            subject_id=subject_id,
            assignment_id=assignment_id if assignment_id else None,
            tagged_teacher_id=tagged_teacher_id,
            visibility='classroom',  # Default visibility
            is_student_created=(assignment_id is None)
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
        
        # Handle screenshot upload
        if 'screenshot' in request.files:
            screenshot = request.files['screenshot']
            if screenshot.filename and allowed_image_file(screenshot.filename):
                filename = secure_filename(f"screenshot_{current_user.id}_{datetime.now().timestamp()}.{screenshot.filename.rsplit('.', 1)[1].lower()}")
                filepath = os.path.join(app.config['SCREENSHOT_FOLDER'], filename)
                screenshot.save(filepath)
                project.screenshot_path = filename
        
        # Set submission time for assignments
        if assignment_id:
            assignment = Assignment.query.get(assignment_id)
            if assignment:
                project.submitted_at = datetime.utcnow()
                # Check if late
                if project.submitted_at > assignment.deadline:
                    flash(f'Project uploaded successfully! Note: This submission is late.')
                else:
                    flash('Project uploaded successfully!')
        
        db.session.add(project)
        db.session.commit()
        
        if assignment_id:
            return redirect(url_for('view_assignment', assignment_id=assignment_id))
        return redirect(url_for('classroom_view', classroom_id=classroom_id))
    
    # Get student's classrooms
    enrollments = ClassroomStudent.query.filter_by(student_id=current_user.id).all()
    if not enrollments:
        flash('You must be enrolled in a classroom to upload projects')
        return redirect(url_for('dashboard'))
    
    classroom_ids = [e.classroom_id for e in enrollments]
    classrooms = Classroom.query.filter(Classroom.id.in_(classroom_ids)).all()
    
    # Get available assignments for student's classrooms
    assignments = Assignment.query.join(Subject).filter(Subject.classroom_id.in_(classroom_ids)).all()
    
    return render_template('upload_project.html', classrooms=classrooms, assignments=assignments)

@app.route('/project/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check access based on visibility
    if not check_project_access(project):
        flash('You do not have access to this project')
        return redirect(url_for('dashboard'))
    
    project.views += 1
    db.session.commit()
    
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
    
    # Check access based on visibility
    if not check_project_access(project):
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

@app.route('/project/<int:project_id>/code/<path:file_path>')
@login_required
def view_code(project_id, file_path):
    # View code content of a file
    project = Project.query.get_or_404(project_id)
    
    if not check_project_access(project):
        abort(403)
    
    if not project.project_dir:
        abort(404)
    
    project_dir_path = os.path.join(app.config['UPLOAD_FOLDER'], project.project_dir)
    safe_path = os.path.normpath(file_path).lstrip('/')
    if '..' in safe_path or safe_path.startswith('/'):
        abort(403)
    
    file_full_path = os.path.join(project_dir_path, safe_path)
    if not os.path.exists(file_full_path) or not os.path.isfile(file_full_path):
        abort(404)
    
    if not os.path.commonpath([project_dir_path, file_full_path]) == project_dir_path:
        abort(403)
    
    # Read file content
    try:
        with open(file_full_path, 'r', encoding='utf-8', errors='ignore') as f:
            code_content = f.read()
        file_extension = os.path.splitext(safe_path)[1].lstrip('.')
        return render_template('view_code.html', project=project, file_path=safe_path, code_content=code_content, file_extension=file_extension)
    except Exception as e:
        flash('Error reading file: ' + str(e))
        return redirect(url_for('view_project', project_id=project_id))

def calculate_late_time(deadline, submitted_at):
    """Calculate how late a submission is"""
    if submitted_at <= deadline:
        return None
    delta = submitted_at - deadline
    hours = delta.total_seconds() / 3600
    days = delta.days
    if days > 0:
        return f"{days} day{'s' if days > 1 else ''} {int(hours % 24)} hour{'s' if int(hours % 24) != 1 else ''} late"
    elif hours >= 1:
        return f"{int(hours)} hour{'s' if int(hours) > 1 else ''} late"
    else:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} late"

def check_project_access(project):
    # Check if user has access to project based on visibility settings
    if current_user.role == 'admin':
        return True
    if project.student_id == current_user.id:
        return True
    if project.visibility == 'public':
        return True
    if project.visibility == 'private':
        return False
    if project.visibility == 'classroom':
        if current_user.role in ['teacher', 'staff', 'admin']:
            if current_user.role == 'admin':
                return True
            return project.classroom.teacher_id == current_user.id
        if current_user.role == 'parent':
            # Parents can view if they have a notification for this project
            notification = ParentNotification.query.filter_by(
                project_id=project.id,
                parent_id=current_user.id
            ).first()
            return notification is not None
        enrollment = ClassroomStudent.query.filter_by(
            classroom_id=project.classroom_id,
            student_id=current_user.id
        ).first()
        return enrollment is not None
    if project.visibility == 'parents':
        if current_user.role in ['teacher', 'staff', 'admin']:
            if current_user.role == 'admin':
                return True
            return project.classroom.teacher_id == current_user.id or project.tagged_teacher_id == current_user.id
        if current_user.role == 'parent':
            # Parents can view if they have a notification for this project
            notification = ParentNotification.query.filter_by(
                project_id=project.id,
                parent_id=current_user.id
            ).first()
            return notification is not None
        return False
    return False

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
    if current_user.role not in ['teacher', 'admin']:
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
    if current_user.role != 'student':
        flash('Only students can submit challenges')
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

# Admin routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    users = User.query.all()
    classrooms = Classroom.query.all()
    projects = Project.query.all()
    stats = {
        'total_users': User.query.count(),
        'total_students': User.query.filter_by(role='student').count(),
        'total_teachers': User.query.filter_by(role='teacher').count(),
        'total_staff': User.query.filter_by(role='staff').count(),
        'total_classrooms': Classroom.query.count(),
        'total_projects': Project.query.count()
    }
    return render_template('admin_dashboard.html', users=users, classrooms=classrooms, projects=projects, stats=stats)

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Cannot delete admin user')
        return redirect(url_for('admin_dashboard'))
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} deleted successfully')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Cannot modify admin user')
        return redirect(url_for('admin_dashboard'))
    # Toggle between student and teacher
    user.role = 'teacher' if user.role == 'student' else 'student'
    db.session.commit()
    flash(f'User {user.username} role updated to {user.role}')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-user', methods=['GET', 'POST'])
@admin_required
def admin_add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student')
        parent_email = request.form.get('parent_email', '').strip() if role == 'student' else None
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('admin_add_user'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('admin_add_user'))
        
        # Parent email is required for students
        if role == 'student' and not parent_email:
            flash('Parent email is required for students')
            return redirect(url_for('admin_add_user'))
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            parent_email=parent_email if parent_email else None
        )
        db.session.add(user)
        db.session.commit()
        flash(f'User {username} ({role}) created successfully!')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_add_user.html')

@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin' and user.id != current_user.id:
        flash('Cannot edit other admin users')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        parent_email = request.form.get('parent_email', '').strip() if role == 'student' else None
        
        # Check username uniqueness (except current user)
        existing_user = User.query.filter_by(username=username).first()
        if existing_user and existing_user.id != user.id:
            flash('Username already exists')
            return redirect(url_for('admin_edit_user', user_id=user_id))
        
        # Check email uniqueness (except current user)
        existing_email = User.query.filter_by(email=email).first()
        if existing_email and existing_email.id != user.id:
            flash('Email already exists')
            return redirect(url_for('admin_edit_user', user_id=user_id))
        
        # Parent email required for students
        if role == 'student' and not parent_email:
            flash('Parent email is required for students')
            return redirect(url_for('admin_edit_user', user_id=user_id))
        
        # Update password if provided
        new_password = request.form.get('password', '').strip()
        if new_password:
            user.password_hash = generate_password_hash(new_password)
        
        user.username = username
        user.email = email
        user.role = role
        user.parent_email = parent_email if parent_email else None
        
        db.session.commit()
        flash(f'User {username} updated successfully!')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_edit_user.html', user=user)

# Subject management routes
@app.route('/admin/classroom/<int:classroom_id>/add-subject', methods=['GET', 'POST'])
@admin_required
def add_subject(classroom_id):
    classroom = Classroom.query.get_or_404(classroom_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        teacher_id = request.form.get('teacher_id')
        
        if not name or not teacher_id:
            flash('Subject name and teacher are required')
            return redirect(url_for('add_subject', classroom_id=classroom_id))
        
        teacher = User.query.get(teacher_id)
        if not teacher or teacher.role != 'teacher':
            flash('Invalid teacher selected')
            return redirect(url_for('add_subject', classroom_id=classroom_id))
        
        subject = Subject(name=name, classroom_id=classroom_id, teacher_id=teacher_id)
        db.session.add(subject)
        db.session.commit()
        flash(f'Subject "{name}" added successfully!')
        return redirect(url_for('classroom_view', classroom_id=classroom_id))
    
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('add_subject.html', classroom=classroom, teachers=teachers)

# Assignment routes
@app.route('/subject/<int:subject_id>/create-assignment', methods=['GET', 'POST'])
@teacher_required
def create_assignment(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    
    # Check if teacher has access
    if current_user.role != 'admin' and subject.teacher_id != current_user.id:
        flash('You do not have permission to create assignments for this subject')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        deadline_str = request.form.get('deadline')
        
        if not title or not deadline_str:
            flash('Title and deadline are required')
            return redirect(url_for('create_assignment', subject_id=subject_id))
        
        try:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid deadline format')
            return redirect(url_for('create_assignment', subject_id=subject_id))
        
        assignment = Assignment(
            title=title,
            description=description,
            subject_id=subject_id,
            teacher_id=current_user.id,
            deadline=deadline
        )
        db.session.add(assignment)
        db.session.commit()
        flash('Assignment created successfully!')
        return redirect(url_for('view_subject', subject_id=subject_id))
    
    return render_template('create_assignment.html', subject=subject)

@app.route('/subject/<int:subject_id>')
@login_required
def view_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    
    # Check access
    if current_user.role == 'student':
        enrollment = ClassroomStudent.query.filter_by(
            classroom_id=subject.classroom_id,
            student_id=current_user.id
        ).first()
        if not enrollment:
            flash('You are not enrolled in this classroom')
            return redirect(url_for('dashboard'))
    elif current_user.role not in ['teacher', 'admin']:
        flash('Access denied')
        return redirect(url_for('dashboard'))
    
    assignments = Assignment.query.filter_by(subject_id=subject_id).order_by(Assignment.deadline).all()
    from datetime import datetime as dt
    return render_template('view_subject.html', subject=subject, assignments=assignments, datetime=dt)

@app.route('/assignment/<int:assignment_id>')
@login_required
def view_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    subject = assignment.subject
    
    # Check access
    if current_user.role == 'student':
        enrollment = ClassroomStudent.query.filter_by(
            classroom_id=subject.classroom_id,
            student_id=current_user.id
        ).first()
        if not enrollment:
            flash('You are not enrolled in this classroom')
            return redirect(url_for('dashboard'))
    elif current_user.role not in ['teacher', 'admin']:
        if subject.teacher_id != current_user.id and current_user.role != 'admin':
            flash('Access denied')
            return redirect(url_for('dashboard'))
    
    # Get submissions
    submissions = Project.query.filter_by(assignment_id=assignment_id).all()
    
    # Calculate late status for each submission
    submission_data = []
    for submission in submissions:
        late_time = None
        if submission.submitted_at:
            late_time = calculate_late_time(assignment.deadline, submission.submitted_at)
        submission_data.append({
            'project': submission,
            'late_time': late_time,
            'is_late': submission.submitted_at and submission.submitted_at > assignment.deadline
        })
    
    # Check if current student has submitted
    student_submission = None
    if current_user.role == 'student':
        student_submission = Project.query.filter_by(
            assignment_id=assignment_id,
            student_id=current_user.id
        ).first()
    
    from datetime import datetime as dt
    return render_template('view_assignment.html', 
                        assignment=assignment, 
                        subject=subject,
                        submissions=submission_data,
                        student_submission=student_submission,
                        calculate_late_time=calculate_late_time,
                        datetime=dt)

# Project permissions and settings
@app.route('/project/<int:project_id>/settings', methods=['GET', 'POST'])
@login_required
def project_settings(project_id):
    project = Project.query.get_or_404(project_id)
    if project.student_id != current_user.id and current_user.role != 'admin':
        flash('You can only edit your own projects')
        return redirect(url_for('view_project', project_id=project_id))
    
    if request.method == 'POST':
        project.visibility = request.form.get('visibility', 'classroom')
        tagged_teacher_id = request.form.get('tagged_teacher_id')
        if tagged_teacher_id:
            teacher = User.query.get(tagged_teacher_id)
            if teacher and teacher.role == 'teacher':
                project.tagged_teacher_id = teacher.id
        else:
            project.tagged_teacher_id = None
        
        if 'screenshot' in request.files:
            screenshot = request.files['screenshot']
            if screenshot.filename and allowed_image_file(screenshot.filename):
                filename = secure_filename(f"screenshot_{project.id}_{datetime.now().timestamp()}.{screenshot.filename.rsplit('.', 1)[1].lower()}")
                filepath = os.path.join(app.config['SCREENSHOT_FOLDER'], filename)
                screenshot.save(filepath)
                project.screenshot_path = filename
        
        db.session.commit()
        flash('Project settings updated successfully!')
        return redirect(url_for('view_project', project_id=project_id))
    
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('project_settings.html', project=project, teachers=teachers)

# Teacher sharing with parents
@app.route('/teacher/share-project/<int:project_id>', methods=['GET', 'POST'])
@teacher_required
def share_project_with_parents(project_id):
    project = Project.query.get_or_404(project_id)
    if project.classroom.teacher_id != current_user.id and current_user.role != 'admin':
        flash('You can only share projects from your classrooms')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        share_type = request.form.get('share_type', 'parents')
        
        # For non-public projects, only allow sharing to student's parent
        if project.visibility != 'public' and share_type == 'parents':
            student = project.student
            if not student.parent_email:
                flash('Cannot share: This student has no parent email registered and project is not public.')
                return redirect(url_for('share_project_with_parents', project_id=project_id))
        
        share_code = generate_share_code()
        
        existing_share = ProjectShare.query.filter_by(project_id=project_id, teacher_id=current_user.id).first()
        if existing_share:
            existing_share.share_code = share_code
            existing_share.share_type = share_type
        else:
            share = ProjectShare(
                project_id=project_id,
                teacher_id=current_user.id,
                share_type=share_type,
                share_code=share_code
            )
            db.session.add(share)
        
        db.session.commit()
        flash(f'Project shared! Share code: {share_code}')
        return redirect(url_for('teacher_sharing'))
    
    return render_template('share_project.html', project=project)

@app.route('/teacher/sharing')
@teacher_required
def teacher_sharing():
    classrooms = Classroom.query.filter_by(teacher_id=current_user.id).all()
    classroom_ids = [c.id for c in classrooms]
    projects = Project.query.filter(Project.classroom_id.in_(classroom_ids)).all()
    shares = ProjectShare.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher_sharing.html', projects=projects, shares=shares)

@app.route('/share/<share_code>')
def view_shared_project(share_code):
    share = ProjectShare.query.filter_by(share_code=share_code).first_or_404()
    project = share.project
    
    # Mark notification as viewed if parent is logged in
    if current_user.is_authenticated and current_user.role == 'parent':
        notification = ParentNotification.query.filter_by(
            project_id=project.id,
            parent_id=current_user.id,
            share_code=share_code
        ).first()
        if notification and not notification.viewed:
            notification.viewed = True
            db.session.commit()
    
    return render_template('view_shared_project.html', project=project, share=share)

# Parent dashboard
@app.route('/parent/dashboard')
@login_required
def parent_dashboard():
    if current_user.role != 'parent':
        flash('Access denied. Parent privileges required.')
        return redirect(url_for('dashboard'))
    
    # Get all notifications for this parent
    notifications = ParentNotification.query.filter_by(parent_id=current_user.id).order_by(ParentNotification.created_at.desc()).all()
    
    # Get unread count
    unread_count = ParentNotification.query.filter_by(parent_id=current_user.id, viewed=False).count()
    
    return render_template('parent_dashboard.html', notifications=notifications, unread_count=unread_count)

@app.route('/parent/notification/<int:notification_id>/view')
@login_required
def view_parent_notification(notification_id):
    if current_user.role != 'parent':
        flash('Access denied. Parent privileges required.')
        return redirect(url_for('dashboard'))
    
    notification = ParentNotification.query.get_or_404(notification_id)
    if notification.parent_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('parent_dashboard'))
    
    # Mark as viewed
    notification.viewed = True
    db.session.commit()
    
    if notification.share_code:
        return redirect(url_for('view_shared_project', share_code=notification.share_code))
    else:
        return redirect(url_for('view_project', project_id=notification.project_id))

@app.route('/parent/notification/<int:notification_id>/mark-read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    if current_user.role != 'parent':
        abort(403)
    
    notification = ParentNotification.query.get_or_404(notification_id)
    if notification.parent_id != current_user.id:
        abort(403)
    
    notification.viewed = True
    db.session.commit()
    return redirect(url_for('parent_dashboard'))

# Email sending routes
@app.route('/teacher/send-email/<int:project_id>', methods=['GET', 'POST'])
@teacher_required
def send_project_email(project_id):
    project = Project.query.get_or_404(project_id)
    if project.classroom.teacher_id != current_user.id and current_user.role != 'admin':
        flash('You can only send emails for projects from your classrooms')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        parent_email = request.form.get('parent_email', '').strip()
        custom_message = request.form.get('message', '')
        
        if not parent_email:
            flash('Parent email is required')
            return redirect(url_for('send_project_email', project_id=project_id))
        
        # Check if project is public or if parent email matches student's parent
        student = project.student
        if not student.parent_email:
            flash('This student has no parent email registered. Cannot send email.')
            return redirect(url_for('send_project_email', project_id=project_id))
        if project.visibility != 'public':
            if parent_email.lower() != student.parent_email.lower():
                flash('You can only send this project to the student\'s registered parent email. This project is not public.')
                return redirect(url_for('send_project_email', project_id=project_id))
        
        # Generate or get share code
        share = ProjectShare.query.filter_by(project_id=project_id, teacher_id=current_user.id).first()
        if not share:
            share_code = generate_share_code()
            share = ProjectShare(
                project_id=project_id,
                teacher_id=current_user.id,
                share_type='parents',
                share_code=share_code
            )
            db.session.add(share)
        else:
            share_code = share.share_code
        
        share_url = url_for('view_shared_project', share_code=share_code, _external=True)
        
        # Send email
        try:
            msg = Message(
                subject=f'Student Project: {project.title}',
                recipients=[parent_email],
                html=render_template('email_project_link.html', 
                                   project=project, 
                                   share_url=share_url,
                                   teacher=current_user,
                                   custom_message=custom_message)
            )
            mail.send(msg)
            
            # Log email
            email_log = EmailLog(
                project_id=project_id,
                teacher_id=current_user.id,
                parent_email=parent_email,
                status='sent'
            )
            db.session.add(email_log)
            
            # Create parent notification
            parent_user = User.query.filter_by(email=parent_email, role='parent').first()
            if parent_user:
                notification = ParentNotification(
                    project_id=project_id,
                    parent_id=parent_user.id,
                    teacher_id=current_user.id,
                    student_id=project.student_id,
                    share_code=share_code
                )
                db.session.add(notification)
            
            db.session.commit()
            flash(f'Email sent successfully to {parent_email}!')
        except Exception as e:
            email_log = EmailLog(
                project_id=project_id,
                teacher_id=current_user.id,
                parent_email=parent_email,
                status='failed'
            )
            db.session.add(email_log)
            db.session.commit()
            flash(f'Failed to send email: {str(e)}')
        
        return redirect(url_for('teacher_sharing'))
    
    # Get student's parent email if available
    student = project.student
    parent_email = student.parent_email if student.parent_email else ''
    
    return render_template('send_email.html', project=project, parent_email=parent_email)

@app.route('/teacher/send-bulk-email/<int:project_id>', methods=['POST'])
@teacher_required
def send_bulk_email(project_id):
    project = Project.query.get_or_404(project_id)
    if project.classroom.teacher_id != current_user.id and current_user.role != 'admin':
        flash('You can only send emails for projects from your classrooms')
        return redirect(url_for('dashboard'))
    
    # Only send to the specific student's parent (not all parents in classroom)
    student = project.student
    if not student.parent_email:
        flash('This student has no parent email registered. Cannot send email.')
        return redirect(url_for('send_project_email', project_id=project_id))
    
    # Check if project is public - if not, only send to student's parent
    if project.visibility != 'public':
        students_with_parents = [student] if student.parent_email else []
    else:
        # For public projects, get all students in classroom with parent emails
        enrollments = ClassroomStudent.query.filter_by(classroom_id=project.classroom_id).all()
        students = [User.query.get(e.student_id) for e in enrollments]
        students_with_parents = [s for s in students if s and s.parent_email]
    
    if not students_with_parents:
        flash('No parent email available for this project')
        return redirect(url_for('send_project_email', project_id=project_id))
    
    # Generate or get share code
    share = ProjectShare.query.filter_by(project_id=project_id, teacher_id=current_user.id).first()
    if not share:
        share_code = generate_share_code()
        share = ProjectShare(
            project_id=project_id,
            teacher_id=current_user.id,
            share_type='parents',
            share_code=share_code
        )
        db.session.add(share)
    else:
        share_code = share.share_code
    
    share_url = url_for('view_shared_project', share_code=share_code, _external=True)
    custom_message = request.form.get('message', '')
    
    sent_count = 0
    failed_count = 0
    
    for student in students_with_parents:
        try:
            msg = Message(
                subject=f'Student Project: {project.title}',
                recipients=[student.parent_email],
                html=render_template('email_project_link.html', 
                                   project=project, 
                                   share_url=share_url,
                                   teacher=current_user,
                                   student=student,
                                   custom_message=custom_message)
            )
            mail.send(msg)
            
            email_log = EmailLog(
                project_id=project_id,
                teacher_id=current_user.id,
                parent_email=student.parent_email,
                status='sent'
            )
            db.session.add(email_log)
            
            # Create parent notification
            parent_user = User.query.filter_by(email=student.parent_email, role='parent').first()
            if parent_user:
                notification = ParentNotification(
                    project_id=project_id,
                    parent_id=parent_user.id,
                    teacher_id=current_user.id,
                    student_id=student.id,
                    share_code=share_code
                )
                db.session.add(notification)
            
            sent_count += 1
        except Exception as e:
            email_log = EmailLog(
                project_id=project_id,
                teacher_id=current_user.id,
                parent_email=student.parent_email,
                status='failed'
            )
            db.session.add(email_log)
            failed_count += 1
    
    db.session.commit()
    flash(f'Bulk email sent! {sent_count} successful, {failed_count} failed.')
    return redirect(url_for('teacher_sharing'))

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
        # Create tables if they don't exist (preserves existing data)
        # Uncomment the next 2 lines if you want to reset the database during development
        # db.drop_all()
        db.create_all()
        
        # Create default test users if they don't exist
        default_users = [
            {'username': 'richard', 'email': 'richard@gmail.com', 'password': 'richard', 'role': 'admin'},
            {'username': 'teacher', 'email': 'teacher@gmail.com', 'password': 'teacher', 'role': 'teacher'},
            {'username': 'student', 'email': 'student@gmail.com', 'password': 'student', 'role': 'student', 'parent_email': 'parent@gmail.com'},
            {'username': 'parent', 'email': 'parent@gmail.com', 'password': 'parent', 'role': 'parent'}
        ]
        
        for user_data in default_users:
            existing = User.query.filter_by(email=user_data['email']).first()
            if not existing:
                user = User(
                    username=user_data['username'],
                    email=user_data['email'],
                    password_hash=generate_password_hash(user_data['password']),
                    role=user_data['role'],
                    parent_email=user_data.get('parent_email')
                )
                db.session.add(user)
                print(f"Created {user_data['role']} user: {user_data['username']} / {user_data['email']} : {user_data['password']}")
        
        db.session.commit()
        
        # Create sample classroom and subjects
        sample_classroom = Classroom.query.filter_by(code='SAMPLE01').first()
        if not sample_classroom:
            teacher_user = User.query.filter_by(email='teacher@gmail.com').first()
            if teacher_user:
                sample_classroom = Classroom(
                    name='Sample Classroom',
                    code='SAMPLE01',
                    teacher_id=teacher_user.id
                )
                db.session.add(sample_classroom)
                db.session.commit()
                
                # Add sample subjects
                subjects_data = [
                    {'name': 'Mathematics', 'teacher_id': teacher_user.id},
                    {'name': 'Science', 'teacher_id': teacher_user.id},
                    {'name': 'Computer Science', 'teacher_id': teacher_user.id}
                ]
                
                for subj_data in subjects_data:
                    subject = Subject(
                        name=subj_data['name'],
                        classroom_id=sample_classroom.id,
                        teacher_id=subj_data['teacher_id']
                    )
                    db.session.add(subject)
                
                # Add student to sample classroom
                student_user = User.query.filter_by(email='student@gmail.com').first()
                if student_user:
                    enrollment = ClassroomStudent(
                        classroom_id=sample_classroom.id,
                        student_id=student_user.id
                    )
                    db.session.add(enrollment)
                
                db.session.commit()
                print("Sample classroom and subjects created successfully")
        
        print("Database initialized successfully")
        print("Starting server on http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
