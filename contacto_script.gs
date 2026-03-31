// PatagoniaGLOBAL — Formulario de contacto
// Instrucciones:
//   1. Abrí script.google.com con ficciontvpatagonia@gmail.com
//   2. Nuevo proyecto → pegá este código → guardá (Ctrl+S)
//   3. Clic en "Implementar" → "Nueva implementación"
//   4. Tipo: Aplicación web
//   5. Ejecutar como: Yo (ficciontvpatagonia@gmail.com)
//   6. Quién tiene acceso: Cualquier usuario
//   7. Clic en "Implementar" → copiá la URL que aparece
//   8. Pasale esa URL a Claude

const DESTINO     = "ficciontvpatagonia@gmail.com";
const ETIQUETA    = "PatagoniaGLOBAL/Contacto";
const ASUNTO_BASE = "[PatagoniaGLOBAL] Contacto: ";

function doPost(e) {
  try {
    const datos = JSON.parse(e.postData.contents);
    const nombre  = limpiar(datos.nombre  || "Sin nombre");
    const email   = limpiar(datos.email   || "Sin email");
    const asunto  = limpiar(datos.asunto  || "Consulta general");
    const mensaje = limpiar(datos.mensaje || "");

    // Cuerpo del email
    const cuerpo = `
Nuevo mensaje desde el formulario de PatagoniaGLOBAL.

Nombre:  ${nombre}
Email:   ${email}
Asunto:  ${asunto}

Mensaje:
${mensaje}

---
Enviado desde patagoniaglobal.org/acerca.html
    `.trim();

    // Enviar email
    GmailApp.sendEmail(
      DESTINO,
      ASUNTO_BASE + asunto,
      cuerpo,
      { replyTo: email, name: "PatagoniaGLOBAL Contacto" }
    );

    // Aplicar etiqueta al mensaje enviado
    aplicarEtiqueta(ASUNTO_BASE + asunto);

    return respuesta(200, { ok: true, mensaje: "Mensaje enviado correctamente." });

  } catch (err) {
    return respuesta(500, { ok: false, mensaje: "Error al procesar el mensaje: " + err.message });
  }
}

// Aplica o crea la etiqueta en el último mensaje enviado
function aplicarEtiqueta(asunto) {
  try {
    let etiqueta = GmailApp.getUserLabelByName(ETIQUETA);
    if (!etiqueta) etiqueta = GmailApp.createLabel(ETIQUETA);

    // Busca en Enviados el mensaje recién mandado
    const hilos = GmailApp.search('in:sent subject:"' + asunto + '"', 0, 1);
    if (hilos.length > 0) etiqueta.addToThread(hilos[0]);
  } catch (err) {
    // Si falla el etiquetado no interrumpimos el flujo
    Logger.log("Error etiquetando: " + err.message);
  }
}

function limpiar(str) {
  return String(str).replace(/<[^>]*>/g, "").substring(0, 2000);
}

function respuesta(codigo, datos) {
  return ContentService
    .createTextOutput(JSON.stringify(datos))
    .setMimeType(ContentService.MimeType.JSON);
}

// Prueba manual — ejecutala desde el editor para verificar que funciona
function testEnvio() {
  doPost({
    postData: {
      contents: JSON.stringify({
        nombre:  "Test Usuario",
        email:   "test@ejemplo.com",
        asunto:  "Prueba de formulario",
        mensaje: "Este es un mensaje de prueba desde el editor de Apps Script."
      })
    }
  });
}
