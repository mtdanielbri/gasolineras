"""Guarda, para cada gasolinera, desde cuándo no cambia su precio.

Se ejecuta una vez al día desde GitHub Actions. Descarga los precios de toda España,
los compara con los de la última ejecución y actualiza la fecha de cambio solo de las
que se han movido. No guarda histórico completo: una fecha por gasolinera y carburante.

Formato de data/cambios.json (compacto, porque lo descarga el móvil):
    {
      "generado": "2026-09-27",          fecha de esta ejecución
      "inicio":   "2026-09-27",          desde cuándo se vigila (para no exagerar los días)
      "est": { "4867": [1829,0, 2199,3, 2045,0, 0,0] }
    }
Cada gasolinera son cuatro pares [precio en milésimas de euro, días sin cambiar],
en el orden: gasolina 95, gasolina 98, diésel, GLP. Un precio 0 significa que no lo vende.
"""

import json
import pathlib
import urllib.request
from datetime import date

API = ('https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes'
       '/PreciosCarburantes/EstacionesTerrestres/')
RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / 'data' / 'cambios.json'

# El orden importa: es el que espera la web
CARBURANTES = [
    'Precio Gasolina 95 E5',
    'Precio Gasolina 98 E5',
    'Precio Gasoleo A',
    'Precio Gases licuados del petróleo',
]


def milesimas(txt):
    """'1,829' -> 1829. Vacío o ilegible -> 0 (no lo vende)."""
    try:
        v = float(str(txt).replace(',', '.'))
    except (TypeError, ValueError):
        return 0
    return round(v * 1000) if v > 0 else 0


def descargar():
    req = urllib.request.Request(API, headers={'User-Agent': 'surtidor-historico'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode('utf-8-sig'))


def main():
    hoy = date.today()
    previo = {}
    if SALIDA.exists():
        previo = json.loads(SALIDA.read_text(encoding='utf-8'))

    # Los días guardados eran relativos a la ejecución anterior: se pasan a hoy
    try:
        desfase = (hoy - date.fromisoformat(previo.get('generado', ''))).days
    except ValueError:
        desfase = 0
    antes = previo.get('est', {})
    inicio = previo.get('inicio') or hoy.isoformat()

    datos = descargar()
    lista = datos.get('ListaEESSPrecio') or []
    if len(lista) < 1000:
        raise SystemExit(f'Respuesta sospechosa: solo {len(lista)} gasolineras, no se toca nada')

    est = {}
    cambiadas = nuevas = 0
    for e in lista:
        ide = str(e.get('IDEESS') or '').strip()
        if not ide:
            continue
        viejo = antes.get(ide)
        fila = []
        movida = False
        for i, clave in enumerate(CARBURANTES):
            precio = milesimas(e.get(clave))
            if viejo is None:
                dias = 0                       # primera vez que la vemos
            else:
                anterior, dias_ant = viejo[i * 2], viejo[i * 2 + 1]
                if precio != anterior:
                    dias = 0                   # hoy ha cambiado
                    movida = True
                else:
                    dias = dias_ant + desfase  # sigue igual que la última vez
            fila += [precio, dias]
        est[ide] = fila
        if viejo is None:
            nuevas += 1
        elif movida:
            cambiadas += 1

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({
        'generado': hoy.isoformat(),
        'inicio': inicio,
        'fuente': datos.get('Fecha'),
        'est': est,
    }, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')

    print(f'{len(est)} gasolineras · {cambiadas} con cambio de precio · {nuevas} nuevas '
          f'· vigilando desde {inicio} · {SALIDA.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
