"""Genera la carta de index.html a partir de carta.json.

Uso (desde la carpeta del proyecto):
    python _fuente/generar_carta.py

Reemplaza en index.html lo que está entre estos marcadores:
    <!-- PESTANAS:INICIO --> ... <!-- PESTANAS:FIN -->        botones de categorías
    <!-- CARTA:INICIO --> ... <!-- CARTA:FIN -->              listado de productos
    <!-- MENU-JSONLD:INICIO --> ... <!-- MENU-JSONLD:FIN -->  datos estructurados (schema.org/Menu)
    <!-- CARTA-FECHA -->...<!-- /CARTA-FECHA -->              fecha de actualización visible
Además actualiza los precios marcados con data-precio-de="Nombre" o "Nombre|Variante" (sección de clásicos),
tanto el texto de <span>/<p> como el atributo data-precio de los botones.
"""
import html
import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SITIO = 'https://www.coppeliarestobar.cl/'
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre']
GRUPOS = {'comida': 'Comida', 'bebestibles': 'Para beber'}


def clp(n):
    return '$' + f'{n:,}'.replace(',', '.')


def esc(s):
    return html.escape(s, quote=True)


def normalizar(s):
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9ñ]+', ' ', s).strip()


def boton(nombre, precio, variante=None):
    etiqueta = f'{nombre} ({variante.lower()})' if variante else nombre
    attrs = f'data-nombre="{esc(nombre)}" data-precio="{precio}"'
    if variante:
        attrs += f' data-variante="{esc(variante)}"'
    return (f'<button type="button" class="agregar js-agregar" {attrs} '
            f'aria-label="Agregar {esc(etiqueta)} al pedido">'
            f'<svg class="i" aria-hidden="true"><use href="#i-mas"/></svg></button>')


def item_html(it):
    nombre = it['nombre']
    texto_busqueda = normalizar(nombre + ' ' + it.get('descripcion', ''))
    veg = ' <span class="tag-veg">Vegetariano</span>' if it.get('vegetariano') else ''
    partes = [f'<li class="carta-item" data-q="{esc(texto_busqueda)}">']
    if 'variantes' in it:
        partes.append(f'<p class="carta-linea"><span class="carta-nombre">{esc(nombre)}</span>{veg}</p>')
        if it.get('descripcion'):
            partes.append(f'<p class="carta-desc">{esc(it["descripcion"])}</p>')
        partes.append('<ul class="carta-variantes">')
        for v in it['variantes']:
            partes.append(
                f'<li class="carta-linea"><span class="carta-variante">{esc(v["etiqueta"])}</span>'
                f'<span class="carta-guia" aria-hidden="true"></span>'
                f'<span class="carta-precio">{clp(v["precio"])}</span>{boton(nombre, v["precio"], v["etiqueta"])}</li>')
        partes.append('</ul>')
    else:
        partes.append(
            f'<p class="carta-linea"><span class="carta-nombre">{esc(nombre)}</span>{veg}'
            f'<span class="carta-guia" aria-hidden="true"></span>'
            f'<span class="carta-precio">{clp(it["precio"])}</span>{boton(nombre, it["precio"])}</p>')
        if it.get('descripcion'):
            partes.append(f'<p class="carta-desc">{esc(it["descripcion"])}</p>')
    partes.append('</li>')
    return ''.join(partes)


def pestanas_html(cats):
    out = []
    grupo = None
    for i, c in enumerate(cats):
        if c['grupo'] != grupo:
            grupo = c['grupo']
            out.append(f'<span class="cat-grupo" aria-hidden="true">{GRUPOS[grupo]}</span>')
        activa = i == 0
        clase = 'cat-tab active' if activa else 'cat-tab'
        estado = 'aria-selected="true"' if activa else 'aria-selected="false" tabindex="-1"'
        out.append(
            f'<button type="button" class="{clase}" id="tab-{c["id"]}" data-bs-toggle="tab" '
            f'data-bs-target="#cat-{c["id"]}" role="tab" aria-controls="cat-{c["id"]}" {estado}>{esc(c["nombre"])}</button>')
    return '\n'.join(out)


def paneles_html(cats):
    out = []
    for i, c in enumerate(cats):
        out.append(f'<div class="tab-pane{" active" if i == 0 else ""}" id="cat-{c["id"]}" role="tabpanel" '
                   f'aria-labelledby="tab-{c["id"]}" tabindex="0">')
        out.append(f'<h3 class="carta-cat">{esc(c["nombre"])}</h3>')
        for s in c['secciones']:
            out.append('<section class="carta-seccion">')
            if s['nombre']:
                out.append(f'<h4 class="carta-sub">{esc(s["nombre"])}</h4>')
            out.append('<ul class="carta-lista">')
            out.extend(item_html(it) for it in s['items'])
            out.append('</ul></section>')
        out.append('</div>')
    return '\n'.join(out)


def menu_jsonld(cats):
    secciones = []
    for c in cats:
        items = []
        for s in c['secciones']:
            for it in s['items']:
                m = {'@type': 'MenuItem', 'name': it['nombre']}
                if it.get('descripcion'):
                    m['description'] = it['descripcion']
                if 'variantes' in it:
                    m['offers'] = [{'@type': 'Offer', 'name': v['etiqueta'], 'price': v['precio'],
                                    'priceCurrency': 'CLP'} for v in it['variantes']]
                else:
                    m['offers'] = {'@type': 'Offer', 'price': it['precio'], 'priceCurrency': 'CLP'}
                if it.get('vegetariano'):
                    m['suitableForDiet'] = 'https://schema.org/VegetarianDiet'
                items.append(m)
        secciones.append({'@type': 'MenuSection', 'name': c['nombre'], 'hasMenuItem': items})
    menu = {'@context': 'https://schema.org', '@type': 'Menu', '@id': SITIO + '#carta', 'name': 'Carta de Coppelia',
            'inLanguage': 'es-CL', 'hasMenuSection': secciones}
    return '<script type="application/ld+json">' + json.dumps(menu, ensure_ascii=False, separators=(',', ':')) + '</script>'


def reemplazar(texto, marca, contenido):
    patron = re.compile(rf'(<!-- {marca}:INICIO -->)(.*?)(<!-- {marca}:FIN -->)', re.S)
    if not patron.search(texto):
        raise SystemExit(f'No encontré los marcadores {marca} en index.html')
    return patron.sub(lambda m: m.group(1) + '\n' + contenido + '\n' + m.group(3), texto)


def precios_destacados(texto, cats):
    precios = {}
    for c in cats:
        for s in c['secciones']:
            for it in s['items']:
                if 'variantes' in it:
                    for v in it['variantes']:
                        precios[f'{it["nombre"]}|{v["etiqueta"]}'] = v['precio']
                else:
                    precios[it['nombre']] = it['precio']
    faltan = set()

    def elemento(m):
        clave = html.unescape(m.group(3))
        if clave not in precios:
            faltan.add(clave)
            return m.group(0)
        return m.group(1) + clp(precios[clave]) + m.group(5)

    def boton_attr(m):
        clave = html.unescape(m.group(2))
        if clave not in precios:
            faltan.add(clave)
            return m.group(0)
        return m.group(1) + str(precios[clave]) + m.group(4)

    texto = re.sub(r'(<(span|p)\b[^>]*\sdata-precio-de="([^"]+)"[^>]*>)([^<]*)(</\2>)', elemento, texto)
    texto = re.sub(r'(\sdata-precio-de="([^"]+)"[^>]*?\sdata-precio=")(\d+)(")', boton_attr, texto)
    return texto, faltan


def main():
    datos = json.loads((RAIZ / '_fuente' / 'carta.json').read_text(encoding='utf-8'))
    cats = datos['categorias']
    pagina = RAIZ / 'index.html'
    texto = pagina.read_text(encoding='utf-8')
    texto = reemplazar(texto, 'PESTANAS', pestanas_html(cats))
    texto = reemplazar(texto, 'CARTA', paneles_html(cats))
    texto = reemplazar(texto, 'MENU-JSONLD', menu_jsonld(cats))
    a, m, d = (int(x) for x in datos['actualizado'].split('-'))
    texto = re.sub(r'(<!-- CARTA-FECHA -->).*?(<!-- /CARTA-FECHA -->)',
                   lambda mm: f'{mm.group(1)}<time datetime="{datos["actualizado"]}">{d} de {MESES[m - 1]} de {a}</time>{mm.group(2)}',
                   texto, flags=re.S)
    texto, faltan = precios_destacados(texto, cats)
    pagina.write_text(texto, encoding='utf-8', newline='\n')
    total = sum(len(s['items']) for c in cats for s in c['secciones'])
    print(f'Carta generada: {len(cats)} categorías, {total} productos.')
    if faltan:
        print('Aviso: estos destacados no existen en carta.json:', ', '.join(sorted(faltan)))


if __name__ == '__main__':
    main()
