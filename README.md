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

---

## License

This project is created for educational purposes.



## Upload images with API, directly from terminal

1)  Run the project in your main terminal:
python manage.py runserver

2) Open a new local terminal. We will use only this one from now on. Set it up with:
cd C:\Users\misei\PycharmProjects\LabelFlow
venv\Scripts\activate

3) Use your real username and password. Paste this:
$login = Invoke-WebRequest -Method POST -Uri "http://127.0.0.1:8000/app/images/api/token/" -ContentType "application/json" -Body '{"username": "REAL_USERNAME", "password": "REAL_PASSWORD"}' -UseBasicParsing; $token = ($login.Content | ConvertFrom-Json).token; Write-Host "Token:" $token

4) Get the project ID from the project page URL. For example:
http://127.0.0.1:8000/app/images/project/4/
                                         ↑
                                     projectId = 4
5) Change $token and $projectId to your own values, then paste all of this into the terminal:
Add-Type -AssemblyName System.Net.Http
$token = "975de635b239286364f08f"
$projectId = "69"
function Upload-Image($path) {
    $client = New-Object System.Net.Http.HttpClient
    $client.DefaultRequestHeaders.Add("Authorization", "Token $token")
    $content = New-Object System.Net.Http.MultipartFormDataContent
    $content.Add((New-Object System.Net.Http.StringContent($projectId)), "project")
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $file = New-Object System.Net.Http.ByteArrayContent(,$bytes)
    $file.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("image/png")
    $content.Add($file, "image_file", [System.IO.Path]::GetFileName($path))
    $client.PostAsync("http://127.0.0.1:8000/app/images/api/upload/", $content).Result.Content.ReadAsStringAsync().Result | ConvertFrom-Json
}

6) Upload an image from your PC with:
Upload-Image "C:\User\abc\photo.png"
Upload-Image "C:\User\abc\another_photo.png"


