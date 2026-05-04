#!/usr/bin/env python3
"""
traducir_multiidioma.py
Genera versiones EN/PT/ZH de informes (propios.json) y guías (guias.json).
También actualiza el switcher de idiomas en páginas existentes.

Uso:
  python3 traducir_multiidioma.py              # procesa todo lo pendiente
  python3 traducir_multiidioma.py ID           # procesa solo ese ID
  python3 traducir_multiidioma.py --historial  # incluye propios_historial.json
"""

import json, sys, re, os
from pathlib import Path
import anthropic

# Cargar .env si existe
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

BASE = Path(__file__).parent
NOTAS_DIR = BASE / "notas"
PROPIOS_FILE = BASE / "propios.json"
PROPIOS_HISTORIAL_FILE = BASE / "propios_historial.json"
GUIAS_FILE = BASE / "guias.json"

client = anthropic.Anthropic()
LANGUAGES = ["en", "pt", "zh"]

LANG_NAMES = {"en": "English", "pt": "Portuguese (Brazilian)", "zh": "Simplified Chinese"}
LANG_HTML = {"en": "en", "pt": "pt", "zh": "zh-Hans"}
OG_LOCALE = {"en": "en_US", "pt": "pt_BR", "zh": "zh_CN"}

SWITCHER_CSS = """\
    .lang-switcher{display:flex;gap:8px;margin:0 0 24px;align-items:center;flex-wrap:wrap;}
    .lang-switcher a{display:inline-flex;align-items:center;gap:4px;padding:5px 12px;border:1.5px solid #c8d4dc;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.5px;text-decoration:none;color:#3a5a7a;background:#fff;transition:all 0.2s;}
    .lang-switcher a:hover,.lang-switcher a.active{background:var(--verde);color:white;border-color:var(--verde);}"""


def make_switcher(note_id: str, active_lang: str) -> str:
    def a(lang):
        return ' class="active"' if lang == active_lang else ""
    return (
        f'    <div class="lang-switcher">\n'
        f'      <a href="{note_id}.html"{a("es")}>🇦🇷 ES</a>\n'
        f'      <a href="{note_id}-en.html"{a("en")}>🇬🇧 EN</a>\n'
        f'      <a href="{note_id}-pt.html"{a("pt")}>🇧🇷 PT</a>\n'
        f'      <a href="{note_id}-zh.html"{a("zh")}>🇨🇳 中文</a>\n'
        f'    </div>'
    )


def make_hreflang(note_id: str) -> str:
    return (
        f'  <link rel="alternate" hreflang="es" href="https://globalpatagonia.org/notas/{note_id}.html"/>\n'
        f'  <link rel="alternate" hreflang="en" href="https://globalpatagonia.org/notas/{note_id}-en.html"/>\n'
        f'  <link rel="alternate" hreflang="pt" href="https://globalpatagonia.org/notas/{note_id}-pt.html"/>\n'
        f'  <link rel="alternate" hreflang="zh-Hans" href="https://globalpatagonia.org/notas/{note_id}-zh.html"/>\n'
        f'  <link rel="alternate" hreflang="x-default" href="https://globalpatagonia.org/notas/{note_id}.html"/>'
    )


def update_switcher_and_hreflang(html: str, note_id: str, active_lang: str) -> str:
    switcher = make_switcher(note_id, active_lang)
    hreflang = make_hreflang(note_id)

    # Add CSS if missing
    if ".lang-switcher" not in html:
        html = html.replace("  </style>", f"{SWITCHER_CSS}\n  </style>", 1)

    # Replace existing switcher, or inject it
    if 'class="lang-switcher"' in html:
        html = re.sub(
            r'[ \t]*<div class="lang-switcher">.*?</div>',
            switcher,
            html,
            flags=re.DOTALL,
        )
    elif "<article>" in html:
        html = html.replace("<article>", f"<article>\n{switcher}", 1)
    else:
        html = re.sub(
            r'(<a [^>]*class="volver"[^>]*/?>(?:.*?)?</a>)',
            r'\1\n' + switcher,
            html,
            count=1,
            flags=re.DOTALL,
        )

    # Remove existing hreflang tags then re-insert
    html = re.sub(r'  <link rel="alternate" hreflang[^\n]*/>\n?', "", html)
    html = html.replace('  <link rel="icon"', f'{hreflang}\n  <link rel="icon"', 1)

    return html


def translate_page(html_es: str, note_id: str, lang: str) -> str:
    zh_extras = ""
    if lang == "zh":
        zh_extras = """
EXTRA PARA CHINO (obligatorio):
- CSS: reemplazar fonts.googleapis.com → fonts.loli.net
- body font-family: 'Inter','Noto Sans SC',sans-serif
- Después del script GA, agregar: <meta name="renderer" content="webkit"/><meta http-equiv="X-UA-Compatible" content="IE=Edge,chrome=1"/><meta name="applicable-device" content="pc,mobile"/>
- top-bar izquierda: 阿根廷与智利巴塔哥尼亚
- slogan/logo-tagline: 全球南方，万物起源。
- nav: 首页 / 新闻 / 运动 &amp; 活动 / 旅游 &amp; 指南 / 巴塔哥尼亚文化 / 搜索
- ← Inicio / ← Volver → ← 返回首页
- footer sub (Argentina · Chile · Sin fronteras) → 阿根廷 · 智利 · 无界
- nota-fuente "Nota de producción propia / Original reporting" → 原创报道
- nota-meta fecha: formato chino (2026年X月X日)"""

    switcher_html = make_switcher(note_id, lang)
    hreflang_html = make_hreflang(note_id)

    prompt = f"""Traducí esta página HTML de GLOBALpatagonia del español al {LANG_NAMES[lang]}.

REGLAS:
- Traducir TODO el texto visible (título, meta, cuerpo, nav, footer, etiquetas, listas, botones, fechas)
- Preservar TODA la estructura HTML, CSS, URLs, rutas de imágenes, class names exactamente
- No modificar scripts ni sus contenidos
- Devolver ÚNICAMENTE el HTML completo, sin markdown, sin explicaciones

CAMBIOS MECÁNICOS (exactos):
1. <html lang="es"> → <html lang="{LANG_HTML[lang]}">
2. canonical, og:url, twitter:url: .html → -{lang}.html
3. og:locale → {OG_LOCALE[lang]}
4. JSON-LD: url → -{lang}.html, inLanguage → "{LANG_HTML[lang]}", traducir headline y description
5. Reemplazar todos los tags hreflang existentes con:
{hreflang_html}
6. Reemplazar/insertar el switcher de idiomas (justo antes de .nota-tag o después de <article> o después del link .volver):
{switcher_html}
7. Si el CSS no tiene .lang-switcher, agregar antes de </style>:
{SWITCHER_CSS}
{zh_extras}

HTML FUENTE (español):
{html_es}"""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    result = msg.content[0].text.strip()
    # Strip markdown code fences if model added them
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
        if "```" in result:
            result = result.rsplit("```", 1)[0]
    return result.strip()


def get_ids(include_historial: bool = False) -> list:
    ids = []
    for f in [PROPIOS_FILE, GUIAS_FILE]:
        data = json.loads(f.read_text(encoding="utf-8"))
        for item in data:
            nid = item.get("id")
            if nid and (NOTAS_DIR / f"{nid}.html").exists():
                if nid not in ids:
                    ids.append(nid)
    if include_historial and PROPIOS_HISTORIAL_FILE.exists():
        data = json.loads(PROPIOS_HISTORIAL_FILE.read_text(encoding="utf-8"))
        for item in data:
            nid = item.get("id")
            if nid and (NOTAS_DIR / f"{nid}.html").exists():
                if nid not in ids:
                    ids.append(nid)
    return ids


def needs_work(note_id: str) -> bool:
    missing = [l for l in LANGUAGES if not (NOTAS_DIR / f"{note_id}-{l}.html").exists()]
    if missing:
        return True
    # Check if any existing page needs switcher/hreflang update
    for lang in ["es"] + LANGUAGES:
        suffix = "" if lang == "es" else f"-{lang}"
        path = NOTAS_DIR / f"{note_id}{suffix}.html"
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        if f"{note_id}-pt.html" not in html or f"{note_id}-zh.html" not in html:
            return True
    return False


def process(note_id: str):
    src_path = NOTAS_DIR / f"{note_id}.html"
    html_es = src_path.read_text(encoding="utf-8")

    # 1. Create missing translations
    missing = [l for l in LANGUAGES if not (NOTAS_DIR / f"{note_id}-{l}.html").exists()]
    for lang in missing:
        print(f"  → Traduciendo al {lang.upper()}...", end="", flush=True)
        try:
            translated = translate_page(html_es, note_id, lang)
            out = NOTAS_DIR / f"{note_id}-{lang}.html"
            out.write_text(translated, encoding="utf-8")
            print(f" ✓")
        except Exception as e:
            print(f" ✗ ERROR: {e}")

    # 2. Update switcher + hreflang in ALL variants (including existing ones)
    variants = [("es", src_path)] + [
        (l, NOTAS_DIR / f"{note_id}-{l}.html")
        for l in LANGUAGES
        if (NOTAS_DIR / f"{note_id}-{l}.html").exists()
    ]
    for lang, path in variants:
        html = path.read_text(encoding="utf-8")
        updated = update_switcher_and_hreflang(html, note_id, lang)
        if updated != html:
            path.write_text(updated, encoding="utf-8")
            print(f"  ✓ {path.name} — switcher/hreflang actualizado")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    include_historial = "--historial" in flags
    target = args[0] if args else None

    if target:
        ids = [target]
    else:
        ids = get_ids(include_historial)

    pending = [nid for nid in ids if needs_work(nid)]

    if not pending:
        print("Todo al día, no hay nada pendiente.")
        return

    print(f"\nNotas a procesar: {len(pending)}")
    for nid in pending:
        missing = [l for l in LANGUAGES if not (NOTAS_DIR / f"{nid}-{l}.html").exists()]
        label = f"traducir: {', '.join(missing)}" if missing else "actualizar switcher"
        print(f"\n[{nid}] — {label}")
        process(nid)

    print("\n¡Listo! Acordate de hacer push.")


if __name__ == "__main__":
    main()
