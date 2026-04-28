# 🚀 Deploy TextileERP Free — Step by Step

## ✅ Option 1: Render.com (Easiest — Recommended)

### Step 1 — Push to GitHub
Unzip TextileERP_v2.zip, open terminal inside textile_erp folder:

    git init
    git add .
    git commit -m "deploy"
    git branch -M main
    git remote add origin https://github.com/YOUR_USERNAME/textile-erp.git
    git push -u origin main

### Step 2 — Deploy on Render
1. Visit https://render.com — sign up free (use GitHub)
2. New + → Web Service → connect your repo
3. Build Command:  pip install -r requirements.txt
4. Start Command:  gunicorn app:app
5. Instance: Free → Create Web Service
6. Wait ~3 min → your URL appears: https://textile-erp.onrender.com

Login: admin / admin123

---

## ✅ Option 2: PythonAnywhere (Persistent Storage)

1. https://pythonanywhere.com — free account
2. Files → upload zip → unzip
3. Web → New web app → Flask → Python 3.11
4. WSGI file: set path to your app folder
5. Bash console: pip install --user flask flask-sqlalchemy flask-login werkzeug reportlab pillow gunicorn
6. Reload → live at https://yourusername.pythonanywhere.com

---

## ✅ Option 3: Railway.app

1. https://railway.app — sign up with GitHub
2. New Project → Deploy from GitHub repo
3. Auto-detects Procfile → done in 2 min

---

Demo logins: admin/admin123  |  staff1/staff123  |  staff2/staff123
