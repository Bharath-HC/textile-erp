# 🏬 TextileERP — Full-Stack Showroom Management System

A professional, production-ready ERP system for textile retail showrooms (like Reliance Trends / Max Fashion), built with **Flask + SQLite + Bootstrap 5**.

---

## ✨ Features

| Module | Capabilities |
|---|---|
| 🔐 Auth | Role-based login (Admin / Staff), session handling |
| 📦 Products | Add/Edit/Delete, images, barcode, GST, low-stock alerts |
| 🧾 POS Billing | Camera barcode scanner, cart, GST calc, invoice PDF |
| 📊 Analytics | Revenue charts, top products, category breakdown |
| 👥 Employees | Add/Edit, roles, department, salary |
| 📅 Attendance | Staff self-mark + Admin bulk-mark, monthly report |

---

## 🚀 Quick Start (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python app.py

# 3. Open browser
http://localhost:5000
```

**Demo Credentials:**
- Admin: `admin` / `admin123`
- Staff: `staff1` / `staff123`

---

## 📁 Project Structure

```
textile_erp/
├── app.py                  # Main Flask app (models + routes)
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html           # Sidebar layout
│   ├── login.html
│   ├── dashboard.html      # KPIs + charts
│   ├── products.html       # Product grid
│   ├── product_form.html   # Add/Edit product
│   ├── billing.html        # POS system
│   ├── invoice.html        # Invoice view + PDF
│   ├── sales.html          # Sales history
│   ├── analytics.html      # Analytics charts
│   ├── employees.html      # Employee cards
│   ├── employee_form.html  # Add/Edit employee
│   ├── attendance_admin.html
│   ├── attendance_staff.html
│   ├── attendance_report.html
│   └── categories.html
└── static/
    ├── css/style.css       # Professional theme
    ├── js/main.js          # UI interactions
    └── uploads/            # Product images
```

---

## ☁️ Deploy on Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app`
   - **Environment:** Python 3.11
5. Click Deploy

---

## 🚂 Deploy on Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

Set start command: `gunicorn app:app`

---

## 🎨 Tech Stack

- **Backend:** Python 3.11 + Flask 3.0
- **Database:** SQLite + SQLAlchemy ORM
- **Frontend:** Bootstrap 5 + Chart.js + Font Awesome
- **Fonts:** Plus Jakarta Sans + Space Grotesk
- **PDF:** ReportLab
- **Auth:** Flask-Login + Werkzeug password hashing

---

## 👤 User Roles

| Role | Access |
|---|---|
| **Admin** | Full access — all modules, analytics, employee management |
| **Staff** | POS billing, products view, own attendance marking |
