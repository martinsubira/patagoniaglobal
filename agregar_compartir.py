#!/usr/bin/env python3
"""Agrega botones de compartir a todas las notas estáticas en notas/*.html
que tengan el botón .ver-completo y no tengan ya la sección de compartir."""

import os
import re

NOTAS_DIR = os.path.join(os.path.dirname(__file__), "notas")

CSS_COMPARTIR = """
    /* COMPARTIR */
    .compartir-bloque{margin:32px 0 8px;}
    .compartir-label-s{font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#7a7a7a;display:block;margin-bottom:10px;}
    .compartir-btns{display:flex;flex-wrap:wrap;gap:8px;}
    .btn-c{display:inline-flex;align-items:center;gap:5px;padding:8px 14px;border-radius:3px;font-size:12px;font-weight:600;text-decoration:none;cursor:pointer;border:none;transition:opacity 0.2s;color:white;}
    .btn-c:hover{opacity:0.85;}
    .btn-c-wa{background:#25D366;}
    .btn-c-x{background:#000;}
    .btn-c-fb{background:#1877F2;}
    .btn-c-mail{background:#555;}
    .btn-c-copy{background:#3a5a7a;}"""

JS_COMPARTIR = """
<script>
(function(){
  var href = encodeURIComponent(window.location.href);
  var titulo = encodeURIComponent(document.title.replace(' — GLOBALpatagonia','').replace(' - GLOBALpatagonia',''));
  var mailSubject = encodeURIComponent(document.title.replace(' — GLOBALpatagonia','').replace(' - GLOBALpatagonia',''));
  var mailBody = encodeURIComponent(document.title + '\\n' + window.location.href);
  var div = document.getElementById('compartir-bloque');
  if (!div) return;
  div.innerHTML =
    '<span class="compartir-label-s">Compartir</span>' +
    '<div class="compartir-btns">' +
    '<a class="btn-c btn-c-wa" href="https://wa.me/?text='+titulo+'%20'+href+'" target="_blank" rel="noopener">WhatsApp</a>' +
    '<a class="btn-c btn-c-x" href="https://twitter.com/intent/tweet?text='+titulo+'&url='+href+'" target="_blank" rel="noopener">X</a>' +
    '<a class="btn-c btn-c-fb" href="https://www.facebook.com/sharer/sharer.php?u='+href+'" target="_blank" rel="noopener">Facebook</a>' +
    '<a class="btn-c btn-c-mail" href="mailto:?subject='+mailSubject+'&body='+mailBody+'">Email</a>' +
    '<button class="btn-c btn-c-copy" onclick="navigator.clipboard.writeText(window.location.href);this.textContent=\'¡Copiado!\'">Copiar enlace</button>' +
    '</div>';
})();
</script>"""

PLACEHOLDER = '<div class="compartir-bloque" id="compartir-bloque"></div>'

VER_COMPLETO_RE = re.compile(r'(<a [^>]*class="ver-(?:completo|mas)"[^>]*>.*?</a>)', re.DOTALL)

SKIP_SUFFIXES = ('-en.html', '-pt.html', '-zh.html')
SKIP_FILES = {'perito-moreno-timeout-2026.html'}


def procesar(path):
    with open(path, encoding='utf-8') as f:
        html = f.read()

    # Skip si ya tiene la sección
    if 'compartir-bloque' in html or 'btn-c-wa' in html:
        return False

    # Skip si no tiene ver-completo ni ver-mas
    if 'ver-completo' not in html and 'ver-mas' not in html:
        return False

    # Agregar CSS antes de </style>
    if CSS_COMPARTIR.strip() not in html:
        html = html.replace('</style>', CSS_COMPARTIR + '\n  </style>', 1)

    # Insertar placeholder antes de .ver-completo o .ver-mas
    html = VER_COMPLETO_RE.sub(PLACEHOLDER + '\n    \\1', html, count=1)

    # Agregar JS antes de </body>
    html = html.replace('</body>', JS_COMPARTIR + '\n</body>', 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)

    return True


def main():
    archivos = [
        f for f in os.listdir(NOTAS_DIR)
        if f.endswith('.html')
        and not any(f.endswith(s) for s in SKIP_SUFFIXES)
        and f not in SKIP_FILES
    ]
    actualizados = 0
    for nombre in sorted(archivos):
        path = os.path.join(NOTAS_DIR, nombre)
        if procesar(path):
            print(f"  ✓ {nombre}")
            actualizados += 1
        else:
            print(f"  — {nombre} (sin cambios)")

    print(f"\nActualizados: {actualizados} / {len(archivos)}")


if __name__ == '__main__':
    main()
