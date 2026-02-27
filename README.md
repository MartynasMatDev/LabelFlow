# 🏷️ LabelFlow

**LabelFlow** is a Django-based web application developed as a **team / university project**. The goal of the project is to build a platform for managing projects, teams, and image-labeling workflows.

---

## 🎓 Project Context

| Field | Details |
|---|---|
| **Project type** | University / Team Project |
| **Backend** | Django |
| **Frontend** | HTML, CSS, JavaScript |
| **Database** | SQLite (default) |
| **Version control** | Git & GitHub |
| **Collaboration model** | Feature-based development with pull requests |

---

## 📁 Project Structure

```text
labelflow/
├── manage.py
├── requirements.txt            # Project dependencies
├── labelflow/                  # Django project configuration
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/               # Authentication, profiles
│   ├── projects/               # Projects & team management
│   └── images/                 # Image upload and listing
├── static/
│   ├── css/main.css
│   └── js/main.js
├── media/                      # User-uploaded files
└── templates/                  # HTML templates
```

---

## ✅ Requirements

- Python 3.12 (recommended)
- pip
- Git
- PyCharm (recommended for development)

**Check versions:**
```bash
python --version
pip --version
```

---

## 🚀 Setup & Run

### 1️⃣ Clone the repository

```bash
git clone https://github.com/your-username/labelflow.git
cd labelflow
```

### 2️⃣ Create and activate virtual environment

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

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Run migrations

```bash
python manage.py migrate
```

### 5️⃣ Create superuser *(optional)*

```bash
python manage.py createsuperuser
```

### 6️⃣ Start development server

```bash
python manage.py runserver
```

Open: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 🧠 PyCharm Setup

1. Open PyCharm
2. Click **Open** → select the `labelflow/` directory
3. Configure interpreter: **File → Settings → Python Interpreter** → Add Virtualenv → Python 3.12
4. Install dependencies: `pip install -r requirements.txt`
5. Create Django Run Configuration:
   - **Host:** `127.0.0.1`
   - **Port:** `8000`
   - **Environment variable:** `DJANGO_SETTINGS_MODULE=labelflow.settings`

---

## 🔐 Features

- User registration & login
- User profiles
- Project and team management
- Image upload & listing
- Role-based access (basic)

---

## 🧪 Development Commands

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py test
```

---

## 🌿 Branching Strategy

> ⚠️ **Direct pushes to `main` are not allowed.**

```text
feature/* → dev → main
```

| Branch | Purpose |
|---|---|
| `main` | Stable, production-ready code |
| `dev` | Integration branch |
| `feature/*` | Individual tasks or features |

For detailed contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 License

This project is created for educational purposes.

---

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before creating branches or pull requests.
