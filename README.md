# LabelFlow

**LabelFlow** is a Django-based web application developed as a **team / university project**. The goal is to provide a platform for managing image-labeling workflows — from organizing projects and teams to annotating images with bounding boxes and polygons.

---

## Screenshots

| Dashboard | Workspaces |
|---|---|
| ![Dashboard](.github/im1.png) | ![Workspaces](.github/im2.png) |

| Image Upload | Annotation Canvas |
|---|---|
| ![Image Upload](.github/im3.png) | ![Annotation Canvas](.github/im4.png) |

---

## Project Context

| Field | Details |
|---|---|
| **Project type** | University / Team Project |
| **Backend** | Django 6 |
| **Frontend** | HTML, CSS, JavaScript |
| **Database** | SQLite (default) |
| **Version control** | Git & GitHub |
| **Collaboration model** | Feature-based development with pull requests |

---

## Features

- User registration & login
- User profiles
- Personal and organization workspaces
- Project and team management with role-based access (admin / annotator)
- Workspace invitations via email
- Image upload with drag-and-drop (JPG, PNG, WEBP, BMP, GIF)
- Bounding box and polygon annotation canvas
- YOLO export
- Activity log per project
- Dark mode

---

## Project Structure

```text
LabelFlow/
├── manage.py
├── requirements.txt
├── labelflow/                  # Django project configuration
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/               # Registration, login, profiles
│   ├── projects/               # Workspaces, projects, teams, invitations, activity
│   └── images/                 # Image upload, annotation, tags, export
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── templates/                  # HTML templates
│   ├── app/
│   ├── email/
│   └── registration/
├── media/                      # User-uploaded files (gitignored)
└── .github/                    # README screenshots
```

---

## Requirements

- Python 3.12+
- pip
- Git

**Check versions:**
```bash
python --version
pip --version
```

---

## Setup & Run

### 1. Clone the repository

```bash
git clone https://github.com/MartynasMatDev/LabelFlow.git
cd LabelFlow
```

### 2. Create and activate virtual environment

**Linux / macOS:**
```bash
python -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Create superuser *(optional)*

```bash
python manage.py createsuperuser
```

### 6. Start development server

```bash
python manage.py runserver
```

Open: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## Development Commands

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py test
```

---

## Branching Strategy

> **Direct pushes to `main` are not allowed.**

```text
feature/* → dev → main
bugfixes/* → dev → main
```

| Branch | Purpose |
|---|---|
| `main` | Stable, production-ready code |
| `dev` | Integration branch |
| `feature/*` | New features |
| `bugfixes/*` | Bug fixes |

For detailed contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

This project is created for educational purposes.
