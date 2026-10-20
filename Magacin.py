import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'super_tajni_kljuc_magacin_2026'

# Dohvaćanje URL-a baze iz Render Environment varijable
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL nije postavljen u Environment Variables na Renderu!")
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Stvara tablice u PostgreSQL bazi ako već ne postoje."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Tablica za korisnike
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            approved BOOLEAN DEFAULT FALSE,
            is_admin BOOLEAN DEFAULT FALSE
        );
    ''')
    
    # Tablica za skladišne podatke
    cur.execute('''
        CREATE TABLE IF NOT EXISTS magacin_data (
            id INT PRIMARY KEY DEFAULT 1,
            filename VARCHAR(255),
            headers TEXT,
            rows TEXT
        );
    ''')

    # Provjeri postoji li glavni admin korisnik (mirzad)
    cur.execute("SELECT * FROM users WHERE username = 'mirzad';")
    if not cur.fetchone():
        cur.execute('''
            INSERT INTO users (username, password, approved, is_admin)
            VALUES ('mirzad', 'mojalozinka123', TRUE, TRUE);
        ''')

    conn.commit()
    cur.close()
    conn.close()

# Inicijalizacija baze pri pokretanju
try:
    init_db()
except Exception as e:
    print(f"Greška pri inicijalizaciji baze: {e}")

@app.route('/')
def home():
    if session.get('logged_in'):
        return redirect(url_for('admin_panel'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM users WHERE username = %s;", (username,))
            user = cur.fetchone()
            cur.close()
            conn.close()

            if user and user['password'] == password:
                if not user['approved']:
                    error = "Vaš račun još nije odobren od strane administratora!"
                else:
                    session['logged_in'] = True
                    session['username'] = username
                    session['is_admin'] = user['is_admin']
                    return redirect(url_for('admin_panel'))
            else:
                error = "Pogrešno korisničko ime ili lozinka!"
        except Exception as e:
            error = f"Greška s bazom podataka: {e}"

    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    success = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        if not username or not password:
            error = "Molimo unesite sve podatke!"
        else:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
                if cur.fetchone():
                    error = "Korisničko ime je već zauzeto!"
                else:
                    cur.execute(
                        "INSERT INTO users (username, password, approved, is_admin) VALUES (%s, %s, FALSE, FALSE);",
                        (username, password)
                    )
                    conn.commit()
                    success = "Registracija uspješna! Vaš račun čeka odobrenje administratora."
                cur.close()
                conn.close()
            except Exception as e:
                error = f"Greška s bazom: {e}"

    return render_template('register.html', error=error, success=success)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin_panel():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('admin.html', is_admin=session.get('is_admin', False), current_user=session.get('username'))

@app.route('/api/data', methods=['GET'])
def get_data():
    if not session.get('logged_in'):
        return jsonify({'error': 'Neovlašten pristup'}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT filename, headers, rows FROM magacin_data WHERE id = 1;")
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            return jsonify({
                "filename": row['filename'],
                "headers": json.loads(row['headers']),
                "rows": json.loads(row['rows'])
            })
        else:
            return jsonify({
                "filename": "",
                "headers": ["Ladica", "Šifra alata", "Šifra materijala", "Naziv alata", "Količina"],
                "rows": []
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data', methods=['POST'])
def save_data():
    if not session.get('logged_in'):
        return jsonify({'error': 'Neovlašten pristup'}), 403

    req_data = request.get_json(silent=True) or {}
    filename = req_data.get('filename', 'Dokument')
    headers_str = json.dumps(req_data.get('headers', []))
    rows_str = json.dumps(req_data.get('rows', []))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO magacin_data (id, filename, headers, rows)
            VALUES (1, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE 
            SET filename = EXCLUDED.filename,
                headers = EXCLUDED.headers,
                rows = EXCLUDED.rows;
        ''', (filename, headers_str, rows_str))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'error': 'Neovlašten pristup'}), 403
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT username, approved, is_admin FROM users ORDER BY id ASC;")
        users_list = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(users_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/toggle', methods=['POST'])
def toggle_user():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'error': 'Neovlašten pristup'}), 403

    req_data = request.get_json(silent=True) or {}
    username = req_data.get('username')

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT is_admin, approved FROM users WHERE username = %s;", (username,))
        user = cur.fetchone()

        if user:
            if user['is_admin']:
                cur.close()
                conn.close()
                return jsonify({'error': 'Nije moguće promijeniti status glavnog administratora!'}), 400
            
            new_status = not user['approved']
            cur.execute("UPDATE users SET approved = %s WHERE username = %s;", (new_status, username))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'success': True, 'approved': new_status})

        cur.close()
        conn.close()
        return jsonify({'error': 'Korisnik nije pronađen'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
