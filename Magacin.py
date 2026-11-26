def pronadji_stanje_u_lageru(sifra):
    """Sabira količine i spaja nazive ladica za istu šifru u svim redovima glavnog lagera."""
    lager = LagerData.query.order_by(LagerData.id.desc()).first()
    if not lager or not lager.rows:
        return {
            'nadjen': False,
            'stanje': None,
            'stanje_broj': None,
            'naziv': None,
            'ladica': None,
            'broj_stavki': 0
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
            'ladica': None,
            'broj_stavki': 0
        }

    if imao_broj:
        # Prikaži cijeli broj ako nema decimale (npr. 12 umjesto 12.0)
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
        'ladica': ', '.join(ladice) if ladice else '-',
        'broj_stavki': len(ladice) if len(ladice) > 1 else (1 if nadjen else 0)
    }


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

    # GET: vrati sve alate iz stoka sa sabranim stanjem iz magacina
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
