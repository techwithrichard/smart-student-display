# Student Projects Display Platform

A fullstack web application built with Flask, HTML, and CSS that allows students to upload and showcase coding projects (HTML pages and Scratch links) in a classroom environment. The platform facilitates peer learning through project exhibitions, challenges, and leaderboards.

## Features

- **User Authentication**: Separate login/registration for students and teachers
- **Classroom Management**: Teachers can create classrooms with unique codes for students to join
- **Project Upload**: Students can upload HTML files or share Scratch project links
- **Project Gallery**: Creative display of all projects in a classroom with likes and views
- **Challenges**: Teachers can create coding challenges with point rewards
- **Leaderboard**: Track student points and rankings within each classroom
- **Responsive Design**: Modern, clean UI that works on all devices

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML5, CSS3
- **Authentication**: Flask-Login with password hashing

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

## Usage

### For Teachers

1. Register as a teacher
2. Create a classroom and share the classroom code with students
3. Create challenges to engage students
4. Monitor student projects and leaderboard

### For Students

1. Register as a student
2. Join a classroom using the code provided by your teacher
3. Upload HTML projects or share Scratch links
4. Submit projects to complete challenges
5. View and like peer projects
6. Track your position on the leaderboard

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

- **User**: Stores user accounts (students and teachers)
- **Classroom**: Represents a classroom created by a teacher
- **ClassroomStudent**: Junction table for student enrollments and points
- **Project**: Stores student projects (HTML or Scratch)
- **Challenge**: Coding challenges created by teachers
- **ChallengeSubmission**: Tracks student challenge submissions

## Security Notes

- Change the `SECRET_KEY` in `app.py` before deploying to production
- Consider using environment variables for sensitive configuration
- Implement additional security measures for production deployment

## License

This project is open source and available for educational purposes.
