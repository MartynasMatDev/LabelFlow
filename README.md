# LabelFlow — Paleidimo gidas

## Struktūra

```
my_annotation_project/
├── manage.py
├── requirements.txt
├── my_annotation_project/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/          # Registracija, prisijungimas, profilis
│   ├── projects/          # Projektai, komandos valdymas
│   └── images/            # Paveikslėlių įkėlimas ir sąrašas
├── static/
│   ├── css/main.css
│   └── js/main.js
├── media/                 # Vartotojų įkelti failai (auto)
└── templates/
    ├── base.html
    ├── index.html
    ├── registration/
    │   ├── login.html
    │   └── register.html
    └── app/
        ├── app_base.html
        ├── dashboard.html
        ├── project_list.html
        ├── project_create.html
        ├── project_detail.html
        ├── image_list.html
        ├── image_upload.html
        ├── profile.html
        └── team_management.html
```

---

## 1. Reikalavimai

- **Python** 3.10 ar naujesnė versija
- **pip** paketų valdytojas

Patikrinkite:
```bash
python --version
pip --version
```

---