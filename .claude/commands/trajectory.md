---
description: Corre el loop evaluator-optimizer para reconstruir la trayectoria de UNA startup — ejecutor + auditor en loop hasta PASS, RETRY (máx 3) o ESCALATE_HUMAN
argument-hint: "<slug>  (obligatorio)  [stage: full | executor | critic]  (default: full)"
---

Corre el loop de reconstrucción de trayectoria para la startup `<slug>` del portafolio.

Scope = `$ARGUMENTS`:

- **full** — el ciclo completo:
  1. Lanzar subagente `trajectory-executor` → produce artefacto JSON siguiendo el schema fijo,
     guarda en `data/audit/<slug>/tick-N.json` bajo la clave `artefacto`.
  2. Lanzar subagente `trajectory-critic` → audita el artefacto contra su rúbrica, guarda en
     el mismo tick file bajo la clave `verdicts`.
  3. Leer `global_verdict`:
     - `PASS` →
       - Escribir artefacto verificado en `data/audit/<slug>/final.json`.
       - **Mergear al JSON canónico**: por cada `phases[i]` de tipo `pivot` o `rebrand`,
         upsert una entrada en `data/curated_trajectories.json` (borrar entradas previas del
         mismo `<slug>` con mismo `<type>`+`<date>` para evitar duplicados). Ver "Merge al JSON
         canónico" abajo.
       - **Mergear correcciones**: por cada `phases[i]` de tipo `funding` / `shutdown` cuya
         fecha o prosa difiera del `funding.json` / `identity.json` legacy, upsert en
         `data/corrections.json` con key `<display_name>|capital|<date>` (o `|cierre|` /
         `|fundacion|`).
       - Actualizar `data/audit/loop-state.md`: `<slug>` pasa a `pending_curation`.
     - `RETRY` → reejecutar ejecutor pasándole `tick-N.json` completo (artefacto + verdicts)
       como contexto. Máx 3 ticks.
     - `ESCALATE_HUMAN` → escribir `data/audit/<slug>/HUMAN_REVIEW.md` con resumen del último
       veredicto + claims problemáticos con evidencia citada. Actualizar `loop-state.md`.
       NO tocar el JSON canónico.
- **executor** — solo el ejecutor. Útil para inspeccionar el artefacto en crudo. No corre auditor.
- **critic** — solo el auditor contra el último `tick-N.json` en `data/audit/<slug>/`. Útil para
  re-auditar tras retocar la rúbrica.

## Reglas para toda corrida

- Leer `data/audit/loop-state.md` ANTES de arrancar para saber el estado de `<slug>`. Si está
  `closed` sin razón externa, avisar y salir.
- El ejecutor DEBE entregar el output en el schema JSON definido en
  `.claude/agents/trajectory-executor.md`. Sin ese schema, el auditor responde `INCORRECT: formato
  inválido` y gastas una pasada del loop.
- La rúbrica vive dentro de `.claude/agents/trajectory-critic.md`. El auditor la aplica cada
  tick — no la memorices.
- **Autonomy gates**: escribir a `data/audit/<slug>/tick-N.json`, `final.json`,
  `HUMAN_REVIEW.md` y **mergear al JSON canónico** (`data/curated_trajectories.json` +
  `data/corrections.json`) es autónomo — pero SOLO cuando `global_verdict == PASS`. El humano
  puede vetar antes de correr los builds editando los JSONs a mano; git da el historial.
  Correr `build_pivots_curated.py` / `build_timeline.py` **espera al humano**.
- **Stop condition in-run-achievable**: PASS, o tick == 3, o `no_progress_signal == true`. Nunca
  esperar por acciones externas (WebArchive rate-limit, prensa nueva).
- **Nunca** correr `build_pivots_curated.py` / `build_timeline.py`. Eso es del humano post-PASS.

## Closing message

Al terminar, escribe dos secciones autocontenidas en el chat (no diferir a otros archivos):

1. **Lo que hice** — un bullet por fase que el loop identificó. Encabezado con el efecto en
   producto ("añadí el pivot a B2B en marzo 2023"), después el detalle para verificar
   (`phases[2]`, verified por `data/wayback/foo.cl/202303.html:120-180`, cita textual). Cerrar con
   el resultado del loop: "Tick N, global_verdict `<verdict>`, N claims verified, N incorrect".

2. **Qué necesita tu decisión** — items gated: `pending_curation` (decidir si los pivots verified
   se llevan a `CURATED`) o `pending_human_review` (evidencia ambigua). Cada item con la
   decisión en una línea + path + línea afectados + recomendación del loop.

## Merge al JSON canónico (solo cuando PASS)

Los dos JSONs canónicos son la fuente de verdad que `build_pivots_curated.py` y
`build_timeline.py` consumen para generar `web/src/data/timeline.json` (el que sirve el sitio).

### `data/curated_trajectories.json`

Lista de dicts. Schema por entrada:

```json
{
  "slug": "…",
  "type": "pivot|rebrand",
  "date": "YYYY-MM",
  "domain": "cardda.com | profile:<slug>",
  "title": "De X a Y  |  X pasa a Y",
  "prose": "Prosa producto-oriented (qué + para quién + qué reemplaza)."
}
```

Reglas del merge:
- Solo `phases[i]` de tipo `pivot` o `rebrand` del `final.json` entran acá. Los `funding`
  van al legacy `funding.json` (que ya lo maneja el scraper) o a `corrections.json` para
  overrides. Los `shutdown` confirmed van a `corrections.json` con key `|cierre|`.
- Por cada nueva entrada `<slug>` + `<type>` + `<date>`: si ya existe → sobrescribir; si no
  existe → append.
- Borrar entradas viejas del mismo `<slug>` cuyo `<date>` no aparezca más en el `final.json`
  del tick actual (eran fabricadas por curación previa y el loop las mató).
- Producir la `prose` sin slogans citados, sin palabras prohibidas (`Wayback`, `TF-IDF`,
  `coseno`, `cheque`) — el criterio R11 aplica.

### `data/corrections.json`

Dict con keys aplanadas `"<display_name>|<type>|<old_date>"`. Schema por override:

```json
{
  "date": "YYYY-MM",    // opcional: re-datar
  "prose": "…",         // opcional: reescribir la prosa
  "title": "…"          // opcional: reescribir el título
}
```

Reglas del merge:
- Solo tocar `corrections.json` cuando el `final.json` tiene evidencia dura de que la fecha
  o la prosa del legacy están mal.
- Key `|fundacion|` para fundaciones corregidas (producto original, no actual).
- Key `|capital|` para rondas cuya fecha o prosa se corrige.
- Key `|cierre|` para cierres confirmados con corrección.

## Candidatos a criterio nuevo

Si el auditor devolvió un `candidate_new_criterion` no null, mencionarlo al final del closing
message. Es un modo de falla que la rúbrica actual no atrapa. La decisión de agregarlo a la
rúbrica es del humano (editar `.claude/agents/trajectory-critic.md`).
