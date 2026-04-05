#!/usr/bin/env python3
"""
globalPATAGONIA — Actualizador de Noticias
Obtiene noticias de fuentes RSS, filtra las patagónicas y las reescribe con Claude.
Acumula artículos en historial.json (1-3 nuevos por corrida).
Genera noticias.json que el sitio web carga automáticamente.

Uso:
    python3 actualizar_noticias.py
"""

import json
import sys
import os
import random
import urllib.request
import urllib.parse
from datetime import datetime

import feedparser
import anthropic

# ══════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════

# Carga las claves desde el archivo .env si existe
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

API_KEY          = os.environ.get("ANTHROPIC_API_KEY", "")
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
    # ── Argentina · Nacional ──
    {"nombre": "La Nación",               "url": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/",   "region": "Nacional"},
    {"nombre": "Infobae",                 "url": "https://www.infobae.com/feeds/rss/",                   "region": "Nacional"},
    {"nombre": "Clarín",                  "url": "https://www.clarin.com/rss/lo-ultimo/",                "region": "Nacional"},
    # ── Chile · Regionales ──
    {"nombre": "La Prensa Austral",       "url": "https://laprensaaustral.cl/feed/",                     "region": "Magallanes"},
    {"nombre": "El Divisadero",           "url": "https://www.eldivisadero.cl/feed/",                    "region": "Aysén"},
    {"nombre": "El Llanquihue",           "url": "https://www.elllanquihue.cl/feed/",                    "region": "Los Lagos"},
    {"nombre": "El Pingüino",             "url": "https://www.elpinguino.com/feed/",                     "region": "Magallanes"},
    {"nombre": "Diario de Valdivia",      "url": "https://www.diariodevaldivia.cl/feed/",                "region": "Los Ríos"},
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
    # Medio ambiente — PRIORIDAD MÁXIMA
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
    # Servicios cotidianos
    "clima", "alerta meteorológica", "viento", "nevada", "temporal",
]

MAX_HISTORIAL = 50   # artículos máximos a guardar
MAX_FEED      = 15   # artículos máximos a mostrar en el feed

# ══════════════════════════════════════════════════════════

DIAS_ES   = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
MESES_ES  = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio",
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


# ── Historial ──────────────────────────────────────────────

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
    path = os.path.join(os.path.dirname(__file__), "historial.json")
    archivo_path = os.path.join(os.path.dirname(__file__), "archivo.json")

    # Notas que quedan fuera del historial → van al archivo
    descartadas = articulos[MAX_HISTORIAL:]
    if descartadas:
        try:
            with open(archivo_path, encoding="utf-8") as f:
                archivo = json.load(f)
        except Exception:
            archivo = {"_info": "Notas que rotaron del feed principal. Base del buscador.", "notas": []}
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


# ── RSS ────────────────────────────────────────────────────

def fetch_noticias_crudas():
    noticias = []
    print(f"\n{'='*55}")
    print(f"  globalPATAGONIA — Actualizando noticias")
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


# ── Claude ─────────────────────────────────────────────────

def reescribir_con_claude(noticias_crudas, historial):
    if not noticias_crudas:
        print("  ⚠ No se encontraron noticias patagónicas.")
        return None

    client = anthropic.Anthropic(api_key=API_KEY)

    ya_publicadas  = urls_ya_publicadas(historial)
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

    prompt = f"""Sos el editor jefe de globalPATAGONIA, el primer medio digital panpatagónico. Slogan: "Sur Global, principio de todo." Cobertura: Argentina y Chile sin fronteras.

IDENTIDAD EDITORIAL:
- La Patagonia no es periferia — es el comienzo. Escribís desde adentro, no desde Buenos Aires ni Santiago.
- Voz: directa, contextual, apasionada por la región, rigurosa. Nunca alarmista, nunca partidaria.
- Cada nota tiene perspectiva propia: qué significa para la Patagonia binacional, antecedentes, qué viene después.
- Si el hecho cruza la frontera Argentina-Chile, marcarlo siempre.
- NUNCA copiés párrafos de la fuente. Reescribí con voz propia.

CRITERIO DE SELECCIÓN — solo entran notas con anclaje patagónico real:
✓ Medio Ambiente: glaciares, agua, fauna, ecosistemas, legislación ambiental, especies invasoras, contaminación
✓ Pueblos Originarios: Mapuche, Tehuelche, Kawésqar, Selknam — territorio, derechos, cultura viva
✓ Deportes Patagónicos: trail, escalada, kayak, ski, triatlón, expediciones, carreras aventura
✓ Desarrollo & Producción: economía regional, pesca, ganadería, energía, infraestructura, conectividad
✓ Cultura: arte, música, identidad, historia, gastronomía, fiestas regionales, pioneros
✓ Ciencia & Tecnología: hallazgos CONICET, paleontología, innovación aplicada al territorio
✓ Turismo & Guías: destinos, temporadas, premios internacionales a Patagonia
✓ Bienestar: salud, comunidad, calidad de vida con impacto regional concreto

PRIORIDADES EDITORIALES — orden estricto:
1. MEDIO AMBIENTE CRÍTICO: glaciares, pesca ilegal en ZEE, incendios, especies en peligro, contaminación → TAPA AUTOMÁTICA.
2. PUEBLOS ORIGINARIOS: cualquier nota sobre comunidades originarias patagónicas con hecho concreto.
3. DEPORTES ÚNICOS: premios internacionales, expediciones históricas, trail, escalada, ski.
4. PRODUCCIÓN CON IDENTIDAD: historia de productor patagónico, producto único de la región, primer hito económico local.
5. TURISMO & CULTURA: destinos, fiestas regionales, artistas, premiaciones.
6. DESARROLLO: infraestructura, conectividad, energía con impacto concreto.
7. POLÍTICA: SOLO decisión de gobierno con impacto territorial directo y concreto. Sin política partidaria.

DESCARTAR SIEMPRE: policiales, accidentes de tránsito, crónica roja, economía nacional sin anclaje patagónico, política porteña o santiaguina sin efecto en el territorio.

REGLA DE ORO: el lector viene a leer la Patagonia. Ante la duda, elegí la nota que habla de territorio, naturaleza, gente o cultura.

Tenés estas noticias nuevas disponibles hoy:
{listado}

Tu tarea:
1. Elegí LA MEJOR para la tapa del día (medio ambiente y pueblos originarios tienen prioridad automática)
2. Elegí entre 1 y 3 noticias adicionales para el feed del día
3. Escribí el artículo completo de cada una con voz propia de globalPATAGONIA
4. Generá 5 titulares breves para el ticker (hechos concretos, sin clickbait)

Estructura del artículo (campo "cuerpo"):
- Párrafo de entrada: el hecho central con ángulo patagónico propio
- 2-3 párrafos: contexto regional, qué significa para la Patagonia, antecedentes, conexión binacional si aplica
- Párrafo de cierre: diagnóstico editorial, qué se espera o qué está en juego
- Separar párrafos con \\n\\n — entre 350 y 500 palabras

Respondé SOLO con este JSON válido (sin texto adicional):
{{
  "ticker": ["titular corto 1", "titular corto 2", "titular corto 3", "titular corto 4", "titular corto 5"],
  "tapa": {{
    "id": "{hoy}-tapa",
    "titulo": "Título reescrito atractivo (máx 15 palabras)",
    "bajada": "Bajada con contexto y ángulo propio (2-3 oraciones)",
    "cuerpo": "Artículo completo con párrafos separados por \\n\\n",
    "tag": "emoji + categoría",
    "categoria": "medio ambiente|pueblos originarios|deportes|turismo|cultura|ciencia|producción|conectividad|bienestar|pesca|historia|general",
    "fuente": "Nombre del medio original",
    "url_original": "url completa",
    "pais": "argentina|chile|ambos",
    "imagen": null,
    "imagen_keywords": "2-3 palabras en inglés para buscar foto (ej: glacier patagonia, indigenous patagonia, trail running mountains)"
  }},
  "nuevas": [
    {{
      "id": "{hoy}-1",
      "titulo": "Título (máx 12 palabras)",
      "bajada": "Una oración de contexto con dato concreto",
      "cuerpo": "Artículo completo con párrafos separados por \\n\\n",
      "tag": "· Categoría ·",
      "categoria": "...",
      "fuente": "...",
      "url_original": "url completa",
      "pais": "argentina|chile|ambos",
      "imagen": null,
      "imagen_keywords": "2-3 palabras en inglés"
    }}
  ]
}}"""

    print("  Enviando a Claude para reescritura editorial...", end=" ", flush=True)
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()
        if "```" in texto:
            partes = texto.split("```")
            for parte in partes:
                if parte.startswith("json"):
                    texto = parte[4:].strip()
                    break
                elif parte.strip().startswith("{"):
                    texto = parte.strip()
                    break
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


# ── Imágenes ───────────────────────────────────────────────

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

        # Buscar og:image en ambos órdenes de atributos
        match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if not match:
            match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
        if not match:
            return None

        img_url = match.group(1).strip()
        if not img_url.startswith("http"):
            return None

        # Determinar extensión
        ext = img_url.split("?")[0].rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        filename = f"foto-{nota_id}.{ext}"
        ruta_local = os.path.join(os.path.dirname(__file__), "fotos", filename)

        # No descargar si ya existe
        if os.path.exists(ruta_local):
            return f"fotos/{filename}"

        img_req = urllib.request.Request(img_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(img_req, timeout=10) as resp:
            contenido = resp.read()

        with open(ruta_local, "wb") as f:
            f.write(contenido)

        return f"fotos/{filename}"

    except Exception as e:
        print(f"(og:image error: {e})")
        return None


def extraer_galeria_articulo(url_articulo, nota_id):
    """Descarga las fotos del interior del artículo fuente y las guarda en fotos/.
    Retorna lista de rutas locales (máx. 4 fotos, excluyendo thumbnails y gifs)."""
    if not url_articulo:
        return []
    try:
        import re
        req = urllib.request.Request(url_articulo, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Recolectar URLs desde data-src y src en img tags
        candidatas = []

        # data-src (lazy loading — más confiable para imágenes reales del artículo)
        for m in re.finditer(r'data-src=["\']([^"\']+)["\']', html):
            candidatas.append(m.group(1))

        # src convencional como fallback
        for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html):
            candidatas.append(m.group(1))

        # Filtrar y deduplicar
        base = url_articulo.split("/")[0] + "//" + url_articulo.split("/")[2]
        vistas = set()
        urls_limpias = []
        for url in candidatas:
            # Completar URLs relativas
            if url.startswith("/"):
                url = base + url
            if not url.startswith("http"):
                continue
            # Saltar gifs, thumbnails, logos, iconos, tracking pixels y banners promo
            url_lower = url.lower()
            if any(x in url_lower for x in [
                ".gif", "miniatura", "thumbnail", "thumb", "logo",
                "favicon", "icon", "avatar", "pixel", "static/custom",
                "data:,", "1x1", "spacer",
                # Banners publicitarios y elementos de medio (TV, radio, señal online)
                "radio", "-tv", "tv-", "senal-online", "señal-online",
                "publicidad", "banner", "promo", "newsletter", "popup",
                "sidebar", "portada-diario", "tapa-diario", "tapa_diario",
                "portada_diario", "anuncio", "advertisement", "ads/",
                "/ad-", "widget", "plugin", "share", "social-icon",
            ]):
                continue
            # Solo imágenes reales
            ext_match = re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', url_lower)
            if not ext_match:
                continue
            # Deduplicar por URL limpia (sin query string)
            url_base = url.split("?")[0]
            if url_base in vistas:
                continue
            vistas.add(url_base)
            urls_limpias.append(url)
            if len(urls_limpias) >= 6:  # tomar más candidatas para filtrar después
                break

        # Descargar hasta 4 fotos (saltando la primera si ya es la og:image)
        fotos_dir = os.path.join(os.path.dirname(__file__), "fotos")
        galeria = []
        descargadas = 0
        for i, img_url in enumerate(urls_limpias):
            if descargadas >= 4:
                break
            ext = re.search(r'\.(jpg|jpeg|png|webp)', img_url.lower())
            ext = ext.group(1) if ext else "jpg"
            if ext == "jpeg":
                ext = "jpg"
            filename = f"foto-{nota_id}-g{i+1}.{ext}"
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
                # Saltar imágenes muy pequeñas (< 10 KB = probablemente ícono)
                if len(contenido) < 10_000:
                    continue
                with open(ruta_local, "wb") as f:
                    f.write(contenido)
                galeria.append(f"fotos/{filename}")
                descargadas += 1
            except Exception:
                continue

        return galeria

    except Exception as e:
        print(f"(galeria error: {e})")
        return []


def buscar_foto_propia(nota, fotos):
    # Solo matchea contra imagen_keywords (campo específico que Claude genera para la foto)
    # No usa el título para evitar falsos positivos por palabras comunes como "neuquén" o "historia"
    keywords_nota = nota.get("imagen_keywords", "").lower()
    if not keywords_nota:
        return None
    for foto in fotos:
        if any(kw in keywords_nota for kw in foto.get("keywords", [])):
            return f"fotos/{foto['archivo']}"
    return None


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


def _descargar_imagen_externa(url_http, nota_id, sufijo=""):
    """Descarga una URL de imagen externa y la guarda en fotos/. Retorna ruta local o None."""
    if not url_http or not url_http.startswith("http"):
        return None
    try:
        ext = url_http.split("?")[0].rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"
        filename = f"foto-{nota_id}{sufijo}.{ext}"
        ruta_local = os.path.join(os.path.dirname(__file__), "fotos", filename)
        if os.path.exists(ruta_local):
            return f"fotos/{filename}"
        req = urllib.request.Request(url_http, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            contenido = resp.read()
        if len(contenido) < 5_000:   # descarte imágenes insignificantes
            return None
        with open(ruta_local, "wb") as f:
            f.write(contenido)
        return f"fotos/{filename}"
    except Exception:
        return None


def _foto_fallback(fotos_propias, fotos_usadas):
    """Devuelve una foto genérica de patagonia del repositorio como último recurso."""
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
    # Si todas están usadas, reusar la primera disponible
    for f in fallbacks:
        if os.path.exists(f):
            return f
    return None


def resolver_imagen(nota, fotos_propias, fotos_usadas):
    """Siempre retorna una ruta local fotos/... — nunca una URL externa.
    Jerarquía: RSS (descargada) > og:image (descargada) > foto propia > Unsplash (descargada) > fallback."""
    nota_id = nota.get("id", "sin-id")

    # 1. Imagen del RSS → descargar localmente
    rss_url = nota.get("imagen", "")
    if rss_url and str(rss_url).startswith("http"):
        print(f"    [{nota_id}] imagen RSS...", end=" ", flush=True)
        local = _descargar_imagen_externa(rss_url, nota_id, "-rss")
        if local:
            print(f"OK → {local}")
            return local
        print("falló descarga")

    # 2. og:image de la URL original del artículo (ya descarga internamente)
    url_original = nota.get("url_original", "")
    if url_original:
        print(f"    [{nota_id}] og:image fuente...", end=" ", flush=True)
        og_img = extraer_og_image(url_original, nota_id)
        if og_img:
            print(f"OK → {og_img}")
            return og_img
        print("no encontrada")

    # 3. Foto propia por keywords (sin repetir)
    foto_propia = buscar_foto_propia(nota, fotos_propias)
    if foto_propia and foto_propia not in fotos_usadas:
        fotos_usadas.add(foto_propia)
        print(f"    [{nota_id}] foto propia: {foto_propia} ✓")
        return foto_propia

    # 4. Unsplash → descargar localmente
    keywords = nota.get("imagen_keywords", "patagonia landscape")
    print(f"    [{nota_id}] Unsplash: '{keywords}' ...", end=" ", flush=True)
    url = buscar_imagen_unsplash(keywords)
    if url:
        local = _descargar_imagen_externa(url, nota_id, "-unsplash")
        if local:
            print(f"OK → {local}")
            return local
    print("sin resultado")

    # 5. Fallback: foto genérica del repositorio
    fallback = _foto_fallback(fotos_propias, fotos_usadas)
    if fallback:
        print(f"    [{nota_id}] fallback: {fallback}")
        return fallback

    return None


# ── JSON de salida ─────────────────────────────────────────

def cargar_historias_permanentes():
    """Carga las notas permanentes desde historias.json (nunca se sobreescribe)."""
    ruta = os.path.join(os.path.dirname(__file__), "historias.json")
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("notas", [])
    except Exception:
        return []


def cargar_propios():
    """Carga las notas propias (globalPATAGONIA / J. Martineau) desde propios.json.
    Este archivo es el archivo permanente de notas de producción propia.
    El script AGREGA notas nuevas pero NUNCA borra las existentes."""
    ruta = os.path.join(os.path.dirname(__file__), "propios.json")
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def auto_archivar_propios(historial):
    """Detecta notas propias en el historial y las archiva en propios.json
    si aún no están. Garantiza que ninguna nota de J. Martineau se pierda.
    EXCLUYE las notas de historias.json: esas tienen su propia sección
    permanente (Cultura Patagónica) y no deben aparecer también en INFORMES."""
    ruta = os.path.join(os.path.dirname(__file__), "propios.json")
    archivados = cargar_propios()
    ids_archivados = {a.get("id") for a in archivados}

    # IDs de historias.json → nunca archivar en propios.json (evita duplicados)
    ids_historias = {a.get("id") for a in cargar_historias_permanentes()}

    nuevos = [
        a for a in historial
        if es_propio(a)
        and a.get("id") not in ids_archivados
        and a.get("id") not in ids_historias
    ]
    if not nuevos:
        return

    archivados = nuevos + archivados  # los más recientes al frente
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(archivados, f, ensure_ascii=False, indent=2)
    titulos = [n.get("titulo", "")[:50] for n in nuevos]
    print(f"  ★ Archivadas {len(nuevos)} nota(s) propia(s) en propios.json: {titulos}")


def es_propio(articulo):
    """Artículo escrito por globalPATAGONIA / J. Martineau."""
    fuente = articulo.get("fuente", "") or ""
    autor  = articulo.get("autor", "")  or ""
    return (
        "globalPATAGONIA" in fuente or
        "Martineau" in autor or
        "globalPATAGONIA" in autor or
        articulo.get("propio") is True
    )


def dias_desde_id(articulo_id):
    """Extrae la fecha del ID (YYYYMMDD-...) y devuelve días transcurridos."""
    try:
        fecha_str = str(articulo_id)[:8]
        fecha_art = datetime.strptime(fecha_str, "%Y%m%d")
        return (datetime.now() - fecha_art).days
    except Exception:
        return 999


def construir_noticias_json(tapa, historial, ticker):
    """Arma noticias.json con tapa + feed.

    REGLAS:
    - Los artículos propios (J. Martineau / globalPATAGONIA) van EXCLUSIVAMENTE
      a INFORMES (propios.json). NUNCA aparecen en tapa ni en el feed de noticias.
    - INFORMES solo se renueva cuando se agrega una nota nueva manualmente.
    - No puede haber el mismo artículo dos veces en el feed (deduplicación por ID).
    """
    hoy = datetime.now()

    # ── IDs a excluir del feed ──────────────────────────────────
    # Propios (van a INFORMES) + historias permanentes (tienen su sección propia)
    ids_propios   = {a.get("id") for a in cargar_propios()}
    ids_historias = {a.get("id") for a in cargar_historias_permanentes()}
    ids_excluir   = ids_propios | ids_historias

    # ── Tapa ────────────────────────────────────────────────────
    # La tapa es siempre la que eligió Claude; los propios nunca la ocupan.
    tapa_final = tapa

    # ── Feed: historial sin propios ni historias, sin duplicados ─
    ids_vistos = {tapa_final.get("id")}
    feed = []
    for a in historial:
        aid = a.get("id")
        if aid in ids_vistos or aid in ids_excluir or es_propio(a):
            continue
        ids_vistos.add(aid)
        feed.append(a)
        if len(feed) >= MAX_FEED:
            break

    secundarias    = feed[:2]
    noticias_cards = feed[2:10]  # 8 tarjetas en Noticias de la Semana

    historias = cargar_historias_permanentes()

    # Nota: turismo.json es manual (se actualiza los domingos) — el script no lo toca.

    return {
        "generado":      hoy.isoformat(),
        "fecha_display": fecha_display(),
        "ticker":        ticker,
        "tapa":          tapa_final,
        "secundarias":   secundarias,
        "noticias":      noticias_cards,
        "historias":     historias,
    }


def guardar_json(datos):
    ruta = os.path.join(os.path.dirname(__file__), "noticias.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ noticias.json guardado")
    return ruta


# ── Agenda ────────────────────────────────────────────────

PALABRAS_EVENTO = [
    "festival", "carrera", "maratón", "maratón", "trail", "ultratrail",
    "muestra", "exposición", "feria", "fiesta regional", "fiesta nacional",
    "congreso", "encuentro", "torneo", "campeonato", "competencia",
    "convocatoria abierta", "ciclo de cine", "ciclo cultural",
    "regata", "travesía", "expedición", "kayak", "ski", "snowboard",
    "semana de", "aniversario", "celebración",
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
    """Purga eventos vencidos y busca nuevos en las noticias del día."""
    agenda = cargar_agenda()
    hoy = datetime.now().strftime("%Y-%m-%d")

    # 1. Purgar eventos vencidos
    antes = len(agenda)
    agenda = [e for e in agenda if (e.get("fecha_fin") or e.get("fecha", "")) >= hoy]
    purgados = antes - len(agenda)
    if purgados:
        print(f"  Agenda: {purgados} evento(s) vencido(s) eliminado(s)")

    # 2. Filtrar noticias que parecen eventos
    ids_existentes = {e.get("id", "") for e in agenda}
    candidatos = [n for n in noticias_crudas if es_evento(n["titulo_original"], n["resumen_original"])]

    if not candidatos:
        print(f"  Agenda: sin eventos nuevos detectados en RSS")
        guardar_agenda(agenda)
        return

    print(f"  Agenda: {len(candidatos)} posible(s) evento(s) encontrado(s) en RSS")

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
    prompt = f"""Sos el editor de agenda de globalPATAGONIA. Hoy es {hoy}.

Analizá estas noticias y extraé SOLO las que corresponden a un evento futuro concreto (festival, carrera, muestra, fiesta, torneo, congreso, etc.) con fecha definida en la Patagonia argentina o chilena. Ignorá inauguraciones de obras, nombramientos, noticias sin fecha de evento.

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

Respondé SOLO con un array JSON válido. Si no hay eventos válidos respondé [].
"""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()
        # Limpiar markdown
        if "```" in texto:
            for parte in texto.split("```"):
                p = parte.strip()
                if p.startswith("json"):
                    texto = p[4:].strip(); break
                elif p.startswith("[") or p.startswith("{"):
                    texto = p; break
        inicio = texto.find("[")
        fin = texto.rfind("]") + 1
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

    # Ordenar por fecha
    agenda.sort(key=lambda e: e.get("fecha", ""))
    guardar_agenda(agenda)


# ── Rotación diaria de Deportes ────────────────────────────

def rotar_deportes(historial):
    """Cada día: agrega la nota de deportes más reciente del historial
    al frente de row_cards en deportes_feed.json. Mantiene máximo 4 entradas."""
    ruta = os.path.join(os.path.dirname(__file__), "deportes_feed.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            feed = json.load(f)
    except Exception:
        return

    row_cards = feed.get("row_cards", [])
    ids_en_feed = (
        {feed.get("principal", {}).get("id")}
        | {s.get("id") for s in feed.get("secundarias", [])}
        | {c.get("id") for c in row_cards}
    )

    nueva = None
    cats_deportes = ("deportes", "aventura", "escalada", "trail", "ski", "kayak")
    for art in historial:
        if art.get("id") in ids_en_feed or es_propio(art):
            continue
        if art.get("categoria", "").lower() in cats_deportes:
            nueva = art
            break

    if not nueva:
        return

    nueva_card = {
        "id":     nueva["id"],
        "tag":    nueva.get("tag", "🏃 Deportes"),
        "titulo": nueva["titulo"],
        "imagen": nueva.get("imagen", ""),
        "meta":   nueva.get("meta", ""),
    }
    feed["row_cards"] = [nueva_card] + row_cards[:3]

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)
    print(f"  Deportes rotado: [{nueva['id']}] '{nueva['titulo'][:55]}…'")


# ── Rotación semanal de Cultura ───────────────────────────

def rotar_cultura(historial):
    """Los sábados: agrega la nota de cultura/historia más reciente del historial
    al frente de cultura.json. Mantiene máximo 6 entradas (grilla 2×3)."""
    if datetime.now().weekday() != 5:   # 5 = sábado
        return

    ruta = os.path.join(os.path.dirname(__file__), "cultura.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            cultura_actual = json.load(f)
    except Exception:
        cultura_actual = []

    ids_en_cultura = {c["id"] for c in cultura_actual}
    ids_historias  = {a.get("id") for a in cargar_historias_permanentes()}

    # Categorías consideradas "cultura"
    cats_cultura = ("cultura", "historia", "pueblos originarios")

    nueva = None
    for art in historial:
        if art.get("id") in ids_en_cultura or art.get("id") in ids_historias:
            continue
        if es_propio(art):
            continue
        if art.get("categoria", "").lower() in cats_cultura:
            nueva = art
            break

    if not nueva:
        print("  Cultura: sin nota nueva para rotar este sábado.")
        return

    entrada = {
        "id":        nueva["id"],
        "titulo":    nueva["titulo"],
        "bajada":    nueva.get("bajada", ""),
        "imagen":    nueva.get("imagen", ""),
        "tag":       nueva.get("tag", "🎭 Cultura"),
        "categoria": nueva.get("categoria", "cultura"),
        "meta":      nueva.get("meta", ""),
        "pais":      nueva.get("pais", "argentina"),
    }

    # Insertar al frente, mantener máximo 6
    cultura_nuevo = [entrada] + cultura_actual[:5]

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cultura_nuevo, f, ensure_ascii=False, indent=2)

    print(f"  Cultura rotada (sábado): [{nueva['id']}] '{nueva['titulo'][:60]}…'")


# ── Rotación semanal de Turismo ────────────────────────────

def rotar_turismo(historial):
    """Los domingos: agrega la mejor nota de turismo de la semana al frente
    de turismo.json y descarta la última. El archivo siempre mantiene 3 entradas."""
    if datetime.now().weekday() != 6:   # 6 = domingo
        return

    ruta = os.path.join(os.path.dirname(__file__), "turismo.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            turismo_actual = json.load(f)
    except Exception:
        turismo_actual = []

    ids_en_turismo = {t["id"] for t in turismo_actual}

    # Buscar la nota de turismo más reciente en historial que no esté ya en turismo.json
    nueva = None
    for art in historial:
        if art.get("id") in ids_en_turismo or es_propio(art):
            continue
        cat = art.get("categoria", "").lower()
        if cat in ("turismo", "turismo y guías", "guías"):
            nueva = art
            break

    if not nueva:
        print("  Turismo: sin nota nueva para rotar este domingo.")
        return

    entrada = {
        "id":     nueva["id"],
        "badge":  "TURISMO",
        "titulo": nueva["titulo"],
        "bajada": nueva.get("bajada", ""),
        "imagen": nueva.get("imagen", ""),
        "meta":   nueva.get("meta", ""),
        "url_original": nueva.get("url_original", ""),
    }

    # Insertar al frente, mantener máximo 3
    turismo_nuevo = [entrada] + turismo_actual[:2]

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(turismo_nuevo, f, ensure_ascii=False, indent=2)

    print(f"  Turismo rotado (domingo): [{nueva['id']}] '{nueva['titulo'][:60]}…'")


# ── Main ───────────────────────────────────────────────────

def main():
    # 1. Cargar historial
    historial = cargar_historial()
    print(f"\n  Historial actual: {len(historial)} artículos publicados")

    # 1b. Archivar automáticamente cualquier nota propia en historial
    auto_archivar_propios(historial)

    # 2. Obtener noticias crudas de RSS
    noticias_crudas = fetch_noticias_crudas()

    # 3. Reescribir con Claude (solo noticias nuevas)
    resultado = reescribir_con_claude(noticias_crudas, historial)
    if not resultado:
        print("\n  ✗ No se generaron artículos nuevos.\n")
        sys.exit(1)

    tapa   = resultado.get("tapa", {})
    nuevas = resultado.get("nuevas", [])
    ticker = resultado.get("ticker", [])

    todos_nuevos = [tapa] + nuevas

    # 4. Resolver imágenes
    fotos_propias = fotos_propias_disponibles()
    if fotos_propias:
        print(f"\n  Fotos propias en biblioteca: {len(fotos_propias)}")
    print("\n  Resolviendo imágenes...")
    fotos_usadas = set()
    for nota in todos_nuevos:
        nota["imagen"] = resolver_imagen(nota, fotos_propias, fotos_usadas)
        # Agregar meta si no tiene
        if "meta" not in nota:
            nota["meta"] = f"Hoy · {nota.get('fuente','globalPATAGONIA')}"

    # 4b. Descargar galería de fotos internas del artículo fuente
    print("\n  Descargando galería de fotos internas...")
    for nota in todos_nuevos:
        url_original = nota.get("url_original", "")
        if not url_original or not url_original.startswith("http"):
            continue
        galeria = extraer_galeria_articulo(url_original, nota["id"])
        if galeria:
            nota["galeria"] = galeria
            print(f"    [{nota['id']}] galería: {len(galeria)} foto(s) descargada(s)")

    # 5. Agregar al historial (nuevos van al frente)
    historial = todos_nuevos + historial
    guardar_historial(historial)
    print(f"\n  Artículos nuevos agregados: {len(todos_nuevos)}")
    print(f"  Total en historial: {min(len(historial), MAX_HISTORIAL)}")

    # 5b. Rotación diaria de deportes_feed.json
    rotar_deportes(historial)

    # 5c. Rotación semanal de cultura.json (solo sábados)
    rotar_cultura(historial)

    # 5d. Rotación semanal de turismo.json (solo domingos)
    rotar_turismo(historial)

    # 6. Construir y guardar noticias.json
    datos = construir_noticias_json(tapa, historial, ticker)

    # 6b. Garantía final: ningún artículo en el feed puede tener imagen inexistente
    fotos_usadas_final = set()
    todos_en_feed = [datos["tapa"]] + datos["secundarias"] + datos["noticias"]
    for art in todos_en_feed:
        img = art.get("imagen", "")
        if not img or not os.path.exists(img):
            fb = _foto_fallback([], fotos_usadas_final)
            if fb:
                print(f"  ⚠ Sin foto: [{art.get('id')}] → asignando fallback {fb}")
                art["imagen"] = fb
        else:
            fotos_usadas_final.add(img)

    guardar_json(datos)

    print(f"\n  Feed visible: tapa + {len(datos['secundarias'])} secundarias + {len(datos['noticias'])} cards")

    # 7. Actualizar agenda (purgar vencidos + buscar nuevos)
    print(f"\n  Actualizando agenda...")
    actualizar_agenda(noticias_crudas)

    print(f"\n  Listo. Publicá en Netlify.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
