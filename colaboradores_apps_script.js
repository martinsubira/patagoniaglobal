/**
 * GLOBALpatagonia — Apps Script para portal de colaboradores
 *
 * INSTALACIÓN:
 * 1. Ir a script.google.com → Nuevo proyecto
 * 2. Pegar este código completo
 * 3. En "Implementar" → "Nueva implementación" → Aplicación web
 *    - Ejecutar como: Yo (ficciontvpatagonia@gmail.com)
 *    - Acceso: Cualquier persona
 * 4. Copiar la URL generada y pegarla en colaboradores.html (const APPS_SCRIPT_URL)
 * 5. Crear carpeta en Drive: "GLOBALpatagonia_Colaboradores"
 *    y pegar su ID en DRIVE_FOLDER_ID
 *
 * CONTRASEÑAS iniciales — cambiá después del primer acceso:
 *   amolina → GP2026am
 *   bortega → GP2026bo
 */

// ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────

const TELEGRAM_BOT_TOKEN = "PEGAR_BOT_TOKEN_AQUI";
const TELEGRAM_CHAT_ID   = "791032547";      // Chat de Marto
const ANTHROPIC_API_KEY  = "PEGAR_API_KEY_AQUI";
const DRIVE_FOLDER_ID    = "PEGAR_ID_CARPETA_DRIVE_AQUI";

// Colaboradores autorizados
// Para cambiar contraseña: modificar el campo 'pass'
const USUARIOS = {
  "amolina": {
    nombre: "A. Molina",
    email:  "",      // completar cuando confirmen
    pass:   "GP2026am"
  },
  "bortega": {
    nombre: "B. Ortega",
    email:  "",      // completar cuando confirmen
    pass:   "GP2026bo"
  }
};

// Nombre de sección legible
const SECCIONES = {
  "propios":        "INFORMES",
  "noticias":       "Noticias generales",
  "turismo":        "Turismo en Patagonia",
  "deportes":       "Deportes & Aventura",
  "negocios":       "Economía & Empresas",
  "historia":       "Cultura Patagónica & Historia",
  "medioambiente":  "Medio Ambiente"
};

// ─── ENTRADA PRINCIPAL ──────────────────────────────────────────────────────

function doPost(e) {
  try {
    const datos = JSON.parse(e.postData.contents);
    let resultado;

    if (datos.accion === "login") {
      resultado = manejarLogin(datos);
    } else if (datos.accion === "enviar_articulo") {
      resultado = manejarArticulo(datos);
    } else {
      resultado = { ok: false, mensaje: "Acción desconocida" };
    }

    return ContentService
      .createTextOutput(JSON.stringify(resultado))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, mensaje: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// ─── LOGIN ───────────────────────────────────────────────────────────────────

function manejarLogin(datos) {
  const user = USUARIOS[datos.usuario];
  if (!user || user.pass !== datos.pass) {
    return { ok: false };
  }
  return {
    ok:     true,
    nombre: user.nombre,
    email:  user.email
  };
}

// ─── RECEPCIÓN DE ARTÍCULO ───────────────────────────────────────────────────

function manejarArticulo(datos) {
  // Verificar sesión
  const user = USUARIOS[datos.usuario];
  if (!user) return { ok: false, mensaje: "Sesión inválida" };

  // Generar ID único
  const id = "GP-" + Utilities.formatDate(new Date(), "America/Argentina/Buenos_Aires", "yyyyMMdd") +
             "-" + Math.random().toString(36).substr(2, 5).toUpperCase();

  // Guardar en Drive
  const folder = DriveApp.getFolderById(DRIVE_FOLDER_ID);
  const contenido = armarTextoArticulo(datos, id);
  const archivo = folder.createFile(id + ".txt", contenido, MimeType.PLAIN_TEXT);

  // Guardar foto si existe
  let urlFoto = "";
  if (datos.foto_base64) {
    try {
      const blob = Utilities.newBlob(
        Utilities.base64Decode(datos.foto_base64),
        datos.foto_tipo || "image/jpeg",
        id + "_foto_" + (datos.foto_nombre || "foto.jpg")
      );
      const fotoArchivo = folder.createFile(blob);
      urlFoto = fotoArchivo.getUrl();
    } catch (err) {
      urlFoto = "(error guardando foto: " + err.message + ")";
    }
  }

  // Procesar con Claude
  const procesado = procesarConClaude(datos);

  // Notificar por Telegram
  const msgId = notificarTelegram(datos, procesado, id, urlFoto);

  return { ok: true, id: id };
}

// ─── ARMAR TEXTO COMPLETO PARA DRIVE ────────────────────────────────────────

function armarTextoArticulo(d, id) {
  return [
    "ID: " + id,
    "Fecha: " + new Date().toISOString(),
    "Colaborador: " + d.firma + " <" + d.email + ">",
    "Sección: " + (SECCIONES[d.seccion] || d.seccion),
    "Lugar: " + (d.lugar || "—"),
    "",
    "TÍTULO: " + d.titulo,
    "BAJADA: " + d.bajada,
    "KEYWORDS: " + (d.keywords || "—"),
    "FUENTES: " + (d.fuentes || "—"),
    "",
    "─── CUERPO ───────────────────────────────────────────",
    d.cuerpo || "(texto en documento adjunto)",
    "",
    "─── OBSERVACIONES ────────────────────────────────────",
    d.observaciones || "(ninguna)",
    "",
    "─── EPÍGRAFE FOTO ────────────────────────────────────",
    d.foto_epigrafe || "(sin epígrafe)"
  ].join("\n");
}

// ─── CLAUDE: CORRECCIÓN + SEO ────────────────────────────────────────────────

function procesarConClaude(datos) {
  const cuerpo = datos.cuerpo || "(el colaborador adjuntó documento — revisar en Drive)";

  const prompt = `Sos el editor de GLOBALpatagonia, portal de noticias panpatagónico (Argentina y Chile).
Recibiste el siguiente artículo de un colaborador externo. Tu tarea es:

1. CORRECCIÓN: corregir ortografía, puntuación y gramática. Mantener la voz del autor.
2. TÍTULO SEO: proponer un título optimizado para buscadores (50-65 caracteres).
3. META DESCRIPTION: escribir descripción para SEO (130-155 caracteres).
4. SLUG: generar slug en minúsculas con guiones (ej: glaciar-perito-moreno-record-retroceso).
5. KEYWORDS SEO: listar 5-8 palabras clave separadas por coma.
6. RESUMEN EDITORIAL: 1 párrafo de 2-3 oraciones sobre el artículo para el editor.

DATOS DEL ARTÍCULO:
Título original: ${datos.titulo}
Bajada original: ${datos.bajada}
Sección: ${SECCIONES[datos.seccion] || datos.seccion}
Lugar: ${datos.lugar || "no especificado"}
Keywords del autor: ${datos.keywords || "ninguna"}
Fuentes: ${datos.fuentes || "no especificadas"}

CUERPO:
${cuerpo.substring(0, 4000)}

Respondé EXCLUSIVAMENTE en este formato JSON (sin markdown, sin explicaciones):
{
  "titulo_seo": "...",
  "meta_description": "...",
  "slug": "...",
  "keywords_seo": "...",
  "cuerpo_corregido": "...",
  "resumen_editorial": "..."
}`;

  try {
    const response = UrlFetchApp.fetch("https://api.anthropic.com/v1/messages", {
      method: "post",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
      },
      payload: JSON.stringify({
        model: "claude-opus-4-6",
        max_tokens: 2048,
        messages: [{ role: "user", content: prompt }]
      }),
      muteHttpExceptions: true
    });

    const data = JSON.parse(response.getContentText());
    const texto = data.content[0].text.trim();
    return JSON.parse(texto);

  } catch (err) {
    return {
      titulo_seo: datos.titulo,
      meta_description: datos.bajada,
      slug: datos.titulo.toLowerCase().replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, '-').substring(0, 60),
      keywords_seo: datos.keywords || "",
      cuerpo_corregido: "(procesamiento Claude falló — revisar manualmente)",
      resumen_editorial: "Error al procesar con Claude: " + err.message
    };
  }
}

// ─── TELEGRAM ────────────────────────────────────────────────────────────────

function notificarTelegram(datos, procesado, id, urlFoto) {
  const seccionNombre = SECCIONES[datos.seccion] || datos.seccion;

  const mensaje = [
    "📬 *NUEVO ARTÍCULO PARA REVISIÓN*",
    "",
    `🆔 \`${id}\``,
    `👤 *Autor:* ${escapeMD(datos.firma)} (${datos.usuario})`,
    `📂 *Sección:* ${escapeMD(seccionNombre)}`,
    `📍 *Lugar:* ${escapeMD(datos.lugar || "—")}`,
    "",
    `📝 *Título original:*`,
    escapeMD(datos.titulo),
    "",
    `✨ *Título SEO sugerido (${(procesado.titulo_seo || "").length} car):*`,
    escapeMD(procesado.titulo_seo || "—"),
    "",
    `🔍 *Meta description (${(procesado.meta_description || "").length} car):*`,
    escapeMD(procesado.meta_description || "—"),
    "",
    `🔗 *Slug:* \`${procesado.slug || "—"}\``,
    `🏷️ *Keywords SEO:* ${escapeMD(procesado.keywords_seo || "—")}`,
    "",
    `📋 *Resumen editorial:*`,
    escapeMD(procesado.resumen_editorial || "—"),
    "",
    urlFoto ? `🖼️ [Ver foto en Drive](${urlFoto})` : "🖼️ Sin foto adjunta",
    "",
    `💬 *Observaciones del autor:* ${escapeMD(datos.observaciones || "ninguna")}`,
    "",
    "─────────────────────────",
    `Para *aprobar* respondé: \`aprobar ${id}\``,
    `Para *rechazar* respondé: \`rechazar ${id} motivo\``
  ].join("\n");

  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
  UrlFetchApp.fetch(url, {
    method: "post",
    headers: { "Content-Type": "application/json" },
    payload: JSON.stringify({
      chat_id: TELEGRAM_CHAT_ID,
      text: mensaje,
      parse_mode: "Markdown",
      disable_web_page_preview: true
    }),
    muteHttpExceptions: true
  });
}

function escapeMD(text) {
  if (!text) return "";
  return String(text).replace(/[_*[\]()~`>#+=|{}.!-]/g, '\\$&');
}
