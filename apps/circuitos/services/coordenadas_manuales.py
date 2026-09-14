"""
Overrides manuales de coordenadas por código de circuito.

Se aplican ANTES de cualquier estrategia automática. Sirven para:
  - Circuitos sin dirección conocida (solo aparecen en reportes UNE).
  - Soterrados de Habana Vieja (OP3XX) que comparten zona.
  - Circuitos cuya dirección no matchea ningún reparto del diccionario.
  - Correcciones manuales post-revisión del mapa.

Si añades una entrada aquí, prevalece sobre cualquier heurística.
"""


COORDENADAS_MANUALES = {
    # ── Soterrados Habana Vieja (comparten centro del municipio) ─
    'OP304': (23.1367, -82.3558),
    'OP306': (23.1367, -82.3558),
    'OP307': (23.1367, -82.3558),
    'OP318': (23.1367, -82.3558),
    'OP320': (23.1367, -82.3558),
    'OP406': (23.1367, -82.3558),
    'OP410': (23.1367, -82.3558),
    'OP411': (23.1367, -82.3558),
    'OP424': (23.1367, -82.3558),

    # ── Sin dirección en el scrape ────────────────────────────
    'A1425': (23.1300, -82.3400),   # Regla (aparece junto a A1516)
    'A1565': (23.1800, -82.2900),   # Habana del Este (aparece con A1570)
    'A1570': (23.1800, -82.2900),

    # ── Calles específicas sin reparto claro ──────────────────
    '1242':  (23.1125, -82.4297),   # Playa, av 25 e/ 60 y 48
    '1246':  (23.0831, -82.4481),   # Playa, av 47 e/ 50 y 52
    '1248':  (23.1200, -82.4000),   # Plaza, av del Río / Nuevo Vedado
    'L317':  (23.1111, -82.4311),   # Playa, Almendares
    'L322':  (23.1042, -82.4408),   # Playa, Querejeta/Almendares
    'L323':  (23.1064, -82.4439),   # Playa, Querejeta
    'L325':  (23.1050, -82.4475),   # Playa, Hotel Muthu
    'L316':  (23.1106, -82.4356),   # Playa, Buenavista/Miramar
    'A1380': (23.0850, -82.2786),   # Guanabacoa, Cambute/Villa María
    'M2044': (23.0300, -82.3967),   # Boyeros, Dinorah/Jesús Nazareno
    'OP319': (23.1294, -82.3728),   # Centro Habana, Hospital/Soledad
    'OP325': (23.1283, -82.3772),   # Centro Habana, San Benigno/Macedonia
    'AL53':  (23.1622, -82.2736),   # Alamar (zonas 1-24)
    'AL55':  (23.1622, -82.2736),   # Alamar (zonas 12-25)
    'S516':  (23.0850, -82.3189),   # San Miguel del Padrón

        # ── Plaza de la Revolución (Vedado) ───────────────────────
    'PZ15':  (23.1256, -82.3825),   # Vedado, calles 35-37 e/ 4-6
    'PZ16':  (23.1239, -82.3828),   # Vedado, calle 6 e/ 37 y Hidalgo
    'PZ19':  (23.1289, -82.3886),   # Vedado, calle 21 e/ 2 y K
    'PZ24':  (23.1300, -82.3897),   # Vedado, entre Línea y Malecón

    # ── Regla ─────────────────────────────────────────────────
    'R464':  (23.1344, -82.3297),   # Regla, Reparto Modelo
    # ── Notas ─────────────────────────────────────────────────
    # Estos valores son APROXIMADOS y pueden mejorarse con
    # revisión manual desde el admin una vez tengamos el mapa
    # interactivo funcionando.
     # ── Últimos faltantes ─────────────────────────────────────
    'OP310':  (23.1367, -82.3558),   # Soterrado Habana Vieja
    'P329':   (23.1290, -82.3830),   # Vedado, 21 desde O hasta K
    'PZ4':    (23.1275, -82.3800),   # Vedado, 27 y 2 hasta B
    'PZ5':    (23.1281, -82.3825),   # Vedado, 2 desde 27 hasta 25
    'PZ6':    (23.1289, -82.3876),   # Vedado, 4 desde 27 hasta 11
}