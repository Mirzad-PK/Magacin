import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tajni_kljuc_magacin')

# Povezivanje na PostgreSQL bazu preko Render DATABASE_URL-a
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///magacin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Model baze za korisnike
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

# Model baze za spremanje stanja lagera (Excel/PDF podaci)
class LagerData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    headers = db.Column(db.JSON)
    rows = db.Column(db.JSON)

with app.app_context():
    db.create_all()
    # Automatski kreiraj admina ako ne postoji
    admin_user = User.query.filter_by(username='mirzad').first()
    if not admin_user:
        hashed_pw = generate_password_hash('admin123')
        admin = User(username='mirzad', password_hash=hashed_pw, approved=True, is_admin=True)
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('admin_panel'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            if not user.approved:
                return render_template('login.html', error='Vaš račun čekа odobrenje administratora.')
            
            session['user'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('admin_panel'))
        
        return render_template('login.html', error='Pogrešno korisničko ime ili šifra.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('register.html', error='Korisničko ime već postoji.')
            
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_pw, approved=False, is_admin=False)
        db.session.add(new_user)
        db.session.commit()
        
        return render_template('login.html', success='Uspješna registracija! Pričekajte da administrator odobri račun.')
    return render_template('register.html')

@app.route('/admin')
def admin_panel():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('admin.html', current_user=session['user'], is_admin=session.get('is_admin', False))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# API za dohvat i spremanje podataka lagera
@app.route('/api/data', methods=['GET', 'POST'])
def handle_data():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
        
    if request.method == 'POST':
        if not session.get('is_admin'):
            return jsonify({'success': False, 'error': 'Samo administrator može mijenjati podatke.'}), 403
            
        req_data = request.json
        # Očisti stare podatke i spremi nove
        LagerData.query.delete()
        
        new_lager = LagerData(
            filename=req_data.get('filename'),
            headers=req_data.get('headers'),
            rows=req_data.get('rows')
        )
        db.session.add(new_lager)
        db.session.commit()
        return jsonify({'success': True})
        
    else:
        lager = LagerData.query.first()
        if lager:
            return jsonify({
                'filename': lager.filename,
                'headers': lager.headers,
                'rows': lager.rows
            })
        return jsonify({'rows': []})

# API za upravljanje korisnicima (samo admin)
@app.route('/api/users', methods=['GET'])
def get_users():
    if 'user' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    users = User.query.all()
    users_list = [{
        'username': u.username,
        'approved': u.approved,
        'is_admin': u.is_admin
    } for u in users]
    
    return jsonify(users_list)

@app.route('/api/users/toggle', methods=['POST'])
def toggle_user():
    if 'user' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    data = request.json
    username = data.get('username')
    user = User.query.filter_by(username=username).first()
    
    if user:
        if user.is_admin:
            return jsonify({'success': False, 'error': 'Ne možeš mijenjati status administratora!'}), 400
        user.approved = not user.approved
        db.session.commit()
        return jsonify({'success': True})
        
    return jsonify({'success': False, 'error': 'Korisnik nije pronađen.'}), 404

@app.route('/api/users/delete', methods=['POST'])
def delete_user():
    if 'user' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    data = request.json
    username = data.get('username')
    
    if username == session.get('user'):
        return jsonify({'success': False, 'error': 'Ne možeš obrisati vlastiti administrator račun!'}), 400
        
    user = User.query.filter_by(username=username).first()
    if user:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True})
        
    return jsonify({'success': False, 'error': 'Korisnik nije pronađen.'}), 404

@app.route('/api/users/reset-password', methods=['POST'])
def reset_password():
    if 'user' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    data = request.json
    username = data.get('username')
    new_password = data.get('new_password')
    
    if not new_password:
        return jsonify({'success': False, 'error': 'Nova šifra ne može biti prazna.'}), 400
        
    user = User.query.filter_by(username=username).first()
    if user:
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        return jsonify({'success': True})
        
    return jsonify({'success': False, 'error': 'Korisnik nije pronađen.'}), 404

# Ruta za sprečavanje uspavljivanja poslužitelja na Renderu
@app.route('/ping')
def ping():
    return jsonify({'status': 'active'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
