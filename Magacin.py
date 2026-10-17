from flask import Flask, render_template_string, request, redirect, url_for, session
import sqlite3
import os
from pypdf import PdfReader

app = Flask(__name__)
app.secret_key = 'tajni_kljuc_za_sigurnost_app_123'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DB_PATH = os.path.join(BASE_DIR, 'korisnici.db')
ALATI_DB_PATH = os.path.join(BASE_DIR, 'baza_magacin.db')

def get_user_db_connection():
    return sqlite3.connect(USER_DB_PATH)

def get_alati_db_connection():
    return sqlite3.connect(ALATI_DB_PATH)

def init_user_db():
    conn = get_user_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_approved INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO users (username, password, is_approved, is_admin) VALUES (?, ?, 1, 1)',
                       ('admin', 'admin123'))
    conn.commit()
    conn.close()

def init_alati_db():
    conn = get_alati_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ALATI (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            SIFRA TEXT,
            NAZIV TEXT NOT NULL,
            KOLICINA INTEGER DEFAULT 0,
            STATUS TEXT DEFAULT 'Dostupno',
            LADICA TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_user_db()
init_alati_db()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    pretraga = request.args.get('pretraga', '')
    alati = []
    greska = None

    try:
        con = get_alati_db_connection()
        cur = con.cursor()
        
        if pretraga:
            sql = "SELECT SIFRA, NAZIV, KOLICINA, STATUS, LADICA FROM ALATI WHERE UPPER(NAZIV) LIKE UPPER(?) OR UPPER(SIFRA) LIKE UPPER(?)"
            cur.execute(sql, (f'%{pretraga}%', f'%{pretraga}%'))
        else:
            sql = "SELECT SIFRA, NAZIV, KOLICINA, STATUS, LADICA FROM ALATI"
            cur.execute(sql)
            
        alati = cur.fetchall()
        con.close()
    except Exception as e:
        greska = f"Greška pri čitanju baze alata: {str(e)}"

    return render_template_string(HTML_INDEX, alati=alati, pretraga=pretraga, greska=greska, username=session.get('username'), is_admin=session.get('is_admin'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    poruka = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_user_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password, is_approved, is_admin FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            if user[3] == 1:
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['is_admin'] = user[4]
                return redirect(url_for('index'))
            else:
                poruka = "Vaš nalog čeka odobrenje administratora."
        else:
            poruka = "Pogrešno korisničko ime ili lozinka!"
            
    return render_template_string(HTML_LOGIN, poruka=poruka)

@app.route('/register', methods=['GET', 'POST'])
def register():
    poruka = None
    uspjeh = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_user_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password, is_approved, is_admin) VALUES (?, ?, 0, 0)', (username, password))
            conn.commit()
            uspjeh = "Nalog uspješno kreiran! Pričekajte odobrenje administratora."
        except sqlite3.IntegrityError:
            poruka = "Korisničko ime je već zauzeto!"
        conn.close()
        
    return render_template_string(HTML_REGISTER, poruka=poruka, uspjeh=uspjeh)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or session.get('is_admin') != 1:
        return "Pristup odbijen!", 403
    
    poruka = None
    if request.method == 'POST' and 'pdf_file' in request.files:
        file = request.files['pdf_file']
        if file and file.filename.endswith('.pdf'):
            pdf_path = os.path.join(BASE_DIR, 'temp.pdf')
            file.save(pdf_path)
            
            try:
                reader = PdfReader(pdf_path)
                conn = get_alati_db_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM ALATI')
                
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        lines = text.split('\n')
                        for line in lines:
                            parts = line.split()
                            if len(parts) >= 3:
                                sifra = parts[0]
                                kolicina = parts[-3] if len(parts) >= 5 else "1"
                                status = parts[-2] if len(parts) >= 5 else "Dostupno"
                                ladica = parts[-1] if len(parts) >= 5 else "Nepoznato"
                                naziv = " ".join(parts[1:-3]) if len(parts) >= 5 else " ".join(parts[1:-1])
                                
                                try:
                                    kol_num = int(kolicina)
                                except ValueError:
                                    kol_num = 1
                                    
                                cursor.execute('INSERT INTO ALATI (SIFRA, NAZIV, KOLICINA, STATUS, LADICA) VALUES (?, ?, ?, ?, ?)',
                                               (sifra, naziv, kol_num, status, ladica))
                                               
                conn.commit()
                conn.close()
                poruka = "PDF baza alata je uspješno učitana i obrađena!"
            except Exception as e:
                poruka = f"Greška pri čitanju PDF-a: {str(e)}"
        else:
            poruka = "Molimo izaberite ispravan .pdf fajl!"
    
    conn = get_user_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, is_approved FROM users WHERE is_admin = 0')
    users = cursor.fetchall()
    conn.close()
    
    return render_template_string(HTML_ADMIN, users=users, poruka=poruka)

@app.route('/admin/odobri/<int:user_id>')
def odobri(user_id):
    if session.get('is_admin') == 1:
        conn = get_user_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_approved = 1 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/blokiraj/<int:user_id>')
def blokiraj(user_id):
    if session.get('is_admin') == 1:
        conn = get_user_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_approved = 0 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
    return redirect(url_for('admin'))

HTML_HEAD = '''
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Magacin">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 15px; background: #f2f2f7; color: #1c1c1e; }
        .box { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); max-width: 350px; margin: 40px auto; }
        h2 { text-align: center; margin-bottom: 20px; }
        input[type="text"], input[type="password"], input[type="file"] { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #c7c7cc; border-radius: 8px; box-sizing: border-box; font-size: 16px; }
        button, input[type="submit"] { width: 100%; padding: 12px; background: #007aff; color: white; border: none; border-radius: 8px; font-weight: 600; font-size: 16px; cursor: pointer; margin-top: 10px; }
        .top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .btn-nav { font-size: 13px; padding: 6px 12px; background: #e5e5ea; text-decoration: none; color: #007aff; border-radius: 6px; font-weight: 500; }
        .card { background: white; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }
        .badge { background: #e5e5ea; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
        .badge-ladica { background: #ff9f0a; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
        .err { background: #ffe5e5; color: #ff3b30; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 14px; }
        .ok { background: #e5ffe5; color: #34c759; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 14px; }
    </style>
</head>
'''

HTML_LOGIN = '<doctype html><html>' + HTML_HEAD + '<body><div class="box"><h2>🔑 Prijava</h2>{% if poruka %}<div class="err">{{ poruka }}</div>{% endif %}<form method="POST"><input type="text" name="username" placeholder="Korisničko ime" required><input type="password" name="password" placeholder="Lozinka" required><button type="submit">Prijavi se</button></form><p style="text-align:center; font-size:14px; margin-top:15px;"><a href="/register" style="color:#007aff; text-decoration:none;">Registracija</a></p></div></body></html>'

HTML_REGISTER = '<doctype html><html>' + HTML_HEAD + '<body><div class="box"><h2>📝 Registracija</h2>{% if poruka %}<div class="err">{{ poruka }}</div>{% endif %}{% if uspjeh %}<div class="ok">{{ uspjeh }}</div>{% endif %}<form method="POST"><input type="text" name="username" placeholder="Korisničko ime" required><input type="password" name="password" placeholder="Lozinka" required><button type="submit" style="background:#34c759;">Registruj se</button></form><p style="text-align:center; font-size:14px; margin-top:15px;"><a href="/login" style="color:#007aff; text-decoration:none;">Nazad na prijavu</a></p></div></body></html>'

HTML_INDEX = '<doctype html><html>' + HTML_HEAD + '''<body>
<div class="top">
    <span>👤 <strong>{{ username }}</strong></span>
    <div>
        {% if is_admin == 1 %}<a href="/admin" class="btn-nav" style="background:#fff9c4; color:#f57f17;">Admin Panel</a>{% endif %}
        <a href="/logout" class="btn-nav">Odjava</a>
    </div>
</div>

<h2>🔧 Stanje Alata</h2>
{% if greska %}<div class="err">{{ greska }}</div>{% endif %}

<form method="GET"><input type="text" name="pretraga" style="width:100%; padding:12px; font-size:16px; border:1px solid #c7c7cc; border-radius:8px; box-sizing:border-box; margin-bottom:15px;" placeholder="Pretraži po nazivu ili šifri..." value="{{ pretraga }}"></form>

{% for alat in alati %}
<div class="card">
    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <h3 style="margin:0 0 8px 0; color:#000;">{{ alat[1] }}</h3>
        <span class="badge-ladica">🗄️ Ladica: {{ alat[4] }}</span>
    </div>
    <p style="margin:4px 0; color:#8e8e93; font-size:13px;">Šifra: <code>{{ alat[0] }}</code></p>
    <p style="margin:4px 0; color:#8e8e93;">Količina: <strong style="color:#000;">{{ alat[2] }}</strong> | Status: <span class="badge">{{ alat[3] }}</span></p>
</div>
{% else %}
<p style="text-align:center; color:#8e8e93;">Nema pronađenih alata.</p>
{% endfor %}
</body></html>'''

HTML_ADMIN = '<doctype html><html>' + HTML_HEAD + '''<body>
<a href="/" style="color:#007aff; text-decoration:none; display:inline-block; margin-bottom:15px;">← Nazad na magacin</a>
<h2>🛠️ Admin Panel</h2>

{% if poruka %}<div class="ok">{{ poruka }}</div>{% endif %}

<div class="card" style="border: 2px dashed #007aff; padding: 20px; text-align: center;">
    <h3 style="margin-top:0;">📤 Učitavanje PDF izvještaja alata</h3>
    <p style="font-size:13px; color:#8e8e93;">Izaberite PDF izvještaj iz vašeg programa:</p>
    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="pdf_file" accept=".pdf" required>
        <button type="submit" style="background:#34c759;">Učitaj PDF bazu</button>
    </form>
</div>

<h3 style="margin-top:25px;">👥 Odobrenje korisnika</h3>
{% for u in users %}
<div class="card" style="display:flex; justify-content:space-between; align-items:center;">
    <div>
        <strong>{{ u[1] }}</strong><br>
        <small style="color:#8e8e93;">Status: {% if u[2] == 1 %}<span style="color:#34c759;">Odobren</span>{% else %}<span style="color:#ff3b30;">Na čekanju</span>{% endif %}</small>
    </div>
    <div>
        {% if u[2] == 0 %}
        <a href="/admin/odobri/{{ u[0] }}" class="btn-nav" style="background:#34c759; color:white;">Odobri</a>
        {% else %}
        <a href="/admin/blokiraj/{{ u[0] }}" class="btn-nav" style="background:#ff3b30; color:white;">Blokiraj</a>
        {% endif %}
    </div>
</div>
{% else %}
<p style="color:#8e8e93;">Nema registrovanih radnika.</p>
{% endfor %}
</body></html>'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
