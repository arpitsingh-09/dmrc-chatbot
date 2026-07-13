import os, hashlib, pandas as pd, re
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'dmrc_secret_key_2025'

# ── Paths ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # folder where app.py lives
DB_PATH  = os.path.join(BASE_DIR, 'dmrc.db')           # always same folder as app.py

# ── Database configuration ───────────────────────────────────────────
# Set DATABASE_URL env variable for PostgreSQL, e.g.:
#   export DATABASE_URL=postgresql://user:password@localhost:5432/dmrc_db
# If not set, falls back to SQLite stored permanently next to app.py
DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_POSTGRES = bool(DATABASE_URL)

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
PDF_FOLDER    = os.path.join(BASE_DIR, 'uploads', 'pdfs')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

# ── DB connection ────────────────────────────────────────────────────
def get_db():
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def db_execute(conn, sql, params=()):
    """Execute SQL — handles both Postgres (%s) and SQLite (?) placeholders."""
    if USE_POSTGRES:
        sql = sql.replace('?', '%s')
        sql = sql.replace('INSERT OR IGNORE', 'INSERT')
        sql = sql.replace('INSERT OR REPLACE', 'INSERT')
        # Convert ON CONFLICT for upsert
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    else:
        return conn.execute(sql, params)

def db_fetchall(conn, sql, params=()):
    if USE_POSTGRES:
        import psycopg2.extras
        sql = sql.replace('?', '%s')
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return cur.fetchall()
    else:
        return conn.execute(sql, params).fetchall()

def db_fetchone(conn, sql, params=()):
    if USE_POSTGRES:
        import psycopg2.extras
        sql = sql.replace('?', '%s')
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return cur.fetchone()
    else:
        return conn.execute(sql, params).fetchone()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ── Init DB ──────────────────────────────────────────────────────────
def init_db():
    conn = get_db()
    if USE_POSTGRES:
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            department TEXT,
            status TEXT DEFAULT 'Active'
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS hospitals (
            hospital_id SERIAL PRIMARY KEY,
            hospital_name TEXT NOT NULL,
            address TEXT,
            category TEXT,
            rates TEXT,
            contact_person TEXT,
            contact_number TEXT,
            email TEXT,
            annual_checkup TEXT DEFAULT 'NO',
            cashless TEXT DEFAULT 'NO',
            source TEXT DEFAULT 'main'
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS additional_hospitals (
            id SERIAL PRIMARY KEY,
            hospital_name TEXT NOT NULL,
            address TEXT,
            rates TEXT,
            contact_person TEXT,
            contact_number TEXT,
            email TEXT,
            validity_date TEXT,
            office_order TEXT,
            source_file TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS admin (
            admin_id TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        cur.execute("INSERT INTO admin VALUES (%s,%s) ON CONFLICT DO NOTHING",
                    ('ADMIN001', hash_password('admin123')))
        cur.execute("INSERT INTO employees VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    ('EMP001', 'Rajesh Kumar', hash_password('emp123'), 'Operations', 'Active'))
        cur.execute("INSERT INTO employees VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    ('EMP002', 'Priya Sharma', hash_password('emp123'), 'HR', 'Active'))
        conn.commit()
    else:
        import sqlite3
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            department TEXT,
            status TEXT DEFAULT 'Active'
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS hospitals (
            hospital_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_name TEXT NOT NULL,
            address TEXT,
            category TEXT,
            rates TEXT,
            contact_person TEXT,
            contact_number TEXT,
            email TEXT,
            annual_checkup TEXT DEFAULT 'NO',
            cashless TEXT DEFAULT 'NO',
            source TEXT DEFAULT 'main'
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS additional_hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_name TEXT NOT NULL,
            address TEXT,
            rates TEXT,
            contact_person TEXT,
            contact_number TEXT,
            email TEXT,
            validity_date TEXT,
            office_order TEXT,
            source_file TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS admin (
            admin_id TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        c.execute("INSERT OR IGNORE INTO admin VALUES (?, ?)", ('ADMIN001', hash_password('admin123')))
        c.execute("INSERT OR IGNORE INTO employees VALUES (?, ?, ?, ?, ?)",
                  ('EMP001', 'Rajesh Kumar', hash_password('emp123'), 'Operations', 'Active'))
        c.execute("INSERT OR IGNORE INTO employees VALUES (?, ?, ?, ?, ?)",
                  ('EMP002', 'Priya Sharma', hash_password('emp123'), 'HR', 'Active'))
        conn.commit()
    conn.close()

# ── Auth routes ──────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        user_id = data.get('id','').strip().upper()
        password = data.get('password','').strip()
        role = data.get('role','employee')
        hashed = hash_password(password)
        conn = get_db()
        if role == 'admin':
            row = db_fetchone(conn, "SELECT * FROM admin WHERE admin_id=? AND password=?", (user_id, hashed))
            if row:
                session['user_id'] = user_id
                session['role'] = 'admin'
                conn.close()
                return jsonify({'success': True, 'redirect': '/admin'})
        else:
            row = db_fetchone(conn, "SELECT * FROM employees WHERE employee_id=? AND password=? AND status='Active'", (user_id, hashed))
            if row:
                session['user_id'] = user_id
                session['role'] = 'employee'
                session['name'] = row['name']
                conn.close()
                return jsonify({'success': True, 'redirect': '/employee'})
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid credentials. Please try again.'})
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Static files ─────────────────────────────────────────────────────
@app.route('/static/<filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)

@app.route('/uploads/pdfs/<filename>')
def serve_pdf(filename):
    if session.get('role') not in ('employee', 'admin'):
        return redirect(url_for('login'))
    return send_from_directory(PDF_FOLDER, filename)

# ── Employee routes ──────────────────────────────────────────────────
@app.route('/employee')
def employee_dashboard():
    if session.get('role') != 'employee':
        return redirect(url_for('login'))
    return render_template('employee.html', name=session.get('name',''))

@app.route('/api/chat', methods=['POST'])
def chat():
    if session.get('role') != 'employee':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    action = data.get('action')
    conn = get_db()

    # Fetch validity date from settings
    valid_row = db_fetchone(conn, "SELECT value FROM settings WHERE key='validity_date'")
    validity_date = valid_row['value'] if valid_row else None

    if action == 'get_validity':
        conn.close()
        return jsonify({'validity_date': validity_date})

    if action == 'hospital_list':
        setting = db_fetchone(conn, "SELECT value FROM settings WHERE key='pdf_filename'")
        conn.close()
        if not setting:
            return jsonify({'type': 'error', 'message': 'No hospital list has been uploaded yet. Please contact the admin.'})

        # Auto-expiry check — parse validity date and compare with today
        pdf_status = 'valid'
        days_left = None
        expired = False
        if validity_date:
            try:
                from datetime import datetime
                # Parse DD.MM.YYYY or DD/MM/YYYY or DD-MM-YYYY
                for fmt in ('%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y'):
                    try:
                        expiry = datetime.strptime(validity_date, fmt)
                        break
                    except:
                        expiry = None
                if expiry:
                    today = datetime.today()
                    delta = (expiry - today).days
                    days_left = delta
                    if delta < 0:
                        expired = True
                        pdf_status = 'expired'
            except:
                pass

        return jsonify({
            'type': 'pdf',
            'filename': setting['value'],
            'validity_date': validity_date,
            'expired': expired,
            'days_left': days_left,
            'pdf_status': pdf_status
        })

    elif action == 'hospital_details':
        name = data.get('query','').strip()
        if not name:
            return jsonify({'type': 'ask', 'message': 'Please enter the hospital name you want to search for.'})

        # Search BOTH tables
        main_rows = db_fetchall(conn,
            "SELECT *, 'main' as src FROM hospitals WHERE hospital_name LIKE ?", (f'%{name}%',))
        add_rows = db_fetchall(conn,
            "SELECT *, 'additional' as src FROM additional_hospitals WHERE hospital_name LIKE ?", (f'%{name}%',))
        conn.close()

        if not main_rows and not add_rows:
            return jsonify({'type': 'not_found',
                'message': f'No hospital found matching "{name}". Try a different name or spelling.'})

        results = []
        for r in main_rows:
            results.append({
                'hospital_name': r['hospital_name'],
                'address': r['address'] or '',
                'category': r['category'] or '',
                'rates': r['rates'] or '',
                'contact_person': r['contact_person'] or '',
                'contact_number': r['contact_number'] or '',
                'email': r['email'] or '',
                'annual_checkup': r['annual_checkup'] or 'NO',
                'cashless': r['cashless'] or 'NO',
                'source': 'Consolidated List',
                'office_order': '',
                'validity_date_src': validity_date,
            })
        for r in add_rows:
            results.append({
                'hospital_name': r['hospital_name'],
                'address': r['address'] or '',
                'category': '',
                'rates': r['rates'] or '',
                'contact_person': r['contact_person'] or '',
                'contact_number': r['contact_number'] or '',
                'email': r['email'] or '',
                'annual_checkup': 'NO',
                'cashless': 'NO',
                'source': 'Office Order',
                'office_order': r['office_order'] or '',
                'validity_date_src': r['validity_date'] or '',
            })
        return jsonify({'type': 'hospital_details', 'data': results, 'validity_date': validity_date})

    elif action == 'annual_checkup':
        rows = db_fetchall(conn,
            "SELECT hospital_name,address,contact_person,contact_number,email FROM hospitals WHERE UPPER(annual_checkup)='YES'")
        conn.close()
        if not rows:
            return jsonify({'type': 'empty', 'message': 'No annual health check-up hospitals found.'})
        return jsonify({'type': 'hospital_list', 'data': [dict(r) for r in rows],
            'title': 'Annual Health Check-up Hospitals', 'validity_date': validity_date})

    elif action == 'cashless':
        rows = db_fetchall(conn,
            "SELECT hospital_name,address,contact_person,contact_number,email FROM hospitals WHERE UPPER(cashless)='YES'")
        conn.close()
        if not rows:
            return jsonify({'type': 'empty', 'message': 'No cashless hospitals found.'})
        return jsonify({'type': 'hospital_list', 'data': [dict(r) for r in rows],
            'title': 'Cashless Hospitals', 'validity_date': validity_date})

    conn.close()
    return jsonify({'type': 'error', 'message': 'Unknown action.'})

# ── Admin routes ─────────────────────────────────────────────────────
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin.html')

# ── Shared Excel parsing helpers ─────────────────────────────────────
def extract_validity_from_text(text):
    patterns = [
        r'upto\s+(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'up\s+to\s+(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'valid\s+(?:till|upto|up\s*to|as\s+on|until)\s+(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'(?:till|upto?|until)\s+(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'validity\s*[:\-]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'approved\s+up\s+to\s+(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None

def clean_val(v):
    s = str(v).strip().replace('\n', ', ') if v is not None else ''
    return '' if s.lower() in ('nan','none','') else s

# ── Upload: Main Consolidated Hospital Excel ─────────────────────────
@app.route('/api/admin/upload_hospital_excel', methods=['POST'])
def upload_hospital_excel():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided.'})
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx','.xls')):
        return jsonify({'success': False, 'message': 'Please upload a valid Excel file (.xlsx or .xls).'})
    try:
        raw = pd.read_excel(file, header=None)
        validity_date = None

        # Extract validity date from entire file
        for i in range(len(raw)):
            row_text = ' '.join(str(v) for v in raw.iloc[i] if pd.notna(v)).replace('\n',' ')
            vd = extract_validity_from_text(row_text)
            if vd:
                validity_date = vd
                break

        def get_by_idx(row_vals, idx, default=''):
            if idx is not None and 0 <= idx < len(row_vals):
                return clean_val(row_vals[idx]) or default
            return default

        def is_header_row(row_vals):
            c0 = str(row_vals[0]).strip().lower() if row_vals else ''
            c1 = str(row_vals[1]).strip().lower() if len(row_vals) > 1 else ''
            sr_ok = any(k in c0 for k in ['sr.n','sr.no','s.no','sno'])
            name_ok = any(k in c1 for k in ['hospital','clinic','labs','lab_location','location'])
            return sr_ok and name_ok

        def build_col_map(row_vals):
            cmap = {'hospital_name':1,'address':3,'category':6,'rates':7,'contact':10}
            for idx, cell in enumerate(row_vals):
                if idx == 0: continue
                n = str(cell).strip().lower()
                if any(k in n for k in ['hospital','clinic','labs','lab_location','location']) and 'hospital_name' not in cmap:
                    cmap['hospital_name'] = idx
                elif 'address' in n: cmap['address'] = idx
                elif 'category' in n or 'speciality' in n: cmap['category'] = idx
                elif 'rate' in n or 'tariff' in n: cmap['rates'] = idx
                elif 'contact' in n or 'phone' in n or 'mobile' in n: cmap['contact'] = idx
                elif 'email' in n or 'e-mail' in n: cmap['email'] = idx
                elif 'annual' in n or 'checkup' in n: cmap['annual_checkup'] = idx
                elif 'cashless' in n: cmap['cashless'] = idx
            return cmap

        def section_flags(row_idx):
            is_annual = False
            is_cashless = False
            for k in range(max(0, row_idx-8), row_idx):
                above = ' '.join(clean_val(v).lower() for v in raw.iloc[k] if pd.notna(v))
                if 'annual' in above and ('check' in above or 'health' in above): is_annual = True
                if 'cashless' in above and 'treatment' in above: is_cashless = True
            return is_annual, is_cashless

        section_headers = []
        for i, row in raw.iterrows():
            row_vals = [v for v in row]
            if is_header_row(row_vals):
                cmap = build_col_map(row_vals)
                section_headers.append((i, cmap))

        if not section_headers:
            return jsonify({'success': False, 'message': 'Could not find hospital table header in this Excel file.'})

        hospitals_out = []
        seen = set()

        for sec_idx, (hdr_row, cmap) in enumerate(section_headers):
            is_annual, is_cashless = section_flags(hdr_row)
            next_hdr = section_headers[sec_idx+1][0] if sec_idx+1 < len(section_headers) else len(raw)

            for i in range(hdr_row+1, next_hdr):
                row_vals = list(raw.iloc[i])
                try: int(float(str(row_vals[0]).strip()))
                except: continue

                name = get_by_idx(row_vals, cmap.get('hospital_name'))
                if not name or len(name) < 3: continue
                if name.lower().strip() in ['hospital /labs/ clinics','name of hospital /labs/ clinics','sr.no','sr.n.']: continue

                address  = get_by_idx(row_vals, cmap.get('address'))[:300]
                category = get_by_idx(row_vals, cmap.get('category'))[:100]
                rates    = get_by_idx(row_vals, cmap.get('rates'))[:300]
                contact_raw = get_by_idx(row_vals, cmap.get('contact'))
                phones   = re.findall(r'\d{10}', contact_raw)
                emails   = re.findall(r'[\w.\-]+@[\w.\-]+\.\w+', contact_raw)
                cp_parts = re.split(r'\s*\d{10}', contact_raw)
                contact_person = cp_parts[0].strip().rstrip(',')[:100] if cp_parts else ''
                contact_number = ', '.join(phones[:2])
                email = get_by_idx(row_vals, cmap.get('email')) or ', '.join(emails[:2])

                annual_val = get_by_idx(row_vals, cmap.get('annual_checkup'),'')
                cashless_val = get_by_idx(row_vals, cmap.get('cashless'),'')
                annual   = 'YES' if is_annual   or annual_val.upper().startswith('Y')   else 'NO'
                cashless = 'YES' if is_cashless or cashless_val.upper().startswith('Y') else 'NO'

                key = (name.lower(), address.lower()[:40])
                if key in seen: continue
                seen.add(key)

                hospitals_out.append((name[:200], address, category, rates,
                    contact_person, contact_number[:100], email[:100], annual, cashless, 'main'))

        if not hospitals_out:
            return jsonify({'success': False, 'message': 'No hospital records found in the file.'})

        conn = get_db()
        conn.execute("DELETE FROM hospitals") if not USE_POSTGRES else conn.cursor().execute("DELETE FROM hospitals")
        if USE_POSTGRES:
            cur = conn.cursor()
            for h in hospitals_out:
                cur.execute("""INSERT INTO hospitals
                    (hospital_name,address,category,rates,contact_person,contact_number,email,annual_checkup,cashless,source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", h)
            if validity_date:
                cur.execute("INSERT INTO settings(key,value) VALUES('validity_date',%s) ON CONFLICT(key) DO UPDATE SET value=%s",
                    (validity_date, validity_date))
        else:
            for h in hospitals_out:
                conn.execute("""INSERT INTO hospitals
                    (hospital_name,address,category,rates,contact_person,contact_number,email,annual_checkup,cashless,source)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""", h)
            if validity_date:
                conn.execute("INSERT OR REPLACE INTO settings VALUES ('validity_date',?)", (validity_date,))
        conn.commit()
        conn.close()

        msg = f'Consolidated hospital list updated. {len(hospitals_out)} hospitals imported.'
        if validity_date: msg += f' Valid upto {validity_date}.'
        return jsonify({'success': True, 'message': msg, 'validity_date': validity_date})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# ── Upload: Additional Hospitals (Office Orders) ──────────────────────
@app.route('/api/admin/upload_additional_excel', methods=['POST'])
def upload_additional_excel():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided.'})
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx','.xls')):
        return jsonify({'success': False, 'message': 'Please upload a valid Excel file (.xlsx or .xls).'})
    try:
        raw = pd.read_excel(file, header=None)
        source_file = secure_filename(file.filename)

        # Extract validity date and office order number from file
        validity_date = None
        office_order = ''
        for i in range(min(15, len(raw))):
            row_text = ' '.join(str(v) for v in raw.iloc[i] if pd.notna(v)).replace('\n',' ')
            if not validity_date:
                validity_date = extract_validity_from_text(row_text)
            # Look for office order number
            m = re.search(r'(?:office\s+order|order\s+no|no\.?)\s*[:\-]?\s*([\w/\-]+/\d{4})', row_text, re.IGNORECASE)
            if m and not office_order:
                office_order = m.group(1)

        # Find header row — look for S.N + Hospital Name
        header_idx = None
        col_map = {}
        HOSP_KEYS = ['hospital','clinic','labs','name']
        for i, row in raw.iterrows():
            row_vals = [v for v in row]
            row_text = ' '.join(str(v).lower() for v in row_vals if pd.notna(v))
            has_sn = any(k in row_text for k in ['s.n','sr.n','sno','sl.'])
            has_hosp = any(k in row_text for k in HOSP_KEYS)
            if has_sn and has_hosp:
                header_idx = i
                for idx, cell in enumerate(row_vals):
                    n = str(cell).strip().lower() if pd.notna(cell) else ''
                    if any(k in n for k in ['hospital','clinic','name']) and 'name' not in col_map:
                        col_map['name'] = idx
                    elif 'address' in n: col_map['address'] = idx
                    elif 'rate' in n or 'tariff' in n: col_map['rates'] = idx
                    elif 'contact' in n or 'phone' in n or 'mobile' in n: col_map['contact'] = idx
                    elif 'email' in n or 'e-mail' in n: col_map['email'] = idx
                break

        # Fallback positional mapping (S.N=0, Name=1, Address=2, Rates=3, Contact=4)
        if header_idx is None or 'name' not in col_map:
            for i, row in raw.iterrows():
                row_vals = [v for v in row]
                try:
                    int(float(str(row_vals[0]).strip()))
                    header_idx = i - 1
                    col_map = {'name':1, 'address':2, 'rates':3, 'contact':4}
                    break
                except: continue

        if header_idx is None:
            return jsonify({'success': False, 'message': 'Could not find hospital table in this file.'})

        hospitals_out = []
        seen = set()

        for i in range(header_idx+1, len(raw)):
            row_vals = list(raw.iloc[i])
            try: int(float(str(row_vals[0]).strip()))
            except: continue

            def gv(key, default=''):
                idx = col_map.get(key)
                if idx is not None and idx < len(row_vals):
                    return clean_val(row_vals[idx]) or default
                return default

            name = gv('name')
            if not name or len(name) < 3: continue

            address     = gv('address')[:300]
            rates       = gv('rates')[:300]
            contact_raw = gv('contact')
            phones  = re.findall(r'\d{10}', contact_raw)
            emails  = re.findall(r'[\w.\-]+@[\w.\-]+\.\w+', contact_raw)
            cp_parts = re.split(r'\s*\d{10}', contact_raw)
            contact_person = cp_parts[0].strip().rstrip(',')[:100] if cp_parts else ''
            contact_number = ', '.join(phones[:2])
            email = gv('email') or ', '.join(emails[:2])

            key = name.lower()
            if key in seen: continue
            seen.add(key)

            hospitals_out.append((name[:200], address, rates[:300],
                contact_person, contact_number[:100], email[:100],
                validity_date or '', office_order, source_file))

        if not hospitals_out:
            return jsonify({'success': False, 'message': 'No hospital records found in this file.'})

        conn = get_db()
        if USE_POSTGRES:
            cur = conn.cursor()
            # Remove old records from same source file
            cur.execute("DELETE FROM additional_hospitals WHERE source_file=%s", (source_file,))
            for h in hospitals_out:
                cur.execute("""INSERT INTO additional_hospitals
                    (hospital_name,address,rates,contact_person,contact_number,email,validity_date,office_order,source_file)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", h)
        else:
            conn.execute("DELETE FROM additional_hospitals WHERE source_file=?", (source_file,))
            for h in hospitals_out:
                conn.execute("""INSERT INTO additional_hospitals
                    (hospital_name,address,rates,contact_person,contact_number,email,validity_date,office_order,source_file)
                    VALUES (?,?,?,?,?,?,?,?,?)""", h)
        conn.commit()
        conn.close()

        msg = f'Additional hospitals added. {len(hospitals_out)} hospitals imported.'
        if office_order: msg += f' Office Order: {office_order}.'
        if validity_date: msg += f' Valid upto {validity_date}.'
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# ── Upload: Employee Excel ───────────────────────────────────────────
@app.route('/api/admin/upload_employee_excel', methods=['POST'])
def upload_employee_excel():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided.'})
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx','.xls')):
        return jsonify({'success': False, 'message': 'Please upload a valid Excel file.'})
    try:
        df = pd.read_excel(file)
        df.columns = [c.strip().lower().replace(' ','_') for c in df.columns]
        df = df.fillna('')
        conn = get_db()
        updated = inserted = 0
        for _, row in df.iterrows():
            emp_id = str(row.get('employee_id','')).strip().upper()
            if not emp_id: continue
            hashed = hash_password(str(row.get('password','')))
            existing = db_fetchone(conn, "SELECT 1 FROM employees WHERE employee_id=?", (emp_id,))
            if existing:
                if USE_POSTGRES:
                    conn.cursor().execute("UPDATE employees SET name=%s,password=%s,department=%s,status=%s WHERE employee_id=%s",
                        (str(row.get('name','')), hashed, str(row.get('department','')), str(row.get('status','Active')), emp_id))
                else:
                    conn.execute("UPDATE employees SET name=?,password=?,department=?,status=? WHERE employee_id=?",
                        (str(row.get('name','')), hashed, str(row.get('department','')), str(row.get('status','Active')), emp_id))
                updated += 1
            else:
                if USE_POSTGRES:
                    conn.cursor().execute("INSERT INTO employees VALUES (%s,%s,%s,%s,%s)",
                        (emp_id, str(row.get('name','')), hashed, str(row.get('department','')), str(row.get('status','Active'))))
                else:
                    conn.execute("INSERT INTO employees VALUES (?,?,?,?,?)",
                        (emp_id, str(row.get('name','')), hashed, str(row.get('department','')), str(row.get('status','Active'))))
                inserted += 1
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'Employees updated. {inserted} added, {updated} updated.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# ── Admin: Employee management ───────────────────────────────────────
@app.route('/api/admin/add_employee', methods=['POST'])
def add_employee():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json()
    emp_id = data.get('employee_id','').strip().upper()
    name   = data.get('name','').strip()
    password = data.get('password','').strip()
    department = data.get('department','').strip()
    if not emp_id or not name or not password:
        return jsonify({'success': False, 'message': 'Employee ID, name and password are required.'})
    conn = get_db()
    existing = db_fetchone(conn, "SELECT 1 FROM employees WHERE employee_id=?", (emp_id,))
    if existing:
        conn.close()
        return jsonify({'success': False, 'message': f'Employee {emp_id} already exists.'})
    if USE_POSTGRES:
        conn.cursor().execute("INSERT INTO employees VALUES (%s,%s,%s,%s,%s)",
            (emp_id, name, hash_password(password), department, 'Active'))
    else:
        conn.execute("INSERT INTO employees VALUES (?,?,?,?,?)",
            (emp_id, name, hash_password(password), department, 'Active'))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': f'Employee {name} ({emp_id}) added.'})

@app.route('/api/admin/remove_employee', methods=['POST'])
def remove_employee():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json()
    emp_id = data.get('employee_id','').strip().upper()
    conn = get_db()
    row = db_fetchone(conn, "SELECT name FROM employees WHERE employee_id=?", (emp_id,))
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': f'Employee {emp_id} not found.'})
    if USE_POSTGRES:
        conn.cursor().execute("DELETE FROM employees WHERE employee_id=%s", (emp_id,))
    else:
        conn.execute("DELETE FROM employees WHERE employee_id=?", (emp_id,))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': f'Employee {row["name"]} removed.'})

@app.route('/api/admin/reset_password', methods=['POST'])
def reset_password():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json()
    emp_id   = data.get('employee_id','').strip().upper()
    new_pass = data.get('new_password','').strip()
    conn = get_db()
    row = db_fetchone(conn, "SELECT name FROM employees WHERE employee_id=?", (emp_id,))
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': f'Employee {emp_id} not found.'})
    if USE_POSTGRES:
        conn.cursor().execute("UPDATE employees SET password=%s WHERE employee_id=%s", (hash_password(new_pass), emp_id))
    else:
        conn.execute("UPDATE employees SET password=? WHERE employee_id=?", (hash_password(new_pass), emp_id))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': f'Password reset for {row["name"]}.'})

@app.route('/api/admin/employees', methods=['GET'])
def list_employees():
    if session.get('role') != 'admin':
        return jsonify({'success': False}), 401
    conn = get_db()
    rows = db_fetchall(conn, "SELECT employee_id,name,department,status FROM employees ORDER BY employee_id")
    conn.close()
    return jsonify({'success': True, 'data': [dict(r) for r in rows]})

@app.route('/api/admin/set_validity_date', methods=['POST'])
def set_validity_date():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json()
    validity_date = data.get('validity_date', '').strip()
    if not validity_date:
        return jsonify({'success': False, 'message': 'Please provide a validity date.'})
    # Validate format DD.MM.YYYY
    import re as _re
    if not _re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', validity_date):
        return jsonify({'success': False, 'message': 'Invalid date format. Use DD.MM.YYYY.'})
    conn = get_db()
    if USE_POSTGRES:
        conn.cursor().execute(
            "INSERT INTO settings(key,value) VALUES('validity_date',%s) ON CONFLICT(key) DO UPDATE SET value=%s",
            (validity_date, validity_date))
    else:
        conn.execute("INSERT OR REPLACE INTO settings VALUES ('validity_date',?)", (validity_date,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f'Validity date set to {validity_date}.'})


@app.route('/api/admin/upload_pdf', methods=['POST'])
def upload_pdf():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided.'})
    file = request.files['file']
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'message': 'Please upload a PDF file.'})

    # Check if current PDF is still valid — block overwrite until expired
    conn = get_db()
    valid_row = db_fetchone(conn, "SELECT value FROM settings WHERE key='validity_date'")
    pdf_row   = db_fetchone(conn, "SELECT value FROM settings WHERE key='pdf_filename'")
    conn.close()

    if pdf_row and valid_row:
        try:
            from datetime import datetime
            for fmt in ('%d.%m.%Y','%d/%m/%Y','%d-%m-%Y'):
                try:
                    expiry = datetime.strptime(valid_row['value'], fmt); break
                except: expiry = None
            if expiry and datetime.today() < expiry:
                days_left = (expiry - datetime.today()).days
                return jsonify({'success': False,
                    'message': f'Current PDF is still valid upto {valid_row["value"]} ({days_left} days remaining). You can only replace it after the validity expires.',
                    'blocked': True, 'days_left': days_left})
        except: pass

    filename = 'hospital_list.pdf'
    filepath = os.path.join(PDF_FOLDER, filename)
    file.save(filepath)
    conn = get_db()
    if USE_POSTGRES:
        conn.cursor().execute("INSERT INTO settings(key,value) VALUES('pdf_filename',%s) ON CONFLICT(key) DO UPDATE SET value=%s", (filename, filename))
    else:
        conn.execute("INSERT OR REPLACE INTO settings VALUES ('pdf_filename',?)", (filename,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Hospital list PDF uploaded. Employees can view it until the validity date expires.'})


@app.route('/api/admin/status', methods=['GET'])
def admin_status():
    """Returns current status of all uploaded files for admin dashboard."""
    if session.get('role') != 'admin':
        return jsonify({'success': False}), 401
    conn = get_db()
    settings = {}
    rows = db_fetchall(conn, "SELECT key, value FROM settings")
    for r in rows:
        settings[r['key']] = r['value']

    hosp_count = db_fetchone(conn, "SELECT COUNT(*) as c FROM hospitals")
    add_count  = db_fetchone(conn, "SELECT COUNT(*) as c FROM additional_hospitals")
    add_files  = db_fetchall(conn, "SELECT DISTINCT source_file, office_order, validity_date FROM additional_hospitals")
    emp_count  = db_fetchone(conn, "SELECT COUNT(*) as c FROM employees")
    conn.close()

    # Calculate PDF expiry
    validity_date = settings.get('validity_date')
    pdf_filename  = settings.get('pdf_filename')
    days_left = None
    expired = False
    if validity_date:
        try:
            from datetime import datetime
            for fmt in ('%d.%m.%Y','%d/%m/%Y','%d-%m-%Y'):
                try: expiry = datetime.strptime(validity_date, fmt); break
                except: expiry = None
            if expiry:
                delta = (expiry - datetime.today()).days
                days_left = delta
                expired = delta < 0
        except: pass

    return jsonify({
        'success': True,
        'hospital_excel': {
            'uploaded': hosp_count['c'] > 0,
            'count': hosp_count['c'],
            'validity_date': validity_date,
            'days_left': days_left,
            'expired': expired,
        },
        'hospital_pdf': {
            'uploaded': bool(pdf_filename),
            'filename': pdf_filename,
            'validity_date': validity_date,
            'days_left': days_left,
            'expired': expired,
        },
        'additional': {
            'total': add_count['c'],
            'files': [dict(f) for f in add_files],
        },
        'employees': {
            'count': emp_count['c'],
        }
    })


@app.route('/api/admin/remove_hospital_excel', methods=['POST'])
def remove_hospital_excel():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    conn = get_db()
    if USE_POSTGRES:
        conn.cursor().execute("DELETE FROM hospitals")
        conn.cursor().execute("DELETE FROM settings WHERE key IN ('validity_date')")
    else:
        conn.execute("DELETE FROM hospitals")
        conn.execute("DELETE FROM settings WHERE key IN ('validity_date')")
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'All hospital records removed from database.'})


@app.route('/api/admin/remove_pdf', methods=['POST'])
def remove_pdf():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    # Block removal if PDF is still valid
    conn = get_db()
    valid_row = db_fetchone(conn, "SELECT value FROM settings WHERE key='validity_date'")
    conn.close()
    if valid_row:
        try:
            from datetime import datetime
            for fmt in ('%d.%m.%Y','%d/%m/%Y','%d-%m-%Y'):
                try: expiry = datetime.strptime(valid_row['value'], fmt); break
                except: expiry = None
            if expiry and datetime.today() < expiry:
                days_left = (expiry - datetime.today()).days
                return jsonify({'success': False,
                    'message': f'PDF is still valid upto {valid_row["value"]} ({days_left} days left). Cannot remove an active list.',
                    'blocked': True})
        except: pass

    filepath = os.path.join(PDF_FOLDER, 'hospital_list.pdf')
    if os.path.exists(filepath):
        os.remove(filepath)
    conn = get_db()
    if USE_POSTGRES:
        conn.cursor().execute("DELETE FROM settings WHERE key='pdf_filename'")
    else:
        conn.execute("DELETE FROM settings WHERE key='pdf_filename'")
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Hospital list PDF removed.'})


@app.route('/api/admin/remove_employee_excel', methods=['POST'])
def remove_employee_excel():
    """Remove all non-admin employees (keeps admin account)."""
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    conn = get_db()
    if USE_POSTGRES:
        conn.cursor().execute("DELETE FROM employees")
    else:
        conn.execute("DELETE FROM employees")
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'All employee records removed.'})


@app.route('/api/admin/change_id', methods=['POST'])
def change_admin_id():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json()
    current_pass = data.get('current_password', '').strip()
    new_id = data.get('new_id', '').strip().upper()
    if not current_pass or not new_id:
        return jsonify({'success': False, 'message': 'Current password and new ID are required.'})
    conn = get_db()
    current_id = session.get('user_id')
    row = db_fetchone(conn, "SELECT * FROM admin WHERE admin_id=? AND password=?",
                      (current_id, hash_password(current_pass)))
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': 'Current password is incorrect.'})
    # Check new ID not already taken
    existing = db_fetchone(conn, "SELECT 1 FROM admin WHERE admin_id=?", (new_id,))
    if existing:
        conn.close()
        return jsonify({'success': False, 'message': f'Admin ID {new_id} already exists.'})
    if USE_POSTGRES:
        conn.cursor().execute("UPDATE admin SET admin_id=%s WHERE admin_id=%s", (new_id, current_id))
    else:
        conn.execute("UPDATE admin SET admin_id=? WHERE admin_id=?", (new_id, current_id))
    conn.commit()
    conn.close()
    session.clear()
    return jsonify({'success': True, 'message': f'Admin ID updated to {new_id}. Please log in again.'})


@app.route('/api/admin/change_password', methods=['POST'])
def change_admin_password():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json()
    current_pass = data.get('current_password', '').strip()
    new_pass = data.get('new_password', '').strip()
    if not current_pass or not new_pass:
        return jsonify({'success': False, 'message': 'Both fields are required.'})
    if len(new_pass) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters.'})
    conn = get_db()
    current_id = session.get('user_id')
    row = db_fetchone(conn, "SELECT * FROM admin WHERE admin_id=? AND password=?",
                      (current_id, hash_password(current_pass)))
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': 'Current password is incorrect.'})
    if USE_POSTGRES:
        conn.cursor().execute("UPDATE admin SET password=%s WHERE admin_id=%s",
                              (hash_password(new_pass), current_id))
    else:
        conn.execute("UPDATE admin SET password=? WHERE admin_id=?",
                     (hash_password(new_pass), current_id))
    conn.commit()
    conn.close()
    session.clear()
    return jsonify({'success': True, 'message': 'Password updated successfully. Please log in again.'})



def list_additional_hospitals():
    if session.get('role') != 'admin':
        return jsonify({'success': False}), 401
    conn = get_db()
    rows = db_fetchall(conn, "SELECT * FROM additional_hospitals ORDER BY id")
    conn.close()
    return jsonify({'success': True, 'data': [dict(r) for r in rows]})

@app.route('/api/admin/delete_additional', methods=['POST'])
def delete_additional():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json()
    source_file = data.get('source_file','')
    conn = get_db()
    if USE_POSTGRES:
        conn.cursor().execute("DELETE FROM additional_hospitals WHERE source_file=%s", (source_file,))
    else:
        conn.execute("DELETE FROM additional_hospitals WHERE source_file=?", (source_file,))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'message': f'Removed hospitals from {source_file}.'})

if __name__ == '__main__':
    os.makedirs(PDF_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static'), exist_ok=True)
    init_db()
    print(f"Database: {DB_PATH}")
    print(f"Uploads:  {UPLOAD_FOLDER}")
    app.run(debug=True, port=5000)
