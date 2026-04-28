#!/usr/bin/env python3
"""
Agrega sección "También te puede interesar" a todas las notas estáticas.
Ejecutar una sola vez desde el directorio raíz del repo.
No modifica archivos que ya tienen la sección ni variantes de idioma.
"""
import json, os, glob, random, re

BASE_URL = "https://globalpatagonia.org/"

def norm_tag(tag):
    """Limpia emoji/puntos y devuelve solo el texto de la etiqueta."""
    if not tag:
        return "Patagonia"
    m = re.search(r'[A-Za-záéíóúüñÁÉÍÓÚÜÑ\d]', tag)
    if not m:
        return "Patagonia"
    result = tag[m.start():].strip().rstrip('·').strip()
    return result or "Patagonia"

def abs_img(imagen):
    """Convierte ruta relativa de imagen a URL absoluta."""
    if not imagen:
        return ""
    if imagen.startswith("http"):
        return imagen
    return BASE_URL + imagen

def build_pool():
    """Construye pool de todas las notas: {id: {id, titulo, tag, imagen}}."""
    pool = {}

    def add(n):
        if not isinstance(n, dict):
            return
        nid = n.get("id")
        if not nid:
            return
        pool[nid] = {
            "id": nid,
            "titulo": n.get("titulo", ""),
            "tag": n.get("tag", ""),
            "imagen": abs_img(n.get("imagen", ""))
        }

    # Fuentes de lista directa
    for fname in ["historial.json", "propios.json", "propios_historial.json",
                  "turismo.json", "cultura.json", "negocios.json"]:
        if os.path.exists(fname):
            data = json.load(open(fname))
            if isinstance(data, list):
                for n in data:
                    add(n)

    # historias.json (dict con clave "notas")
    if os.path.exists("historias.json"):
        for n in json.load(open("historias.json")).get("notas", []):
            add(n)

    # noticias.json (dict con múltiples claves)
    if os.path.exists("noticias.json"):
        data = json.load(open("noticias.json"))
        add(data.get("tapa"))
        for key in ("secundarias", "noticias", "historias"):
            for n in data.get(key, []):
                add(n)

    # deportes_feed.json
    if os.path.exists("deportes_feed.json"):
        data = json.load(open("deportes_feed.json"))
        add(data.get("principal"))
        for key in ("secundarias", "row_cards"):
            for n in data.get(key, []):
                add(n)

    return pool

RELACIONADAS_CSS = """
    .relacionadas{margin-top:48px;padding-top:24px;border-top:2px solid #e0ddd8;}
    .relacionadas-titulo{font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#5a6070;margin-bottom:20px;}
    .relacionadas-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}
    .rel-card{cursor:pointer;border-radius:4px;overflow:hidden;background:white;transition:transform 0.2s;text-decoration:none;color:inherit;display:block;}
    .rel-card:hover{transform:translateY(-2px);}
    .rel-img{width:100%;height:100px;object-fit:cover;display:block;background:linear-gradient(160deg,#0e1a26,#1c2d3d);}
    .rel-body{padding:10px 12px 12px;}
    .rel-tag{font-size:9px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#3a7a5a;margin-bottom:4px;}
    .rel-titulo{font-size:13px;font-weight:600;line-height:1.35;color:#252830;}
    @media(max-width:600px){.relacionadas-grid{grid-template-columns:1fr 1fr;}}
    @media(max-width:480px){.relacionadas-grid{grid-template-columns:1fr;}}"""

def make_rel_html(notes):
    cards = ""
    for n in notes:
        if n["imagen"]:
            img = f'<img class="rel-img" src="{n["imagen"]}" alt="{n["titulo"]}" onerror="this.style.display=\'none\'">'
        else:
            img = '<div class="rel-img"></div>'
        tag = norm_tag(n["tag"])
        cards += (
            f'<a class="rel-card" href="/notas/{n["id"]}.html">'
            f'{img}'
            f'<div class="rel-body">'
            f'<div class="rel-tag">{tag}</div>'
            f'<div class="rel-titulo">{n["titulo"]}</div>'
            f'</div></a>'
        )
    return (
        '\n    <div class="relacionadas">'
        '\n      <div class="relacionadas-titulo">También te puede interesar</div>'
        f'\n      <div class="relacionadas-grid">{cards}</div>'
        '\n    </div>'
    )

def pick_related(nid, nota_tag, pool, n=3):
    """Selecciona n notas relacionadas: primero mismo tag, luego otras."""
    others = [v for k, v in pool.items() if k != nid]
    rng = random.Random(nid)
    clean = norm_tag(nota_tag).lower()
    same = [x for x in others if norm_tag(x["tag"]).lower() == clean]
    diff = [x for x in others if norm_tag(x["tag"]).lower() != clean]
    rng.shuffle(same)
    rng.shuffle(diff)
    return (same + diff)[:n]

VER_COMPLETO = '<a href="../" class="ver-completo">← Más noticias en GLOBALpatagonia</a>'

def process():
    pool = build_pool()
    print(f"Pool: {len(pool)} notas")

    html_files = sorted(glob.glob("notas/*.html"))
    # Saltar variantes de idioma
    html_files = [f for f in html_files
                  if not f.endswith("-en.html") and not f.endswith("-pt.html")]

    updated = skipped_existing = skipped_no_anchor = skipped_no_related = 0

    for fpath in html_files:
        content = open(fpath, encoding="utf-8").read()

        if 'class="relacionadas"' in content:
            skipped_existing += 1
            continue

        if VER_COMPLETO not in content:
            skipped_no_anchor += 1
            continue

        nid = os.path.basename(fpath).replace(".html", "")
        nota = pool.get(nid, {})
        related = pick_related(nid, nota.get("tag", ""), pool, n=3)

        if not related:
            skipped_no_related += 1
            continue

        rel_html = make_rel_html(related)

        # Inyectar CSS justo antes del cierre de </style>
        new_content = content.replace("</style>", RELACIONADAS_CSS + "\n  </style>", 1)

        # Insertar sección antes del link ver-completo
        new_content = new_content.replace(
            "\n    " + VER_COMPLETO,
            rel_html + "\n    " + VER_COMPLETO
        )
        # Fallback si no tenía el indent exacto
        if 'class="relacionadas"' not in new_content:
            new_content = new_content.replace(
                VER_COMPLETO,
                rel_html + "\n    " + VER_COMPLETO
            )

        open(fpath, "w", encoding="utf-8").write(new_content)
        updated += 1

    print(f"Actualizadas: {updated}")
    print(f"Ya tenían relacionadas: {skipped_existing}")
    print(f"Sin anchor ver-completo: {skipped_no_anchor}")
    print(f"Sin notas relacionadas: {skipped_no_related}")

if __name__ == "__main__":
    process()
