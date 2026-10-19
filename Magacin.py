from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'super_tajni_kljuc_magacin_2026'

# Baza korisnika u memoriji (sigurno za Render, ne ruši server)
# Tvoj admin račun je automatski odobren
USERS = {
    "mirzad": {
        "password": "mojalozinka123",
        "approved": True,
        "is_admin": True
    }
}

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

        if username in USERS and USERS[username]['password'] == password:
            if not USERS[username]['approved']:
                error = "Vaš račun još nije odobren od strane administratora!"
            else:
                session['logged_in'] = True
                session['username'] = username
                session['is_admin'] = USERS[username].get('is_admin', False)
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

        if not username or not password:
            error = "Molimo unesite sve podatke!"
        elif username in USERS:
            error = "Korisničko ime je već zauzeto!"
        else:
            USERS[username] = {
                "password": password,
                "approved": False,
                "is_admin": False
            }
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

@app.route('/api/users', methods=['GET'])
def get_users():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'error': 'Neovlašten pristup'}), 403
    
    users_list = []
    for user, data in USERS.items():
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

    if username in USERS:
        if USERS[username].get('is_admin'):
            return jsonify({'error': 'Nije moguće promijeniti status glavnog administratora!'}), 400
        
        USERS[username]['approved'] = not USERS[username]['approved']
        return jsonify({'success': True, 'approved': USERS[username]['approved']})
    
    return jsonify({'error': 'Korisnik nije pronađen'}), 404

if __name__ == '__main__':
    app.run(debug=True)
