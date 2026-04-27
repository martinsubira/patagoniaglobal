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
import re
import unicodedata
import urllib.request
import urllib.parse
from datetime import datetime


def slugify(text, max_len=55):
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode()
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    if len(text) > max_len:
        cut = text[:max_len]
        last_dash = cut.rfind('-')
        text = cut[:last_dash] if last_dash > max_len // 2 else cut
    return text

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
BREVO_API_KEY       = os.environ.get("BREVO_API_KEY", "")
BREVO_LIST_ID       = 3

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
    {"nombre": "El Magallánico",          "url": "https://www.elmagallanico.com/feed/",                  "region": "Magallanes"},
    {"nombre": "Diálogo Sur",             "url": "https://dialogosur.cl/feed/",                          "region": "Magallanes"},
    # ── Chile · Antártica ──
    {"nombre": "INACH",                   "url": "https://www.inach.cl/feed/",                           "region": "Antártica Chile"},
    # ── Islas Malvinas / Falkland Islands ──
    {"nombre": "Penguin News",            "url": "https://penguin-news.com/feed/",                        "region": "Malvinas", "idioma": "en"},
    # ── Deportes de aventura patagónicos ──
    {"nombre": "Club Andino Bariloche",   "url": "https://clubandino.org/feed/",                         "region": "Bariloche"},
    {"nombre": "Catedral Alta Patagonia", "url": "https://www.catedralaltapatagonia.com/feed/",           "region": "Bariloche"},
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
    "inach", "instituto antártico chileno",
    "rompehielos", "buque oceanográfico", "buque patrulla",
    "soberanía antártica", "tratado antártico",
    "isla de los estados", "isla grande de tierra del fuego",
    "canal beagle", "paso drake", "cabo de hornos",
    # Islas disputadas / soberanía austral
    "isla decepción", "islas orcadas", "orcadas del sur", "base orcadas",
    "isla picton", "isla lenox", "isla nueva", "picton lenox nueva",
    "islas del pacífico sur", "isla diego ramírez",
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


def _id_a_año_mes(nid):
    """Extrae YYYY-MM del ID de nota: '20260416-1210-tapa' → '2026-04'."""
    import re
    m = re.match(r'^(\d{4})(\d{2})\d{2}-', str(nid))
    return f"{m.group(1)}-{m.group(2)}" if m else None


def guardar_historial(articulos):
    """Guarda los últimos MAX_HISTORIAL artículos. Los que salen van a archivo/YYYY-MM.json."""
    base         = os.path.dirname(__file__)
    path         = os.path.join(base, "historial.json")
    archivo_dir  = os.path.join(base, "archivo")
    os.makedirs(archivo_dir, exist_ok=True)

    descartadas = articulos[MAX_HISTORIAL:]
    if descartadas:
        # Agrupar por año-mes según el ID
        por_mes = {}
        for nota in descartadas:
            ym = _id_a_año_mes(nota.get("id", "")) or datetime.now().strftime("%Y-%m")
            por_mes.setdefault(ym, []).append(nota)

        total_nuevas = 0
        for ym, notas_mes in sorted(por_mes.items()):
            path_mes = os.path.join(archivo_dir, f"{ym}.json")
            try:
                with open(path_mes, encoding="utf-8") as f:
                    existentes = json.load(f)
            except Exception:
                existentes = []
            ids_existentes = {n.get("id") for n in existentes}
            nuevas = [n for n in notas_mes if n.get("id") not in ids_existentes]
            if nuevas:
                existentes.extend(nuevas)
                with open(path_mes, "w", encoding="utf-8") as f:
                    json.dump(existentes, f, ensure_ascii=False, indent=2)
                total_nuevas += len(nuevas)
        if total_nuevas:
            print(f"  → {total_nuevas} nota(s) archivadas en archivo/YYYY-MM.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(articulos[:MAX_HISTORIAL], f, ensure_ascii=False, indent=2)


def actualizar_search_index():
    """Construye/actualiza search-index.json con todas las notas publicadas."""
    base       = os.path.dirname(__file__)
    index_path = os.path.join(base, "search-index.json")

    try:
        with open(index_path, encoding="utf-8") as f:
            indice = json.load(f)
    except Exception:
        indice = []

    ids_existentes = {n["id"] for n in indice if n.get("id")}
    nuevas = []

    def _agregar(nota):
        nid = nota.get("id")
        if not nid or nid in ids_existentes:
            return
        ids_existentes.add(nid)
        nuevas.append({
            "id":       nid,
            "titulo":   nota.get("titulo", ""),
            "bajada":   nota.get("bajada", ""),
            "fecha":    nota.get("fecha", ""),
            "categoria": nota.get("categoria", nota.get("tag", "")),
            "imagen":   nota.get("imagen", ""),
        })

    fuentes = [
        "historial.json", "noticias.json", "historias.json",
        "turismo.json", "deportes_feed.json", "propios.json",
        "propios_historial.json", "negocios.json", "guias.json",
    ]
    for nombre in fuentes:
        ruta = os.path.join(base, nombre)
        if not os.path.exists(ruta):
            continue
        try:
            with open(ruta, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if data.get("tapa"):
                    _agregar(data["tapa"])
                for clave in ("secundarias", "noticias", "historias", "notas"):
                    for n in data.get(clave, []):
                        _agregar(n)
            elif isinstance(data, list):
                for n in data:
                    _agregar(n)
        except Exception:
            pass

    # Escanear archivo/YYYY-MM.json
    archivo_dir = os.path.join(base, "archivo")
    if os.path.isdir(archivo_dir):
        for fname in sorted(os.listdir(archivo_dir)):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(archivo_dir, fname), encoding="utf-8") as f:
                        for n in json.load(f):
                            _agregar(n)
                except Exception:
                    pass

    # Migración: leer archivo.json legado si existe
    archivo_legado = os.path.join(base, "archivo.json")
    if os.path.exists(archivo_legado):
        try:
            with open(archivo_legado, encoding="utf-8") as f:
                data = json.load(f)
            for n in data.get("notas", []):
                _agregar(n)
        except Exception:
            pass

    if nuevas:
        indice = nuevas + indice
        indice.sort(key=lambda n: n.get("fecha", ""), reverse=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(indice, f, ensure_ascii=False, indent=2)
        print(f"  → {len(nuevas)} nota(s) agregadas al índice ({len(indice)} total)")
    else:
        print(f"  → Índice de búsqueda sin cambios ({len(indice)} notas)")


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
✓ Deportes Patagónicos: SOLO deportes que se practican en o son distintivos de la Patagonia — trail running, escalada en roca/hielo, kayak de mar/río, ski/snowboard, mountainbike de montaña, triatlón, carreras de aventura, andinismo, trekking de larga distancia, surf en costas patagónicas, natación en aguas frías/lagos. DESCARTAR: rugby, fútbol, básquet, tenis, athletics, cualquier deporte de equipo nacional o internacional sin anclaje patagónico concreto (ej: Los Pumas, selección argentina, torneos nacionales).
✓ Desarrollo & Producción: economía regional, pesca, ganadería, energía, infraestructura, conectividad
✓ Cultura: arte, música, identidad, historia, gastronomía, fiestas regionales, pioneros
✓ Ciencia & Tecnología: hallazgos CONICET, paleontología, innovación aplicada al territorio
✓ Turismo & Guías: destinos, temporadas, premios internacionales a Patagonia
✓ Negocios: empresas, producción, pesca comercial, energía, comercio, economía regional
✓ Atlántico Sur & Antártida: Malvinas, Georgias del Sur, Sándwich del Sur, Orcadas del Sur, isla Decepción, islas Picton/Lenox/Nueva, base antártica, soberanía, expediciones, tratado antártico, buques, paso Drake, canal Beagle, isla de los Estados. INACH (Instituto Antártico Chileno): sus notas son de alta prioridad — investigación científica, expediciones, biodiversidad antártica.

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
- DEPORTES — criterio excluyente: la nota debe ser sobre un deporte que se practica EN la Patagonia o es identitario de la región: trail running, escalada en roca/hielo, kayak de mar o río, ski/snowboard en cerros patagónicos, mountainbike de montaña, triatlón, carreras de aventura, andinismo, trekking, surf costero, natación en lagos/ríos/mar patagónico. VETO ABSOLUTO (poné null si solo hay estas): rugby (incluyendo Los Pumas, Los Pumas 7s, URBA, selección argentina de rugby), fútbol (cualquier liga, cualquier equipo, cualquier selección), básquet, tenis, atletismo de pista, selecciones nacionales de cualquier deporte, torneos nacionales/internacionales de deportes convencionales (SVNS, Hong Kong Sevens, Sudamericano de atletismo, etc.). Un deporte es patagónico si el EVENTO o el ATLETA es de una ciudad o provincia de la Patagonia — no alcanza con que el deportista sea "argentino". Si la nota de deportes no cumple este criterio, poné null aunque haya notas disponibles.
- Cada sección debe usar una noticia DISTINTA (URLs diferentes).
- Si no hay nota de deportes patagónicos disponible hoy, poné null en "deportes".
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
    """Busca la foto propia más relevante para una nota.

    Scoring (acumulativo):
    - keyword de la foto aparece en imagen_keywords de la nota (+2 por match exacto de palabra, +1 por substring)
    - keyword de la foto aparece en el título de la nota (+2)
    - keyword de la foto aparece en fuente/pais de la nota (+1)

    Retorna (ruta, score) — score 0 significa sin match."""
    import re as _re

    def _tokenize(s):
        return set(_re.findall(r'[a-záéíóúüñ]+', s.lower())) if s else set()

    kw_img   = nota.get("imagen_keywords", "").lower()
    titulo   = nota.get("titulo", "").lower()
    fuente   = nota.get("fuente", "").lower()
    pais     = nota.get("pais", "").lower()
    contexto = f"{kw_img} {titulo} {fuente} {pais}"

    tokens_kw     = _tokenize(kw_img)
    tokens_titulo = _tokenize(titulo)

    mejor = None
    mejor_score = 0

    for foto in fotos:
        score = 0
        for kw in foto.get("keywords", []):
            kw_l      = kw.lower()
            tokens_kw_foto = _tokenize(kw_l)
            # Match exacto de palabra (todos los tokens del keyword están en el contexto)
            if tokens_kw_foto and tokens_kw_foto.issubset(_tokenize(contexto)):
                score += 2 * len(tokens_kw_foto)
            # Match de substrings en imagen_keywords
            elif kw_l in kw_img:
                score += 1
            # Match en título (más peso)
            if tokens_kw_foto and tokens_kw_foto.issubset(tokens_titulo):
                score += 2
        if score > mejor_score:
            mejor_score = score
            mejor = foto

    if mejor and mejor_score > 0:
        return f"fotos/{mejor['archivo']}", mejor_score
    return None, 0


def _unsplash_query(keywords):
    try:
        query = urllib.parse.quote(keywords)
        url   = f"https://api.unsplash.com/search/photos?query={query}&per_page=5&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}"
        req   = urllib.request.Request(url, headers={"Accept-Version": "v1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data    = json.loads(resp.read())
            results = data.get("results", [])
            if results:
                return results[0]["urls"]["full"]
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
        # Descartar imágenes demasiado pequeñas (píxeles insuficientes para lucir bien)
        try:
            from PIL import Image as _PilChk
            with _PilChk.open(ruta_final) as _im:
                w, h = _im.size
            if w < 600 or h < 400:
                print(f"muy pequeña ({w}×{h}), descartada")
                for _f in (ruta_final, ruta_local):
                    try: os.remove(_f)
                    except FileNotFoundError: pass
                return None
        except Exception:
            pass
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
        print("falló/descartada → buscando alternativa")

    url_original = nota.get("url_original", "")
    if url_original:
        print(f"    [{nota_id}] og:image fuente...", end=" ", flush=True)
        og_img = extraer_og_image(url_original, nota_id)
        if og_img:
            print(f"OK → {og_img}")
            return og_img
        print("no encontrada")

    foto_propia, foto_score = buscar_foto_propia(nota, fotos_propias)
    if foto_propia:
        # Si hay match real (score > 0), usar la foto aunque ya fue usada por otra nota.
        # Solo respetar fotos_usadas cuando no hay match (fallback aleatorio).
        fotos_usadas.add(foto_propia)
        print(f"    [{nota_id}] foto propia: {foto_propia} (score {foto_score}) ✓")
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
    """
    Gestiona noticias_ayer.json: la PRIMERA vez que corre en el día copia
    noticias.json (= estado de ayer) a noticias_ayer.json y lo marca con la
    fecha. Re-runs del mismo día reusan noticias_ayer.json sin re-copiarlo,
    evitando que el segundo run borre la acumulación de tarjetas.
    """
    base         = os.path.dirname(__file__)
    ruta_actual  = os.path.join(base, "noticias.json")
    ruta_ayer    = os.path.join(base, "noticias_ayer.json")
    hoy          = datetime.now().strftime("%Y-%m-%d")

    # Si ya existe noticias_ayer.json copiado HOY → usarlo directamente
    if os.path.exists(ruta_ayer):
        try:
            with open(ruta_ayer, encoding="utf-8") as f:
                ayer = json.load(f)
            if ayer.get("_copiado_el", "") == hoy:
                return ayer
        except Exception:
            pass

    # Primera corrida del día: copiar noticias.json → noticias_ayer.json
    if not os.path.exists(ruta_actual):
        return {}
    try:
        with open(ruta_actual, encoding="utf-8") as f:
            actual = json.load(f)
        actual["_copiado_el"] = hoy
        with open(ruta_ayer, "w", encoding="utf-8") as f:
            json.dump(actual, f, ensure_ascii=False, indent=2)
        print(f"  ✓ noticias_ayer.json guardado ({hoy})")
        return actual
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
    Mantiene máximo 6: hasta 3 rotativos al frente + permanentes al final (nunca se borran).
    """
    if not nota:
        return

    ruta = os.path.join(os.path.dirname(__file__), "cultura.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            cultura_actual = json.load(f)
    except Exception:
        cultura_actual = []

    permanentes  = [n for n in cultura_actual if n.get("permanente")]
    rotativos    = [n for n in cultura_actual if not n.get("permanente")]

    max_rotativos = max(1, 6 - len(permanentes))   # cuántos slots quedan para rotativos

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

    nuevos_rotativos = [entrada] + rotativos[:max_rotativos - 1]
    cultura_nuevo = nuevos_rotativos + permanentes
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

    # Slugificar IDs de notas auto-generadas
    hoy_slug = datetime.now().strftime('%Y%m%d')
    _slug_sufijos = {'tapa': 'tapa', 'sec1': 'sec1', 'sec2': 'sec2',
                     'dep': 'dep', 'neg': 'neg', 'cul': 'cul', 'tur': 'tur'}
    for sufijo, nota in [('tapa', tapa), ('dep', deportes), ('neg', negocios),
                         ('cul', cultura), ('tur', turismo)]:
        if nota and nota.get('titulo'):
            nota['id'] = f"{hoy_slug}-{slugify(nota['titulo'])}-{sufijo}"
    for i, nota in enumerate(secundarias, 1):
        if nota and nota.get('titulo'):
            nota['id'] = f"{hoy_slug}-{slugify(nota['titulo'])}-sec{i}"

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
    # Las 3 notas de tapa van a todas las redes
    notas_tapa_redes = [n for n in [tapa] + secundarias if n]

    # Generar imágenes con overlay de texto para Instagram (tapa + secciones + informes)
    print(f"\n  Generando imágenes para Instagram...")
    _base_dir = os.path.dirname(__file__)
    for _nota_ig in notas_tapa_redes:
        _img_local = os.path.join(_base_dir, _nota_ig.get("imagen", ""))
        if os.path.exists(_img_local):
            _generar_imagen_ig(_img_local, _nota_ig.get("titulo", ""), _nota_ig.get("tag", ""), nota_id=_nota_ig.get("id", ""))
    # Secciones automáticas
    for _nota_sec_ig in [n for n in [deportes, negocios, cultura, turismo] if n]:
        _img_sec_ig = os.path.join(_base_dir, _nota_sec_ig.get("imagen", ""))
        if os.path.exists(_img_sec_ig):
            _generar_imagen_ig(_img_sec_ig, _nota_sec_ig.get("titulo", ""), _nota_sec_ig.get("tag", ""), nota_id=_nota_sec_ig.get("id", ""))
    try:
        with open(os.path.join(_base_dir, "propios.json"), encoding="utf-8") as _fp:
            _propios_ig = json.load(_fp)
        if _propios_ig:
            _p0 = _propios_ig[0]
            _img_p = os.path.join(_base_dir, _p0.get("imagen", ""))
            if os.path.exists(_img_p):
                _generar_imagen_ig(_img_p, _p0.get("titulo", ""), _p0.get("tag", "📋 Informe"), nota_id=_p0.get("id", ""))
    except Exception:
        pass

    print(f"\n  Publicando en Telegram...")
    for nota in notas_tapa_redes:
        publicar_telegram(nota)
    publicar_telegram_informe_nuevo()

    print(f"\n  Publicando en Facebook...")
    for nota in notas_tapa_redes:
        publicar_facebook(nota)
    publicar_facebook_informe_nuevo()

    print(f"\n  Enviando newsletter...")
    enviar_newsletter()

    # Instagram solo se publica en --solo-instagram (después del push, cuando las imágenes están en Pages)

    # 9b. Publicar secciones automáticas (deportes / negocios / turismo / cultura)
    _sec_state_path = os.path.join(_base_dir, "telegram_state.json")
    try:
        with open(_sec_state_path, encoding="utf-8") as _f:
            _sec_state = json.load(_f)
    except Exception:
        _sec_state = {}

    _secciones_hoy = [
        (deportes, "deportes"),
        (negocios, "negocios"),
        (cultura,  "cultura"),
        (turismo,  "turismo"),
    ]
    for _ns, _clave in _secciones_hoy:
        if not _ns:
            continue
        _ns_id = _ns.get("id", "")
        if not _ns_id:
            continue
        if _sec_state.get(f"ultimo_{_clave}_telegram") != _ns_id:
            print(f"\n  Publicando {_clave} en Telegram...")
            publicar_telegram(_ns)
            _sec_state[f"ultimo_{_clave}_telegram"] = _ns_id
        if _sec_state.get(f"ultimo_{_clave}_facebook") != _ns_id:
            print(f"  Publicando {_clave} en Facebook...")
            publicar_facebook(_ns)
            _sec_state[f"ultimo_{_clave}_facebook"] = _ns_id

    with open(_sec_state_path, "w", encoding="utf-8") as _f:
        json.dump(_sec_state, _f, ensure_ascii=False, indent=2)

    # 9c. Publicar notas manuales nuevas (cualquier nota con "postear_redes": true no posteada aún)
    publicar_notas_manuales_nuevas()

    print(f"\n  Actualizando índice de búsqueda...")
    actualizar_search_index()

    print(f"\n  Generando páginas OG para compartir...")
    _notas_og = [tapa] + secundarias + [n for n in [deportes, negocios, cultura, turismo] if n]
    try:
        with open(os.path.join(os.path.dirname(__file__), "propios.json"), encoding="utf-8") as _f:
            _notas_og += json.load(_f)
    except Exception:
        pass
    try:
        with open(os.path.join(os.path.dirname(__file__), "historias.json"), encoding="utf-8") as _f:
            _hist = json.load(_f)
            _notas_og += _hist["notas"] if isinstance(_hist, dict) else _hist
    except Exception:
        pass
    _notas_og_filtradas = [n for n in _notas_og if isinstance(n, dict)]
    generar_paginas_og(_notas_og_filtradas)

    print(f"\n  Actualizando archivo estático en index.html...")
    actualizar_archivo_en_index(_notas_og_filtradas)

    print(f"\n  Generando páginas de temas...")
    generar_paginas_temas(_notas_og_filtradas)

    print(f"\n  Actualizando sitemap...")
    actualizar_sitemap()

    print(f"\n  ✓ Listo — {fecha_display()}")
    print(f"{'='*55}\n")


# ══════════════════════════════════════════════════════════
#  PÁGINAS ESTÁTICAS PARA SEO (contenido completo, sin JS)
# ══════════════════════════════════════════════════════════

def _render_cuerpo_html(cuerpo):
    """Convierte cuerpo de nota a HTML. Bloques que empiezan con '<' van como raw HTML."""
    import html as htmllib
    if not cuerpo:
        return ""
    if cuerpo.strip().startswith("<"):
        return cuerpo
    out = []
    for bloque in cuerpo.split("\n\n"):
        bloque = bloque.strip()
        if not bloque:
            continue
        if bloque.startswith("<"):
            out.append(bloque)
        elif bloque.startswith("## "):
            out.append(f"<h3>{htmllib.escape(bloque[3:])}</h3>")
        else:
            out.append(f"<p>{htmllib.escape(bloque)}</p>")
    return "\n".join(out)


def generar_paginas_og(notas):
    """Genera notas/[id].html con contenido completo — indexable por Google sin JS."""
    import html as htmllib
    import json as _json

    base = os.path.dirname(__file__)
    notas_dir = os.path.join(base, "notas")
    os.makedirs(notas_dir, exist_ok=True)

    generadas = 0
    for nota in notas:
        nid = nota.get("id", "")
        if not nid:
            continue

        titulo    = nota.get("titulo", "GLOBALpatagonia")
        bajada    = nota.get("bajada", "")
        cuerpo    = nota.get("cuerpo", "")
        tag       = nota.get("tag", "")
        fuente    = nota.get("fuente", "GLOBALpatagonia")
        fecha_raw = nota.get("fecha", nota.get("meta", ""))
        pais      = nota.get("pais", "")
        imagen    = nota.get("imagen", "")
        imagen_abs = (f"https://globalpatagonia.org/{imagen}"
                      if imagen else "https://globalpatagonia.org/fotos/torres-del-paine.webp")
        static_url = f"https://globalpatagonia.org/notas/{nid}.html"
        interactive_url = f"https://globalpatagonia.org/nota.html?id={nid}"

        def e(s): return htmllib.escape(str(s or ""))
        def ea(s): return htmllib.escape(str(s or ""), quote=True)

        # Fecha ISO para JSON-LD
        fecha_iso = datetime.now().strftime("%Y-%m-%d")
        if fecha_raw:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", str(fecha_raw))
            if m:
                fecha_iso = m.group(1)

        pais_label = {"argentina": "Argentina", "chile": "Chile",
                      "ambos": "Argentina y Chile", "malvinas": "Malvinas"}.get(pais, "Patagonia")

        jsonld = _json.dumps({
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": titulo,
            "description": bajada,
            "image": imagen_abs,
            "datePublished": fecha_iso,
            "dateModified": fecha_iso,
            "url": static_url,
            "inLanguage": "es",
            "keywords": f"patagonia, {pais_label.lower()}, {tag}",
            "publisher": {
                "@type": "NewsMediaOrganization",
                "name": "GLOBALpatagonia",
                "url": "https://globalpatagonia.org/",
                "logo": {"@type": "ImageObject", "url": "https://globalpatagonia.org/favicon.svg"}
            },
            "author": {"@type": "Organization", "name": fuente or "GLOBALpatagonia"},
            "isPartOf": {"@type": "CreativeWork", "name": "GLOBALpatagonia"}
        }, ensure_ascii=False, indent=2)

        cuerpo_html = _render_cuerpo_html(cuerpo)
        imagen_block = (f'<div class="nota-imagen-wrap"><img src="{ea(imagen_abs)}" '
                        f'alt="{ea(titulo)}" class="nota-imagen" loading="eager"/></div>'
                        if imagen else '<div class="nota-imagen-placeholder"></div>')

        html_out = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{e(titulo)} — GLOBALpatagonia</title>
  <meta name="description" content="{ea(bajada)}"/>
  <link rel="canonical" href="{ea(static_url)}"/>
  <meta property="og:site_name" content="GLOBALpatagonia"/>
  <meta property="og:type" content="article"/>
  <meta property="og:url" content="{ea(static_url)}"/>
  <meta property="og:title" content="{ea(titulo)} — GLOBALpatagonia"/>
  <meta property="og:description" content="{ea(bajada)}"/>
  <meta property="og:image" content="{ea(imagen_abs)}"/>
  <meta name="twitter:card" content="summary_large_image"/>
  <meta name="twitter:site" content="@GLOBALpatagonia"/>
  <meta name="twitter:title" content="{ea(titulo)} — GLOBALpatagonia"/>
  <meta name="twitter:description" content="{ea(bajada)}"/>
  <meta name="twitter:image" content="{ea(imagen_abs)}"/>
  <script type="application/ld+json">{jsonld}</script>
  <link rel="icon" type="image/svg+xml" href="../favicon.svg"/>
  <!-- Google Analytics -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-5FP2F41BZG"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-5FP2F41BZG');</script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@300;400;500;600&display=swap');
    :root{{--verde:#1c2d3d;--azul-claro:#8ab8d4;--gris-oscuro:#252830;--gris-medio:#5a6070;--crema:#f0ede8;}}
    *{{margin:0;padding:0;box-sizing:border-box;}}
    body{{font-family:'Inter',sans-serif;background:var(--crema);color:var(--gris-oscuro);}}
    header{{background:var(--verde);}}
    .top-bar{{background:#252830;display:flex;justify-content:space-between;align-items:center;padding:6px 40px;font-size:11px;color:#aaa;}}
    .header-main{{display:flex;flex-direction:column;align-items:center;padding:20px 40px 14px;}}
    .logo-tagline{{font-size:11px;color:#8ab8d4;letter-spacing:4px;text-transform:uppercase;margin-bottom:4px;}}
    .logo-img{{height:60px;width:auto;max-width:100%;display:block;}}
    nav{{background:var(--verde);display:flex;justify-content:center;gap:0;border-top:1px solid rgba(255,255,255,0.08);}}
    nav a{{color:rgba(255,255,255,0.75);text-decoration:none;font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;padding:12px 18px;border-bottom:3px solid transparent;transition:all 0.2s;}}
    nav a:hover{{color:#8ab8d4;border-bottom-color:#8ab8d4;}}
    .container{{max-width:800px;margin:0 auto;padding:0 20px;}}
    .volver{{display:inline-flex;align-items:center;gap:6px;margin:28px 0 24px;font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#3a5a7a;text-decoration:none;}}
    .volver:hover{{color:var(--verde);}}
    .nota-tag{{display:inline-block;background:var(--verde);color:#8ab8d4;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:4px 12px;border-radius:2px;margin-bottom:18px;}}
    .nota-titulo{{font-family:'Playfair Display',serif;font-size:clamp(28px,5vw,48px);font-weight:900;line-height:1.15;color:var(--gris-oscuro);margin-bottom:20px;letter-spacing:-0.5px;}}
    .nota-bajada{{font-size:19px;font-weight:400;color:var(--gris-medio);line-height:1.65;margin-bottom:24px;border-left:4px solid #8ab8d4;padding-left:18px;font-style:italic;}}
    .nota-meta{{font-size:11px;color:#aaa;letter-spacing:1px;text-transform:uppercase;margin-bottom:28px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding-bottom:16px;border-bottom:1px solid #e0ddd8;}}
    .nota-fuente{{margin-top:40px;padding:16px 20px;background:white;border-radius:4px;border-left:3px solid #5a6070;font-size:12px;color:#5a6070;}}
    .nota-fuente strong{{color:#252830;}}
    .nota-imagen-wrap{{width:100%;background:#0e1a26;border-radius:4px;margin-bottom:32px;display:flex;justify-content:center;align-items:center;overflow:hidden;max-height:480px;}}
    .nota-imagen{{width:100%;max-height:480px;object-fit:contain;display:block;}}
    .nota-imagen-placeholder{{width:100%;height:320px;background:linear-gradient(160deg,#0e1a26 0%,#1c2d3d 45%,#4a7a9a 100%);border-radius:4px;margin-bottom:32px;}}
    .nota-cuerpo p{{font-size:17.5px;line-height:1.85;color:#2a2a2a;margin-bottom:24px;}}
    .nota-cuerpo p:first-of-type{{font-size:20px;line-height:1.8;color:#1c2d3d;font-weight:400;border-left:4px solid #7aadcc;padding-left:20px;margin-bottom:32px;}}
    .nota-cuerpo h3{{font-family:'Playfair Display',serif;font-size:clamp(20px,3vw,28px);font-weight:700;color:var(--verde);margin:48px 0 16px;padding-bottom:10px;border-bottom:3px solid var(--azul-claro);line-height:1.2;}}
    .ver-completo{{display:inline-flex;align-items:center;gap:8px;margin:32px 0;padding:12px 24px;background:var(--verde);color:white;text-decoration:none;border-radius:3px;font-size:13px;font-weight:600;letter-spacing:1px;text-transform:uppercase;}}
    .ver-completo:hover{{opacity:0.85;}}
    .divider-footer{{height:2px;background:linear-gradient(90deg,#1c2d3d,#7aadcc,#1c2d3d);}}
    footer{{background:#1c2d3d;color:rgba(255,255,255,0.6);text-align:center;padding:32px 20px;}}
    .footer-logo{{font-family:'Playfair Display',serif;font-size:22px;font-weight:900;color:white;letter-spacing:1px;margin-bottom:6px;}}
    .footer-logo span{{color:#8ab8d4;font-weight:400;font-style:italic;}}
    .footer-copy{{font-size:11px;letter-spacing:1px;margin-top:12px;color:rgba(255,255,255,0.35);}}
    @media(max-width:600px){{.top-bar{{padding:6px 16px;}}.logo-img{{height:46px;}}nav a{{padding:10px 10px;font-size:10px;}}}}
  </style>
</head>
<body>
<header>
  <div class="top-bar">
    <span>Patagonia Argentina y Chilena</span>
    <span style="color:#8ab8d4;font-weight:600;">Sur Global, principio de todo.</span>
  </div>
  <div class="header-main">
    <div class="logo-tagline">Sur Global, principio de todo.</div>
    <a href="../index.html" style="text-decoration:none">
      <img src="../logo-globalpatagonia.png" alt="GLOBALpatagonia" class="logo-img"/>
    </a>
  </div>
  <nav>
    <a href="../index.html">Inicio</a>
    <a href="../index.html#sec-noticias">Noticias</a>
    <a href="../index.html#sec-deportes">Deportes &amp; Actividades</a>
    <a href="../index.html#sec-turismo">Turismo &amp; Guías</a>
    <a href="../index.html#sec-historia">Cultura Patagónica</a>
    <a href="../buscar.html">Buscar</a>
  </nav>
</header>

<div class="container">
  <a href="../index.html" class="volver">← Inicio</a>
  <article>
    {f'<div class="nota-tag">{e(tag)}</div>' if tag else ''}
    <h1 class="nota-titulo">{e(titulo)}</h1>
    {f'<p class="nota-bajada">{e(bajada)}</p>' if bajada else ''}
    <div class="nota-meta">
      {f'<span>🌎 {e(pais_label)}</span>' if pais else ''}
      <span>{fecha_iso}</span>
    </div>
    {imagen_block}
    <div class="nota-cuerpo">{cuerpo_html}</div>
    <div class="nota-fuente"><strong>Fuente original:</strong> Esta nota fue elaborada con información de <strong>{e(fuente)}</strong>.</div>
    <a href="../" class="ver-completo">← Más noticias en GLOBALpatagonia</a>
  </article>
</div>

<div class="divider-footer"></div>
<footer>
  <div class="footer-logo"><span>global</span>PATAGONIA</div>
  <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,0.3);margin-top:4px;">Argentina · Chile · Sin fronteras</div>
  <div class="footer-copy">© 2026 GLOBALpatagonia · globalpatagonia.org</div>
</footer>
</body>
</html>"""

        ruta = os.path.join(notas_dir, f"{nid}.html")
        # Notas de producción propia: si el HTML ya existe, no sobreescribir.
        # Se identifican por campo "autor" o por "-propio-" en el ID.
        es_propia = bool(nota.get("autor")) or "-propio-" in nid
        if es_propia and os.path.exists(ruta):
            continue
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(html_out)
        generadas += 1

    print(f"  Páginas estáticas generadas: {generadas}")


# ══════════════════════════════════════════════════════════
#  PÁGINAS DE TEMAS (SEO navegación por categoría)
# ══════════════════════════════════════════════════════════

_TEMA_LABELS = {
    "medio-ambiente":     "Medio Ambiente",
    "economia":           "Economía",
    "produccion":         "Producción",
    "cultura":            "Cultura",
    "ciencia":            "Ciencia",
    "deportes":           "Deportes & Aventura",
    "turismo":            "Turismo",
    "conectividad":       "Conectividad",
    "historia":           "Historia",
    "pueblos-originarios":"Pueblos Originarios",
    "bienestar":          "Bienestar",
    "sociedad":           "Sociedad",
}

def _slug_categoria(cat):
    import unicodedata
    cat = cat.strip().lower()
    cat = unicodedata.normalize("NFD", cat)
    cat = "".join(c for c in cat if unicodedata.category(c) != "Mn")
    cat = cat.replace(" ", "-")
    return cat


def generar_paginas_temas(notas_all):
    """Genera temas/[slug].html — una página indexable por Google por cada categoría."""
    import html as htmllib

    def e(s):  return htmllib.escape(str(s or ""))
    def ea(s): return htmllib.escape(str(s or ""), quote=True)

    base      = os.path.dirname(__file__)
    temas_dir = os.path.join(base, "temas")
    os.makedirs(temas_dir, exist_ok=True)

    # Agrupar notas por slug de categoría (normalizado)
    por_tema = {}
    for nota in notas_all:
        if not isinstance(nota, dict):
            continue
        cat_raw = nota.get("categoria", "").strip()
        if not cat_raw or cat_raw == "general":
            continue
        slug = _slug_categoria(cat_raw)
        if slug not in _TEMA_LABELS:
            continue
        por_tema.setdefault(slug, [])
        nid = nota.get("id", "")
        if nid and not any(n.get("id") == nid for n in por_tema[slug]):
            por_tema[slug].append(nota)

    # Ordenar cada tema por fecha descendente
    for slug in por_tema:
        por_tema[slug].sort(key=lambda n: str(n.get("fecha", n.get("meta", ""))), reverse=True)

    generadas = 0
    for slug, notas in por_tema.items():
        if len(notas) < 2:
            continue
        label    = _TEMA_LABELS[slug]
        tema_url = f"https://globalpatagonia.org/temas/{slug}.html"
        desc_seo = f"Todas las noticias de {label} en la Patagonia argentina y chilena — GLOBALpatagonia"

        # Generar cards de notas
        cards_html = ""
        for nota in notas[:30]:
            nid     = nota.get("id", "")
            titulo  = nota.get("titulo", "")
            bajada  = nota.get("bajada", "")
            imagen  = nota.get("imagen", "")
            fecha   = str(nota.get("fecha", nota.get("meta", "")))[:10]
            fuente  = nota.get("fuente", "")
            img_url = (f"https://globalpatagonia.org/{imagen}"
                       if imagen else "https://globalpatagonia.org/fotos/torres-del-paine.webp")
            nota_url = f"../notas/{nid}.html"
            cards_html += f"""
  <article class="tema-card">
    <a href="{ea(nota_url)}" class="card-img-wrap">
      <img src="{ea(img_url)}" alt="{ea(titulo)}" loading="lazy"/>
    </a>
    <div class="card-body">
      <h2 class="card-titulo"><a href="{ea(nota_url)}">{e(titulo)}</a></h2>
      {f'<p class="card-bajada">{e(bajada)}</p>' if bajada else ''}
      <div class="card-meta">{e(fuente)}{f" · {fecha}" if fecha else ""}</div>
    </div>
  </article>"""

        html_out = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{e(label)} en la Patagonia — GLOBALpatagonia</title>
  <meta name="description" content="{ea(desc_seo)}"/>
  <link rel="canonical" href="{ea(tema_url)}"/>
  <meta property="og:site_name" content="GLOBALpatagonia"/>
  <meta property="og:type" content="website"/>
  <meta property="og:url" content="{ea(tema_url)}"/>
  <meta property="og:title" content="{ea(label)} en la Patagonia — GLOBALpatagonia"/>
  <meta property="og:description" content="{ea(desc_seo)}"/>
  <meta property="og:image" content="https://globalpatagonia.org/fotos/torres-del-paine.webp"/>
  <link rel="icon" type="image/svg+xml" href="../favicon.svg"/>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-5FP2F41BZG"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-5FP2F41BZG');</script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@300;400;500;600&display=swap');
    :root{{--verde:#1c2d3d;--azul-claro:#8ab8d4;--gris-oscuro:#252830;--gris-medio:#5a6070;--crema:#f0ede8;}}
    *{{margin:0;padding:0;box-sizing:border-box;}}
    body{{font-family:'Inter',sans-serif;background:var(--crema);color:var(--gris-oscuro);}}
    header{{background:var(--verde);}}
    .top-bar{{background:#252830;display:flex;justify-content:space-between;align-items:center;padding:6px 40px;font-size:11px;color:#aaa;}}
    .header-main{{display:flex;flex-direction:column;align-items:center;padding:20px 40px 14px;}}
    .logo-tagline{{font-size:11px;color:#8ab8d4;letter-spacing:4px;text-transform:uppercase;margin-bottom:4px;}}
    .logo-img{{height:60px;width:auto;max-width:100%;display:block;}}
    nav{{background:var(--verde);display:flex;justify-content:center;gap:0;border-top:1px solid rgba(255,255,255,0.08);}}
    nav a{{color:rgba(255,255,255,0.75);text-decoration:none;font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;padding:12px 18px;border-bottom:3px solid transparent;transition:all 0.2s;}}
    nav a:hover{{color:#8ab8d4;border-bottom-color:#8ab8d4;}}
    .container{{max-width:1100px;margin:0 auto;padding:0 20px;}}
    .page-header{{padding:40px 0 32px;border-bottom:2px solid #d8d4ce;margin-bottom:36px;}}
    .page-tag{{display:inline-block;background:var(--verde);color:#8ab8d4;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:4px 12px;border-radius:2px;margin-bottom:14px;}}
    .page-titulo{{font-family:'Playfair Display',serif;font-size:clamp(32px,5vw,52px);font-weight:900;line-height:1.1;color:var(--gris-oscuro);margin-bottom:10px;}}
    .page-desc{{font-size:15px;color:var(--gris-medio);}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:28px;padding-bottom:60px;}}
    .tema-card{{background:white;border-radius:4px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.07);transition:transform 0.2s,box-shadow 0.2s;}}
    .tema-card:hover{{transform:translateY(-3px);box-shadow:0 6px 20px rgba(0,0,0,0.12);}}
    .card-img-wrap{{display:block;height:180px;overflow:hidden;background:#1c2d3d;}}
    .card-img-wrap img{{width:100%;height:100%;object-fit:cover;transition:transform 0.3s;}}
    .tema-card:hover .card-img-wrap img{{transform:scale(1.03);}}
    .card-body{{padding:18px 20px 20px;}}
    .card-titulo{{font-family:'Playfair Display',serif;font-size:17px;font-weight:700;line-height:1.3;margin-bottom:10px;}}
    .card-titulo a{{color:var(--gris-oscuro);text-decoration:none;}}
    .card-titulo a:hover{{color:var(--verde);}}
    .card-bajada{{font-size:13px;color:var(--gris-medio);line-height:1.6;margin-bottom:12px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}}
    .card-meta{{font-size:11px;color:#aaa;letter-spacing:0.5px;text-transform:uppercase;}}
    .volver{{display:inline-flex;align-items:center;gap:6px;margin:28px 0;font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#3a5a7a;text-decoration:none;}}
    .volver:hover{{color:var(--verde);}}
    .divider-footer{{height:2px;background:linear-gradient(90deg,#1c2d3d,#7aadcc,#1c2d3d);}}
    footer{{background:#1c2d3d;color:rgba(255,255,255,0.6);text-align:center;padding:32px 20px;}}
    .footer-logo{{font-family:'Playfair Display',serif;font-size:22px;font-weight:900;color:white;letter-spacing:1px;margin-bottom:6px;}}
    .footer-logo span{{color:#8ab8d4;font-weight:400;font-style:italic;}}
    .footer-copy{{font-size:11px;letter-spacing:1px;margin-top:12px;color:rgba(255,255,255,0.35);}}
    @media(max-width:600px){{.top-bar{{padding:6px 16px;}}.logo-img{{height:46px;}}nav a{{padding:10px 10px;font-size:10px;}}.grid{{grid-template-columns:1fr;}}}}
  </style>
</head>
<body>
<header>
  <div class="top-bar">
    <span>Patagonia Argentina y Chilena</span>
    <span style="color:#8ab8d4;font-weight:600;">Sur Global, principio de todo.</span>
  </div>
  <div class="header-main">
    <div class="logo-tagline">Sur Global, principio de todo.</div>
    <a href="../index.html" style="text-decoration:none">
      <img src="../logo-globalpatagonia.png" alt="GLOBALpatagonia" class="logo-img"/>
    </a>
  </div>
  <nav>
    <a href="../index.html">Inicio</a>
    <a href="../index.html#sec-noticias">Noticias</a>
    <a href="../index.html#sec-deportes">Deportes &amp; Actividades</a>
    <a href="../index.html#sec-turismo">Turismo &amp; Guías</a>
    <a href="../index.html#sec-historia">Cultura Patagónica</a>
    <a href="../buscar.html">Buscar</a>
  </nav>
</header>

<div class="container">
  <a href="../index.html" class="volver">← Inicio</a>
  <div class="page-header">
    <div class="page-tag">Tema</div>
    <h1 class="page-titulo">{e(label)}</h1>
    <p class="page-desc">Noticias de {e(label)} en la Patagonia argentina y chilena</p>
  </div>
  <div class="grid">
{cards_html}
  </div>
</div>

<div class="divider-footer"></div>
<footer>
  <div class="footer-logo"><span>global</span>PATAGONIA</div>
  <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,0.3);margin-top:4px;">Argentina · Chile · Sin fronteras</div>
  <div class="footer-copy">© 2026 GLOBALpatagonia · globalpatagonia.org</div>
</footer>
</body>
</html>"""

        ruta = os.path.join(temas_dir, f"{slug}.html")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(html_out)
        generadas += 1

    print(f"  Páginas de temas generadas: {generadas}")


# ══════════════════════════════════════════════════════════
#  ARCHIVO ESTÁTICO EN INDEX.HTML (crawl budget)
# ══════════════════════════════════════════════════════════

def actualizar_archivo_en_index(notas):
    """Inyecta links estáticos a todas las notas en index.html entre marcadores.
    Google sigue estos links al rastrear el home, aumentando el crawl budget de cada nota."""
    import html as htmllib
    base = os.path.dirname(__file__)
    index_path = os.path.join(base, "index.html")
    if not os.path.exists(index_path):
        return

    with open(index_path, encoding="utf-8") as f:
        contenido = f.read()

    if "<!-- ARCHIVO-STATIC-START -->" not in contenido:
        print("  ⚠ Marcadores ARCHIVO-STATIC no encontrados en index.html — omitiendo")
        return

    # Ordenar por fecha descendente
    def _fecha_nota(n):
        return n.get("fecha") or n.get("id", "") or ""
    notas_ord = sorted(notas, key=_fecha_nota, reverse=True)

    links = []
    for n in notas_ord:
        nid = n.get("id", "")
        titulo = n.get("titulo", "")
        if not nid or not titulo:
            continue
        url = f"/notas/{nid}.html"
        cat = n.get("categoria", n.get("tag", "")).replace("·", "").strip()
        cat_html = f'<span class="arc-cat">{htmllib.escape(cat)}</span> ' if cat else ""
        links.append(f'    <li>{cat_html}<a href="{url}">{htmllib.escape(titulo)}</a></li>')

    bloque = (
        "<!-- ARCHIVO-STATIC-START -->\n"
        '<section id="archivo-notas" style="background:#f0ede8;padding:32px 20px 40px;border-top:1px solid #ddd;">\n'
        '  <div style="max-width:900px;margin:0 auto;">\n'
        '    <p style="font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#8c6b4a;font-weight:700;margin-bottom:16px;">Archivo de notas</p>\n'
        '    <ul style="list-style:none;columns:2;column-gap:32px;" id="archivo-lista">\n'
        + "\n".join(links) + "\n"
        '    </ul>\n'
        '  </div>\n'
        '</section>\n'
        '<style>\n'
        '#archivo-notas a{font-size:13px;color:#1c2d3d;text-decoration:none;line-height:1.9;}\n'
        '#archivo-notas a:hover{text-decoration:underline;}\n'
        '#archivo-notas .arc-cat{font-size:10px;color:#8c6b4a;font-weight:600;letter-spacing:1px;text-transform:uppercase;}\n'
        '@media(max-width:600px){#archivo-notas ul{columns:1;}}\n'
        '</style>\n'
        "<!-- ARCHIVO-STATIC-END -->"
    )

    nuevo = re.sub(
        r"<!-- ARCHIVO-STATIC-START -->.*?<!-- ARCHIVO-STATIC-END -->",
        bloque,
        contenido,
        flags=re.DOTALL
    )
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(nuevo)
    print(f"  Archivo estático: {len(links)} links en index.html")


# ══════════════════════════════════════════════════════════
#  SITEMAP
# ══════════════════════════════════════════════════════════

def actualizar_sitemap():
    """Regenera sitemap.xml con todas las notas actualmente accesibles."""
    base = os.path.dirname(__file__)
    today = datetime.now().strftime("%Y-%m-%d")

    fuentes = [
        "historial.json", "noticias.json", "historias.json",
        "turismo.json", "guias.json", "deportes_feed.json", "propios.json",
        "propios_historial.json", "negocios.json",
    ]
    ids = {}        # id → fecha
    historias_ids = set()  # IDs de historias permanentes (priority alta, monthly)
    for nombre in fuentes:
        path = os.path.join(base, nombre)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # historias.json tiene estructura {"_info": ..., "notas": [...]}
            if isinstance(data, dict) and "notas" in data:
                lista = data["notas"]
                es_historias = True
            elif isinstance(data, list):
                lista = data
                es_historias = False
            else:
                continue
            for nota in lista:
                if isinstance(nota, dict) and nota.get("id"):
                    nid = nota["id"]
                    if nid not in ids:
                        ids[nid] = nota.get("fecha", today) or today
                    if es_historias:
                        historias_ids.add(nid)
        except Exception:
            pass

    # Escanear archivo/YYYY-MM.json para incluir notas históricas
    archivo_dir = os.path.join(base, "archivo")
    if os.path.isdir(archivo_dir):
        for fname in sorted(os.listdir(archivo_dir)):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(archivo_dir, fname), encoding="utf-8") as f:
                    for nota in json.load(f):
                        nid = nota.get("id")
                        if nid and nid not in ids:
                            ids[nid] = nota.get("fecha", today) or today
            except Exception:
                pass

    # Migración: archivo.json legado
    archivo_legado = os.path.join(base, "archivo.json")
    if os.path.exists(archivo_legado):
        try:
            with open(archivo_legado, encoding="utf-8") as f:
                data = json.load(f)
            for nota in data.get("notas", []):
                nid = nota.get("id")
                if nid and nid not in ids:
                    ids[nid] = nota.get("fecha", today) or today
        except Exception:
            pass

    static = [
        ("https://globalpatagonia.org/",              today, "daily",   "1.0"),
        ("https://globalpatagonia.org/agenda.html",   today, "daily",   "0.7"),
        ("https://globalpatagonia.org/videos.html",   today, "weekly",  "0.7"),
        ("https://globalpatagonia.org/acerca.html",   today, "monthly", "0.5"),
        ("https://globalpatagonia.org/privacidad.html", today, "monthly", "0.3"),
    ]

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod, freq, prio in static:
        lines += [f"  <url>", f"    <loc>{loc}</loc>",
                  f"    <lastmod>{lastmod}</lastmod>",
                  f"    <changefreq>{freq}</changefreq>",
                  f"    <priority>{prio}</priority>", f"  </url>"]

    for nid, fecha in sorted(ids.items(), key=lambda x: x[1], reverse=True):
        es_historia = nid in historias_ids
        freq = "monthly" if es_historia else "weekly"
        prio = "0.9" if es_historia else "0.8"
        lines += [f"  <url>",
                  f"    <loc>https://globalpatagonia.org/notas/{nid}.html</loc>",
                  f"    <lastmod>{fecha}</lastmod>",
                  f"    <changefreq>{freq}</changefreq>",
                  f"    <priority>{prio}</priority>", f"  </url>"]

    # Páginas de temas navegables
    temas_dir = os.path.join(base, "temas")
    if os.path.isdir(temas_dir):
        for fname in sorted(os.listdir(temas_dir)):
            if fname.endswith(".html"):
                slug = fname[:-5]
                lines += [f"  <url>",
                          f"    <loc>https://globalpatagonia.org/temas/{slug}.html</loc>",
                          f"    <lastmod>{today}</lastmod>",
                          f"    <changefreq>daily</changefreq>",
                          f"    <priority>0.7</priority>", f"  </url>"]

    lines.append("</urlset>")

    sitemap_path = os.path.join(base, "sitemap.xml")
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"    Sitemap OK — {len(ids)} notas + {len(static)} páginas estáticas")


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


def _renovar_token_facebook(token):
    """Intercambia el token actual por uno long-lived y obtiene el Page Access Token real.
    Retorna (page_token, page_id_real) — usa el page_id correcto aunque el secret esté mal."""
    app_id     = os.environ.get("FACEBOOK_APP_ID", "")
    app_secret = os.environ.get("FACEBOOK_APP_SECRET", "")
    page_id    = os.environ.get("FACEBOOK_PAGE_ID", "")
    if not app_id or not app_secret or not token:
        return token, page_id
    try:
        # Paso 1: exchange → long-lived token
        params = urllib.parse.urlencode({
            "grant_type":        "fb_exchange_token",
            "client_id":         app_id,
            "client_secret":     app_secret,
            "fb_exchange_token": token,
        })
        url = f"https://graph.facebook.com/oauth/access_token?{params}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        nuevo = data.get("access_token", "")
        if not nuevo:
            return token, page_id

        # Paso 2a: intentar /me/accounts (funciona si el token es un User Token)
        try:
            accounts_url = f"https://graph.facebook.com/me/accounts?access_token={nuevo}"
            with urllib.request.urlopen(accounts_url, timeout=15) as resp2:
                accounts = json.loads(resp2.read().decode())
            pages = accounts.get("data", [])
            for page in pages:
                if page.get("id") == page_id:
                    print("  Facebook: token renovado automáticamente ✓")
                    return page["access_token"], page["id"]
            if pages:
                first = pages[0]
                if page_id and page_id != first["id"]:
                    print(f"  Facebook: ADVERTENCIA — page_id '{page_id}' no coincide, usando página '{first.get('name','')}' ({first['id']})")
                print("  Facebook: token renovado automáticamente ✓")
                return first["access_token"], first["id"]
        except Exception as e_acc:
            print(f"  Facebook: /me/accounts no disponible ({e_acc.__class__.__name__}), probando /me...")

        # Paso 2b: si el token YA ES un page token, /me devuelve el ID de la propia página
        try:
            me_url = f"https://graph.facebook.com/me?fields=id,name&access_token={nuevo}"
            with urllib.request.urlopen(me_url, timeout=15) as resp3:
                me_data = json.loads(resp3.read().decode())
            actual_id = me_data.get("id", "")
            if actual_id:
                if page_id and page_id != actual_id:
                    print(f"  Facebook: page_id del secret ('{page_id}') != real ('{actual_id}' — {me_data.get('name','')}). Usando el real.")
                print("  Facebook: token renovado automáticamente ✓")
                return nuevo, actual_id
        except Exception as e_me:
            print(f"  Facebook: /me también falló ({e_me.__class__.__name__})")

        print("  Facebook: token renovado automáticamente ✓")
        return nuevo, page_id
    except Exception as e:
        print(f"  Facebook: no se pudo renovar el token ({e}), se usa el existente.")
    return token, page_id


def publicar_facebook(tapa):
    """Publica la tapa del día en la página de Facebook con foto y link."""
    page_id    = os.environ.get("FACEBOOK_PAGE_ID", "")
    page_token = os.environ.get("FACEBOOK_PAGE_TOKEN", "")
    if not page_token:
        print("  Facebook: sin credenciales, se omite.")
        return
    page_token, page_id = _renovar_token_facebook(page_token)
    if not page_id:
        print("  Facebook: no se encontró página, se omite.")
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
        import tempfile
        from PIL import Image as _PilImg
        jpg_tmp = tempfile.mktemp(suffix=".jpg")
        try:
            with _PilImg.open(ruta_img) as _wim:
                _wim.convert("RGB").save(jpg_tmp, "JPEG", quality=88)
            ruta_img = jpg_tmp
        except Exception as _we:
            print(f"  WebP→JPEG falló: {_we}")
            jpg_tmp = None
            ruta_img = ""

    try:
        api_url = f"https://graph.facebook.com/v21.0/{page_id}"

        if ruta_img:
            # Publicar con foto via /photos
            with open(ruta_img, "rb") as img_file:
                boundary = "----GLOBALpatagonia"
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
    if not page_token:
        return
    page_token, page_id = _renovar_token_facebook(page_token)
    if not page_id:
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
        import tempfile
        from PIL import Image as _PilImg
        jpg_tmp = tempfile.mktemp(suffix=".jpg")
        try:
            with _PilImg.open(ruta_img) as _wim:
                _wim.convert("RGB").save(jpg_tmp, "JPEG", quality=88)
            ruta_img = jpg_tmp
        except Exception as _we:
            print(f"  WebP→JPEG falló: {_we}")
            jpg_tmp = None
            ruta_img = ""

    try:
        api_url = f"https://graph.facebook.com/v21.0/{page_id}"

        if ruta_img:
            boundary = "----GLOBALpatagonia"
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


def _nl_seccion_html(label, nota, color_label="#7aadcc"):
    """Genera bloque HTML de una sección para el newsletter (deportes, turismo, etc.)."""
    if not nota:
        return ""
    n_id    = nota.get("id", "")
    titulo  = nota.get("titulo", "")
    bajada  = nota.get("bajada", "")
    imagen  = nota.get("imagen", "")
    link    = f"https://globalpatagonia.org/nota.html?id={n_id}"
    if imagen and not imagen.startswith("http"):
        imagen = f"https://globalpatagonia.org/{imagen}"
    img_tag = f'<img src="{imagen}" alt="" width="520" style="width:100%;max-width:520px;height:220px;object-fit:cover;display:block;border-radius:4px;margin-bottom:14px;" />' if imagen else ""
    return f"""
        <tr><td style="padding:28px 40px 0 40px;border-top:1px solid #e8e4de;">
          {img_tag}
          <div style="font-family:Inter,sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:0.12em;
                      color:{color_label};text-transform:uppercase;margin-bottom:8px;">{label}</div>
          <div style="font-family:'Playfair Display',Georgia,serif;font-size:1.15rem;font-weight:700;
                      color:#1c2d3d;line-height:1.3;margin-bottom:8px;">{titulo}</div>
          <div style="font-family:Inter,sans-serif;font-size:0.88rem;color:#555;line-height:1.55;
                      margin-bottom:12px;">{bajada}</div>
          <a href="{link}" style="font-family:Inter,sans-serif;font-size:0.83rem;font-weight:600;
                                   color:#1c2d3d;text-decoration:underline;">Leer más →</a>
        </td></tr>"""


def enviar_newsletter():
    """Crea y envía la campaña diaria de newsletter via Brevo.
    Incluye: tapa (3 notas) + informes nuevos + deportes + economía + turismo (semanal) + cultura (semanal) + guías nuevas."""
    if not BREVO_API_KEY:
        print("  Newsletter: BREVO_API_KEY no configurada, saltando.")
        return

    base_dir   = os.path.dirname(__file__)
    state_path = os.path.join(base_dir, "telegram_state.json")

    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}

    hoy = datetime.now().strftime("%Y-%m-%d")
    if state.get("ultimo_newsletter") == hoy:
        print(f"  Newsletter: ya enviado hoy ({hoy}), saltando.")
        return

    # ── Leer noticias del día ────────────────────────────────────────────────
    try:
        with open(os.path.join(base_dir, "noticias.json"), encoding="utf-8") as f:
            noticias_data = json.load(f)
    except Exception:
        noticias_data = {}

    tapa        = noticias_data.get("tapa") or {}
    secundarias = noticias_data.get("secundarias", [])[:2]

    if not tapa:
        print("  Newsletter: noticias.json sin tapa, saltando.")
        return

    # ── Leer secciones ──────────────────────────────────────────────────────
    def _leer_json(nombre):
        try:
            with open(os.path.join(base_dir, nombre), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    dep_data     = _leer_json("deportes_feed.json")
    deportes     = dep_data.get("principal") if isinstance(dep_data, dict) else (dep_data[0] if isinstance(dep_data, list) and dep_data else None)

    neg_data     = _leer_json("negocios.json")
    economia     = neg_data[0] if isinstance(neg_data, list) and neg_data else None

    tur_data     = _leer_json("turismo.json")
    turismo_nota = None
    if isinstance(tur_data, list) and tur_data:
        tur_id = tur_data[0].get("id", "")
        if state.get("ultimo_turismo_newsletter") != tur_id:
            turismo_nota = tur_data[0]
            state["ultimo_turismo_newsletter"] = tur_id
    elif isinstance(tur_data, dict):
        tur_id = tur_data.get("principal", {}).get("id", "") if tur_data.get("principal") else ""
        if tur_id and state.get("ultimo_turismo_newsletter") != tur_id:
            turismo_nota = tur_data.get("principal")
            state["ultimo_turismo_newsletter"] = tur_id

    cul_data     = _leer_json("cultura.json")
    cultura_nota = None
    if isinstance(cul_data, list) and cul_data:
        cul_id = cul_data[0].get("id", "")
        if state.get("ultimo_cultura_newsletter") != cul_id:
            cultura_nota = cul_data[0]
            state["ultimo_cultura_newsletter"] = cul_id

    propios_data = _leer_json("propios.json") or []
    informe_nota = None
    if propios_data:
        inf_id = propios_data[0].get("id", "")
        if state.get("ultimo_informe_newsletter") != inf_id:
            informe_nota = propios_data[0]
            state["ultimo_informe_newsletter"] = inf_id

    guias_data  = _leer_json("guias.json") or []
    nl_guias_enviadas = set(state.get("guias_newsletter_enviadas", []))
    guias_nuevas = [g for g in guias_data if g.get("postear_redes") and g.get("id", "") not in nl_guias_enviadas]
    guia_nota   = guias_nuevas[0] if guias_nuevas else None
    if guia_nota:
        nl_guias_enviadas.add(guia_nota.get("id", ""))
        state["guias_newsletter_enviadas"] = list(nl_guias_enviadas)

    fecha_dd_mm = datetime.now().strftime("%d/%m/%Y")

    # ── Bloque tapa ─────────────────────────────────────────────────────────
    tapa_id     = tapa.get("id", "")
    tapa_titulo = tapa.get("titulo", "")
    tapa_bajada = tapa.get("bajada", "")
    tapa_imagen = tapa.get("imagen", "")
    tapa_link   = f"https://globalpatagonia.org/nota.html?id={tapa_id}"
    if tapa_imagen and not tapa_imagen.startswith("http"):
        tapa_imagen = f"https://globalpatagonia.org/{tapa_imagen}"
    tapa_img_tag = f'<img src="{tapa_imagen}" alt="" width="520" style="width:100%;max-width:520px;height:auto;display:block;border-radius:4px;margin-bottom:20px;" />' if tapa_imagen else ""

    # ── Bloques secundarias ─────────────────────────────────────────────────
    sec_rows = ""
    for s in secundarias:
        s_id    = s.get("id", "")
        s_tit   = s.get("titulo", "")
        s_link  = f"https://globalpatagonia.org/nota.html?id={s_id}"
        sec_rows += (
            f'<tr><td style="padding:10px 0;border-bottom:1px solid #e8e4de;">'
            f'<a href="{s_link}" style="font-family:Inter,sans-serif;font-size:0.93rem;color:#1c2d3d;'
            f'text-decoration:none;font-weight:500;">{s_tit}</a></td></tr>\n'
        )
    sec_block = (
        f'<tr><td style="padding:24px 40px 0 40px;">'
        f'<div style="font-family:Inter,sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:0.12em;'
        f'color:#7aadcc;text-transform:uppercase;margin-bottom:14px;">Más noticias</div>'
        f'<table width="100%" cellpadding="0" cellspacing="0">{sec_rows}</table></td></tr>'
    ) if sec_rows else ""

    # ── Bloque informe ──────────────────────────────────────────────────────
    informe_block = ""
    if informe_nota:
        inf_id    = informe_nota.get("id", "")
        inf_tit   = informe_nota.get("titulo", "")
        inf_baj   = informe_nota.get("bajada", "")
        inf_link  = f"https://globalpatagonia.org/nota.html?id={inf_id}"
        informe_block = f"""
        <tr><td style="padding:28px 40px 0 40px;border-top:1px solid #e8e4de;">
          <div style="background:#f0ede8;border-left:4px solid #7aadcc;padding:20px 24px;border-radius:4px;">
            <div style="font-family:Inter,sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:0.12em;
                        color:#7aadcc;text-transform:uppercase;margin-bottom:8px;">Informe especial</div>
            <div style="font-family:'Playfair Display',Georgia,serif;font-size:1.15rem;font-weight:700;
                        color:#1c2d3d;margin-bottom:8px;">{inf_tit}</div>
            <div style="font-family:Inter,sans-serif;font-size:0.88rem;color:#444;margin-bottom:14px;
                        line-height:1.5;">{inf_baj}</div>
            <a href="{inf_link}" style="font-family:Inter,sans-serif;font-size:0.85rem;font-weight:600;
                                        color:#1c2d3d;text-decoration:underline;">Leer informe →</a>
          </div>
        </td></tr>"""

    # ── Secciones dinámicas ─────────────────────────────────────────────────
    dep_block     = _nl_seccion_html("Deportes & Aventura",       deportes,     "#8c6b4a")
    eco_block     = _nl_seccion_html("Economía & Empresas",       economia,     "#7aadcc")
    tur_block     = _nl_seccion_html("Turismo en Patagonia",      turismo_nota, "#7aadcc")
    cul_block     = _nl_seccion_html("Cultura Patagónica",        cultura_nota, "#7aadcc")
    guia_block    = _nl_seccion_html("Guía",                      guia_nota,    "#8c6b4a")

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0ede8;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0ede8;">
    <tr><td align="center" style="padding:0;">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;">

        <!-- Header -->
        <tr><td style="background:#1c2d3d;padding:28px 40px;text-align:center;">
          <div style="font-family:'Playfair Display',Georgia,serif;font-size:1.6rem;font-weight:900;
                      color:#f0ede8;letter-spacing:0.02em;">
            GLOBAL<span style="color:#7aadcc">patagonia</span>
          </div>
          <div style="font-family:Inter,sans-serif;font-size:0.72rem;color:#7aadcc;
                      letter-spacing:0.1em;margin-top:6px;text-transform:uppercase;">
            Sur Global, principio de todo &nbsp;·&nbsp; {fecha_dd_mm}
          </div>
        </td></tr>

        <!-- Tapa -->
        <tr><td style="padding:32px 40px 0 40px;">
          {tapa_img_tag}
          <div style="font-family:Inter,sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:0.12em;
                      color:#7aadcc;text-transform:uppercase;margin-bottom:10px;">Tapa del día</div>
          <div style="font-family:'Playfair Display',Georgia,serif;font-size:1.5rem;font-weight:700;
                      color:#1c2d3d;line-height:1.25;margin-bottom:12px;">{tapa_titulo}</div>
          <div style="font-family:Inter,sans-serif;font-size:0.92rem;color:#444;
                      line-height:1.6;margin-bottom:18px;">{tapa_bajada}</div>
          <a href="{tapa_link}" style="display:inline-block;background:#1c2d3d;color:#f0ede8;
                                       font-family:Inter,sans-serif;font-size:0.85rem;font-weight:600;
                                       padding:10px 22px;border-radius:5px;text-decoration:none;">
            Leer más →
          </a>
        </td></tr>

        {sec_block}
        {informe_block}
        {dep_block}
        {eco_block}
        {tur_block}
        {cul_block}
        {guia_block}

        <!-- Separador -->
        <tr><td style="padding:32px 40px 0 40px;"></td></tr>

        <!-- Footer -->
        <tr><td style="background:#1c2d3d;padding:24px 40px;text-align:center;">
          <a href="https://globalpatagonia.org" style="font-family:'Playfair Display',Georgia,serif;
                                                        font-size:1rem;font-weight:900;color:#f0ede8;
                                                        text-decoration:none;">
            GLOBAL<span style="color:#7aadcc">patagonia</span>
          </a>
          <div style="font-family:Inter,sans-serif;font-size:0.72rem;color:rgba(240,237,232,0.5);
                      margin-top:10px;line-height:1.6;">
            Recibiste este email porque te suscribiste en
            <a href="https://globalpatagonia.org" style="color:#7aadcc;text-decoration:none;">globalpatagonia.org</a>
          </div>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    # ── Crear y enviar campaña en Brevo ─────────────────────────────────────
    try:
        campaign_payload = json.dumps({
            "name":        f"GLOBALpatagonia — {fecha_dd_mm}",
            "subject":     f"El Sur de hoy — {fecha_dd_mm}",
            "sender":      {"name": "GLOBALpatagonia", "email": "ficciontvpatagonia@gmail.com"},
            "type":        "classic",
            "htmlContent": html_content,
            "recipients":  {"listIds": [BREVO_LIST_ID]}
        }).encode("utf-8")

        req_create = urllib.request.Request(
            "https://api.brevo.com/v3/emailCampaigns",
            data=campaign_payload,
            headers={
                "api-key":      BREVO_API_KEY,
                "accept":       "application/json",
                "content-type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req_create, timeout=30) as resp:
            resultado = json.loads(resp.read().decode())

        campaign_id = resultado.get("id")
        if not campaign_id:
            print(f"  Newsletter: error al crear campaña — {resultado}")
            return

        req_send = urllib.request.Request(
            f"https://api.brevo.com/v3/emailCampaigns/{campaign_id}/sendNow",
            data=b"{}",
            headers={
                "api-key":      BREVO_API_KEY,
                "accept":       "application/json",
                "content-type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req_send, timeout=30) as resp_send:
            resp_send.read()

        state["ultimo_newsletter"] = hoy
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print(f"  Newsletter OK ✓ campaña {campaign_id} enviada ({fecha_dd_mm})")

    except urllib.error.HTTPError as http_err:
        detalle = http_err.read().decode("utf-8", errors="replace")
        print(f"  Newsletter falló {http_err.code}: {detalle}")
    except Exception as e:
        print(f"  Newsletter falló: {e}")


def _generar_imagen_ig(ruta_local, titulo, tag="", nota_id=""):
    """Genera imagen portrait 4:5 (1080×1350) con diseño GLOBALpatagonia para Instagram.
    Layout: header con logo | foto grande | sección oscura con tag + título + CTA.
    Guarda como fotos/{nota_id}_ig.jpg (o {base}_ig.jpg si no hay nota_id). Retorna la ruta o None si falla."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import os as _os, numpy as np

        # ── Dimensiones ───────────────────────────────────────────────────────────
        ANCHO    = 1080
        ALTO     = 1350
        H_HEADER = 65
        H_FOTO   = 780   # foto: y=65 → y=845
        Y_DARK   = 845   # sección oscura: y=845 → y=1350

        # ── Paleta GLOBALpatagonia ────────────────────────────────────────────────
        C_DARK   = (28,  45,  61)    # #1c2d3d azul oscuro
        C_TEAL   = (122, 173, 204)   # #7aadcc azul glacial
        C_BLANCO = (255, 255, 255)
        C_CREMA  = (240, 237, 232)   # #f0ede8
        C_SHADOW = (10,  20,  30)

        # ── Canvas oscuro base ────────────────────────────────────────────────────
        canvas = Image.new("RGB", (ANCHO, ALTO), C_DARK)
        draw   = ImageDraw.Draw(canvas)

        # ── Foto: recortar en ratio 1080:780 y pegar ─────────────────────────────
        img = Image.open(ruta_local).convert("RGB")
        w, h = img.size
        target_ratio = ANCHO / H_FOTO   # 1080/780 ≈ 1.385
        img_ratio    = w / h
        if img_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left  = (w - new_w) // 2
            img   = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top   = (h - new_h) // 3    # ligero sesgo hacia arriba para retratos
            img   = img.crop((0, top, w, top + new_h))
        img = img.resize((ANCHO, H_FOTO), Image.LANCZOS)
        canvas.paste(img, (0, H_HEADER))

        # ── Gradiente suave al pie de la foto (transición foto→sección oscura) ───
        arr        = np.array(canvas, dtype=np.float32)
        grad_start = H_HEADER + H_FOTO - 120   # últimos 120px de la foto
        azul_np    = np.array(C_DARK,  dtype=np.float32)
        for y in range(grad_start, H_HEADER + H_FOTO):
            t       = (y - grad_start) / 120
            alpha   = t * 0.75
            arr[y]  = arr[y] * (1 - alpha) + azul_np * alpha
        canvas = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
        draw   = ImageDraw.Draw(canvas)

        # ── Fuentes ───────────────────────────────────────────────────────────────
        def _fuente(paths, size):
            for p in paths:
                if _os.path.exists(p):
                    try: return ImageFont.truetype(p, size)
                    except Exception: pass
            return ImageFont.load_default(size=size)

        # Paths: Ubuntu/GitHub Actions primero, macOS como fallback
        _sans_bold = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
        _sans_reg = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        _arial_black = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",  # Ubuntu (pre-instalado)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",          # Ubuntu fallback
            "/System/Library/Fonts/Supplemental/Arial Black.ttf",            # macOS
            "/Library/Fonts/Arial Black.ttf",
        ]

        font_logo_bold = _fuente(_sans_bold,   38)
        font_logo_reg  = _fuente(_sans_reg,    38)
        font_titulo    = _fuente(_arial_black, 82)
        font_tag       = _fuente(_sans_bold,   34)
        font_cta       = _fuente(_sans_bold,   38)

        # ── Header: "GLOBALpatagonia" centrado ───────────────────────────────────
        bb_g    = draw.textbbox((0, 0), "GLOBAL",     font=font_logo_bold)
        bb_p    = draw.textbbox((0, 0), "patagonia",  font=font_logo_reg)
        total_w = (bb_g[2] - bb_g[0]) + (bb_p[2] - bb_p[0])
        x0      = (ANCHO - total_w) // 2
        y0      = (H_HEADER - (bb_g[3] - bb_g[1])) // 2
        draw.text((x0,                      y0), "GLOBAL",    font=font_logo_bold, fill=C_TEAL)
        draw.text((x0 + bb_g[2] - bb_g[0], y0), "patagonia", font=font_logo_reg,  fill=C_BLANCO)

        # ── Badge de tag (al inicio de la sección oscura, sobre la foto) ─────────
        PADDING = 60
        if tag:
            import re as _re
            _tag_limpio = _re.sub(r"[^\w\sáéíóúüñÁÉÍÓÚÜÑ&/\-]", "", tag).strip().strip("- ").strip()
            tag_txt = f"- {_tag_limpio} -"
            bb_tag  = draw.textbbox((0, 0), tag_txt, font=font_tag)
            tag_w   = (bb_tag[2] - bb_tag[0]) + 44
            tag_h   = (bb_tag[3] - bb_tag[1]) + 18
            tag_x   = PADDING
            tag_y   = Y_DARK - tag_h - 18
            draw.rectangle([(tag_x, tag_y), (tag_x + tag_w, tag_y + tag_h)], fill=C_TEAL)
            draw.text((tag_x + 22, tag_y + 9), tag_txt, font=font_tag, fill=C_DARK)

        # ── Título (sección oscura) ───────────────────────────────────────────────
        MAX_PX   = ANCHO - PADDING * 2
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
                    remaining = word + " " + " ".join(words[idx_w + 1:])
                    current   = remaining.strip()
                    break
                current = word
        if current:
            lines.append(current)
        lines = lines[:3]
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

        LINE_H  = 100
        y_txt   = Y_DARK + 42
        for linea in lines:
            draw.text((PADDING + 2, y_txt + 2), linea, font=font_titulo, fill=C_SHADOW)
            draw.text((PADDING,     y_txt),     linea, font=font_titulo, fill=C_CREMA)
            y_txt += LINE_H

        # ── CTA "ver nota completa" ───────────────────────────────────────────────
        draw.text((PADDING, ALTO - 60), "ver nota completa", font=font_cta, fill=C_TEAL)

        # ── Guardar _ig.jpg ───────────────────────────────────────────────────────
        # Usar nota_id como nombre de archivo para evitar que Instagram cachee 404 de runs anteriores
        if nota_id:
            fotos_dir = _os.path.join(_os.path.dirname(ruta_local))
            ruta_ig = _os.path.join(fotos_dir, nota_id + "_ig.jpg")
        else:
            base    = ruta_local.rsplit(".", 1)[0]
            ruta_ig = base + "_ig.jpg"
        canvas.save(ruta_ig, "JPEG", quality=92)
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
    # Buscar _ig.jpg: primero por nota_id (nombre único), fallback por nombre de imagen
    _ig_by_id   = os.path.join(base_dir, "fotos", nota_id + "_ig.jpg") if nota_id else ""
    _ig_by_name = os.path.join(base_dir, imagen.rsplit(".", 1)[0] + "_ig.jpg") if imagen else ""
    if _ig_by_id and os.path.exists(_ig_by_id):
        imagen_ig     = f"fotos/{nota_id}_ig.jpg"
    elif _ig_by_name and os.path.exists(_ig_by_name):
        imagen_ig     = imagen.rsplit(".", 1)[0] + "_ig.jpg"
    else:
        imagen_ig     = None
    image_url_ig   = f"https://globalpatagonia.org/{imagen_ig}" if imagen_ig else None
    image_url_orig = f"https://globalpatagonia.org/{imagen}"
    image_url = image_url_ig or image_url_orig

    hashtags = "#Patagonia #GLOBALpatagonia #Noticias #SurGlobal #PatagoniaArgentina"
    cuerpo_raw = tapa.get("cuerpo", "")
    # Limpiar HTML si lo hubiera
    import re as _re
    cuerpo_texto = _re.sub(r"<[^>]+>", "", cuerpo_raw).strip()
    encabezado = f"{bandera} {titulo}\n\n{bajada}\n\n"
    pie = f"\n\n{hashtags}"
    disponible = 2200 - len(encabezado) - len(pie)
    if len(cuerpo_texto) > disponible:
        # Truncar en el último párrafo completo que quepa
        corte = cuerpo_texto[:disponible].rfind("\n\n")
        cuerpo_texto = cuerpo_texto[:corte if corte > 0 else disponible].rstrip() + "…"
    caption = encabezado + cuerpo_texto + pie

    try:
        api_base = f"https://graph.facebook.com/v21.0/{ig_user_id}"

        # Paso 1: crear media container (con fallback a imagen original si _ig.jpg falla)
        def _crear_container_ig(url_img):
            data = urllib.parse.urlencode({
                "image_url":    url_img,
                "caption":      caption,
                "access_token": access_token,
            }).encode()
            req = urllib.request.Request(f"{api_base}/media", data=data, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())

        try:
            resultado = _crear_container_ig(image_url)
        except urllib.error.HTTPError as http_err:
            detalle = http_err.read().decode("utf-8", errors="replace")
            # Si falló con la imagen _ig.jpg, reintentar con la original
            if image_url_ig and image_url != image_url_orig:
                print(f"  Instagram _ig.jpg falló ({http_err.code}): {detalle[:200]}, reintentando con imagen original...")
                try:
                    resultado = _crear_container_ig(image_url_orig)
                except urllib.error.HTTPError as http_err2:
                    detalle2 = http_err2.read().decode("utf-8", errors="replace")
                    print(f"  Instagram container falló {http_err2.code}: {detalle2}")
                    return
            else:
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

    base_dir_i    = os.path.dirname(__file__)
    imagen_ig_i   = imagen.rsplit(".", 1)[0] + "_ig.jpg"
    image_url_ig_i  = f"https://globalpatagonia.org/{imagen_ig_i}" if os.path.exists(os.path.join(base_dir_i, imagen_ig_i)) else None
    image_url_orig_i = f"https://globalpatagonia.org/{imagen}"
    image_url = image_url_ig_i or image_url_orig_i

    caption = (
        f"{tag} {titulo}\n\n"
        f"{bajada}\n\n"
        f"🔗 Ver nota completa → link en bio\n\n"
        f"#Patagonia #GLOBALpatagonia #Informe #SurGlobal #PatagoniaArgentina"
    )

    try:
        api_base = f"https://graph.facebook.com/v21.0/{ig_user_id}"

        # Paso 1: crear container (con fallback a imagen original si _ig.jpg falla)
        def _crear_container_informe_ig(url_img):
            data = urllib.parse.urlencode({
                "image_url":    url_img,
                "caption":      caption,
                "access_token": access_token,
            }).encode()
            req = urllib.request.Request(f"{api_base}/media", data=data, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())

        try:
            resultado = _crear_container_informe_ig(image_url)
        except urllib.error.HTTPError as http_err:
            detalle = http_err.read().decode("utf-8", errors="replace")
            if image_url_ig_i and image_url != image_url_orig_i:
                print(f"  Instagram informe _ig.jpg falló ({http_err.code}), reintentando con imagen original...")
                try:
                    resultado = _crear_container_informe_ig(image_url_orig_i)
                except urllib.error.HTTPError as http_err2:
                    detalle2 = http_err2.read().decode("utf-8", errors="replace")
                    print(f"  Instagram informe container falló {http_err2.code}: {detalle2}")
                    return
            else:
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


def publicar_notas_manuales_nuevas():
    """Publica en Telegram y Facebook notas manuales con campo 'postear_redes': true que aún no fueron posteadas."""
    base_dir   = os.path.dirname(__file__)
    state_path = os.path.join(base_dir, "telegram_state.json")
    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}

    manuales_posteadas = set(state.get("manuales_posteadas", []))

    # JSONs de sección donde pueden aparecer notas manuales
    fuentes_manuales = [
        "turismo.json",
        "deportes_feed.json",
        "negocios.json",
        "cultura.json",
        "guias.json",
        "historias.json",
    ]

    nuevas = []
    for archivo in fuentes_manuales:
        path = os.path.join(base_dir, archivo)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                datos = json.load(f)
        except Exception:
            continue
        # Normalizar a lista de notas
        if isinstance(datos, dict):
            notas_candidatas = [datos.get("principal")] + datos.get("secundarias", []) + datos.get("row_cards", [])
        else:
            notas_candidatas = datos
        for nota in notas_candidatas:
            if not nota:
                continue
            if not nota.get("postear_redes"):
                continue
            nota_id = nota.get("id", "")
            if nota_id and nota_id not in manuales_posteadas:
                nuevas.append(nota)

    if not nuevas:
        return

    print(f"\n  Notas manuales a publicar: {len(nuevas)}")
    for nota in nuevas:
        nota_id = nota.get("id", "")
        # Generar _ig.jpg con nota_id como nombre de archivo
        img_local = os.path.join(base_dir, nota.get("imagen", ""))
        if os.path.exists(img_local):
            _generar_imagen_ig(img_local, nota.get("titulo", ""), nota.get("tag", ""), nota_id=nota_id)
        # Telegram
        print(f"  Manual Telegram: [{nota_id}]...")
        publicar_telegram(nota)
        # Facebook
        print(f"  Manual Facebook: [{nota_id}]...")
        publicar_facebook(nota)
        manuales_posteadas.add(nota_id)

    state["manuales_posteadas"] = list(manuales_posteadas)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


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
    # Las 3 notas de tapa van a Instagram (misma regla que Telegram/Facebook)
    notas_ig    = [n for n in [tapa] + secundarias if n]

    state_path = os.path.join(base_dir, "telegram_state.json")
    try:
        with open(state_path, encoding="utf-8") as f:
            ig_state = json.load(f)
    except Exception:
        ig_state = {}

    tapa_ig_posteadas = set(ig_state.get("tapa_ig_posteadas", []))
    for nota_ig in notas_ig:
        nid = nota_ig.get("id", "")
        if nid in tapa_ig_posteadas:
            continue
        print(f"\n  Publicando tapa en Instagram (post-push)…")
        publicar_instagram(nota_ig)
        if nid:
            tapa_ig_posteadas.add(nid)
    ig_state["tapa_ig_posteadas"] = list(tapa_ig_posteadas)

    print("\n  Publicando informe en Instagram (post-push)…")
    publicar_instagram_informe_nuevo()

    # Secciones automáticas (ig_state ya cargado arriba)

    secciones_archivos = [
        ("deportes_feed.json", "deportes",  lambda d: d.get("principal")),
        ("negocios.json",      "negocios",  lambda d: d[0] if d else None),
        ("cultura.json",       "cultura",   lambda d: d[0] if d else None),
        ("turismo.json",       "turismo",   lambda d: d[0] if d else None),
    ]
    for archivo, clave, extractor in secciones_archivos:
        sec_path = os.path.join(base_dir, archivo)
        if not os.path.exists(sec_path):
            continue
        try:
            with open(sec_path, encoding="utf-8") as f:
                sec_data = json.load(f)
        except Exception:
            continue
        nota_sec = extractor(sec_data)
        if not nota_sec:
            continue
        sec_id = nota_sec.get("id", "")
        if not sec_id:
            continue
        if ig_state.get(f"ultimo_{clave}_instagram") == sec_id:
            continue
        print(f"\n  Publicando {clave} en Instagram (post-push)…")
        publicar_instagram(nota_sec)
        ig_state[f"ultimo_{clave}_instagram"] = sec_id

    # Notas manuales en Instagram (fallback al campo viejo para migración)
    manuales_ig_posteadas = set(ig_state.get("manuales_ig_posteadas") or ig_state.get("manuales_posteadas", []))
    # También excluir notas que ya se postearon como sección en este mismo run
    _ya_posteadas_como_seccion = {
        ig_state.get(f"ultimo_{c}_instagram") for c in ["deportes", "negocios", "cultura", "turismo"]
    } - {None}
    manuales_ig_posteadas |= _ya_posteadas_como_seccion

    fuentes_manuales_ig = [
        ("turismo.json",       lambda d: d if isinstance(d, list) else []),
        ("deportes_feed.json", lambda d: [d.get("principal")] + d.get("secundarias", []) + d.get("row_cards", [])),
        ("negocios.json",      lambda d: d if isinstance(d, list) else []),
        ("cultura.json",       lambda d: d if isinstance(d, list) else []),
        ("guias.json",         lambda d: d if isinstance(d, list) else []),
        ("historias.json",     lambda d: d if isinstance(d, list) else []),
    ]
    for archivo, extractor_m in fuentes_manuales_ig:
        path_m = os.path.join(base_dir, archivo)
        if not os.path.exists(path_m):
            continue
        try:
            with open(path_m, encoding="utf-8") as f:
                datos_m = json.load(f)
        except Exception:
            continue
        for nota_m in extractor_m(datos_m):
            if not nota_m or not nota_m.get("postear_redes"):
                continue
            mid = nota_m.get("id", "")
            if mid and mid not in manuales_ig_posteadas:
                print(f"\n  Manual Instagram: [{mid}]…")
                publicar_instagram(nota_m)
                manuales_ig_posteadas.add(mid)

    ig_state["manuales_ig_posteadas"] = list(manuales_ig_posteadas)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(ig_state, f, ensure_ascii=False, indent=2)

    print("\n  ✓ Instagram post-push listo")


def solo_facebook():
    """Postea las notas del día a Facebook sin correr el script completo."""
    base_dir = os.path.dirname(__file__)
    try:
        with open(os.path.join(base_dir, "noticias.json"), encoding="utf-8") as f:
            noticias = json.load(f)
    except Exception as e:
        print(f"  Error leyendo noticias.json: {e}")
        return

    tapa        = noticias.get("tapa", {})
    secundarias = noticias.get("secundarias", [])
    notas       = [n for n in [tapa] + secundarias if n]

    print(f"\n  Publicando {len(notas)} notas de tapa en Facebook...")
    for nota in notas:
        print(f"  → [{nota.get('id','')}] {nota.get('titulo','')[:60]}")
        publicar_facebook(nota)

    # Negocios
    neg_path = os.path.join(base_dir, "negocios.json")
    try:
        with open(neg_path, encoding="utf-8") as f:
            negocios_data = json.load(f)
        if negocios_data:
            neg = negocios_data[0]
            print(f"\n  Publicando negocios en Facebook...")
            print(f"  → [{neg.get('id','')}] {neg.get('titulo','')[:60]}")
            publicar_facebook(neg)
    except Exception as e:
        print(f"  Error en negocios: {e}")

    print("\n  ✓ Facebook manual listo")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--solo-instagram":
        solo_instagram()
    elif len(sys.argv) > 1 and sys.argv[1] == "--solo-facebook":
        solo_facebook()
    else:
        main()
