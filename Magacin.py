import json
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'super_tajni_kljuc_magacin_2026'

USERS_FILE = 'users.json'
DATA_FILE = 'magacin_db.json'

# Učitavanje korisnika iz JSON datoteke
def load_users():
    default_users = {
        "mirzad": {
            "password": "mojalozinka123",
            "approved": True,
            "is_admin": True
        }
    }
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if data else default_users
        except Exception:
            return default_users
    return default_users

# Spremanje korisnika u JSON datoteku
def save_users(users):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Greška pri spremanju korisnika: {e}")

# Učitavanje sačuvanog dokumenta sa servera
def load_saved_data():
    default_data = {
        "filename": "",
        "headers": ["Ladica", "Šifra alata", "Šifra materijala", "Naziv alata", "Količina"],
        "rows": []
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if data else default_data
        except Exception:
            return default_data
    return default_data

# Spremanje novog dokumenta u JSON datoteku
def save_data_to_file(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Greška pri spremanju podataka: {e}")

# Inicijalno učitavanje pri pokretanju
USERS = load_users()
save_users(USERS)

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

        users = load_users()
        if username in users and users[username]['password'] == password:
            if not users[username]['approved']:
                error = "Vaš račun još nije odobren od strane administratora!"
            else:
                session['logged_in'] = True
                session['username'] = username
                session['is_admin'] = users[username].get('is_admin', False)
                return redirect(url_for('admin_panel'))
        else:
            error = "Pogrešno korisničko ime ili lozinka!"

    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    success = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        users = load_users()
        if not username or not password:
            error = "Molimo unesite sve podatke!"
        elif username in users:
            error = "Korisničko ime je već zauzeto!"
        else:
            users[username] = {
                "password": password,
                "approved": False,
                "is_admin": False
            }
            save_users(users)
            success = "Registracija uspješna! Vaš račun čeka odobrenje administratora."

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
    return jsonify(load_saved_data())

@app.route('/api/data', methods=['POST'])
def save_data():
    if not session.get('logged_in'):
        return jsonify({'error': 'Neovlašten pristup'}), 403

    req_data = request.get_json(silent=True) or {}
    new_data = {
        "filename": req_data.get('filename', 'Dokument'),
        "headers": req_data.get('headers', []),
        "rows": req_data.get('rows', [])
    }
    save_data_to_file(new_data)

    return jsonify({'success': True, 'count': len(new_data['rows'])})

@app.route('/api/users', methods=['GET'])
def get_users():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'error': 'Neovlašten pristup'}), 403
    
    users = load_users()
    users_list = []
    for user, data in users.items():
        users_list.append({
            'username': user,
            'approved': data.get('approved', False),
            'is_admin': data.get('is_admin', False)
        })
    return jsonify(users_list)

@app.route('/api/users/toggle', methods=['POST'])
def toggle_user():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'error': 'Neovlašten pristup'}), 403

    req_data = request.get_json(silent=True) or {}
    username = req_data.get('username')

    users = load_users()
    if username in users:
        if users[username].get('is_admin'):
            return jsonify({'error': 'Nije moguće promijeniti status glavnog administratora!'}), 400
        
        users[username]['approved'] = not users[username]['approved']
        save_users(users)
        return jsonify({'success': True, 'approved': users[username]['approved']})
    
    return jsonify({'error': 'Korisnik nije pronađen'}), 404

if __name__ == '__main__':
    app.run(debug=True)
