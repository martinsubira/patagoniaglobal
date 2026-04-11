#!/usr/bin/env python3
"""
GLOBALpatagonia — Actualizador de Noticias
Diagramación fija (DIAGRAMACION.pdf):
  TAPA            → 1 principal + 2 secundarias (diario, Claude elige la más cubierta)
  NOTICIAS SEMANA → 8 cards: [tapa ayer + 2 sec ayer] + [5 sobrevivientes] (rotación)
  DEPORTES        → 7 slots en cascada diaria (principal + 2 sec + 4 row)
  NEGOCIOS        → 6 slots, +1 diario, –1 más antigua
  TURISMO         → 3 slots, +1 semanal (domingos)
  CULTURA         → 6 slots, +1 semanal (domingos)
  GUIAS           → manual, script no toca
  INFORMES        → manual, script no toca
  AGENDA          → purga vencidos + detecta nuevos en RSS
"""

import json
import sys
import os
import urllib.request
import urllib.parse
from datetime import datetime

import feedparser
import anthropic

# ══════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════

_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

API_KEY             = os.environ.get("ANTHROPIC_API_KEY", "")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")

FUENTES_RSS = [
    # ── Argentina · Regionales ──
    {"nombre": "Diario Río Negro",        "url": "https://www.rionegro.com.ar/feed/",                    "region": "Río Negro"},
    {"nombre": "La Opinión Austral",      "url": "https://laopinionaustral.com.ar/feed/",                "region": "Santa Cruz"},
    {"nombre": "El Patagónico",           "url": "https://www.elpatagonico.com/rss/portada.xml",         "region": "Chubut"},
    {"nombre": "Jornada Patagonia",       "url": "https://www.diariojornada.com.ar/rss/",                "region": "Chubut"},
    {"nombre": "ADN Sur",                 "url": "https://www.adnsur.com.ar/feed/",                      "region": "Patagonia"},
    {"nombre": "El Cordillerano",         "url": "https://www.elcordillerano.com.ar/rss/home.xml",       "region": "Río Negro"},
    {"nombre": "Bariloche2000",           "url": "https://www.bariloche2000.com/feed/",                  "region": "Bariloche"},
    {"nombre": "InfoFueguina",            "url": "https://www.infofueguina.com/rss",                     "region": "Tierra del Fuego"},
    {"nombre": "Neuquén Informa",         "url": "https://www.neuqueninforma.gob.ar/feed/",              "region": "Neuquén"},
    {"nombre": "LMNeuquén",              "url": "https://www.lmneuquen.com/rss/",                       "region": "Neuquén"},
    {"nombre": "Tiempo Sur",             "url": "https://www.tiemposur.com.ar/feed",                     "region": "Santa Cruz"},
    # ── Argentina · Nacional ──
    {"nombre": "La Nación",               "url": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/",   "region": "Nacional"},
    {"nombre": "Infobae",                 "url": "https://www.infobae.com/feeds/rss/",                   "region": "Nacional"},
    {"nombre": "Clarín",                  "url": "https://www.clarin.com/rss/lo-ultimo/",                "region": "Nacional"},
    # ── Chile · Nacional ──
    {"nombre": "La Nación Chile",           "url": "https://www.lanacion.cl/feed/",                        "region": "Nacional Chile"},
    # ── Chile · Regionales ──
    {"nombre": "La Prensa Austral",       "url": "https://laprensaaustral.cl/feed/",                     "region": "Magallanes"},
    {"nombre": "El Divisadero",           "url": "https://www.eldivisadero.cl/feed/",                    "region": "Aysén"},
    {"nombre": "El Llanquihue",           "url": "https://www.elllanquihue.cl/feed/",                    "region": "Los Lagos"},
    {"nombre": "El Pingüino",             "url": "https://www.elpinguino.com/feed/",                     "region": "Magallanes"},
    {"nombre": "Diario de Valdivia",      "url": "https://www.diariodevaldivia.cl/feed/",                "region": "Los Ríos"},
    # ── Islas Malvinas / Falkland Islands ──
    {"nombre": "Penguin News",            "url": "https://penguin-news.com/feed/",                        "region": "Malvinas", "idioma": "en"},
]

PALABRAS_CLAVE = [
    # Provincias y regiones
    "patagonia", "neuquén", "neuquen", "río negro", "rio negro", "chubut",
    "santa cruz", "tierra del fuego",
    # Ciudades Argentina
    "bariloche", "ushuaia", "calafate", "chaltén", "chalten", "comodoro",
    "madryn", "trelew", "esquel", "zapala", "viedma", "bolsón", "bolson",
    "san martín de los andes", "junín de los andes", "río gallegos",
    "cipolletti", "general roca", "villa la angostura", "puerto madryn",
    "río colorado", "neuquén capital", "las heras", "perito moreno",
    "puerto deseado", "caleta olivia", "pico truncado", "chos malal",
    "plottier", "piedra buena", "comandante piedra buena", "los antiguos",
    # Chile
    "magallanes", "punta arenas", "puerto natales", "torres del paine",
    "coyhaique", "aysén", "aysen", "puerto aysén", "puerto aysen",
    "puerto montt", "chiloé", "chiloe",
    "valdivia", "osorno", "pucón", "pucon", "villa o'higgins",
    "cochrane", "caleta tortel", "puerto williams", "cabo de hornos",
    # Medio ambiente
    "glaciar", "glaciares", "ley de glaciares", "periglacial",
    "minería", "minero", "sobrepesca", "pesca ilegal", "zona económica exclusiva",
    "incendio", "incendio forestal", "contaminación", "derrame",
    "parque nacional", "reserva natural", "área protegida",
    "huemul", "cóndor", "ballena", "lobo marino", "puma", "guanaco",
    "macá tobiano", "fauna patagónica", "especie invasora", "jabalí",
    "microplástico", "cambio climático", "recurso hídrico",
    # Pueblos Originarios
    "mapuche", "tehuelche", "aonikenk", "kawésqar", "kawesqar",
    "selknam", "ona", "yagán", "yagan", "pueblo originario",
    "comunidad indígena", "territorio ancestral",
    # Deportes patagónicos
    "fitz roy", "cerro torre", "nahuel huapi",
    "trail running", "ultra trail", "patagonia run", "ultra fiord",
    "final frontier", "canotaje", "kayak", "escalada", "andinismo",
    "esquí", "esqui", "snowboard", "ski", "cerro catedral",
    "expedición", "trekking", "mountain bike", "ciclismo de montaña",
    "canapino", "turismo carretera", "automovilismo", "rally",
    # Producción y economía regional
    "langostino", "merluza", "pesca artesanal", "golfo san jorge",
    "vaca muerta", "petróleo", "gas patagónico", "energía eólica",
    "frutilla", "cereza", "fruta fina", "vitivinicultura",
    "ganadería patagónica", "oveja", "lana", "carne de guanaco",
    "conicet", "paleontología", "dinosaurio", "hallazgo fósil",
    # Conectividad e infraestructura
    "ruta 3", "ruta 22", "ruta 40", "paso fronterizo",
    "aeropuerto", "vuelo", "aerolíneas", "lade", "jetsmart", "flybondi",
    "conectividad aérea", "puente patagónico",
    # Cultura e historia
    "historia patagónica", "pionero", "inmigrante patagónico",
    "fiesta regional", "festival", "artista patagónico",
    # Islas Malvinas / Falkland Islands
    "malvinas", "falkland", "falklands", "stanley", "islas malvinas",
    "soberanía malvinas", "atlántico sur",
    # Atlántico Sur, islas y Antártida
    "antártida", "antartida", "antártica", "antartica",
    "base antártica", "campaña antártica", "continente blanco",
    "georgias del sur", "sandwich del sur", "aurora austral",
    "islas del atlántico sur", "territorio antártico",
    "dirección nacional del antártico", "dna antártida",
    "rompehielos", "buque oceanográfico", "buque patrulla",
    "soberanía antártica", "tratado antártico",
    "isla de los estados", "isla grande de tierra del fuego",
    "canal beagle", "paso drake", "cabo de hornos",
    # Servicios cotidianos
    "clima", "alerta meteorológica", "viento", "nevada", "temporal",
]

MAX_HISTORIAL = 50   # artículos en historial.json

DIAS_ES  = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
MESES_ES = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio",
            "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]


def fecha_display():
    hoy = datetime.now()
    return f"{DIAS_ES[hoy.weekday()]}, {hoy.day} de {MESES_ES[hoy.month]} de {hoy.year}"


def es_patagonica(titulo, resumen):
    texto = (titulo + " " + resumen).lower()
    return any(kw in texto for kw in PALABRAS_CLAVE)


def obtener_imagen_rss(entry):
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if m.get("type", "").startswith("image"):
                return m.get("url")
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href")
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    return None


# ══════════════════════════════════════════════════════════
#  HISTORIAL
# ══════════════════════════════════════════════════════════

def cargar_historial():
    path = os.path.join(os.path.dirname(__file__), "historial.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def guardar_historial(articulos):
    """Guarda los últimos MAX_HISTORIAL artículos. Los que salen van a archivo.json."""
    path         = os.path.join(os.path.dirname(__file__), "historial.json")
    archivo_path = os.path.join(os.path.dirname(__file__), "archivo.json")

    descartadas = articulos[MAX_HISTORIAL:]
    if descartadas:
        try:
            with open(archivo_path, encoding="utf-8") as f:
                archivo = json.load(f)
        except Exception:
            archivo = {"_info": "Notas que rotaron del feed principal.", "notas": []}
        ids_existentes = {n.get("id") for n in archivo.get("notas", [])}
        nuevas = [n for n in descartadas if n.get("id") not in ids_existentes]
        archivo["notas"] = archivo.get("notas", []) + nuevas
        with open(archivo_path, "w", encoding="utf-8") as f:
            json.dump(archivo, f, ensure_ascii=False, indent=2)
        print(f"  → {len(nuevas)} nota(s) movidas a archivo.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(articulos[:MAX_HISTORIAL], f, ensure_ascii=False, indent=2)


def urls_ya_publicadas(historial):
    return {a.get("url_original", "") for a in historial if a.get("url_original")}


# ══════════════════════════════════════════════════════════
#  RSS
# ══════════════════════════════════════════════════════════

def fetch_noticias_crudas():
    noticias = []
    print(f"\n{'='*55}")
    print(f"  GLOBALpatagonia — Actualizando noticias")
    print(f"  {fecha_display()}")
    print(f"{'='*55}\n")

    for fuente in FUENTES_RSS:
        print(f"  Leyendo: {fuente['nombre']} ...", end=" ", flush=True)
        try:
            feed = feedparser.parse(fuente["url"])
            encontradas = 0
            for entry in feed.entries[:20]:
                titulo  = entry.get("title", "")
                resumen = entry.get("summary", "")
                if not titulo:
                    continue
                if es_patagonica(titulo, resumen):
                    noticias.append({
                        "fuente":           fuente["nombre"],
                        "region":           fuente["region"],
                        "titulo_original":  titulo,
                        "resumen_original": resumen[:500] if resumen else "",
                        "url":              entry.get("link", ""),
                        "imagen_rss":       obtener_imagen_rss(entry),
                    })
                    encontradas += 1
            print(f"{encontradas} patagónicas")
        except Exception as e:
            print(f"error ({e})")

    print(f"\n  Total encontradas: {len(noticias)} noticias patagónicas\n")
    return noticias[:30]


# ══════════════════════════════════════════════════════════
#  CLAUDE — REESCRITURA EDITORIAL
# ══════════════════════════════════════════════════════════

def reescribir_con_claude(noticias_crudas, historial, es_domingo=False):
    """
    Claude elige y reescribe notas NUEVAS del RSS de hoy para cada sección:
      - 1 tapa (la más cubierta por múltiples medios)
      - 2 secundarias (no deportes)
      - 1 deportes (para rotación diaria de Deportes y Aventura)
      - 1 negocios (economía/empresas)
      - 1 cultura (solo domingos)
      - 1 turismo (solo domingos)
      - 5 ticker
    Todo viene del RSS de hoy — nunca de notas viejas.
    """
    if not noticias_crudas:
        print("  ⚠ No se encontraron noticias patagónicas.")
        return None

    client = anthropic.Anthropic(api_key=API_KEY)

    ya_publicadas   = urls_ya_publicadas(historial)
    noticias_nuevas = [n for n in noticias_crudas if n["url"] not in ya_publicadas]
    print(f"  Noticias nuevas (no publicadas aún): {len(noticias_nuevas)}")

    if not noticias_nuevas:
        print("  ⚠ No hay noticias nuevas para agregar hoy.")
        return None

    listado = ""
    for i, n in enumerate(noticias_nuevas):
        listado += f"""
--- Noticia {i+1} ---
Fuente: {n['fuente']} ({n['region']})
Título original: {n['titulo_original']}
Resumen: {n['resumen_original']}
URL: {n['url']}
"""

    hoy = datetime.now().strftime('%Y%m%d-%H%M')

    seccion_domingo = ""
    if es_domingo:
        seccion_domingo = f"""
  "cultura": {{
    "id": "{hoy}-cul",
    "titulo": "Título (máx 12 palabras)",
    "bajada": "Una oración con dato concreto",
    "cuerpo": "Artículo completo con párrafos separados por \\n\\n (300-450 palabras)",
    "tag": "🎭 Cultura",
    "categoria": "cultura|historia|pueblos originarios",
    "fuente": "...",
    "url_original": "url completa",
    "pais": "argentina|chile|ambos|malvinas",
    "imagen": null,
    "imagen_keywords": "2-3 palabras en español",
    "excluir_feed": true
  }},
  "turismo": {{
    "id": "{hoy}-tur",
    "titulo": "Título (máx 12 palabras)",
    "bajada": "Una oración con dato concreto",
    "cuerpo": "Artículo completo con párrafos separados por \\n\\n (300-450 palabras)",
    "tag": "🏔 Turismo",
    "categoria": "turismo",
    "fuente": "...",
    "url_original": "url completa",
    "pais": "argentina|chile|ambos|malvinas",
    "imagen": null,
    "imagen_keywords": "2-3 palabras en español",
    "excluir_feed": true
  }},"""
    else:
        seccion_domingo = """
  "cultura": null,
  "turismo": null,"""

    prompt = f"""Sos el editor jefe de GLOBALpatagonia, el primer medio digital panpatagónico. Slogan: "Sur Global, principio de todo." Cobertura: Argentina y Chile sin fronteras.

IDENTIDAD EDITORIAL:
- La Patagonia no es periferia — es el comienzo. Escribís desde adentro, no desde Buenos Aires ni Santiago.
- Voz: directa, contextual, apasionada por la región, rigurosa. Nunca alarmista, nunca partidaria.
- Cada nota tiene perspectiva propia: qué significa para la Patagonia binacional, antecedentes, qué viene después.
- Si el hecho cruza la frontera Argentina-Chile, marcarlo siempre.
- NUNCA copiés párrafos de la fuente. Reescribí con voz propia.

CRITERIO DE SELECCIÓN:
✓ Medio Ambiente: glaciares, agua, fauna, ecosistemas, legislación ambiental, especies invasoras, contaminación
✓ Pueblos Originarios: Mapuche, Tehuelche, Kawésqar, Selknam — territorio, derechos, cultura viva
✓ Deportes Patagónicos: trail, escalada, kayak, ski, triatlón, expediciones, natación, carreras aventura
✓ Desarrollo & Producción: economía regional, pesca, ganadería, energía, infraestructura, conectividad
✓ Cultura: arte, música, identidad, historia, gastronomía, fiestas regionales, pioneros
✓ Ciencia & Tecnología: hallazgos CONICET, paleontología, innovación aplicada al territorio
✓ Turismo & Guías: destinos, temporadas, premios internacionales a Patagonia
✓ Negocios: empresas, producción, pesca comercial, energía, comercio, economía regional
✓ Atlántico Sur & Antártida: Malvinas, Georgias del Sur, Sándwich del Sur, base antártica, soberanía, expediciones, tratado antártico, buques, paso Drake, canal Beagle, isla de los Estados

PRIORIDADES para la TAPA — orden estricto:
1. MEDIO AMBIENTE CRÍTICO: glaciares, pesca ilegal en ZEE, incendios, especies en peligro → TAPA AUTOMÁTICA.
2. PUEBLOS ORIGINARIOS: cualquier nota sobre comunidades originarias patagónicas con hecho concreto.
3. PRODUCCIÓN CON IDENTIDAD: historia de productor patagónico, primer hito económico local.
4. TURISMO & CULTURA: destinos, fiestas regionales, artistas, premiaciones.
5. DESARROLLO: infraestructura, conectividad, energía con impacto concreto.
TAPA: si la misma historia aparece en múltiples medios, tiene prioridad automática.

DESCARTAR SIEMPRE: policiales, accidentes de tránsito, crónica roja, economía nacional sin anclaje patagónico, política sin efecto territorial concreto.

FUENTES EN INGLÉS (Penguin News — Malvinas/Falkland Islands): las notas pueden llegar en inglés. Traducí y reescribí en español con voz propia. El campo "pais" para estas notas es "malvinas".

Tenés estas noticias NUEVAS de hoy disponibles:
{listado}

Tu tarea — elegí notas DISTINTAS para cada sección (sin repetir la misma URL en dos secciones).
Devolvé EXACTAMENTE este JSON (sin texto adicional):
{{
  "ticker": ["titular corto 1", "titular corto 2", "titular corto 3", "titular corto 4", "titular corto 5"],
  "tapa": {{
    "id": "{hoy}-tapa",
    "titulo": "Título reescrito (máx 15 palabras)",
    "bajada": "Bajada con contexto y ángulo propio (2-3 oraciones)",
    "cuerpo": "Artículo completo con párrafos separados por \\n\\n (350-500 palabras)",
    "tag": "emoji + categoría",
    "categoria": "medio ambiente|pueblos originarios|turismo|cultura|ciencia|producción|conectividad|bienestar|pesca|historia|general",
    "fuente": "Nombre del medio original",
    "url_original": "url completa",
    "pais": "argentina|chile|ambos|malvinas",
    "imagen": null,
    "imagen_keywords": "2-3 palabras en español"
  }},
  "secundarias": [
    {{
      "id": "{hoy}-sec1",
      "titulo": "Título (máx 12 palabras)",
      "bajada": "Una oración con dato concreto",
      "cuerpo": "Artículo completo con párrafos separados por \\n\\n (300-450 palabras)",
      "tag": "· Categoría ·",
      "categoria": "...",
      "fuente": "...",
      "url_original": "url completa",
      "pais": "argentina|chile|ambos|malvinas",
      "imagen": null,
      "imagen_keywords": "2-3 palabras en español"
    }},
    {{
      "id": "{hoy}-sec2",
      "titulo": "Título (máx 12 palabras)",
      "bajada": "Una oración con dato concreto",
      "cuerpo": "Artículo completo con párrafos separados por \\n\\n (300-450 palabras)",
      "tag": "· Categoría ·",
      "categoria": "...",
      "fuente": "...",
      "url_original": "url completa",
      "pais": "argentina|chile|ambos|malvinas",
      "imagen": null,
      "imagen_keywords": "2-3 palabras en español"
    }}
  ],
  "deportes": {{
    "id": "{hoy}-dep",
    "titulo": "Título (máx 12 palabras)",
    "bajada": "Una oración con dato concreto",
    "cuerpo": "Artículo completo con párrafos separados por \\n\\n (300-450 palabras)",
    "tag": "🏃 Deportes",
    "categoria": "deportes",
    "fuente": "...",
    "url_original": "url completa",
    "pais": "argentina|chile|ambos|malvinas",
    "imagen": null,
    "imagen_keywords": "2-3 palabras en español",
    "excluir_feed": true
  }},{seccion_domingo}
  "negocios": {{
    "id": "{hoy}-neg",
    "titulo": "Título sobre economía/empresas patagónicas (máx 12 palabras)",
    "bajada": "Una oración con dato económico concreto",
    "cuerpo": "Artículo completo con párrafos separados por \\n\\n (300-450 palabras)",
    "tag": "💼 Economía",
    "categoria": "economia",
    "fuente": "...",
    "url_original": "url completa",
    "pais": "argentina|chile|ambos|malvinas",
    "imagen": null,
    "imagen_keywords": "2-3 palabras en español",
    "excluir_feed": true
  }}
}}

REGLAS CRÍTICAS:
- TAPA y SECUNDARIAS: nunca deportes, aventura, trail, escalada, ski, kayak, natación — esos van solo a "deportes".
- Cada sección debe usar una noticia DISTINTA (URLs diferentes).
- Si no hay nota de deportes disponible hoy, poné null en "deportes".
- Si no hay nota de economía/empresas, poné null en "negocios".
{"- HOY ES DOMINGO: completar cultura y turismo con notas del RSS de hoy." if es_domingo else "- Hoy no es domingo: cultura y turismo van en null."}"""

    print("  Enviando a Claude para reescritura editorial...", end=" ", flush=True)
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=10000,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()
        if "```" in texto:
            for parte in texto.split("```"):
                p = parte.strip()
                if p.startswith("json"):
                    texto = p[4:].strip(); break
                elif p.strip().startswith("{"):
                    texto = p.strip(); break
        inicio = texto.find("{")
        fin    = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            texto = texto[inicio:fin]
        datos = json.loads(texto)
        print("OK")
        return datos
    except json.JSONDecodeError as e:
        print(f"error parseando JSON: {e}")
        debug_path = os.path.join(os.path.dirname(__file__), "debug_claude_response.txt")
        try:
            with open(debug_path, "w") as f:
                f.write(texto)
            print(f"  Respuesta guardada en {debug_path}")
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"error: {e}")
        return None


# ══════════════════════════════════════════════════════════
#  IMÁGENES
# ══════════════════════════════════════════════════════════

def fotos_propias_disponibles():
    indice_path = os.path.join(os.path.dirname(__file__), "fotos", "index.json")
    if not os.path.exists(indice_path):
        return []
    try:
        with open(indice_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def extraer_og_image(url_articulo, nota_id):
    """Descarga la og:image del artículo fuente y la guarda en fotos/."""
    if not url_articulo:
        return None
    try:
        import re
        req = urllib.request.Request(url_articulo, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if not match:
            match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
        if not match:
            return None

        img_url = match.group(1).strip()
        if not img_url.startswith("http"):
            return None

        ext = img_url.split("?")[0].rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        base_dir      = os.path.dirname(__file__)
        filename      = f"foto-{nota_id}.{ext}"
        filename_webp = f"foto-{nota_id}.webp"
        ruta_local    = os.path.join(base_dir, "fotos", filename)
        ruta_webp     = os.path.join(base_dir, "fotos", filename_webp)

        if os.path.exists(ruta_webp):
            return f"fotos/{filename_webp}"
        if os.path.exists(ruta_local):
            return f"fotos/{filename}"

        img_req = urllib.request.Request(img_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(img_req, timeout=10) as resp:
            contenido = resp.read()

        with open(ruta_local, "wb") as f:
            f.write(contenido)

        _recortar_banner(ruta_local, url_articulo)
        ruta_final = _convertir_a_webp(ruta_local)
        return f"fotos/{os.path.basename(ruta_final)}"

    except Exception as e:
        print(f"(og:image error: {e})")
        return None


def extraer_galeria_articulo(url_articulo, nota_id):
    """Descarga fotos del cuerpo del artículo fuente (máx 4)."""
    if not url_articulo:
        return []
    try:
        import re
        req = urllib.request.Request(url_articulo, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        CONTENEDORES = [
            r'<article\b[^>]*>(.*?)</article>',
            r'<div[^>]+class=["\'][^"\']*(?:article-body|article-content|nota-cuerpo|'
            r'nota-body|entry-content|post-content|single-content|'
            r'news-content|td-post-content|article__body|story-body|'
            r'content-body|body-content|article_body)[^"\']*["\'][^>]*>(.*?)</div>',
        ]
        cuerpo_html = None
        for patron in CONTENEDORES:
            m = re.search(patron, html, re.DOTALL | re.IGNORECASE)
            if m:
                cuerpo_html = m.group(m.lastindex)
                break

        if not cuerpo_html:
            return []

        candidatas = []
        for m in re.finditer(r'data-src=["\']([^"\']+)["\']', cuerpo_html):
            candidatas.append(m.group(1))
        for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', cuerpo_html):
            candidatas.append(m.group(1))

        base = url_articulo.split("/")[0] + "//" + url_articulo.split("/")[2]
        vistas = set()
        urls_limpias = []
        for url in candidatas:
            if url.startswith("/"):
                url = base + url
            if not url.startswith("http"):
                continue
            url_lower = url.lower()
            if any(x in url_lower for x in [
                ".gif", "miniatura", "thumbnail", "thumb", "logo",
                "favicon", "icon", "avatar", "pixel", "1x1", "spacer",
                "publicidad", "banner", "promo", "ads/", "/ad-", "widget",
            ]):
                continue
            if not re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', url_lower):
                continue
            url_base = url.split("?")[0]
            if url_base in vistas:
                continue
            vistas.add(url_base)
            urls_limpias.append(url)
            if len(urls_limpias) >= 6:
                break

        fotos_dir = os.path.join(os.path.dirname(__file__), "fotos")
        galeria   = []
        descargadas = 0
        for i, img_url in enumerate(urls_limpias):
            if descargadas >= 4:
                break
            ext = re.search(r'\.(jpg|jpeg|png|webp)', img_url.lower())
            ext = ext.group(1) if ext else "jpg"
            if ext == "jpeg":
                ext = "jpg"
            filename   = f"foto-{nota_id}-g{i+1}.{ext}"
            ruta_local = os.path.join(fotos_dir, filename)
            if os.path.exists(ruta_local):
                galeria.append(f"fotos/{filename}")
                descargadas += 1
                continue
            try:
                img_req = urllib.request.Request(img_url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                })
                with urllib.request.urlopen(img_req, timeout=10) as resp:
                    contenido = resp.read()
                if len(contenido) < 10_000:
                    continue
                with open(ruta_local, "wb") as f:
                    f.write(contenido)
                _recortar_banner(ruta_local, url_articulo)
                galeria.append(f"fotos/{filename}")
                descargadas += 1
            except Exception:
                continue

        return galeria

    except Exception as e:
        print(f"(galeria error: {e})")
        return []


def buscar_foto_propia(nota, fotos):
    keywords_nota = nota.get("imagen_keywords", "").lower()
    if not keywords_nota:
        return None
    mejor = None
    mejor_score = 0
    for foto in fotos:
        score = sum(1 for kw in foto.get("keywords", []) if kw in keywords_nota)
        if score > mejor_score:
            mejor_score = score
            mejor = foto
    return f"fotos/{mejor['archivo']}" if mejor else None


def _unsplash_query(keywords):
    try:
        query = urllib.parse.quote(keywords)
        url   = f"https://api.unsplash.com/search/photos?query={query}&per_page=5&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}"
        req   = urllib.request.Request(url, headers={"Accept-Version": "v1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data    = json.loads(resp.read())
            results = data.get("results", [])
            if results:
                return results[0]["urls"]["regular"]
    except Exception:
        pass
    return None


def buscar_imagen_unsplash(keywords):
    if not UNSPLASH_ACCESS_KEY or UNSPLASH_ACCESS_KEY == "PEGAR_ACA_TU_UNSPLASH_KEY":
        return None
    resultado = _unsplash_query(keywords)
    if resultado:
        return resultado
    primera = keywords.split()[0] if keywords else "patagonia"
    resultado = _unsplash_query(f"{primera} patagonia")
    if resultado:
        return resultado
    return _unsplash_query("patagonia landscape argentina")


def _recortar_banner(ruta_local, url_fuente=""):
    """Detecta y elimina banners de diarios pegados al borde inferior de la imagen.
    Para Tiempo Sur: recorte específico del banner rojo corporativo (#E3001B aprox).
    Para otros medios: detección genérica por color de fila."""
    try:
        from PIL import Image
        import numpy as np
        img = Image.open(ruta_local).convert("RGB")
        arr = np.array(img)
        h, w = arr.shape[:2]
        if h < 100:
            return

        # TiempoSur: siempre recortar el 22% inferior (banner rojo fijo)
        if "tiemposur" in url_fuente.lower():
            corte = int(h * 0.78)
            img.crop((0, 0, w, corte)).save(ruta_local, quality=90)
            return

        def es_banner_generico(fila):
            r, g, b = fila[:,0], fila[:,1], fila[:,2]
            rojo    = np.mean((r > 160) & (g < 80)  & (b < 80))   > 0.7
            blanco  = np.mean((r > 220) & (g > 220) & (b > 220))  > 0.7
            negro   = np.mean((r < 40)  & (g < 40)  & (b < 40))   > 0.7
            naranja = np.mean((r > 200) & (g > 80)  & (g < 160) & (b < 60)) > 0.7
            return rojo or blanco or negro or naranja

        zona = int(h * 0.25)
        corte = h
        for i in range(h - 1, h - zona - 1, -1):
            if not es_banner_generico(arr[i]):
                corte = i + 1
                break

        if corte < h:
            img = img.crop((0, 0, w, corte))
            img.save(ruta_local, quality=90)

        # Forzar ratio máximo Instagram (1.91:1)
        img2 = Image.open(ruta_local).convert("RGB")
        w2, h2 = img2.size
        if h2 > 0 and w2 / h2 > 1.91:
            new_w = int(h2 * 1.91)
            left  = (w2 - new_w) // 2
            img2.crop((left, 0, left + new_w, h2)).save(ruta_local, quality=90)

    except Exception:
        pass


def _convertir_a_webp(ruta_original):
    """Convierte una imagen a WebP, borra el original y retorna la nueva ruta.
    Si falla o ya es WebP, retorna la ruta original sin cambios."""
    if not ruta_original or ruta_original.endswith(".webp"):
        return ruta_original
    try:
        from PIL import Image
        ruta_webp = ruta_original.rsplit(".", 1)[0] + ".webp"
        with Image.open(ruta_original) as img:
            modo = "RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB"
            img.convert(modo).save(ruta_webp, "WEBP", quality=85, method=4)
        os.remove(ruta_original)
        return ruta_webp
    except Exception:
        return ruta_original


def _descargar_imagen_externa(url_http, nota_id, sufijo=""):
    if not url_http or not url_http.startswith("http"):
        return None
    try:
        base_dir = os.path.dirname(__file__)
        ext = url_http.split("?")[0].rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"
        filename      = f"foto-{nota_id}{sufijo}.{ext}"
        filename_webp = f"foto-{nota_id}{sufijo}.webp"
        ruta_local    = os.path.join(base_dir, "fotos", filename)
        ruta_webp     = os.path.join(base_dir, "fotos", filename_webp)
        # Si ya existe la versión webp, usar esa directamente
        if os.path.exists(ruta_webp):
            return f"fotos/{filename_webp}"
        if os.path.exists(ruta_local):
            return f"fotos/{filename}"
        req = urllib.request.Request(url_http, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            contenido = resp.read()
        if len(contenido) < 5_000:
            return None
        with open(ruta_local, "wb") as f:
            f.write(contenido)
        _recortar_banner(ruta_local)
        ruta_final = _convertir_a_webp(ruta_local)
        return f"fotos/{os.path.basename(ruta_final)}"
    except Exception:
        return None


def _foto_fallback(fotos_usadas):
    fallbacks = [
        "fotos/fitz-roy-chalten-nevada.jpg",
        "fotos/ruta-estepa-patagonica.jpg",
        "fotos/bariloche-lago-nahuel-huapi.jpg",
        "fotos/Calafate.jpg",
        "fotos/porvenir.jpg",
        "fotos/punta-arenas.jpg",
    ]
    for f in fallbacks:
        if os.path.exists(f) and f not in fotos_usadas:
            fotos_usadas.add(f)
            return f
    for f in fallbacks:
        if os.path.exists(f):
            return f
    return None


def resolver_imagen(nota, fotos_propias, fotos_usadas):
    """Jerarquía: RSS > og:image > foto propia > Unsplash > fallback. Siempre ruta local."""
    nota_id = nota.get("id", "sin-id")

    rss_url = nota.get("imagen", "")
    if rss_url and str(rss_url).startswith("http"):
        print(f"    [{nota_id}] imagen RSS...", end=" ", flush=True)
        local = _descargar_imagen_externa(rss_url, nota_id, "-rss")
        if local:
            print(f"OK → {local}")
            return local
        print("falló descarga")

    url_original = nota.get("url_original", "")
    if url_original:
        print(f"    [{nota_id}] og:image fuente...", end=" ", flush=True)
        og_img = extraer_og_image(url_original, nota_id)
        if og_img:
            print(f"OK → {og_img}")
            return og_img
        print("no encontrada")

    foto_propia = buscar_foto_propia(nota, fotos_propias)
    if foto_propia and foto_propia not in fotos_usadas:
        fotos_usadas.add(foto_propia)
        print(f"    [{nota_id}] foto propia: {foto_propia} ✓")
        return foto_propia

    keywords = nota.get("imagen_keywords", "patagonia landscape")
    print(f"    [{nota_id}] Unsplash: '{keywords}' ...", end=" ", flush=True)
    url = buscar_imagen_unsplash(keywords)
    if url:
        local = _descargar_imagen_externa(url, nota_id, "-unsplash")
        if local:
            print(f"OK → {local}")
            return local
    print("sin resultado")

    fallback = _foto_fallback(fotos_usadas)
    if fallback:
        print(f"    [{nota_id}] fallback: {fallback}")
        return fallback

    return None


# ══════════════════════════════════════════════════════════
#  NOTICIAS.JSON — CONSTRUCCIÓN CON ROTACIÓN
# ══════════════════════════════════════════════════════════

def ids_publicados_en_secciones():
    """Recolecta todos los IDs ya publicados en cualquier sección del sitio.
    Usado para evitar duplicados cross-sección en cualquier rotación."""
    base = os.path.dirname(__file__)

    def _ids(archivo, *campos):
        ids = set()
        try:
            with open(os.path.join(base, archivo), encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, list):
                for x in d:
                    ids.add(x.get("id"))
            else:
                for campo in campos:
                    v = d.get(campo)
                    if isinstance(v, dict):
                        ids.add(v.get("id"))
                    elif isinstance(v, list):
                        for x in v:
                            ids.add(x.get("id"))
        except Exception:
            pass
        return ids - {None}

    return (
        _ids("noticias.json",      "tapa", "secundarias", "noticias", "historias") |
        _ids("deportes_feed.json", "principal", "secundarias", "row_cards") |
        _ids("negocios.json") |
        _ids("turismo.json") |
        _ids("cultura.json") |
        _ids("historias.json",     "notas") |
        _ids("propios.json")
    )


def cargar_noticias_previas():
    """Carga noticias.json solo si fue generado AYER o antes (no hoy)."""
    ruta = os.path.join(os.path.dirname(__file__), "noticias.json")
    if not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        generado = data.get("generado", "")
        hoy = datetime.now().strftime("%Y-%m-%d")
        if generado.startswith(hoy):
            return {}  # Mismo día: no usar como "anterior"
        return data
    except Exception:
        return {}


def cargar_historias_permanentes():
    ruta = os.path.join(os.path.dirname(__file__), "historias.json")
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("notas", [])
    except Exception:
        return []


def construir_noticias_json(tapa, secundarias, prev_tapa, prev_secundarias, prev_noticias, ticker):
    """
    TAPA: tapa (principal) + secundarias[0] + secundarias[1]
    NOTICIAS DE LA SEMANA (8 cards):
      - [prev_tapa, prev_sec0, prev_sec1] = las 3 de ayer → pasan a posiciones 4,5,6
      - + prev_noticias[:5] → posiciones 7 al 11
      - Se eliminan las que estaban en posiciones 9,10,11 (las más antiguas)
    """
    hoy = datetime.now()

    noticias_semana = []
    if prev_tapa:
        noticias_semana.append(prev_tapa)
    for s in (prev_secundarias or [])[:2]:
        noticias_semana.append(s)
    for n in (prev_noticias or []):
        if len(noticias_semana) >= 8:
            break
        noticias_semana.append(n)

    historias = cargar_historias_permanentes()

    return {
        "generado":      hoy.isoformat(),
        "fecha_display": fecha_display(),
        "ticker":        ticker,
        "tapa":          tapa,
        "secundarias":   secundarias[:2],
        "noticias":      noticias_semana[:8],
        "historias":     historias,
    }


def guardar_json(datos):
    ruta = os.path.join(os.path.dirname(__file__), "noticias.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ noticias.json guardado")


# ══════════════════════════════════════════════════════════
#  AGENDA
# ══════════════════════════════════════════════════════════

PALABRAS_EVENTO = [
    "festival", "carrera", "maratón", "maratón", "trail", "ultratrail",
    "muestra", "exposición", "feria", "fiesta regional", "fiesta nacional",
    "congreso", "encuentro", "torneo", "campeonato", "competencia",
    "convocatoria abierta", "ciclo de cine", "ciclo cultural",
    "regata", "travesía", "expedición", "kayak", "ski", "snowboard",
    "semana de", "aniversario", "celebración", "recital", "concierto",
]


def cargar_agenda():
    ruta = os.path.join(os.path.dirname(__file__), "agenda.json")
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def guardar_agenda(eventos):
    ruta = os.path.join(os.path.dirname(__file__), "agenda.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(eventos, f, ensure_ascii=False, indent=2)


def es_evento(titulo, resumen):
    texto = (titulo + " " + resumen).lower()
    return any(kw in texto for kw in PALABRAS_EVENTO) and es_patagonica(titulo, resumen)


def actualizar_agenda(noticias_crudas):
    """Purga eventos vencidos y detecta nuevos en RSS."""
    agenda = cargar_agenda()
    hoy    = datetime.now().strftime("%Y-%m-%d")

    antes  = len(agenda)
    agenda = [e for e in agenda if (e.get("fecha_fin") or e.get("fecha", "")) >= hoy]
    purgados = antes - len(agenda)
    if purgados:
        print(f"  Agenda: {purgados} evento(s) vencido(s) eliminado(s)")

    ids_existentes = {e.get("id", "") for e in agenda}
    candidatos = [n for n in noticias_crudas if es_evento(n["titulo_original"], n["resumen_original"])]

    if not candidatos:
        print("  Agenda: sin eventos nuevos detectados en RSS")
        guardar_agenda(agenda)
        return

    print(f"  Agenda: {len(candidatos)} posible(s) evento(s) encontrado(s)")

    listado = ""
    for i, n in enumerate(candidatos[:8]):
        listado += f"""
--- Candidato {i+1} ---
Fuente: {n['fuente']} ({n['region']})
Título: {n['titulo_original']}
Resumen: {n['resumen_original']}
URL: {n['url']}
"""

    client = anthropic.Anthropic(api_key=API_KEY)
    prompt = f"""Sos el editor de agenda de GLOBALpatagonia. Hoy es {hoy}.

Analizá estas noticias y extraé SOLO las que corresponden a un evento futuro concreto (festival, carrera, muestra, fiesta, torneo, congreso, recital, certamen deportivo, etc.) con fecha definida en la Patagonia argentina o chilena. Ignorá inauguraciones de obras, nombramientos, noticias sin fecha de evento.

Noticias candidatas:
{listado}

Para cada evento válido generá un objeto JSON con estos campos exactos:
- id: slug único (ej: "festival-kayak-bariloche-2026")
- titulo: nombre del evento
- fecha: "YYYY-MM-DD" (primer día)
- fecha_fin: "YYYY-MM-DD" o null si es un solo día
- fecha_display: texto legible en español (ej: "8 al 12 de abril" o "15 de mayo")
- lugar: ciudad/lugar específico
- region: "Provincia/Región, País"
- pais: "AR" o "CL"
- categoria: "deportes" | "cultura" | "gastronomia" | "desarrollo" | "naturaleza"
- emoji: un emoji representativo
- descripcion: 1-2 oraciones descriptivas

Respondé SOLO con un array JSON válido. Si no hay eventos válidos respondé []."""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()
        if "```" in texto:
            for parte in texto.split("```"):
                p = parte.strip()
                if p.startswith("json"):
                    texto = p[4:].strip(); break
                elif p.startswith("[") or p.startswith("{"):
                    texto = p; break
        inicio = texto.find("[")
        fin    = texto.rfind("]") + 1
        if inicio >= 0 and fin > inicio:
            texto = texto[inicio:fin]
        nuevos = json.loads(texto)

        agregados = 0
        for e in nuevos:
            if e.get("id") and e["id"] not in ids_existentes and e.get("fecha", "") >= hoy:
                agenda.append(e)
                ids_existentes.add(e["id"])
                agregados += 1

        print(f"  Agenda: {agregados} evento(s) nuevo(s) agregado(s)")
    except Exception as ex:
        print(f"  Agenda: error procesando con Claude ({ex})")

    agenda.sort(key=lambda e: e.get("fecha", ""))
    guardar_agenda(agenda)


# ══════════════════════════════════════════════════════════
#  ROTACIONES DE SECCIONES
# ══════════════════════════════════════════════════════════

def es_propio(articulo):
    """Artículo de GLOBALpatagonia / J. Martineau — excluir de rotaciones automáticas."""
    fuente = articulo.get("fuente", "") or ""
    autor  = articulo.get("autor", "")  or ""
    return (
        "GLOBALpatagonia" in fuente or
        "Martineau" in autor or
        "GLOBALpatagonia" in autor or
        articulo.get("propio") is True
    )


def rotar_deportes(nota):
    """
    Cascada diaria — 7 posiciones. Recibe la nota fresca reescrita por Claude hoy.
      nueva → principal
      old principal → secundarias[0]
      old secundarias[0] → secundarias[1]
      old secundarias[1] → row_cards[0]
      old row_cards[0..2] → row_cards[1..3]
      old row_cards[3] → eliminado
    """
    if not nota:
        print("  Deportes: sin nota nueva para rotar hoy.")
        return

    ruta = os.path.join(os.path.dirname(__file__), "deportes_feed.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            feed = json.load(f)
    except Exception:
        return

    nueva = nota

    def to_card(art):
        return {
            "id":     art.get("id", ""),
            "tag":    art.get("tag", "🏃 Deportes"),
            "titulo": art.get("titulo", ""),
            "bajada": art.get("bajada", ""),
            "imagen": art.get("imagen", ""),
            "meta":   art.get("meta", ""),
        }

    old_principal   = feed.get("principal", {})
    old_secundarias = feed.get("secundarias", [])
    old_row         = feed.get("row_cards", [])

    # Nueva nota entra como principal
    feed["principal"] = to_card(nueva)

    # Construcción de nuevas secundarias
    new_sec = []
    if old_principal.get("id"):
        new_sec.append(old_principal)
    if old_secundarias:
        new_sec.append(old_secundarias[0])
    feed["secundarias"] = new_sec[:2]

    # Construcción de nueva fila (max 4)
    new_row = []
    if len(old_secundarias) > 1:
        new_row.append(old_secundarias[1])
    new_row += old_row[:3]
    feed["row_cards"] = new_row[:4]

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)
    print(f"  Deportes rotado: [{nueva['id']}] '{nueva['titulo'][:55]}…'")


def rotar_negocios(nota):
    """
    Agrega nota al frente de negocios.json. Mantiene máximo 6 (posiciones 1,2,3,5,6,7).
    Se llama cada vez que el script corre con una nota de economía/empresas.
    """
    ruta = os.path.join(os.path.dirname(__file__), "negocios.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            actual = json.load(f)
    except Exception:
        actual = []

    hoy_str = datetime.now().strftime("%d de %B de %Y")
    entrada = {
        "id":              nota.get("id", ""),
        "titulo":          nota.get("titulo", ""),
        "bajada":          nota.get("bajada", ""),
        "cuerpo":          nota.get("cuerpo", ""),
        "tag":             nota.get("tag", "💼 Economía"),
        "categoria":       nota.get("categoria", "economia"),
        "fuente":          nota.get("fuente", "GLOBALpatagonia"),
        "autor":           "Redacción GLOBALpatagonia",
        "pais":            nota.get("pais", "argentina"),
        "imagen":          nota.get("imagen", ""),
        "imagen_keywords": nota.get("imagen_keywords", ""),
        "url_original":    nota.get("url_original", ""),
        "meta":            f"Hoy · GLOBALpatagonia",
        "excluir_feed":    True,
    }

    nuevo = [entrada] + actual[:5]   # max 6
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(nuevo, f, ensure_ascii=False, indent=2)
    print(f"  Negocios rotado: [{nota.get('id')}] '{nota.get('titulo','')[:55]}…'")


def rotar_cultura(nota):
    """
    Domingos: agrega la nota fresca de Claude al frente de cultura.json.
    Mantiene máximo 6 (posiciones 1,2,3,5,6,7).
    """
    if not nota:
        return

    ruta = os.path.join(os.path.dirname(__file__), "cultura.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            cultura_actual = json.load(f)
    except Exception:
        cultura_actual = []

    entrada = {
        "id":        nota["id"],
        "titulo":    nota["titulo"],
        "bajada":    nota.get("bajada", ""),
        "imagen":    nota.get("imagen", ""),
        "tag":       nota.get("tag", "🎭 Cultura"),
        "categoria": nota.get("categoria", "cultura"),
        "meta":      nota.get("meta", ""),
        "pais":      nota.get("pais", "argentina"),
    }

    cultura_nuevo = [entrada] + cultura_actual[:5]   # max 6
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cultura_nuevo, f, ensure_ascii=False, indent=2)
    print(f"  Cultura rotada (domingo): [{nota['id']}] '{nota['titulo'][:60]}…'")


def rotar_turismo(nota):
    """
    Domingos: agrega la nota fresca de Claude al frente de turismo.json.
    Mantiene máximo 3 (posiciones 1, 2, 3).
    """
    if not nota:
        return

    ruta = os.path.join(os.path.dirname(__file__), "turismo.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            turismo_actual = json.load(f)
    except Exception:
        turismo_actual = []

    entrada = {
        "id":           nota["id"],
        "badge":        "TURISMO",
        "titulo":       nota["titulo"],
        "bajada":       nota.get("bajada", ""),
        "imagen":       nota.get("imagen", ""),
        "meta":         nota.get("meta", ""),
        "url_original": nota.get("url_original", ""),
    }

    turismo_nuevo = [entrada] + turismo_actual[:2]   # max 3
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(turismo_nuevo, f, ensure_ascii=False, indent=2)
    print(f"  Turismo rotado (domingo): [{nota['id']}] '{nota['titulo'][:60]}…'")


# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════

def main():
    # 1. Cargar historial y noticias previas (para rotación)
    historial     = cargar_historial()
    noticias_prev = cargar_noticias_previas()

    prev_tapa        = noticias_prev.get("tapa")
    prev_secundarias = noticias_prev.get("secundarias", [])
    prev_noticias    = noticias_prev.get("noticias", [])

    es_domingo = datetime.now().weekday() == 6
    print(f"\n  Historial actual: {len(historial)} artículos")
    if es_domingo:
        print("  Hoy es domingo — se actualizan Cultura y Turismo")

    # 2. Obtener noticias crudas de RSS
    noticias_crudas = fetch_noticias_crudas()

    # 3. Claude elige y reescribe notas FRESCAS del RSS para cada sección
    resultado = reescribir_con_claude(noticias_crudas, historial, es_domingo=es_domingo)
    if not resultado:
        print("\n  ✗ No se generaron artículos nuevos.\n")
        sys.exit(1)

    tapa        = resultado.get("tapa", {})
    secundarias = resultado.get("secundarias", [])[:2]
    deportes    = resultado.get("deportes")
    negocios    = resultado.get("negocios")
    cultura     = resultado.get("cultura") if es_domingo else None
    turismo     = resultado.get("turismo") if es_domingo else None
    ticker      = resultado.get("ticker", [])

    # Normalizar tag: "Medio Ambiente" → "Ambiente"
    for nota in [tapa, deportes, negocios, cultura, turismo] + secundarias:
        if nota and nota.get("tag"):
            import re
            nota["tag"] = re.sub(r"medio ambiente", "Ambiente", nota["tag"], flags=re.IGNORECASE)

    # 4. Resolver imágenes para todas las notas frescas
    notas_con_imagen = [tapa] + secundarias
    for n in [deportes, negocios, cultura, turismo]:
        if n:
            notas_con_imagen.append(n)

    fotos_propias = fotos_propias_disponibles()
    if fotos_propias:
        print(f"\n  Fotos propias en biblioteca: {len(fotos_propias)}")
    print("\n  Resolviendo imágenes...")
    fotos_usadas = set()
    for nota in notas_con_imagen:
        nota["imagen"] = resolver_imagen(nota, fotos_propias, fotos_usadas)
        if "meta" not in nota:
            nota["meta"] = f"Hoy · {nota.get('fuente','GLOBALpatagonia')}"

    # 4b. Descargar galerías internas
    print("\n  Descargando galerías...")
    for nota in notas_con_imagen:
        url = nota.get("url_original", "")
        if url and url.startswith("http"):
            galeria = extraer_galeria_articulo(url, nota["id"])
            if galeria:
                nota["galeria"] = galeria
                print(f"    [{nota['id']}] galería: {len(galeria)} foto(s)")

    # 5. Agregar al historial: tapa + secundarias + notas de sección (con cuerpo)
    extras = []
    for nota_sec in [deportes, negocios, cultura, turismo]:
        if nota_sec and nota_sec.get("cuerpo"):
            nota_sec["excluir_feed"] = True
            extras.append(nota_sec)
    historial = [tapa] + secundarias + extras + historial
    guardar_historial(historial)
    print(f"\n  Artículos nuevos en historial: {1 + len(secundarias) + len(extras)}")

    # 6. Rotaciones — cada sección recibe su nota fresca de Claude
    rotar_deportes(deportes)
    rotar_negocios(negocios) if negocios else print("  Negocios: sin nota de economía hoy.")
    rotar_cultura(cultura)   # solo si es_domingo y cultura no es None
    rotar_turismo(turismo)   # solo si es_domingo y turismo no es None

    # 7. Construir noticias.json con rotación de tapa
    datos = construir_noticias_json(
        tapa, secundarias,
        prev_tapa, prev_secundarias, prev_noticias,
        ticker
    )

    # 7b. Verificar que todas las notas en feed tienen imagen existente
    fotos_usadas_final = set()
    for art in [datos["tapa"]] + datos["secundarias"] + datos["noticias"]:
        img = art.get("imagen", "")
        if not img or not os.path.exists(img):
            fb = _foto_fallback(fotos_usadas_final)
            if fb:
                print(f"  ⚠ Sin foto: [{art.get('id')}] → fallback {fb}")
                art["imagen"] = fb
        else:
            fotos_usadas_final.add(img)

    guardar_json(datos)
    print(f"  Feed: tapa + {len(datos['secundarias'])} sec + {len(datos['noticias'])} noticias semana")

    # 8. Agenda
    print(f"\n  Actualizando agenda...")
    actualizar_agenda(noticias_crudas)

    # 9. Publicar en Telegram, Facebook e Instagram
    notas_tapa = _seleccionar_notas_binacionales(tapa, secundarias)

    # Generar imágenes con overlay de texto para Instagram
    print(f"\n  Generando imágenes para Instagram...")
    _base_dir = os.path.dirname(__file__)
    for _nota_ig in notas_tapa:
        _img_local = os.path.join(_base_dir, _nota_ig.get("imagen", ""))
        if os.path.exists(_img_local):
            _generar_imagen_ig(_img_local, _nota_ig.get("titulo", ""), _nota_ig.get("tag", ""))
    try:
        with open(os.path.join(_base_dir, "propios.json"), encoding="utf-8") as _fp:
            _propios_ig = json.load(_fp)
        if _propios_ig:
            _p0 = _propios_ig[0]
            _img_p = os.path.join(_base_dir, _p0.get("imagen", ""))
            if os.path.exists(_img_p):
                _generar_imagen_ig(_img_p, _p0.get("titulo", ""), _p0.get("tag", "📋 Informe"))
    except Exception:
        pass

    print(f"\n  Publicando en Telegram...")
    for nota in notas_tapa:
        publicar_telegram(nota)
    publicar_telegram_informe_nuevo()

    print(f"\n  Publicando en Facebook...")
    for nota in notas_tapa:
        publicar_facebook(nota)
    publicar_facebook_informe_nuevo()

    print(f"\n  Publicando en Instagram...")
    publicar_instagram(tapa)
    publicar_instagram_informe_nuevo()

    print(f"\n  ✓ Listo — {fecha_display()}")
    print(f"{'='*55}\n")


# ══════════════════════════════════════════════════════════
#  TELEGRAM
# ══════════════════════════════════════════════════════════

def _telegram_request(token, method, fields, file_path=None):
    """Hace un POST a la API de Telegram. Si file_path está presente, sube la imagen."""
    import http.client, uuid, mimetypes

    boundary = uuid.uuid4().hex
    lines = []

    for key, val in fields.items():
        lines += [
            f"--{boundary}",
            f'Content-Disposition: form-data; name="{key}"',
            "",
            str(val),
        ]

    if file_path and os.path.exists(file_path):
        filename = os.path.basename(file_path)
        mime     = mimetypes.guess_type(filename)[0] or "image/jpeg"
        with open(file_path, "rb") as f:
            img_bytes = f.read()
        lines += [
            f"--{boundary}",
            f'Content-Disposition: form-data; name="photo"; filename="{filename}"',
            f"Content-Type: {mime}",
            "",
        ]
        body = ("\r\n".join(lines) + "\r\n").encode() + img_bytes + f"\r\n--{boundary}--\r\n".encode()
    else:
        lines.append(f"--{boundary}--")
        body = "\r\n".join(lines).encode()

    conn = http.client.HTTPSConnection("api.telegram.org", timeout=20)
    conn.request(
        "POST",
        f"/bot{token}/{method}",
        body,
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = conn.getresponse()
    return json.loads(resp.read())


def publicar_telegram(tapa):
    """Publica la tapa del día en el canal de Telegram con foto."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    if not token or not channel:
        print("  Telegram: sin credenciales, se omite.")
        return

    titulo  = tapa.get("titulo", "")
    bajada  = tapa.get("bajada", "")
    nota_id = tapa.get("id", "")
    imagen  = tapa.get("imagen", "")
    pais    = tapa.get("pais", "")
    tag     = tapa.get("tag", "🗞️")

    banderas = {"argentina": "🇦🇷", "chile": "🇨🇱", "ambos": "🇦🇷🇨🇱", "malvinas": "🗺️"}
    bandera  = banderas.get(pais, "")
    link     = f"https://globalpatagonia.org/nota.html?id={nota_id}"

    # HTML es más seguro que Markdown para caracteres especiales
    caption = (
        f"{tag} {bandera}\n\n"
        f"<b>{titulo}</b>\n\n"
        f"{bajada}\n\n"
        f'<a href="{link}">Leer nota completa →</a>\n\n'
        f"<i>GLOBALpatagonia · Sur Global, principio de todo.</i>"
    )

    ruta_img = os.path.join(os.path.dirname(__file__), imagen) if imagen else ""
    ruta_img = ruta_img if os.path.exists(ruta_img) else ""

    try:
        if ruta_img:
            resultado = _telegram_request(token, "sendPhoto", {
                "chat_id":    channel,
                "caption":    caption,
                "parse_mode": "HTML",
            }, file_path=ruta_img)
        else:
            resultado = _telegram_request(token, "sendMessage", {
                "chat_id":                  channel,
                "text":                     caption,
                "parse_mode":               "HTML",
                "disable_web_page_preview": "false",
            })

        if resultado.get("ok"):
            print(f"  Telegram OK ✓ [{nota_id}]")
        else:
            print(f"  Telegram error: {resultado.get('description')}")
    except Exception as e:
        print(f"  Telegram falló: {e}")


def publicar_telegram_informe_nuevo():
    """Publica en Telegram el informe más reciente de propios.json si es nuevo."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    if not token or not channel:
        return

    base_dir   = os.path.dirname(__file__)
    state_path = os.path.join(base_dir, "telegram_state.json")
    propios_path = os.path.join(base_dir, "propios.json")

    try:
        with open(propios_path, encoding="utf-8") as f:
            propios = json.load(f)
    except Exception:
        return

    if not propios:
        return

    informe = propios[0]
    informe_id = informe.get("id", "")

    # Leer último informe publicado
    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}

    if state.get("ultimo_informe_telegram") == informe_id:
        return  # Ya publicado

    titulo = informe.get("titulo", "")
    bajada = informe.get("bajada", "")
    imagen = informe.get("imagen", "")
    tag    = informe.get("tag", "📋 Informe")
    link   = f"https://globalpatagonia.org/nota.html?id={informe_id}"

    caption = (
        f"{tag}\n\n"
        f"<b>{titulo}</b>\n\n"
        f"{bajada}\n\n"
        f'<a href="{link}">Leer informe completo →</a>\n\n'
        f"<i>GLOBALpatagonia · Sur Global, principio de todo.</i>"
    )

    ruta_img = os.path.join(base_dir, imagen) if imagen else ""
    ruta_img = ruta_img if os.path.exists(ruta_img) else ""

    try:
        if ruta_img:
            resultado = _telegram_request(token, "sendPhoto", {
                "chat_id":    channel,
                "caption":    caption,
                "parse_mode": "HTML",
            }, file_path=ruta_img)
        else:
            resultado = _telegram_request(token, "sendMessage", {
                "chat_id":    channel,
                "text":       caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": "false",
            })

        if resultado.get("ok"):
            state["ultimo_informe_telegram"] = informe_id
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print(f"  Telegram informe OK ✓ [{informe_id}]")
        else:
            print(f"  Telegram informe error: {resultado.get('description')}")
    except Exception as e:
        print(f"  Telegram informe falló: {e}")


def _seleccionar_notas_binacionales(tapa, secundarias):
    """De tapa + secundarias, devuelve [nota_argentina, nota_chilena].
    Si no hay una de cada país, devuelve las dos primeras disponibles."""
    todas = [n for n in ([tapa] + list(secundarias)) if n]
    ar = next((n for n in todas if n.get("pais") == "argentina"), None)
    cl = next((n for n in todas if n.get("pais") == "chile"), None)

    # Si hay una de cada país, publicar ambas
    if ar and cl:
        return [ar, cl]
    # Si solo hay de un país, publicar las dos primeras disponibles
    return todas[:2] if len(todas) >= 2 else todas


def publicar_facebook(tapa):
    """Publica la tapa del día en la página de Facebook con foto y link."""
    page_id    = os.environ.get("FACEBOOK_PAGE_ID", "")
    page_token = os.environ.get("FACEBOOK_PAGE_TOKEN", "")
    if not page_id or not page_token:
        print("  Facebook: sin credenciales, se omite.")
        return

    titulo  = tapa.get("titulo", "")
    bajada  = tapa.get("bajada", "")
    nota_id = tapa.get("id", "")
    imagen  = tapa.get("imagen", "")
    pais    = tapa.get("pais", "")

    banderas = {"argentina": "🇦🇷", "chile": "🇨🇱", "ambos": "🇦🇷🇨🇱", "malvinas": "🗺️"}
    bandera  = banderas.get(pais, "")
    link     = f"https://globalpatagonia.org/nota.html?id={nota_id}"

    mensaje = (
        f"{bandera} {titulo}\n\n"
        f"{bajada}\n\n"
        f"🔗 {link}\n\n"
        f"GLOBALpatagonia · Sur Global, principio de todo.\n"
        f"globalpatagonia.org"
    )

    ruta_img = os.path.join(os.path.dirname(__file__), imagen) if imagen else ""
    ruta_img = ruta_img if os.path.exists(ruta_img) else ""

    # Convertir WebP a JPEG si es necesario (Facebook no acepta WebP)
    jpg_tmp = None
    if ruta_img and ruta_img.lower().endswith(".webp"):
        import tempfile, subprocess
        jpg_tmp  = tempfile.mktemp(suffix=".jpg")
        resultado_conv = subprocess.run(
            ["magick", ruta_img, "-quality", "88", jpg_tmp],
            capture_output=True
        )
        if resultado_conv.returncode == 0 and os.path.exists(jpg_tmp):
            ruta_img = jpg_tmp
        else:
            ruta_img = ""

    try:
        api_url = f"https://graph.facebook.com/v21.0/{page_id}"

        if ruta_img:
            # Publicar con foto via /photos
            with open(ruta_img, "rb") as img_file:
                boundary = "----PatagoniaGLOBAL"
                body = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="caption"\r\n\r\n'
                    f"{mensaje}\r\n"
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="access_token"\r\n\r\n'
                    f"{page_token}\r\n"
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="source"; filename="foto.jpg"\r\n'
                    f"Content-Type: image/jpeg\r\n\r\n"
                ).encode() + img_file.read() + f"\r\n--{boundary}--\r\n".encode()

            if jpg_tmp and os.path.exists(jpg_tmp):
                os.unlink(jpg_tmp)

            req = urllib.request.Request(
                f"{api_url}/photos",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST"
            )
        else:
            # Publicar solo texto + link
            data = urllib.parse.urlencode({
                "message":      mensaje,
                "link":         link,
                "access_token": page_token,
            }).encode()
            req = urllib.request.Request(f"{api_url}/feed", data=data, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resultado = json.loads(resp.read().decode())
            if resultado.get("id"):
                print(f"  Facebook OK ✓ [{nota_id}]")
            else:
                print(f"  Facebook error: {resultado}")
        except urllib.error.HTTPError as http_err:
            detalle = http_err.read().decode("utf-8", errors="replace")
            print(f"  Facebook falló {http_err.code}: {detalle}")

    except Exception as e:
        print(f"  Facebook falló: {e}")


def publicar_facebook_informe_nuevo():
    """Publica en Facebook el informe más reciente de propios.json si es nuevo."""
    page_id    = os.environ.get("FACEBOOK_PAGE_ID", "")
    page_token = os.environ.get("FACEBOOK_PAGE_TOKEN", "")
    if not page_id or not page_token:
        return

    base_dir     = os.path.dirname(__file__)
    state_path   = os.path.join(base_dir, "telegram_state.json")
    propios_path = os.path.join(base_dir, "propios.json")

    try:
        with open(propios_path, encoding="utf-8") as f:
            propios = json.load(f)
    except Exception:
        return

    if not propios:
        return

    informe    = propios[0]
    informe_id = informe.get("id", "")

    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}

    if state.get("ultimo_informe_facebook") == informe_id:
        return  # Ya publicado

    titulo = informe.get("titulo", "")
    bajada = informe.get("bajada", "")
    imagen = informe.get("imagen", "")
    tag    = informe.get("tag", "📋 Informe")
    link   = f"https://globalpatagonia.org/nota.html?id={informe_id}"

    mensaje = (
        f"{tag} {titulo}\n\n"
        f"{bajada}\n\n"
        f"🔗 {link}\n\n"
        f"GLOBALpatagonia · Sur Global, principio de todo.\n"
        f"globalpatagonia.org"
    )

    ruta_img = os.path.join(base_dir, imagen) if imagen else ""
    ruta_img = ruta_img if os.path.exists(ruta_img) else ""

    # Convertir WebP a JPEG si es necesario (Facebook no acepta WebP)
    jpg_tmp = None
    if ruta_img and ruta_img.lower().endswith(".webp"):
        import tempfile, subprocess
        jpg_tmp  = tempfile.mktemp(suffix=".jpg")
        resultado_conv = subprocess.run(
            ["magick", ruta_img, "-quality", "88", jpg_tmp],
            capture_output=True
        )
        if resultado_conv.returncode == 0 and os.path.exists(jpg_tmp):
            ruta_img = jpg_tmp
        else:
            ruta_img = ""

    try:
        api_url = f"https://graph.facebook.com/v21.0/{page_id}"

        if ruta_img:
            boundary = "----PatagoniaGLOBAL"
            with open(ruta_img, "rb") as img_file:
                body = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="caption"\r\n\r\n'
                    f"{mensaje}\r\n"
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="access_token"\r\n\r\n'
                    f"{page_token}\r\n"
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="source"; filename="foto.jpg"\r\n'
                    f"Content-Type: image/jpeg\r\n\r\n"
                ).encode() + img_file.read() + f"\r\n--{boundary}--\r\n".encode()

            if jpg_tmp and os.path.exists(jpg_tmp):
                os.unlink(jpg_tmp)

            req = urllib.request.Request(
                f"{api_url}/photos",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST"
            )
        else:
            data = urllib.parse.urlencode({
                "message":      mensaje,
                "link":         link,
                "access_token": page_token,
            }).encode()
            req = urllib.request.Request(f"{api_url}/feed", data=data, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resultado = json.loads(resp.read().decode())
            if resultado.get("id"):
                state["ultimo_informe_facebook"] = informe_id
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                print(f"  Facebook informe OK ✓ [{informe_id}]")
            else:
                print(f"  Facebook informe error: {resultado}")
        except urllib.error.HTTPError as http_err:
            detalle = http_err.read().decode("utf-8", errors="replace")
            print(f"  Facebook informe falló {http_err.code}: {detalle}")

    except Exception as e:
        print(f"  Facebook informe falló: {e}")



def _generar_imagen_ig(ruta_local, titulo, tag=""):
    """Genera imagen cuadrada 1080×1080 con overlay de texto para Instagram.
    Guarda como {base}_ig.jpg junto al original. Retorna la ruta o None si falla."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap as tw_mod, os as _os, numpy as np

        # ── Cargar y recortar a cuadrado 1:1 ────────────────────────────────────────────────
        img = Image.open(ruta_local).convert("RGB")
        w, h = img.size
        lado = min(w, h)
        left = (w - lado) // 2
        top  = (h - lado) // 2
        img  = img.crop((left, top, left + lado, top + lado))
        img  = img.resize((1080, 1080), Image.LANCZOS)

        # ── Gradiente oscuro en mitad inferior ────────────────────────────────────────────
        arr = np.array(img, dtype=np.float32)
        grad_start = 480
        azul = np.array([28, 45, 61], dtype=np.float32)
        for y in range(grad_start, 1080):
            t     = (y - grad_start) / (1080 - grad_start)
            alpha = t * 0.85
            arr[y] = arr[y] * (1 - alpha) + azul * alpha
        img  = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
        draw = ImageDraw.Draw(img)

        # ── Colores paleta GLOBALpatagonia ──────────────────────────────────────────
        C_TITULO = (240, 237, 232)   # #f0ede8 crema
        C_TAG    = (122, 173, 204)   # #7aadcc azul glacial
        C_MARCA  = (180, 177, 172)   # crema suave para watermark
        C_SHADOW = (10,  20,  30)    # sombra casi negra

        # ── Fuentes (disponibles en Ubuntu/GitHub Actions) ──────────────────────
        def _fuente(paths, size):
            for p in paths:
                if _os.path.exists(p):
                    try:
                        return ImageFont.truetype(p, size)
                    except Exception:
                        pass
            return ImageFont.load_default()

        font_titulo = _fuente([
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
        ], 66)
        font_tag = _fuente([
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ], 34)
        font_marca = _fuente([
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ], 26)

        # ── Wrap dinámico del título (max 3 líneas, ~950px ancho) ────────────────────────
        MAX_PX   = 940
        titulo_s = titulo.replace("\n", " ").strip()
        words    = titulo_s.split()
        lines    = []
        current  = ""
        for idx_w, word in enumerate(words):
            test = (current + " " + word).strip() if current else word
            bb   = draw.textbbox((0, 0), test, font=font_titulo)
            if bb[2] - bb[0] <= MAX_PX:
                current = test
            else:
                if current:
                    lines.append(current)
                if len(lines) >= 2:
                    # Línea 3: juntar todas las palabras restantes
                    remaining = word + " " + " ".join(words[idx_w+1:])
                    current = remaining.strip()
                    break
                current = word
        if current:
            lines.append(current)
        lines = lines[:3]
        # Truncar última línea con ellipsis si sobrepasa el ancho
        if lines:
            last = lines[-1]
            bb   = draw.textbbox((0, 0), last, font=font_titulo)
            if bb[2] - bb[0] > MAX_PX:
                while " " in last:
                    last = last.rsplit(" ", 1)[0]
                    bb   = draw.textbbox((0, 0), last + "…", font=font_titulo)
                    if bb[2] - bb[0] <= MAX_PX:
                        break
                lines[-1] = last + "…"

        # ── Calcular posición del bloque de texto ──────────────────────────────────────────────────────
        LINE_H   = 82
        total_h  = len(lines) * LINE_H
        tag_area = 58 if tag else 0
        texto_y  = 1080 - 52 - total_h - tag_area

        # ── Badge de tag ─────────────────────────────────────────────────────────────────────
        if tag:
            tag_txt  = tag.strip()
            bb_tag   = draw.textbbox((0, 0), tag_txt, font=font_tag)
            tag_w    = bb_tag[2] - bb_tag[0] + 30
            tag_h    = bb_tag[3] - bb_tag[1] + 14
            tag_x, tag_y = 48, texto_y - tag_h - 12
            draw.rectangle([(tag_x, tag_y), (tag_x + tag_w, tag_y + tag_h)], fill=C_TAG)
            draw.text((tag_x + 15, tag_y + 7), tag_txt, font=font_tag, fill=(28, 45, 61))

        # ── Título ───────────────────────────────────────────────────────────────────────────────
        for linea in lines:
            draw.text((50, texto_y + 2), linea, font=font_titulo, fill=C_SHADOW)
            draw.text((48, texto_y),     linea, font=font_titulo, fill=C_TITULO)
            texto_y += LINE_H

        # ── Marca GLOBALpatagonia (esquina inferior derecha) ────────────────────────────────────────────────────────
        marca   = "GLOBALpatagonia"
        bb_m    = draw.textbbox((0, 0), marca, font=font_marca)
        marca_w = bb_m[2] - bb_m[0]
        draw.text((1080 - marca_w - 30, 1080 - 40), marca, font=font_marca, fill=C_MARCA)

        # ── Guardar _ig.jpg ──────────────────────────────────────────────────────────────────────────────────
        base    = ruta_local.rsplit(".", 1)[0]
        ruta_ig = base + "_ig.jpg"
        img.save(ruta_ig, "JPEG", quality=92)
        print(f"  IG overlay → {_os.path.basename(ruta_ig)}")
        return ruta_ig

    except Exception as e:
        print(f"  _generar_imagen_ig falló: {e}")
        return None

# ══════════════════════════════════════════════════════════
#  INSTAGRAM
# ══════════════════════════════════════════════════════════

def publicar_instagram(tapa):
    """Publica la tapa del día en Instagram Business via Graph API (2 pasos: container → publish)."""
    ig_user_id   = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    access_token = os.environ.get("FACEBOOK_PAGE_TOKEN", "")
    if not ig_user_id or not access_token:
        print("  Instagram: sin credenciales, se omite.")
        return

    titulo  = tapa.get("titulo", "")
    bajada  = tapa.get("bajada", "")
    nota_id = tapa.get("id", "")
    imagen  = tapa.get("imagen", "")
    pais    = tapa.get("pais", "")

    if not imagen:
        print("  Instagram: sin imagen, se omite.")
        return

    banderas  = {"argentina": "🇦🇷", "chile": "🇨🇱", "ambos": "🇦🇷🇨🇱", "malvinas": "🗺️"}
    bandera   = banderas.get(pais, "")
    base_dir  = os.path.dirname(__file__)
    imagen_ig = imagen.rsplit(".", 1)[0] + "_ig.jpg"
    if os.path.exists(os.path.join(base_dir, imagen_ig)):
        image_url = f"https://globalpatagonia.org/{imagen_ig}"
    else:
        image_url = f"https://globalpatagonia.org/{imagen}"

    caption = (
        f"{bandera} {titulo}\n\n"
        f"{bajada}\n\n"
        f"🔗 Nota completa en bio\n\n"
        f"#Patagonia #PatagoniaGlobal #Noticias #SurGlobal #GLOBALpatagonia"
    )

    try:
        api_base = f"https://graph.facebook.com/v21.0/{ig_user_id}"

        # Paso 1: crear media container
        data = urllib.parse.urlencode({
            "image_url":    image_url,
            "caption":      caption,
            "access_token": access_token,
        }).encode()
        req = urllib.request.Request(f"{api_base}/media", data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resultado = json.loads(resp.read().decode())
        except urllib.error.HTTPError as http_err:
            detalle = http_err.read().decode("utf-8", errors="replace")
            print(f"  Instagram container falló {http_err.code}: {detalle}")
            return

        creation_id = resultado.get("id")
        if not creation_id:
            print(f"  Instagram container error: {resultado}")
            return

        # Esperar a que el container esté listo (poll de status)
        import time
        for intento in range(12):
            time.sleep(5)
            try:
                poll_url = (f"https://graph.facebook.com/v21.0/{creation_id}"
                            f"?fields=status_code&access_token={access_token}")
                req_poll = urllib.request.Request(poll_url)
                with urllib.request.urlopen(req_poll, timeout=15) as rp:
                    status_data = json.loads(rp.read().decode())
                status_code = status_data.get("status_code", "")
                if status_code == "FINISHED":
                    break
                if status_code == "ERROR":
                    print(f"  Instagram container ERROR de procesamiento")
                    return
            except Exception:
                pass
        else:
            print(f"  Instagram container timeout (no FINISHED)")
            return

        # Paso 2: publicar el container
        data = urllib.parse.urlencode({
            "creation_id":  creation_id,
            "access_token": access_token,
        }).encode()
        req = urllib.request.Request(f"{api_base}/media_publish", data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resultado = json.loads(resp.read().decode())
            if resultado.get("id"):
                print(f"  Instagram OK ✓ [{nota_id}]")
            else:
                print(f"  Instagram publish error: {resultado}")
        except urllib.error.HTTPError as http_err:
            detalle = http_err.read().decode("utf-8", errors="replace")
            print(f"  Instagram publish falló {http_err.code}: {detalle}")

    except Exception as e:
        print(f"  Instagram falló: {e}")


def publicar_instagram_informe_nuevo():
    """Publica en Instagram el informe más reciente de propios.json si es nuevo."""
    ig_user_id   = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    access_token = os.environ.get("FACEBOOK_PAGE_TOKEN", "")
    if not ig_user_id or not access_token:
        return

    base_dir     = os.path.dirname(__file__)
    state_path   = os.path.join(base_dir, "telegram_state.json")
    propios_path = os.path.join(base_dir, "propios.json")

    try:
        with open(propios_path, encoding="utf-8") as f:
            propios = json.load(f)
    except Exception:
        return

    if not propios:
        return

    informe    = propios[0]
    informe_id = informe.get("id", "")

    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}

    if state.get("ultimo_informe_instagram") == informe_id:
        return  # Ya publicado

    titulo = informe.get("titulo", "")
    bajada = informe.get("bajada", "")
    imagen = informe.get("imagen", "")
    tag    = informe.get("tag", "📋 Informe")

    if not imagen:
        return

    base_dir_i  = os.path.dirname(__file__)
    imagen_ig_i = imagen.rsplit(".", 1)[0] + "_ig.jpg"
    if os.path.exists(os.path.join(base_dir_i, imagen_ig_i)):
        image_url = f"https://globalpatagonia.org/{imagen_ig_i}"
    else:
        image_url = f"https://globalpatagonia.org/{imagen}"
    caption = (
        f"{tag} {titulo}\n\n"
        f"{bajada}\n\n"
        f"🔗 Nota completa en bio\n\n"
        f"#Patagonia #PatagoniaGlobal #Informe #SurGlobal #GLOBALpatagonia"
    )

    try:
        api_base = f"https://graph.facebook.com/v21.0/{ig_user_id}"

        # Paso 1: crear container
        data = urllib.parse.urlencode({
            "image_url":    image_url,
            "caption":      caption,
            "access_token": access_token,
        }).encode()
        req = urllib.request.Request(f"{api_base}/media", data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resultado = json.loads(resp.read().decode())
        except urllib.error.HTTPError as http_err:
            detalle = http_err.read().decode("utf-8", errors="replace")
            print(f"  Instagram informe container falló {http_err.code}: {detalle}")
            return

        creation_id = resultado.get("id")
        if not creation_id:
            print(f"  Instagram informe container error: {resultado}")
            return

        # Esperar a que el container esté listo
        import time
        for intento in range(12):
            time.sleep(5)
            try:
                poll_url = (f"https://graph.facebook.com/v21.0/{creation_id}"
                            f"?fields=status_code&access_token={access_token}")
                req_poll = urllib.request.Request(poll_url)
                with urllib.request.urlopen(req_poll, timeout=15) as rp:
                    status_data = json.loads(rp.read().decode())
                status_code = status_data.get("status_code", "")
                if status_code == "FINISHED":
                    break
                if status_code == "ERROR":
                    print(f"  Instagram informe container ERROR")
                    return
            except Exception:
                pass
        else:
            print(f"  Instagram informe container timeout")
            return

        # Paso 2: publicar
        data = urllib.parse.urlencode({
            "creation_id":  creation_id,
            "access_token": access_token,
        }).encode()
        req = urllib.request.Request(f"{api_base}/media_publish", data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resultado = json.loads(resp.read().decode())
            if resultado.get("id"):
                state["ultimo_informe_instagram"] = informe_id
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                print(f"  Instagram informe OK ✓ [{informe_id}]")
            else:
                print(f"  Instagram informe publish error: {resultado}")
        except urllib.error.HTTPError as http_err:
            detalle = http_err.read().decode("utf-8", errors="replace")
            print(f"  Instagram informe publish falló {http_err.code}: {detalle}")

    except Exception as e:
        print(f"  Instagram informe falló: {e}")


def solo_instagram():
    """Modo post-push: lee noticias.json y publica en Instagram."""
    base_dir      = os.path.dirname(__file__)
    noticias_path = os.path.join(base_dir, "noticias.json")
    try:
        with open(noticias_path, encoding="utf-8") as f:
            noticias = json.load(f)
    except Exception as e:
        print(f"  Instagram (post-push): no se pudo leer noticias.json — {e}")
        return
    tapa        = noticias.get("tapa", {})
    secundarias = noticias.get("secundarias", [])
    notas_ig    = _seleccionar_notas_binacionales(tapa, secundarias)

    for nota_ig in notas_ig:
        pais_ig = nota_ig.get("pais", "")
        print(f"\n  Publicando nota ({pais_ig}) en Instagram (post-push)…")
        publicar_instagram(nota_ig)

    print("\n  Publicando informe en Instagram (post-push)…")
    publicar_instagram_informe_nuevo()

    print("\n  ✓ Instagram post-push listo")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--solo-instagram":
        solo_instagram()
    else:
        main()
