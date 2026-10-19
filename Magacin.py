from flask import Flask, render_template_string, request, redirect, url_for, session
import sqlite3
import os
from striprtf.striprtf import rtf_to_text

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
            BROJ_LADICE TEXT,
            SIFRA_ALATA TEXT,
            NAZIV_ALATA TEXT,
            GEOMETRIJA TEXT,
            KOLICINA INTEGER DEFAULT 0
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
    
    sifra_pretraga = request.args.get('sifra', '').strip()
    naziv_pretraga = request.args.get('naziv', '').strip()
    alati = []
    greska = None

    try:
        con = get_alati_db_connection()
        cur = con.cursor()
        
        sql = "SELECT BROJ_LADICE, SIFRA_ALATA, NAZIV_ALATA, GEOMETRIJA, KOLICINA FROM ALATI WHERE 1=1"
        params = []
        
        if sifra_pretraga:
            sql += " AND (UPPER(SIFRA_ALATA) LIKE UPPER(?) OR UPPER(BROJ_LADICE) LIKE UPPER(?))"
            params.extend([f'%{sifra_pretraga}%', f'%{sifra_pretraga}%'])
            
        if naziv_pretraga:
            sql += " AND (UPPER(NAZIV_ALATA) LIKE UPPER(?) OR UPPER(GEOMETRIJA) LIKE UPPER(?) OR UPPER(SIFRA_ALATA) LIKE UPPER(?))"
            params.extend([f'%{naziv_pretraga}%', f'%{naziv_pretraga}%', f'%{naziv_pretraga}%'])
            
        cur.execute(sql, params)
        alati = cur.fetchall()
        con.close()
    except Exception as e:
        greska = f"Greška pri čitanju baze alata: {str(e)}"

    return render_template_string(HTML_INDEX, alati=alati, sifra_pretraga=sifra_pretraga, naziv_pretraga=naziv_pretraga, greska=greska, username=session.get('username'), is_admin=session.get('is_admin'))

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
    if request.method == 'POST' and 'rtf_file' in request.files:
        file = request.files['rtf_file']
        if file and file.filename.endswith('.rtf'):
            rtf_path = os.path.join(BASE_DIR, 'temp.rtf')
            file.save(rtf_path)
            
            try:
                with open(rtf_path, 'r', encoding='utf-8', errors='ignore') as f:
                    rtf_sadrzaj = f.read()
                text = rtf_to_text(rtf_sadrzaj)

                conn = get_alati_db_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM ALATI')
                
                ukupno_ucitano = 0
                lines = text.split('\n')
                for line in lines:
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                        
                    line_lower = line_clean.lower()
                    if any(kw in line_lower for kw in ['sati', 'minuta', 'strana', 'ispis', 'stanje izlaznog', 'pk praezision', 'sarajevska', 'korisnik', 'datum', 'šifra alata', 'broj ladice']):
                        continue

                    parts = line_clean.split()
                    if len(parts) >= 3:
                        kolicina_str = parts[-1]
                        try:
                            kol_num = int(kolicina_str)
                        except ValueError:
                            continue 
                        
                        if len(parts) >= 4 and parts[0] == "SPM":
                            broj_ladice = f"{parts[0]} {parts[1]} {parts[2]}"
                            sredina = parts[3:-1]
                        else:
                            broj_ladice = parts[0]
                            sredina = parts[1:-1]
                        
                        sifra_alata = sredina
