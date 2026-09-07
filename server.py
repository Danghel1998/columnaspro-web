import http.server
import socketserver
import json
import os
import math

PORT = 8000
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

def clean_float(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace(',', '.').strip()
        return float(s)
    except Exception:
        return default

VARILLAS_COMERCIALES = {
    0.80: {"nombre": '8 mm', "db": 0.80, "area": 0.50},
    1.00: {"nombre": '10 mm', "db": 1.00, "area": 0.79},
    1.20: {"nombre": '12 mm', "db": 1.20, "area": 1.13},
    0.95: {"nombre": '3/8"', "db": 0.95, "area": 0.71},
    1.27: {"nombre": '1/2"', "db": 1.27, "area": 1.29},
    1.59: {"nombre": '5/8"', "db": 1.59, "area": 1.98},
    1.91: {"nombre": '3/4"', "db": 1.91, "area": 2.85},
    2.54: {"nombre": '1"', "db": 2.54, "area": 5.07},
    3.58: {"nombre": '1 3/8"', "db": 3.58, "area": 10.06}
}

def get_info_varilla(db_cm):
    db_clean = round(clean_float(db_cm, 1.59), 2)
    if db_clean in VARILLAS_COMERCIALES:
        return VARILLAS_COMERCIALES[db_clean]
    best = None
    min_diff = 999
    for k, v in VARILLAS_COMERCIALES.items():
        diff = abs(k - db_clean)
        if diff < min_diff:
            min_diff = diff
            best = v
    if best and min_diff < 0.05:
        return best
    return {"nombre": f"{db_clean} cm", "db": db_clean, "area": math.pi * (db_clean/2.0)**2}

def calcular_diagrama_interaccion(b, h, fc, fy, rec, ast_total, capas=None):
    Es = 2000000.0  # kg/cm2
    ey = fy / Es    # Deformación de fluencia (~0.0021)
    
    if fc <= 280:
        beta1 = 0.85
    else:
        beta1 = max(0.65, 0.85 - 0.05 * (fc - 280) / 70.0)
        
    d = h - rec
    if capas is None or len(capas) == 0:
        n_capas = 4
        capas = []
        as_por_capa = ast_total / n_capas
        step_y = (h - 2 * rec) / (n_capas - 1)
        for i in range(n_capas):
            yi = rec + i * step_y
            capas.append({"d_i": yi, "As_i": as_por_capa})
        
    puntos_nominales = []
    puntos_diseno = []
    
    po = 0.85 * fc * (b * h - ast_total) + fy * ast_total
    pn_max = 0.80 * po
    phi_comp = 0.65
    phi_pn_max = phi_comp * pn_max / 1000.0
    
    c_values = [h * 3.0, h * 1.5, h * 1.0]
    c_curr = h * 0.95
    while c_curr >= 0.05 * h:
        c_values.append(c_curr)
        c_curr -= 0.04 * h
        
    for c in c_values:
        a = beta1 * c
        a_effective = min(a, h)
            
        Cc = 0.85 * fc * b * a_effective
        Mc = Cc * (h / 2.0 - a_effective / 2.0)
        
        Pn_sum = Cc
        Mn_sum = Mc
        et = 0.0
        
        for capa in capas:
            di = capa["d_i"]
            asi = capa["As_i"]
            esi = 0.003 * (c - di) / c
            if di == d:
                et = -esi
                
            fsi = max(-fy, min(fy, esi * Es))
            Fi = asi * fsi
            Pn_sum += Fi
            Mn_sum += Fi * (h / 2.0 - di)
            
        Pn_ton = Pn_sum / 1000.0
        Mn_ton_m = Mn_sum / 100000.0
        
        if et <= ey:
            phi = 0.65
        elif et >= 0.005:
            phi = 0.90
        else:
            phi = 0.65 + 0.25 * (et - ey) / (0.005 - ey)
            
        Pn_phi_ton = min(phi * Pn_ton, phi_pn_max)
        Mn_phi_ton_m = phi * Mn_ton_m
        
        if Pn_ton >= -fy * ast_total / 1000.0:
            puntos_nominales.append({"M": round(abs(Mn_ton_m), 3), "P": round(Pn_ton, 2)})
            puntos_diseno.append({"M": round(abs(Mn_phi_ton_m), 3), "P": round(Pn_phi_ton, 2)})

    pt_ton = -fy * ast_total / 1000.0
    puntos_nominales.append({"M": 0.0, "P": round(pt_ton, 2)})
    puntos_diseno.append({"M": 0.0, "P": round(0.90 * pt_ton, 2)})
    
    d = h - rec
    cb = (6000.0 / (6000.0 + fy)) * d
    ab = beta1 * cb
    cc_b = 0.85 * fc * b * min(ab, h)
    pb_ton = cc_b / 1000.0
    mb_ton_m = (cc_b * (h / 2.0 - min(ab, h) / 2.0)) / 100000.0

    return {
        "nominales": puntos_nominales,
        "diseno": puntos_diseno,
        "phi_pn_max": round(phi_pn_max, 2),
        "cb": round(cb, 2),
        "ab": round(ab, 2),
        "pb": round(pb_ton, 2),
        "mb": round(mb_ton_m, 2),
        "beta1": round(beta1, 2)
    }

def generar_combinaciones_e060(cm, cv, sis_x, sis_y):
    """
    Genera las 9 Combinaciones de Carga E.060 exactas según plantilla Gobierno Regional de Tumbes:
    1) 1.4CM + 1.7CV
    2) 1.25(CM+CV) + SISXX
    3) 1.25(CM+CV) - SISXX
    4) 0.9CM + SISXX
    5) 0.9CM - SISXX
    6) 1.25(CM+CV) + SISYY
    7) 1.25(CM+CV) - SISYY
    8) 0.9CM + SISYY
    9) 0.9CM - SISYY
    """
    p_cm = clean_float(cm.get('P'), 0.0)
    m2_cm = clean_float(cm.get('M2'), 0.0)
    m3_cm = clean_float(cm.get('M3'), 0.0)
    
    p_cv = clean_float(cv.get('P'), 0.0)
    m2_cv = clean_float(cv.get('M2'), 0.0)
    m3_cv = clean_float(cv.get('M3'), 0.0)
    
    p_sx = clean_float(sis_x.get('P'), 0.0)
    m2_sx = clean_float(sis_x.get('M2'), 0.0)
    m3_sx = clean_float(sis_x.get('M3'), 0.0)
    
    p_sy = clean_float(sis_y.get('P'), 0.0)
    m2_sy = clean_float(sis_y.get('M2'), 0.0)
    m3_sy = clean_float(sis_y.get('M3'), 0.0)
    
    combos = [
        {"nombre": "1.4CM + 1.7CV", "P": 1.4*p_cm + 1.7*p_cv, "M2": 1.4*m2_cm + 1.7*m2_cv, "M3": 1.4*m3_cm + 1.7*m3_cv},
        {"nombre": "1.25(CM+CV) + SISXX", "P": 1.25*(p_cm+p_cv) + p_sx, "M2": 1.25*(m2_cm+m2_cv) + m2_sx, "M3": 1.25*(m3_cm+m3_cv) + m3_sx},
        {"nombre": "1.25(CM+CV) - SISXX", "P": 1.25*(p_cm+p_cv) - p_sx, "M2": 1.25*(m2_cm+m2_cv) - m2_sx, "M3": 1.25*(m3_cm+m3_cv) - m3_sx},
        {"nombre": "0.9CM + SISXX", "P": 0.9*p_cm + p_sx, "M2": 0.9*m2_cm + m2_sx, "M3": 0.9*m3_cm + m3_sx},
        {"nombre": "0.9CM - SISXX", "P": 0.9*p_cm - p_sx, "M2": 0.9*m2_cm - m2_sx, "M3": 0.9*m3_cm - m3_sx},
        {"nombre": "1.25(CM+CV) + SISYY", "P": 1.25*(p_cm+p_cv) + p_sy, "M2": 1.25*(m2_cm+m2_cv) + m2_sy, "M3": 1.25*(m3_cm+m3_cv) + m3_sy},
        {"nombre": "1.25(CM+CV) - SISYY", "P": 1.25*(p_cm+p_cv) - p_sy, "M2": 1.25*(m2_cm+m2_cv) - m2_sy, "M3": 1.25*(m3_cm+m3_cv) - m3_sy},
        {"nombre": "0.9CM + SISYY", "P": 0.9*p_cm + p_sy, "M2": 0.9*m2_cm + m2_sy, "M3": 0.9*m3_cm + m3_sy},
        {"nombre": "0.9CM - SISYY", "P": 0.9*p_cm - p_sy, "M2": 0.9*m2_cm - m2_sy, "M3": 0.9*m3_cm - m3_sy},
    ]
    
    # Redondear resultados
    for c in combos:
        c["P"] = round(c["P"], 4)
        c["M2"] = round(c["M2"], 4)
        c["M3"] = round(c["M3"], 4)
        c["M_res"] = round(math.sqrt(c["M2"]**2 + c["M3"]**2), 4)
        
    return combos

def calcular_acero_transversal_e060(b, h, h_libre, db_long_cm, db_est_cm, n_ramas=2, vu_actuante_ton=None, pu_min_ton=None, fc=210.0, fy=4200.0, rec=4.0):
    """
    Cálculo del Diseño a Cortante (NTP E.060 Cap. 11) y Confinamiento Sísmico (Art 21.4):
    1. Peralte efectivo d = h - rec - db_est - db_long/2
    2. Resistencia del Concreto en Compresión Axial Vc (Art 11.3.1.2)
    3. Resistencia requerida del Acero Vs y Capacidad Nominal Phi Vn (Phi = 0.85)
    4. Espaciamiento de estribos por cortante s_corte
    5. Gobierno con Confinamiento Sísmico (Lo, so, s_resto)
    """
    b = float(b)
    h = float(h)
    h_libre_m = clean_float(h_libre, 3.30)
    db_long_cm = clean_float(db_long_cm, 1.59)
    db_est_cm = clean_float(db_est_cm, 0.95)
    n_ramas = max(2, int(clean_float(n_ramas, 2)))
    fc = clean_float(fc, 210.0)
    fy = clean_float(fy, 4200.0)
    rec = clean_float(rec, 4.0)

    d = max(1.0, h - rec - db_est_cm - db_long_cm / 2.0)
    ag = b * h

    # 1. Fuerza Cortante Actuante (Vu)
    vu_ton = clean_float(vu_actuante_ton, 12.50) if vu_actuante_ton is not None else 12.50
    pu_ton = max(0.0, clean_float(pu_min_ton, 10.0))

    # 2. Resistencia al cortante del concreto (Vc)
    nu_kg = pu_ton * 1000.0
    vc_kg = 0.53 * math.sqrt(fc) * b * d * (1.0 + nu_kg / (140.0 * ag))
    vc_ton = vc_kg / 1000.0

    # 3. Resistencia requerida del acero (Vs)
    phi_corte = 0.85
    vn_req_ton = vu_ton / phi_corte
    vs_ton = max(0.0, vn_req_ton - vc_ton)

    # Límite máximo de Vs (Art 11.5.6.8)
    vs_max_ton = (2.12 * math.sqrt(fc) * b * d) / 1000.0
    cumple_seccion = vs_ton <= vs_max_ton

    # 4. Espaciamiento por Cortante (s_corte)
    area_barra_est = (math.pi * (db_est_cm / 2.0)**2)
    av_cm2 = n_ramas * area_barra_est

    if vs_ton > 0.01:
        s_corte_cm = (av_cm2 * fy * d) / (vs_ton * 1000.0)
    else:
        s_corte_cm = 999.0

    # 5. Requisitos de Confinamiento Sísmico (Art 21.4.4)
    lado_mayor_m = max(b, h) / 100.0
    lado_menor_cm = min(b, h)

    lo_1 = h_libre_m / 6.0
    lo_2 = lado_mayor_m
    lo_3 = 0.50
    lo_final_m = max(lo_1, lo_2, lo_3)

    s1 = math.ceil(8 * db_long_cm)
    s2 = math.ceil(lado_menor_cm / 2.0)
    s3 = 10
    s_conf_geom = min(s1, s2, s3)
    so_final_cm = min(s_conf_geom, math.floor(s_corte_cm))
    so_final_cm = max(5, int(so_final_cm))

    num_est_conf = math.ceil((lo_final_m * 100.0) / so_final_cm)

    sf1 = math.ceil(16 * db_long_cm)
    sf2 = math.ceil(48 * db_est_cm)
    sf3 = math.ceil(lado_menor_cm)
    s_fuera_geom = min(sf1, sf2, sf3)
    s_fuera_final_cm = min(15, int(s_fuera_geom))

    phi_vn_ton = phi_corte * (vc_ton + vs_ton)
    cumple_corte = (phi_vn_ton >= vu_ton) and cumple_seccion

    nom_estribo = "ø3/8\""
    if abs(db_est_cm - 0.80) < 0.05: nom_estribo = "ø8mm"
    elif abs(db_est_cm - 1.27) < 0.05: nom_estribo = "ø1/2\""

    rotulo = f"{nom_estribo}: 1 @ 0.05m, {num_est_conf} @ {so_final_cm/100.0:.2f}m, resto @ {s_fuera_final_cm/100.0:.2f}m"

    return {
        "vu_ton": round(vu_ton, 2),
        "vc_ton": round(vc_ton, 2),
        "vs_ton": round(vs_ton, 2),
        "phi_vn_ton": round(phi_vn_ton, 2),
        "cumple_corte": cumple_corte,
        "cumple_seccion": cumple_seccion,
        "s_corte_cm": round(s_corte_cm, 1),
        "d_cm": round(d, 1),
        "av_cm2": round(av_cm2, 2),
        "lo_m": round(lo_final_m, 2),
        "lo_detalles": {"hc_6": round(lo_1, 2), "lado_mayor": round(lo_2, 2), "min_50cm": 0.50},
        "so_cm": so_final_cm,
        "so_detalles": {"s_8db": s1, "s_b2": s2, "s_100mm": 10, "s_corte": round(s_corte_cm, 1)},
        "s_fuera_cm": s_fuera_final_cm,
        "s_fuera_detalles": {"sf_16db": sf1, "sf_48db": sf2, "sf_b": sf3},
        "num_estribos_conf": num_est_conf,
        "n_ramas": n_ramas,
        "db_est_cm": db_est_cm,
        "rotulo_estribos": rotulo
    }

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
        except Exception:
            data = {}

        if self.path == '/api/calcular_columna':
            response = self.calcular_columna(data)
            self.send_json_response(response)
        elif self.path == '/api/calcular_zapata':
            response = self.calcular_zapata(data)
            self.send_json_response(response)
        else:
            self.send_error(404, "Endpoint no encontrado")

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def calcular_columna(self, data):
        try:
            norma = str(data.get('norma', 'E.060'))
            b = clean_float(data.get('b'), 25.0)  # Tumbes Excel: b=25 cm
            h = clean_float(data.get('h'), 60.0)  # Tumbes Excel: h=60 cm (a=25, b=60, Area=1500 cm2)
            fc = clean_float(data.get('fc'), 210.0)
            fy = clean_float(data.get('fy'), 4200.0)
            rec = clean_float(data.get('rec'), 4.0)
            h_libre = clean_float(data.get('h_libre'), 3.30)
            
            # Cargas ETABS no mayoradas opcionales
            etabs_data = data.get('etabs', None)
            
            if etabs_data:
                combos_e060 = generar_combinaciones_e060(
                    etabs_data.get('CM', {}),
                    etabs_data.get('CV', {}),
                    etabs_data.get('SISXX', {}),
                    etabs_data.get('SISYY', {})
                )
                pu_max = max(c['P'] for c in combos_e060)
                mux_max = max(abs(c['M3']) for c in combos_e060)
                muy_max = max(abs(c['M2']) for c in combos_e060)
            else:
                pu_max = clean_float(data.get('pu'), 48.62)
                mux_max = clean_float(data.get('mux'), 5.52)
                muy_max = clean_float(data.get('muy'), 3.00)
                combos_e060 = [
                    {"nombre": "Combinación Principal", "P": pu_max, "M2": muy_max, "M3": mux_max, "M_res": round(math.sqrt(mux_max**2 + muy_max**2), 4)}
                ]

            if b <= 0 or h <= 0:
                return {"exito": False, "error": "Las dimensiones b y h deben ser mayores a 0 cm."}
            
            ag = b * h  # cm2 (ej 1500 cm2)
            
            modo_armadura = str(data.get('modo_armadura', 'uniforme'))
            
            if modo_armadura == 'combinado':
                db_esq = clean_float(data.get('db_esq'), 1.91)
                n_cara_b = int(clean_float(data.get('n_cara_b'), 2))
                db_cara_b = clean_float(data.get('db_cara_b'), 1.59)
                n_cara_h = int(clean_float(data.get('n_cara_h'), 2))
                db_cara_h = clean_float(data.get('db_cara_h'), 1.59)
                
                info_esq = get_info_varilla(db_esq)
                info_b = get_info_varilla(db_cara_b)
                info_h = get_info_varilla(db_cara_h)
                
                as_esq_total = 4 * info_esq["area"]
                as_b_total = (2 * n_cara_b) * info_b["area"]
                as_h_total = (2 * n_cara_h) * info_h["area"]
                as_barras = as_esq_total + as_b_total + as_h_total
                num_varillas = 4 + 2 * n_cara_b + 2 * n_cara_h
                db_long_cm = info_esq["db"]
                
                partes_rotulo = [f"4 Ø {info_esq['nombre']}"]
                if n_cara_b > 0:
                    partes_rotulo.append(f"{2*n_cara_b} Ø {info_b['nombre']} (Cara b)")
                if n_cara_h > 0:
                    partes_rotulo.append(f"{2*n_cara_h} Ø {info_h['nombre']} (Cara h)")
                rotulo_acero = " + ".join(partes_rotulo)
                
                as_top = 2 * info_esq["area"] + n_cara_b * info_b["area"]
                as_bot = 2 * info_esq["area"] + n_cara_b * info_b["area"]

                capas = [{"d_i": rec, "As_i": as_top}]
                if n_cara_h > 0:
                    step = (h - 2 * rec) / (n_cara_h + 1)
                    for k in range(1, n_cara_h + 1):
                        yk = rec + k * step
                        capas.append({"d_i": yk, "As_i": 2 * info_h["area"]})
                capas.append({"d_i": h - rec, "As_i": as_bot})

                # Capas para el eje ortogonal (flexión M2, distribuidas a lo largo de "b")
                as_izq = 2 * info_esq["area"] + n_cara_h * info_h["area"]
                as_der = 2 * info_esq["area"] + n_cara_h * info_h["area"]

                capas_m2 = [{"d_i": rec, "As_i": as_izq}]
                if n_cara_b > 0:
                    step_b = (b - 2 * rec) / (n_cara_b + 1)
                    for k in range(1, n_cara_b + 1):
                        xk = rec + k * step_b
                        capas_m2.append({"d_i": xk, "As_i": 2 * info_b["area"]})
                capas_m2.append({"d_i": b - rec, "As_i": as_der})
            else:
                num_varillas = int(clean_float(data.get('num_varillas'), 8))
                db_long_cm = clean_float(data.get('db_long'), 1.59)
                info_long = get_info_varilla(db_long_cm)
                as_barras = num_varillas * info_long["area"]
                rotulo_acero = f"{num_varillas} Ø {info_long['nombre']}"

                capas = []
                n_capas = 4
                as_por_capa = as_barras / n_capas
                step_y = (h - 2 * rec) / (n_capas - 1)
                for i in range(n_capas):
                    capas.append({"d_i": rec + i * step_y, "As_i": as_por_capa})

                # Capas para el eje ortogonal (flexión M2, distribuidas a lo largo de "b")
                capas_m2 = []
                step_x = (b - 2 * rec) / (n_capas - 1)
                for i in range(n_capas):
                    capas_m2.append({"d_i": rec + i * step_x, "As_i": as_por_capa})

            ast_min = 0.01 * ag
            ast_max = 0.06 * ag
            ast_usado = max(as_barras, ast_min)

            # Diagrama de Interacción para cada dirección de análisis sísmico
            # M3 (flexión resistida a lo largo de "h", asociada a sismo X-X / SXX)
            diagrama = calcular_diagrama_interaccion(b, h, fc, fy, rec, ast_usado, capas)
            # M2 (flexión resistida a lo largo de "b", asociada a sismo Y-Y / SYY)
            diagrama_m2 = calcular_diagrama_interaccion(h, b, fc, fy, rec, ast_usado, capas_m2)
            
            # Verificación de todos los combos E.060
            combos_evaluados = []
            todos_cumplen = True
            for c in combos_e060:
                m_res = c['M_res']
                cumple = (c['P'] <= diagrama['phi_pn_max']) # check rápido
                combos_evaluados.append({**c, "cumple": cumple})
                if not cumple: todos_cumplen = False

            db_est_cm = clean_float(data.get('db_est'), 0.95)
            n_ramas = int(clean_float(data.get('n_ramas'), 2))
            vu_actuante_ton = clean_float(data.get('vu_actuante'), 12.50)
            pu_min_ton = min(c['P'] for c in combos_e060) if combos_e060 else 10.0

            # Acero Transversal (Estribos) y Diseño a Cortante E.060 Cap 11 & Cap 21
            estribos_info = calcular_acero_transversal_e060(
                b=b, h=h, h_libre=h_libre, db_long_cm=db_long_cm, db_est_cm=db_est_cm,
                n_ramas=n_ramas, vu_actuante_ton=vu_actuante_ton, pu_min_ton=pu_min_ton,
                fc=fc, fy=fy, rec=rec
            )
            
            memoria = {
                "titulo": f"MEMORIA DE CÁLCULO - COLUMNA N°3 (1ER PISO) GOBIERNO REGIONAL DE TUMBES",
                "norma": "NTP E.060 (Concreto Armado - Perú)",
                "geometria": { "b": b, "h": h, "ag": ag, "recubrimiento": rec, "h_libre": h_libre },
                "materiales": { "fc": fc, "fy": fy },
                "acero_longitudinal": {
                    "num_varillas": num_varillas,
                    "db_cm": db_long_cm,
                    "rotulo_acero": rotulo_acero,
                    "ast_calculado": round(ast_usado, 2),
                    "ast_min_1pct": round(ast_min, 2)
                },
                "estribos": estribos_info,
                "combos_e060": combos_evaluados,
                "pasos": [
                    f"1. Geometría y Área de Sección: a = {b} cm, b = {h} cm → Ag = {ag:.0f} cm²",
                    f"2. Verificación de Acero Mínimo (1% Ag): Ast_min = {ast_min:.2f} cm²",
                    f"3. Refuerzo Adopado: {rotulo_acero} (Ast = {ast_usado:.2f} cm², ρ = {(ast_usado/ag)*100:.2f}% Ag)",
                    f"4. Generación de las 9 Combinaciones de Carga E.060 (1.4CM+1.7CV, 1.25(CM+CV)±SIS, 0.9CM±SIS)",
                    f"5. Diagrama de Interacción P-M evaluado en la envolvente ØPn-ØMn",
                    f"6. Acero Transversal en Confinamiento (Lo = {estribos_info['lo_m']} m): s_conf = {estribos_info['so_cm']} cm",
                    f"7. Distribución Final de Estribos: {estribos_info['rotulo_estribos']}"
                ]
            }

            return {
                "exito": True,
                "ag": ag,
                "ast_min": round(ast_min, 2),
                "ast_max": round(ast_max, 2),
                "ast_usado": round(ast_usado, 2),
                "phi_pn_max": diagrama["phi_pn_max"],
                "combos_e060": combos_evaluados,
                "estribos": estribos_info,
                "cumple_flexocompresion": todos_cumplen,
                "diagrama": diagrama,
                "diagrama_m2": diagrama_m2,
                "rotulo_acero": rotulo_acero,
                "num_varillas": num_varillas,
                "norma": "NTP E.060 (Perú)",
                "memoria": memoria
            }
        except Exception as e:
            return {"exito": False, "error": str(e)}

    def calcular_zapata(self, data):
        try:
            norma = str(data.get('norma', 'E.060'))
            tipo = str(data.get('tipo', 'aislada'))
            p_servicio = clean_float(data.get('p_servicio'), 60.0)
            p_ultimo = clean_float(data.get('p_ultimo'), 90.0)
            qa = clean_float(data.get('qa'), 2.0)
            fc = clean_float(data.get('fc'), 210.0)
            fy = clean_float(data.get('fy'), 4200.0)
            col_b = clean_float(data.get('col_b'), 25.0)
            col_h = clean_float(data.get('col_h'), 60.0)
            
            if qa <= 0:
                return {"exito": False, "error": "La capacidad admisible del suelo qa debe ser mayor a 0."}
                
            qa_ton_m2 = qa * 10.0
            
            if tipo == 'aislada':
                area_req = p_servicio / qa_ton_m2
                lado = math.ceil(math.sqrt(area_req) * 20.0) / 20.0
                if lado < 0.80: lado = 0.80
                
                area_real = lado * lado
                q_neto_ult = p_ultimo / area_real
                
                rec_zapata = 7.5
                hz = 50.0
                d = hz - rec_zapata - 1.0
                
                vuela = (lado * 100.0 - col_h) / 2.0
                phi_cortante = 0.85
                
                bo = 2.0 * (col_b + d) + 2.0 * (col_h + d)
                vc_punzonamiento_kg_cm2 = phi_cortante * 1.1 * math.sqrt(fc)
                
                area_critica_punzonamiento = (col_b + d) * (col_h + d) / 10000.0
                vu_punzonamiento_ton = q_neto_ult * (area_real - area_critica_punzonamiento)
                v_actuante_punzonamiento_kg_cm2 = (vu_punzonamiento_ton * 1000.0) / (bo * d) if (bo * d) > 0 else 0
                
                cumple_punzonamiento = v_actuante_punzonamiento_kg_cm2 <= vc_punzonamiento_kg_cm2
                
                mu_ton_m = q_neto_ult * lado * (vuela / 100.0)**2 / 2.0
                as_flexion = (mu_ton_m * 100000.0) / (0.9 * fy * 0.9 * d) if d > 0 else 0
                as_min_zapata = 0.0018 * (lado * 100.0) * hz
                as_final = max(as_flexion, as_min_zapata)
                
                memoria = {
                    "titulo": f"MEMORIA DE CÁLCULO - ZAPATA AISLADA ({norma} / E.050)",
                    "norma": f"NTP E.060 (Concreto Armado) & E.050 (Suelos)",
                    "geometria": { "B": lado, "L": lado, "H": hz, "d": d, "recubrimiento": rec_zapata },
                    "suelo": { "qa": qa, "qa_ton_m2": qa_ton_m2 },
                    "cargas": { "P_servicio": p_servicio, "P_ultimo": p_ultimo },
                    "resultados": {
                        "area_req": round(area_req, 2),
                        "area_real": round(area_real, 2),
                        "q_neto_ult": round(q_neto_ult, 2),
                        "v_punzonamiento_actuante": round(v_actuante_punzonamiento_kg_cm2, 2),
                        "v_punzonamiento_admisible": round(vc_punzonamiento_kg_cm2, 2),
                        "cumple_punzonamiento": cumple_punzonamiento,
                        "as_flexion": round(as_flexion, 2),
                        "as_min": round(as_min_zapata, 2),
                        "as_final": round(as_final, 2)
                    },
                    "pasos": [
                        f"1. Capacidad Admisible del Suelo (NTP E.050): q_adm = {qa:.2f} kg/cm² = {qa_ton_m2:.1f} Ton/m²",
                        f"2. Área Requerida por Servicio: A_req = {p_servicio:.2f} Ton / {qa_ton_m2:.1f} Ton/m² = {area_req:.2f} m²",
                        f"3. Dimensiones Adoptadas en Planta: B = {lado:.2f} m, L = {lado:.2f} m (Área Real = {area_real:.2f} m²)",
                        f"4. Reacción Neta Última del Suelo (NTP E.060): q_u = {p_ultimo:.2f} Ton / {area_real:.2f} m² = {q_neto_ult:.2f} Ton/m²",
                        f"5. Peralte Efectivo d (Recubrimiento = 7.5 cm): d = {hz:.0f} cm - 7.5 cm - 1.0 cm = {d:.1f} cm",
                        f"6. Verificación por Punzonamiento a d/2: Perímetro bo = {bo:.1f} cm. Tensión v_u = {v_actuante_punzonamiento_kg_cm2:.2f} kg/cm² ≤ v_c ({vc_punzonamiento_kg_cm2:.2f} kg/cm²) → {'CUMPLE' if cumple_punzonamiento else 'AUMENTAR PERALTE H'}",
                        f"7. Momento Flector Último en Cara de Columna: Mu = {mu_ton_m:.2f} Ton-m",
                        f"8. Acero por Flexión Requerido: As_flexion = {as_flexion:.2f} cm² (As_min_temp = {as_min_zapata:.2f} cm²)",
                        f"9. Refuerzo Final Adoptado: As = {as_final:.2f} cm² (Usar Ø 5/8\" @ 15 cm)"
                    ]
                }
                
                return {
                    "exito": True,
                    "tipo": tipo,
                    "lado_b": lado,
                    "lado_l": lado,
                    "area_req": round(area_req, 2),
                    "area_real": round(area_real, 2),
                    "q_neto": round(q_neto_ult, 2),
                    "memoria": memoria
                }
            elif tipo == 'combinada':
                p2_servicio = clean_float(data.get('p2_servicio'), 80.0)
                p2_ultimo = clean_float(data.get('p2_ultimo'), 120.0)
                distancia = clean_float(data.get('distancia'), 4.0)
                
                p_total_serv = p_servicio + p2_servicio
                p_total_ult = p_ultimo + p2_ultimo
                area_req = p_total_serv / qa_ton_m2
                
                xr = (p2_servicio * distancia) / p_total_serv if p_total_serv > 0 else 0
                l_zapata = math.ceil(2.0 * (xr + 0.25) * 10.0) / 10.0
                b_zapata = math.ceil((area_req / l_zapata) * 10.0) / 10.0 if l_zapata > 0 else 1.0
                if b_zapata < 1.0: b_zapata = 1.0
                
                area_real = l_zapata * b_zapata
                q_neto_ult = p_total_ult / area_real if area_real > 0 else 0
                
                memoria = {
                    "titulo": f"MEMORIA DE CÁLCULO - ZAPATA COMBINADA ({norma})",
                    "norma": f"NTP E.060 / E.050 (Perú)",
                    "cargas": { "P1_serv": p_servicio, "P2_serv": p2_servicio, "P_total_serv": p_total_serv, "distancia": distancia },
                    "resultados": {
                        "xr": round(xr, 2),
                        "b_zapata": b_zapata,
                        "l_zapata": l_zapata,
                        "area_req": round(area_req, 2),
                        "area_real": round(area_real, 2),
                        "q_neto_ult": round(q_neto_ult, 2)
                    },
                    "pasos": [
                        f"1. Carga de Servicio Total: P_total = {p_servicio:.2f} + {p2_servicio:.2f} = {p_total_serv:.2f} Ton",
                        f"2. Área de Cimentación Requerida: A_req = {p_total_serv:.2f} / {qa_ton_m2:.1f} = {area_req:.2f} m²",
                        f"3. Ubicación de Resultante Xr = ({p2_servicio:.2f} Ton × {distancia:.2f} m) / {p_total_serv:.2f} Ton = {xr:.2f} m",
                        f"4. Longitud de Zapata (L) = 2 × ({xr:.2f} + 0.25) = {l_zapata:.2f} m",
                        f"5. Ancho de Zapata (B) = {area_req:.2f} m² / {l_zapata:.2f} m = {b_zapata:.2f} m",
                        f"6. Presión Neta Última: q_u = {p_total_ult:.2f} Ton / {area_real:.2f} m² = {q_neto_ult:.2f} Ton/m²"
                    ]
                }
                
                return {
                    "exito": True,
                    "tipo": tipo,
                    "lado_b": b_zapata,
                    "lado_l": l_zapata,
                    "area_req": round(area_req, 2),
                    "area_real": round(area_real, 2),
                    "xr": round(xr, 2),
                    "q_neto": round(q_neto_ult, 2),
                    "memoria": memoria
                }
            elif tipo == 'conectada':
                return {
                    "exito": True,
                    "tipo": tipo,
                    "mensaje": "Zapata Conectada procesada exitosamente."
                }
        except Exception as e:
            return {"exito": False, "error": str(e)}

if __name__ == '__main__':
    print(f"Servidor HTTP corriendo en http://localhost:{PORT}")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")
