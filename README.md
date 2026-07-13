# DMRC Hospital Chatbot — PostgreSQL Version

## Quick Start (SQLite — for local development)

```bash
pip3 install -r requirements.txt
python3 app.py
```
Open: http://localhost:5000

---

## PostgreSQL Setup (for production / large data)

### Step 1 — Install PostgreSQL
**Mac:**
```bash
brew install postgresql
brew services start postgresql
```
**Ubuntu/Linux:**
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### Step 2 — Create database and user
```bash
psql postgres
```
Inside psql:
```sql
CREATE DATABASE dmrc_db;
CREATE USER dmrc_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE dmrc_db TO dmrc_user;
\q
```

### Step 3 — Set environment variable
**Mac/Linux:**
```bash
export DATABASE_URL=postgresql://dmrc_user:your_password@localhost:5432/dmrc_db
```
**Windows:**
```cmd
set DATABASE_URL=postgresql://dmrc_user:your_password@localhost:5432/dmrc_db
```

### Step 4 — Run the app
```bash
python3 app.py
```

---

## Demo Credentials
| Role     | ID        | Password |
|----------|-----------|----------|
| Employee | EMP001    | emp123   |
| Admin    | ADMIN001  | admin123 |

---

## Admin Panel Features

### File Uploads Tab
| Upload | What it does |
|--------|-------------|
| Hospital Excel | Main DMRC consolidated list — replaces all hospitals |
| Employee Excel | Add/update employee records |
| Additional Hospital Excel | Office order hospitals — added alongside main list |

### Key Points
- Upload the **main consolidated Excel** first for search/cashless/annual checkup to work
- Upload **additional Excel files** for hospitals added via office orders (e.g. HR/O&M/258/2026)
- Both sources are searched together when employee looks up a hospital
- Each result shows a badge: **Consolidated List** or **Office Order**
- Validity date is auto-extracted from whatever file is uploaded

---

## Excel Formats

### Hospital Excel (Main Consolidated List)
Auto-detects column names. Standard DMRC format works directly.

### Additional Hospital Excel (Office Orders)
Columns: `S.N, Hospital Name, Address, Rates, Contact Details`
Office order number and validity date are auto-detected from the file content.

### Employee Excel
Columns: `Employee_ID, Name, Password, Department, Status`

---

## Project Structure
```
dmrc_chatbot_pg/
├── app.py              # Main Flask app (SQLite + PostgreSQL)
├── requirements.txt
├── README.md
├── static/
│   └── dmrc-logo.png
├── templates/
│   ├── login.html
│   ├── employee.html
│   └── admin.html
└── uploads/
    └── pdfs/
```
