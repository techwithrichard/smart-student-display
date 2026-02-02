# Smart Student Display

A web platform where students can upload coding projects, teachers can create assignments with deadlines, and parents can see their kids' work. Built with Flask, HTML, and CSS.

**Repository**: [https://github.com/techwithrichard/smart-student-display.git](https://github.com/techwithrichard/smart-student-display.git)

## The Problem

Teachers needed a way to:
- See student coding projects in one place
- Create assignments with deadlines and track late submissions
- Share student work with parents easily
- Organize projects by subjects and classrooms

Students needed:
- A simple way to upload HTML projects (single files or entire folders)
- See their assignments and deadlines
- View their classmates' work for inspiration
- Track their progress on a leaderboard

Parents wanted:
- Easy access to see their child's projects
- Notifications when teachers share work

## The Solution

I built a full-stack web app that handles all of this. Here's how it works:

**For Admins:**
- Create classrooms and assign teachers to them
- Add subjects to classrooms (like Math, Science, CS) and assign subject teachers
- Add students to classrooms
- Manage all users and see everything happening in the system

**For Teachers:**
- Get assigned to classrooms and subjects by admin
- Create assignments with deadlines - students submit projects, and the system automatically tracks if they're late (shows "2 hours late" or "1 day late", etc.)
- Create challenges for students to earn points
- Share student projects with parents via email
- See all submissions in one place with late status clearly marked

**For Students:**
- Must be added to a classroom by admin/teacher (can't join on their own)
- Upload their own creative projects OR submit projects for assignments
- See all assignments with deadlines - the system warns if deadline passed
- View code from other students' projects
- Set who can see their projects (public, classroom only, parents only, private)
- Upload screenshots if code can't be visualized
- Track their position on the leaderboard

**For Parents:**
- Get email notifications when teachers share their child's projects
- See all shared projects in a dashboard
- Click links to view projects directly

## Key Features

- **Multi-file project uploads**: Students can upload ZIP files or multiple files - the system preserves folder structure and finds the main HTML file automatically
- **Code viewer**: Click any file in a project to see its source code
- **Late submission tracking**: Automatically calculates and displays how late submissions are (e.g., "3 hours late", "2 days 5 hours late")
- **Subject-based organization**: Each classroom has multiple subjects, each with its own teacher
- **Email integration**: Teachers can send project links to parents via email
- **Project permissions**: Students control who sees their work
- **Color-coded notifications**: Green for success, red for errors, orange for warnings
- **Responsive design**: Works on desktop, tablet, and mobile

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite with SQLAlchemy
- **Frontend**: HTML5, CSS3
- **Authentication**: Flask-Login with password hashing
- **Email**: Flask-Mail for sending project links to parents

## Getting Started

### Quick Setup

1. **Clone the repository:**
```bash
git clone https://github.com/techwithrichard/smart-student-display.git
cd smart-student-display
```

2. **Create a virtual environment:**
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
# or
source venv/bin/activate  # On Mac/Linux
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Run the app:**
```bash
python app.py
```

5. **Open your browser:**
Navigate to `http://localhost:5000`

### Test Accounts

The app comes with pre-configured test accounts (shown on login page):

- **Admin**: `richard` / `richard@gmail.com` : `richard`
- **Teacher**: `teacher` / `teacher@gmail.com` : `teacher`
- **Student**: `student` / `student@gmail.com` : `student`
- **Parent**: `parent` / `parent@gmail.com` : `parent`

The database includes a sample classroom with subjects already set up. The student account is already enrolled.

### Using the Project

**First time setup:**
1. Log in as admin (richard/richard)
2. Create a classroom and assign a teacher
3. Add subjects to the classroom
4. Add students to the classroom
5. Students can now upload projects or teachers can create assignments

**For personal use:**
- The database file (`instance/student_projects.db`) is included with sample data
- All your data persists between runs (database is preserved by default)
- You can add your own classrooms, subjects, and users
- Email functionality requires configuring SMTP settings in environment variables (optional)

**Email setup (optional):**
If you want email notifications to work, set these environment variables:
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

## Project Structure

```
smart-student-display/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── instance/
│   └── student_projects.db   # SQLite database (included with sample data)
├── templates/                # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── admin_dashboard.html
│   ├── teacher_dashboard.html
│   ├── student_dashboard.html
│   ├── parent_dashboard.html
│   ├── classroom.html
│   ├── upload_project.html
│   ├── view_project.html
│   ├── view_code.html
│   ├── create_classroom.html
│   ├── create_challenge.html
│   ├── create_assignment.html
│   ├── view_subject.html
│   ├── view_assignment.html
│   └── ... (other templates)
└── static/
    ├── css/
    │   └── style.css        # Main stylesheet
    ├── uploads/             # Uploaded project files
    └── screenshots/         # Project screenshots
```

## How It Works

**Database Models:**
- `User`: All users (admin, teacher, student, parent, staff) with parent email for students
- `Classroom`: Classrooms created by admin with assigned teacher
- `Subject`: Subjects within classrooms, each with assigned teacher
- `Assignment`: Teacher-created assignments with deadlines
- `Project`: Student projects (can be student-created or assignment submissions) with visibility settings
- `ClassroomStudent`: Links students to classrooms and tracks points
- `Challenge`: Coding challenges for students
- `ProjectShare`: Shareable links for projects
- `ParentNotification`: Notifications when projects are shared
- `EmailLog`: Log of emails sent

**Workflow:**
1. Admin creates classroom → assigns teacher
2. Admin adds subjects → assigns subject teachers
3. Admin/teacher adds students to classroom
4. Teacher creates assignments with deadlines
5. Students upload projects (own projects or for assignments)
6. System tracks late submissions automatically
7. Teacher shares projects with parents via email
8. Parents see notifications and can view projects

## Outcome

The platform successfully:
-  Handles multi-file project uploads with folder structure preservation
-  Tracks assignment deadlines and calculates late submission times
-  Organizes everything by classrooms and subjects
-  Allows teachers to easily share work with parents
-  Provides clear visual feedback (color-coded messages)
-  Works on all devices with responsive design
-  Includes sample data for easy testing

## Notes

- The database is included with sample data - you can start using it immediately
- Database is preserved by default (no data loss on restart)
- Change `SECRET_KEY` in `app.py` before deploying to production
- Email features are optional - the app works without email configuration
- All file uploads are stored in `static/uploads/` directory

## License

Open source - feel free to use this for your own projects, classrooms, or learning purposes.
