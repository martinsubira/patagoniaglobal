# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Portal de noticias panpatagónico (Argentina + Chile). Nombre: **GLOBALpatagonia**. Slogan: *"Sur Global, principio de todo."*
- **URL:** https://globalpatagonia.org
- **Repo:** `ficciontvpatagonia-tech/patagoniaglobal` (GitHub Pages)
- **Push siempre sin preguntar:**
  ```
  git add <archivos> && git commit -m "mensaje" && TOKEN=$(gh auth token --user martinsubira) && git push https://martinsubira:${TOKEN}@github.com/ficciontvpatagonia-tech/patagoniaglobal.git main
  ```

## Archivos clave
| Archivo | Qué es |
|---|---|
| `index.html` | Página principal |
| `nota.html` | Vista individual de nota (`?id=ID`) |
| `noticias.json` | Feed diario (script automático) |
| `noticias_ayer.json` | Feed del día anterior (rotación automática) |
| `historial.json` | Archivo acumulativo de todas las notas |
| `historias.json` | Notas permanentes (nunca se borran) |
| `propios.json` | Artículos de Marto → sección INFORMES (máx 3) |
| `propios_historial.json` | Informes archivados (rotación) |
| `negocios.json` | Economía & Empresas |
| `deportes_feed.json` | Deportes & Aventura |
| `deportes_historial.json` | Historial de deportes |
| `turismo.json` | Turismo en Patagonia |
| `guias.json` | Guías de destinos |
| `guias_historial.json` | Historial de guías |
| `cultura.json` | Cultura Patagónica & Pueblos Originarios |
| `agenda.json` | Eventos patagónicos (purga automática de vencidos) |
| `videos.json` | Cinemateca Patagónica |
| `fotos/` | Fotos propias + `fotos/index.json` |
| `actualizar_noticias.py` | Script RSS → Claude → JSONs (corre en GitHub Actions) |

## Reglas críticas

**INFORMES (`propios.json`):**
- Máximo 3 activos. Al agregar uno nuevo → el más antiguo pasa a `propios_historial.json`, el nuevo va al inicio del array.
- Nunca van a tapa ni al feed de noticias. Solo sección INFORMES.
- El script diario NO toca `propios.json`.
- `historias.json` (Rubén Patagonia, huelgas 1921, kawésqar, Perito Moreno) nunca van a `propios.json` — tienen su propia sección.

**Notas completas:**
- Todo artículo agregado manualmente a cualquier sección (turismo, deportes, guias, negocios) DEBE tener su `cuerpo` completo en `historial.json`.
- Los JSONs de sección solo guardan el resumen para el card.
- Notas manuales en esos JSONs llevan `"excluir_feed": true`.

**`nota.html` busca en este orden:** `noticias.json` → `historias.json` → `propios.json` → `turismo.json` → `historial.json` → `negocios.json`

**"Medio Ambiente"** se muestra siempre como **"Ambiente"** en el frontend.

**Layout:** `DIAGRAMACION.pdf` en ~/Desktop es la referencia fija. No agregar secciones que no estén en él.

## GitHub Actions
- Workflow: `.github/workflows/actualizar-noticias.yml`
- Cron: `0 9 * * *` → 6:00 AM hora Argentina (UTC−3). También dispara manual (`workflow_dispatch`).
- El Action commitea: `noticias.json`, `noticias_ayer.json`, `historial.json`, `agenda.json`, `fotos/`, `propios.json`, `propios_historial.json`, `deportes_feed.json`, `negocios.json`, `turismo.json`, `telegram_state.json`
- Después de publicar espera 90s y corre `--solo-instagram` para publicar tapa en Instagram.
- Secrets: `ANTHROPIC_API_KEY`, `UNSPLASH_ACCESS_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`

**CRÍTICO — notas/ nunca se sobreescriben:**
- `actualizar_noticias.py` genera `notas/[id].html` solo si el archivo NO existe (`if os.path.exists(ruta): continue`)
- El workflow usa `git ls-files --others --exclude-standard notas/ | xargs -r git add --` en lugar de `git add notas/` — esto agrega solo archivos *nuevos*, nunca modifica los existentes
- Motivo: notas colaboradoras (rodrigo-binet, ski-patagonia, etc.) tienen CSS/fotos/traducciones especiales que el script no conoce. Una sobreescritura las destruye sin aviso.

## Paleta visual
`#1c2d3d` azul cordillera · `#7aadcc` azul glacial · `#252830` gris granito · `#8c6b4a` arcilla · `#f0ede8` fondo
Tipografías: **Playfair Display** (títulos) + **Inter** (cuerpo)

## Notas enriquecidas (nota.html)
`nota.html` soporta dos modos de cuerpo:
- **Modo normal:** texto plano separado por `\n\n` → auto-detectado como `<p>` o `<h3>`
- **Modo HTML crudo:** bloques que empiezan con `<` se renderizan como HTML directo (tablas, cards)

CSS disponible para guías: `.ski-table`, `.ski-centro-card`, `.ski-stats-row`, `.ski-stat`, `.ski-nota`, `.ski-vs`

## Multiidioma
Si la nota tiene `titulo_en`/`titulo_pt`, aparece automáticamente el switcher ES/EN/PT.
- Campos: `titulo_en`, `bajada_en`, `cuerpo_en`, `titulo_pt`, `bajada_pt`, `cuerpo_pt`
- URL: `nota.html?id=ID&lang=en`
- Solo agregar a notas que lo justifiquen (no a noticias regulares).

## Cinemateca (`videos.json`)
- Categorías: `ficcion` · `serie_ficcion` · `documental` · `serie_documental`
- Series: una sola tarjeta agrupada (campo `serie`). Click despliega panel fullscreen con episodios.
- `serie_descripcion` = sinopsis general de la serie.
- `episodio` define el orden. Thumbnail: el de mayor impacto visual (no necesariamente ep01).

## GA4 / AdSense
GA4: `G-5FP2F41BZG` | AdSense: `ca-pub-1924505291132800`

## Notas estáticas — "También te puede interesar"
- CSS de las cards `.relacionadas`, `.rel-card`, `.rel-img`, etc. está inlineado en cada `notas/*.html` (no viene de nota.html)
- Script `agregar_relacionadas.py`: agrega la sección a todos los HTMLs estáticos que no la tengan. Ejecutar manualmente si se agregan notas nuevas con HTML propio.
- Notas omitidas: variantes de idioma (`-en.html`, `-pt.html`, `-zh.html`) y el redirect stub `perito-moreno-timeout-2026.html`
- Lógica de selección: mismo tag primero, luego otras, `random.seed(nid)` para que sea determinístico

## Notas estáticas — variantes de idioma (multiidioma)
- Páginas especiales con traducciones completas se crean manualmente: `[id]-en.html`, `[id]-pt.html`
- El switcher de idioma (botones ES/EN/PT) se agrega directamente al HTML de cada página
- Hreflang tags en `<head>` para SEO
- Ejemplo: `notas/ski-patagonia-2026.html`, `notas/ski-patagonia-2026-en.html`, `notas/ski-patagonia-2026-pt.html`
- Agregar estos archivos al sitemap.xml manualmente cuando se crean
