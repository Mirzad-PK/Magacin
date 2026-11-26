import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tajni_kljuc_magacin')

database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///magacin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)


class LagerData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    headers = db.Column(db.JSON)
    rows = db.Column(db.JSON)


class StokAlata(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sifra = db.Column(db.String(120), unique=True, nullable=False)
    naziv = db.Column(db.String(250), nullable=True)
    min_zaliha = db.Column(db.Float, default=0.0)


with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username='mirzad').first()
    if not admin_user:
        hashed_pw = generate_password_hash('admin123')
        admin = User(username='mirzad', password_hash=hashed_pw, approved=True, is_admin=True)
        db.session.add(admin)
        db.session.commit()


def _parse_broj(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(',', '.')
    cleaned = ''.join(ch for ch in s if ch.isdigit() or ch in '.-')
    if not cleaned or cleaned in ('.', '-', '-.'):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def pronadji_stanje_u_lageru(sifra):
    lager = LagerData.query.order_by(LagerData.id.desc()).first()
    if not lager or not lager.rows:
        return {
            'nadjen': False,
            'stanje': None,
            'stanje_broj': None,
            'naziv': None,
            'ladica': None
        }

    sifra_norm = str(sifra).strip().lower()
    ukupno_broj = 0.0
    imao_broj = False
    tekstualna_stanja = []
    ladice = []
    naziv_nadjen = None

    for row in lager.rows:
        if not isinstance(row, list) or len(row) < 2:
            continue

        ladica_raw = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ''
        sifra_alat_val = str(row[1]).strip().lower() if len(row) > 1 and row[1] is not None else ''
        sifra_mat_val = str(row[2]).strip().lower() if len(row) > 2 and row[2] is not None else ''
        naziv_raw = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ''
        kolicina_raw = row[4] if len(row) > 4 else None

        if sifra_alat_val == sifra_norm or (sifra_mat_val and sifra_mat_val == sifra_norm):
            if not naziv_nadjen and naziv_raw and naziv_raw != '-':
                naziv_nadjen = naziv_raw

            if ladica_raw and ladica_raw != '-' and ladica_raw not in ladice:
                ladice.append(ladica_raw)

            broj = _parse_broj(kolicina_raw)
            if broj is not None:
                ukupno_broj += broj
                imao_broj = True
            elif kolicina_raw is not None and str(kolicina_raw).strip() not in ('', '-'):
                tekstualna_stanja.append(str(kolicina_raw).strip())

    nadjen = imao_broj or bool(tekstualna_stanja) or bool(ladice) or bool(naziv_nadjen)
    if not nadjen:
        return {
            'nadjen': False,
            'stanje': None,
            'stanje_broj': None,
            'naziv': None,
            'ladica': None
        }

    if imao_broj:
        stanje_prikaz = int(ukupno_broj) if ukupno_broj.is_integer() else round(ukupno_broj, 4)
        if tekstualna_stanja:
            stanje_prikaz = f"{stanje_prikaz} ({', '.join(tekstualna_stanja)})"
    else:
        stanje_prikaz = ', '.join(tekstualna_stanja) if tekstualna_stanja else '-'

    return {
        'nadjen': True,
        'stanje': stanje_prikaz,
        'stanje_broj': ukupno_broj if imao_broj else None,
        'naziv': naziv_nadjen,
        'ladica': ', '.join(ladice) if ladice else '-'
    }


def lista_sifri_iz_lagera():
    lager = LagerData.query.order_by(LagerData.id.desc()).first()
    if not lager or not lager.rows:
        return []

    stavke = []
    vidjene = set()

    for row in lager.rows:
        if not isinstance(row, list) or len(row) < 2:
            continue

        naziv = str(row[3]).strip() if len(row) > 3 and row[3] is not None and str(row[3]).strip() != '-' else ''
        for idx in (1, 2):
            if len(row) > idx and row[idx] is not None:
                s = str(row[idx]).strip()
                if s and s != '-' and s.lower() not in vidjene:
                    vidjene.add(s.lower())
                    stavke.append({'sifra': s, 'naziv': naziv})

    return stavke


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
                return render_template('login.html', error='Vaš račun čeka odobrenje administratora.')

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


@app.route('/api/data', methods=['GET', 'POST'])
def handle_data():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 403

    if request.method == 'POST':
        if not session.get('is_admin'):
            return jsonify({'success': False, 'error': 'Samo administrator može mijenjati podatke.'}), 403

        req_data = request.json or {}
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
        lager = LagerData.query.order_by(LagerData.id.desc()).first()
        if lager:
            return jsonify({
                'filename': lager.filename,
                'headers': lager.headers,
                'rows': lager.rows
            })
        return jsonify({'rows': []})


@app.route('/api/stok', methods=['GET', 'POST'])
def handle_stok():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 403

    if request.method == 'POST':
        if not session.get('is_admin'):
            return jsonify({'success': False, 'error': 'Samo administrator može mijenjati stok zaliha.'}), 403

        data = request.json or {}
        sifra = str(data.get('sifra', '')).strip()
        naziv = str(data.get('naziv', '')).strip()
        min_zaliha_raw = data.get('min_zaliha', 0)

        try:
            min_zaliha = float(str(min_zaliha_raw).replace(',', '.')) if str(min_zaliha_raw).strip() != '' else 0.0
        except ValueError:
            min_zaliha = 0.0

        if not sifra:
            return jsonify({'success': False, 'error': 'Unesi šifru alata.'}), 400

        postojeci = StokAlata.query.filter(db.func.lower(StokAlata.sifra) == sifra.lower()).first()
        if postojeći:
            if naziv:
                postojeći.naziv = naziv
            postojeći.min_zaliha = min_zaliha
            db.session.commit()
            return jsonify({'success': True, 'updated': True, 'id': postojeći.id})

        info_lager = pronadji_stanje_u_lageru(sifra)
        final_naziv = naziv or (info_lager['naziv'] or '')

        novi = StokAlata(sifra=sifra, naziv=final_naziv, min_zaliha=min_zaliha)
        db.session.add(novi)
        db.session.commit()
        return jsonify({'success': True, 'created': True, 'id': novi.id})

    stavke = StokAlata.query.order_by(StokAlata.id.asc()).all()
    rezultat = []
    for s in stavke:
        info = pronadji_stanje_u_lageru(s.sifra)
        stanje_num = info['stanje_broj']
        ispod_minimuma = False
        if stanje_num is not None and s.min_zaliha is not None and s.min_zaliha > 0:
            ispod_minimuma = stanje_num <= s.min_zaliha

        rezultat.append({
            'id': s.id,
            'sifra': s.sifra,
            'naziv': s.naziv or (info['naziv'] or ''),
            'ladica': info['ladica'] or '-',
            'min_zaliha': s.min_zaliha,
            'stanje_magacin': info['stanje'] if info['nadjen'] else 'Nema u lageru',
            'nadjen_u_lageru': info['nadjen'],
            'ispod_minimuma': ispod_minimuma
        })

    return jsonify({
        'stavke': rezultat,
        'sifre_iz_lagera': lista_sifri_iz_lagera()
    })


@app.route('/api/stok/<int:item_id>', methods=['DELETE'])
def delete_stok_item(item_id):
    if 'user' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    stavka = StokAlata.query.get(item_id)
    if not stavka:
        return jsonify({'success': False, 'error': 'Stavka nije pronađena.'}), 404

    db.session.delete(stavka)
    db.session.commit()
    return jsonify({'success': True})


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

    data = request.json or {}
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

    data = request.json or {}
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

    data = request.json or {}
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


@app.route('/ping')
def ping():
    return jsonify({'status': 'active'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
