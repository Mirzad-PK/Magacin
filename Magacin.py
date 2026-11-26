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

    for row in lager.rows:
        if not isinstance(row, list) or len(row) < 2:
            continue

        ladica_val = row[0] if len(row) > 0 else None
        sifra_alat_val = str(row[1]).strip().lower() if len(row) > 1 and row[1] is not None else ''
        sifra_mat_val = str(row[2]).strip().lower() if len(row) > 2 and row[2] is not None else ''
        naziv_val = row[3] if len(row) > 3 else None
        kolicina_val = row[4] if len(row) > 4 else None

        if sifra_alat_val == sifra_norm or (sifra_mat_val and sifra_mat_val == sifra_norm):
            return {
                'nadjen': True,
                'stanje': kolicina_val,
                'stanje_broj': _parse_broj(kolicina_val),
                'naziv': naziv_val,
                'ladica': ladica_val
            }

    return {
        'nadjen': False,
        'stanje': None,
        'stanje_broj': None,
        'naziv': None,
        'ladica': None
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
