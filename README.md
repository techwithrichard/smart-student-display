# Student Projects Display Platform

A fullstack web application built with Flask, HTML, and CSS that allows students to upload and showcase coding projects (HTML pages and Scratch links) in a classroom environment. The platform facilitates peer learning through project exhibitions, challenges, assignments with deadlines, and leaderboards.

**Repository**: [https://github.com/techwithrichard/smart-student-display.git](https://github.com/techwithrichard/smart-student-display.git)

## Features

- **Role-Based Access Control**: Admin, Teacher, Student, Parent, and Staff roles with appropriate permissions
- **Classroom Management**: Admin creates classrooms and assigns teachers. Teachers and admins can add students to classrooms
- **Subject System**: Multiple subjects per classroom, each with assigned teachers
- **Assignments with Deadlines**: Teachers create assignments with deadlines. Late submissions are automatically tracked
- **Project Upload**: Students can upload single HTML files, multiple files, or entire ZIP archives with full directory structure preservation
- **Multi-File Projects**: Support for complete web projects with HTML, CSS, JavaScript, images, and other assets
- **Code Viewer**: View source code of uploaded projects with syntax highlighting
- **Project Permissions**: Students can set project visibility (public, private, classroom, parents)
- **Parent Dashboard**: Parents receive notifications when teachers share student projects
- **Email Integration**: Teachers can send project links to parents via email
- **Challenges**: Teachers can create coding challenges with point rewards
- **Leaderboard**: Track student points and rankings within each classroom
- **Color-Coded Notifications**: Green for success, red for errors, orange for warnings
- **Responsive Design**: Modern, clean UI that works on all devices

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML5, CSS3
- **Authentication**: Flask-Login with password hashing

## Installation

**Note:** This repository includes a pre-populated database with sample data including:
- Default test accounts (admin, teacher, student, parent)
- Sample classroom with subjects
- All existing records and data

When you clone this repository, you'll have access to all the existing data. The database file is located at `instance/student_projects.db`.

**Important:** The application currently recreates the database on startup (for development). If you want to preserve the included database data, comment out the `db.drop_all()` line in `app.py` before running the application.

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd smart-student-display
```

2. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

5. Open your browser and navigate to `http://localhost:5000`

## Test Accounts

Use these accounts to test the application (displayed on login page):
- **Admin**: `richard` / `richard@gmail.com` : `richard`
- **Teacher**: `teacher` / `teacher@gmail.com` : `teacher`
- **Student**: `student` / `student@gmail.com` : `student`
- **Parent**: `parent` / `parent@gmail.com` : `parent`

## Usage

### For Admins

1. Create classrooms and assign teachers
2. Add subjects to classrooms and assign subject teachers
3. Add students to classrooms
4. Manage all users, classrooms, and projects

### For Teachers

1. View assigned classrooms and subjects
2. Create assignments with deadlines for subjects
3. Create challenges to engage students
4. Share student projects with parents via email
5. Monitor student submissions and track late submissions
6. View leaderboard and student progress

### For Students

1. Must be enrolled in a classroom (added by admin/teacher)
2. Upload own projects or submit assignments
3. View assignments with deadlines and submission status
4. Submit projects for assignments (late submissions are tracked)
5. View and like peer projects
6. Navigate multi-file projects using the built-in file browser
7. Track position on the leaderboard

## Project Structure

```
smart-student-display/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── teacher_dashboard.html
│   ├── student_dashboard.html
│   ├── classroom.html
│   ├── upload_project.html
│   ├── view_project.html
│   ├── create_classroom.html
│   └── create_challenge.html
├── static/
│   ├── css/
│   │   └── style.css     # Main stylesheet
│   └── uploads/          # Uploaded HTML files
└── README.md
```

## Database Models

- **User**: Stores user accounts (admin, teacher, student, parent, staff) with parent email for students
- **Classroom**: Represents a classroom created by admin with assigned teacher
- **ClassroomStudent**: Junction table for student enrollments and points
- **Subject**: Subjects within classrooms, each with assigned teacher
- **Assignment**: Teacher-created assignments with deadlines for subjects
- **Project**: Stores student projects (HTML or Scratch). Supports both student-created projects and assignment submissions. Includes visibility settings, screenshots, and late submission tracking
- **Challenge**: Coding challenges created by teachers
- **ChallengeSubmission**: Tracks student challenge submissions
- **ProjectShare**: Shareable links for projects
- **ParentNotification**: Notifications for parents when projects are shared
- **EmailLog**: Log of emails sent to parents

## Security Notes

- Change the `SECRET_KEY` in `app.py` before deploying to production
- Consider using environment variables for sensitive configuration
- Implement additional security measures for production deployment

## License

This project is open source and available for educational purposes.
