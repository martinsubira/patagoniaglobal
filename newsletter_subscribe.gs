// GLOBALpatagonia — Suscripción al newsletter via Brevo
// Instrucciones:
//   1. Abrí script.google.com con ficciontvpatagonia@gmail.com
//   2. Nuevo proyecto → pegá este código → guardá (Ctrl+S)
//   3. Clic en "Implementar" → "Nueva implementación"
//   4. Tipo: Aplicación web
//   5. Ejecutar como: Yo (ficciontvpatagonia@gmail.com)
//   6. Quién tiene acceso: Cualquier usuario
//   7. Clic en "Implementar" → copiá la URL → pegala en index.html (constante NEWSLETTER_ENDPOINT)

const BREVO_API_KEY = "PEGAR_API_KEY_AQUI";  // ← pegá tu API key de Brevo acá antes de deployar
const BREVO_LIST_ID = 3;

function doPost(e) {
  try {
    const datos = JSON.parse(e.postData.contents);
    const email = (datos.email || "").trim().toLowerCase();
    if (!email || !email.includes("@")) {
      return respuesta(400, { ok: false, mensaje: "Email inválido." });
    }
    const payload = JSON.stringify({ email: email, listIds: [BREVO_LIST_ID], updateEnabled: true });
    const options = {
      method: "post", contentType: "application/json",
      headers: { "api-key": BREVO_API_KEY, "accept": "application/json" },
      payload: payload, muteHttpExceptions: true
    };
    const response = UrlFetchApp.fetch("https://api.brevo.com/v3/contacts", options);
    const code = response.getResponseCode();
    if (code === 201 || code === 204) {
      return respuesta(200, { ok: true, mensaje: "¡Suscripción exitosa!" });
    } else {
      const body = JSON.parse(response.getContentText() || "{}");
      if (body.code === "duplicate_parameter") {
        return respuesta(200, { ok: true, mensaje: "Ya estás suscripto." });
      }
      return respuesta(500, { ok: false, mensaje: "Error al suscribir." });
    }
  } catch (err) {
    return respuesta(500, { ok: false, mensaje: "Error: " + err.message });
  }
}

function doGet(e) {
  return respuesta(200, { ok: true, mensaje: "Endpoint newsletter GLOBALpatagonia." });
}

function respuesta(codigo, datos) {
  return ContentService.createTextOutput(JSON.stringify(datos)).setMimeType(ContentService.MimeType.JSON);
}
