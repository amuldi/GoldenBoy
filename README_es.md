<p align="center">
  <a href="README.md">English</a> | <a href="README_zh.md">中文</a> | <a href="README_ja.md">日本語</a> | <a href="README_ko.md">한국어</a> | <a href="README_ar.md">العربية</a> | <b>Español</b>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/amuldi/GoldenBoy/main/assets/golden-boy.png" width="220" alt="Golden Boy">
</p>

<h1 align="center">Golden Boy</h1>
<p align="center"><b>Inteligencia de recursos para agentes de IA — gasta menos de tu presupuesto de IA en el trabajo equivocado.</b></p>

<p align="center">
  <img src="https://github.com/amuldi/GoldenBoy/actions/workflows/ci.yml/badge.svg" alt="CI status">
  <img src="https://img.shields.io/badge/python-3.9--3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9–3.13">
  <img src="https://img.shields.io/badge/coverage-95%25-2ea44f?style=flat-square" alt="Coverage 95%">
  <img src="https://img.shields.io/badge/dependencies-zero-2ea44f?style=flat-square" alt="Zero required dependencies">
  <img src="https://img.shields.io/badge/TypeScript_SDK-node_%3E%3D18-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript SDK, Node >= 18">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#-qué-es-golden-boy">Qué es</a> &nbsp;&middot;&nbsp;
  <a href="#-ejemplo-real">Ejemplo real</a> &nbsp;&middot;&nbsp;
  <a href="#-capacidades-clave">Capacidades</a> &nbsp;&middot;&nbsp;
  <a href="#-cómo-funciona">Cómo funciona</a> &nbsp;&middot;&nbsp;
  <a href="#-instalación">Instalación</a> &nbsp;&middot;&nbsp;
  <a href="#-referencia-de-cli">CLI</a> &nbsp;&middot;&nbsp;
  <a href="#-protocolo">Protocolo</a> &nbsp;&middot;&nbsp;
  <a href="#-sdk-de-typescript">SDK de TypeScript</a> &nbsp;&middot;&nbsp;
  <a href="#-repetición-y-backtesting">Backtesting</a> &nbsp;&middot;&nbsp;
  <a href="#-validación">Validación</a> &nbsp;&middot;&nbsp;
  <a href="#-hoja-de-ruta">Hoja de ruta</a> &nbsp;&middot;&nbsp;
  <a href="#-contribuir">Contribuir</a>
</p>

> Este documento es una traducción del [README en inglés](README.md). Los bloques de código, comandos,
> salidas de la CLI y JSON se mantienen en el original (inglés) para que puedas copiarlos y ejecutarlos
> tal cual. Si la traducción difiere del original, prevalece el README en inglés.

---

## 💡 ¿Qué es Golden Boy?

Los agentes de codificación con IA tienden a tratar todas las tareas por igual, sin importar cuánto uso
les queda realmente. Una tarea grande que empieza con un 15% de presupuesto restante suele terminar de la
misma manera: interrumpida a mitad de una edición, sin ningún registro de qué se terminó y qué no.

**Golden Boy** es una capa de decisión que se sitúa entre un agente y su trabajo: averigua *qué tipo* de
tarea es, estima cuánto costará, lo compara con el presupuesto restante —*y cuán confiable es en realidad
esa lectura de presupuesto*— y le dice al agente con qué agresividad debe proceder: ejecutarla, seguir
adelante, reducir el alcance, terminar y verificar, o detenerse y guardar un checkpoint. Cada recomendación
viene con una puntuación de confianza y una razón construida a partir de los números reales calculados en
esa llamada, en el mismo formato JSON versionado (el [Protocolo Golden Boy](#-protocolo)) sin importar si
lo llamas desde Python, la CLI o TypeScript.

| | |
|---|---|
| ✅ **Lo que hace** | Clasificar la tarea, estimar su costo, seguir el presupuesto + la confianza, decidir una acción (ejecutar/continuar/reducir alcance/terminar/verificar/detener/preguntar), guardar un checkpoint del trabajo aplazado, registrar localmente lo que ocurrió, y dejarte comparar políticas alternativas contra ese historial. |
| 🚫 **Lo que no hace** | Descomponer una tarea en un plan de codificación, reemplazar al agente que lo invoca, actuar como agente de codificación/IDE/proveedor de LLM, ni ejecutar un servidor. Ver [Principios de diseño](#-principios-de-diseño) y [Sobre la descomposición de tareas](#-sobre-la-descomposición-de-tareas). |

---

## 🧠 Ejemplo real

```
Usuario: "Refactoriza el sistema de autenticación y actualiza las pruebas."
```

Cada valor a continuación es una salida real y en vivo de `goldenboy analyze` — no es una maqueta:

```bash
$ goldenboy analyze "Refactor the authentication system and update tests" --budget 6
--- Golden Boy Analysis: 'Refactor the authentication system and update tests' ---
Task type:        refactor (confidence: 0.47)
Complexity:       LOW (0.05)
Estimated cost:   5.00% (confidence: 0.85)
Remaining usage:  6.00% (exact, source: mock)
Risk:             LIMITED (ESTIMATED_COST_EXCEEDS_USABLE_BUDGET)
Decision:         REDUCE_SCOPE (confidence: 0.77)
Reason:           Task classified as refactor (LOW complexity, estimated cost 5.0% of budget, confidence 0.85). Remaining budget is 6.0% (exact via mock). Risk mode: LIMITED. Recommended action: REDUCE_SCOPE.
Recommendation:
  - Constrain remaining work to P0/P1 items.
  - Explicitly defer P2-P4 items and say so.
```

Nada aquí es una narrativa prefabricada: el tipo de tarea proviene de `TaskClassifier` escaneando
realmente el texto del prompt, el costo de `Estimator` escaneando realmente el repositorio + el prompt de
esta ejecución, y el modo de riesgo de `RiskEngine` comparando realmente ese costo con el presupuesto
simulado que pasaste. Cambia el presupuesto o el texto de la tarea y cada campo cambia con él — el JSON
exacto que produce esto con `--json` está en [Protocolo](#-protocolo).

---

## ✨ Capacidades clave

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🧠 Inteligencia de tareas</h3>
      <div>
        • Clasificador de 13 tipos (corrección de bugs, refactorización, pruebas, cambio de arquitectura, …)<br>
        • Determinista y transparente — una puntuación heurística de coincidencia, nunca una probabilidad calibrada falsa<br>
        • Etiqueta de complejidad (LOW/MEDIUM/HIGH/VERY_HIGH) derivada de la estimación de costo real
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🚦 Decisiones explicadas</h3>
      <div>
        • <b>RUN · CONTINUE · REDUCE_SCOPE · FINISH · VERIFY · STOP · ASK_USER</b><br>
        • Cada decisión incluye una puntuación de confianza y una razón construida con números reales<br>
        • Confianza demasiado baja para actuar con seguridad → <code>ASK_USER</code> en vez de adivinar
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🔋 Seguimiento de presupuesto y confianza</h3>
      <div>
        • Presupuesto restante como porcentaje, más confianza <b>EXACT / ESTIMATED / STALE / UNKNOWN</b><br>
        • Una lectura <code>STALE</code> o <code>UNKNOWN</code> nunca puede pasar silenciosamente por <code>SAFE</code><br>
        • La obsolescencia del adaptador se rige por un reloj inyectable — determinista, sin <code>sleep()</code> en las pruebas
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>💾 Checkpoint y reanudación</h3>
      <div>
        • El trabajo aplazado se guarda, nunca se descarta en silencio<br>
        • <code>goldenboy resume</code> retoma desde el último checkpoint<br>
        • El esquema del checkpoint está versionado — un formato futuro incompatible falla de forma limpia
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>📡 Historial y análisis local</h3>
      <div>
        • Cada llamada decorada añade un evento localmente — nunca el texto crudo de la tarea<br>
        • Informe real de calidad del dataset (filas, ratios de corrupción/duplicados/inválidos)<br>
        • Agregados de costo/tasa de finalización/tasa de fallo sobre tu propio uso real
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔁 Repetición y backtesting</h3>
      <div>
        • 5 políticas de referencia puntuadas contra el historial real: precisión, recall, tasa de parada prematura<br>
        • División cronológica walk-forward, sin fugas de datos<br>
        • <code>N/A</code> honesto por debajo de 10 eventos — nunca una tabla inventada
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🌐 Protocolo Golden Boy</h3>
      <div>
        • Un único esquema de decisión JSON, versionado y neutral respecto al lenguaje<br>
        • Validación estricta — un error específico, nunca un <code>KeyError</code> crudo<br>
        • El mismo payload desde Python, la CLI y TypeScript
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔌 Integraciones de agentes</h3>
      <div>
        • El decorador <code>budget_aware_execution</code> envuelve cualquier función de Python<br>
        • <code>AnthropicAdapter</code> / <code>OpenAIAdapter</code> leen cabeceras reales de rate-limit<br>
        • Un SDK de TypeScript y una skill a nivel de prompt para <b>Claude Code</b>
      </div>
    </td>
  </tr>
</table>

---

## 🔄 Cómo funciona

```
Task
  │
  ▼
Task Classification  ──►  TaskType + complexity label
  │                        (TaskClassifier)
  ▼
Repository scan + prompt  ──►  Cost Estimate
                                     │
                                     ▼
                          Budget × Confidence
                     (EXACT · ESTIMATED · STALE · UNKNOWN)
                                     │
                 ┌───────────┬───────┴───────┬───────────┐
                 ▼           ▼               ▼           ▼
               SAFE      CAUTION         LIMITED     CRITICAL
                                     │
                                     ▼
                     Decision (RUN / CONTINUE / REDUCE_SCOPE /
                        FINISH / VERIFY / STOP / ASK_USER)
                                     │
                                     ▼
                    Record outcome locally (HistoryStore)
                                     │
                                     ▼
                  Backtest policies against it (goldenboy replay)
```

| Modo | Significado | Comportamiento del agente |
|---|---|---|
| 🟢 `SAFE` | Cómodamente por encima del costo estimado | Ejecuta P0–P4 con normalidad |
| 🟡 `CAUTION` | Suficiente, pero la tarea representa una parte grande | Sigue adelante, pero con cautela y sin abrir nuevo alcance |
| 🟠 `LIMITED` | El costo estimado supera el presupuesto utilizable | Se limita a P0/P1 e indica al llamador qué se está omitiendo |
| 🔴 `CRITICAL` | El presupuesto ya está en/por debajo de su margen de seguridad | Termina la unidad P0 actual, guarda checkpoint, se detiene |

El modo se decide con dos comprobaciones ordenadas — ¿el presupuesto ya está agotado (por debajo de
`safety_margin`)? → `CRITICAL`; ¿el costo estimado supera todo lo utilizable? → `LIMITED` — y en caso
contrario, según la proporción entre costo estimado y presupuesto utilizable, dividida en un
`caution_ratio` configurable (por defecto `0.5`). Una lectura de presupuesto `STALE` nunca puede producir
un veredicto `SAFE` — se eleva al menos a `CAUTION`, sin importar cuán cómodos se vean los números en
bruto; `DecisionEngine` aplica la misma regla conservadora a presupuestos con confianza `UNKNOWN` (un
adaptador que nunca se ha actualizado) como una política explícita y separada, encima del `RiskEngine` sin
modificar — ver [`goldenboy/core/risk.py`](goldenboy/core/risk.py) y
[`goldenboy/core/decision_engine.py`](goldenboy/core/decision_engine.py).

---

## ⚖️ Antes vs. después

<table>
  <tr>
    <td width="50%" valign="top">
      <b>❌ Sin Golden Boy</b>
      <p>Un agente recibe "refactoriza todo el sistema de autenticación", empieza de inmediato, gasta
      agresivamente durante exploración/implementación/pruebas, y se interrumpe a mitad de la tarea cuando
      se agota el presupuesto — sin ningún registro de lo que se hizo.</p>
    </td>
    <td width="50%" valign="top">
      <b>✅ Con Golden Boy</b>
      <p>La misma solicitud se clasifica, se estima su costo y se verifica contra el presupuesto
      <i>antes</i> de que se confirme el alcance de ejecución — una decisión real con una puntuación de
      confianza real, no una suposición hecha después de los hechos. Lo que realmente ocurrió queda
      registrado localmente, así que la siguiente tarea similar se beneficia de ello.</p>
    </td>
  </tr>
</table>

---

## 🎬 Demo

Un recorrido completo — planificar, luego ejecutar de forma adaptativa con un presupuesto que se reduce,
y después diagnosticar el entorno. Cada línea a continuación es salida real, capturada de este repositorio
(nada preparado ni acortado):

<details>
<summary><b>$ goldenboy plan "Refactor the entire authentication system" --budget 15</b></summary>

```
--- Execution Plan: 'Refactor the entire authentication system' ---
Remaining Budget: 15.00%
Estimated Cost (heuristic, based on prompt + repo size): 25.37% (confidence: 0.85)
Risk Assessment: LIMITED

Example unit breakdown (illustrative, not derived from the task above):
  [P0] Core feature implementation (Cost: 10.0%)
  [P1] Critical integration tests (Cost: 8.0%)
  [P2] Secondary cleanup (Cost: 5.0%)
  [P3] Animations / visual polish (Cost: 4.0%)
  [P4] Full documentation pass (Cost: 6.0%)
```

</details>

<details>
<summary><b>$ goldenboy -v run "Refactor the auth module" --budget 15</b></summary>

```
[goldenboy.executor] [Refactor the auth module] Budget: 15.00% | Risk: LIMITED
[goldenboy.executor]   -> Executing: [P0] Core feature implementation
[goldenboy.executor]   -> Executing: [P1] Critical integration tests
[goldenboy.executor] Budget critically low. Triggering graceful stop.
[goldenboy.executor] Saving checkpoint for deferred work.
Starting Task: 'Refactor the auth module'
Note: this uses the illustrative example plan (see 'goldenboy plan --help'); it does not decompose the task text above into real units.

--- Result ---
Task 'Refactor the auth module' finished. Completed 1 units. Deferred 4 units.

Deferred Work:
  - [P1] Critical integration tests
  - [P2] Secondary cleanup
  - [P3] Animations / visual polish
  - [P4] Full documentation pass
```

El presupuesto cayó por debajo del margen de seguridad a mitad de la ejecución — el ejecutor terminó su
unidad actual, guardó el resto como checkpoint y se detuvo en lugar de seguir gastando.

</details>

<details>
<summary><b>$ goldenboy validate</b> (instalación nueva, sin historial todavía)</summary>

```
--- Golden Boy Validate ---
Config:     OK — safety_margin=3.0, caution_ratio=0.5, base_cost_per_unit=2.0, max_budget_tokens=100000, stale_after_seconds=300.0
Checkpoint: OK — none present

Dataset Quality
Rows:                 0
Status: NO_DATA — insufficient validated data (no history recorded yet).
```

No se inventa ningún número para rellenar datos que aún no existen — ver
[Historial y análisis](#-historial-y-análisis).

</details>

<details>
<summary><b>$ goldenboy doctor</b></summary>

```
--- Golden Boy Doctor ---
Python: 3.13.7
Optional dependency 'tiktoken': installed
Optional dependency 'anthropic': installed
  Anthropic API key: not configured (ANTHROPIC_API_KEY not set)
Optional dependency 'openai': installed
  OpenAI API key: not configured (OPENAI_API_KEY not set)
Config: OK (safety_margin=3.0, caution_ratio=0.5, base_cost_per_unit=2.0, max_budget_tokens=100000, stale_after_seconds=300.0)
Checkpoint: none present
```

Se informa solo la presencia de la clave API, nunca su valor — todos los comandos de diagnóstico
(`doctor`, `status`, `validate`) también soportan `--json`.

</details>

---

## 🚀 Instalación

```bash
pip install goldenboy
goldenboy --help
```

O desde el código fuente:

```bash
git clone https://github.com/amuldi/GoldenBoy.git
cd GoldenBoy
pip install -e .
```

La instalación principal **no tiene dependencias de terceros obligatorias**. Los extras opcionales añaden
capacidades específicas:

```bash
pip install "goldenboy[tiktoken]"   # conteo exacto de tokens (sin él, recurre a una heurística más basta)
pip install "goldenboy[anthropic]"  # AnthropicAdapter
pip install "goldenboy[openai]"     # OpenAIAdapter
```

Los agentes/herramientas en TypeScript pueden usar [`sdk/typescript`](sdk/typescript) en lugar de llamar
a la CLI directamente — ver [SDK de TypeScript](#-sdk-de-typescript).

---

## ⚡ Inicio rápido

```bash
goldenboy analyze "Refactor the authentication system"   # recomendación completa: tipo, riesgo, acción, por qué
goldenboy status                                          # presupuesto actual y cualquier checkpoint pendiente
goldenboy validate                                         # config + checkpoint + informe local de calidad de datos
goldenboy doctor                                            # diagnóstico de entorno, config y checkpoint
```

---

## 🖥 Referencia de CLI

| Comando | Propósito |
|---|---|
| `goldenboy analyze <task>` | Recomendación completa de inteligencia de tareas: tipo, complejidad, riesgo, acción, confianza, razón. `--progress 0.0-1.0`, `--json`. |
| `goldenboy plan <task>` | Estima el costo real de una tarea a partir de su texto + tamaño del repo, y muestra el modo de riesgo resultante. |
| `goldenboy run <task>` | Ejecuta un plan de demostración consciente del presupuesto, de forma adaptativa, contra un presupuesto simulado. |
| `goldenboy status` | Inspecciona el presupuesto actual y cualquier checkpoint pendiente. `--json`. |
| `goldenboy resume` | Reanuda la ejecución desde el checkpoint anterior. |
| `goldenboy doctor` | Diagnostica la versión de Python, dependencias opcionales, configuración de claves de proveedor, config, checkpoint. `--json`. |
| `goldenboy validate` | Valida config + checkpoint + calidad de los datos del historial local; sale con 1 ante un problema real. `--json`. |
| `goldenboy replay` | Hace backtesting de políticas de referencia contra el historial local (o `--dataset PATH`). `--json`. |
| `goldenboy benchmark` | Mide la latencia de estimator/risk-engine/arranque de la CLI, en esta máquina, ahora mismo. `--json`. |
| `goldenboy export` | Exporta config + checkpoint + historial como un único documento JSON reproducible. `--output PATH`. |

Añade `--budget` a cualquier comando con presupuesto simulado para controlar el presupuesto inicial, y
`-v`/`--verbose` (antes del subcomando) para el registro de decisiones interno por unidad que se muestra
en la [Demo](#-demo) de arriba.

---

## 🐍 Integración con Python

```python
from goldenboy import AdaptiveExecutor, MockProvider, budget_aware_execution, Priority

provider = MockProvider(initial_percentage=40.0)

@budget_aware_execution(provider, "1", "Refactor the auth module", Priority.P1)
def refactor_auth():
    ...  # tu trabajo real va aquí — Golden Boy decide si llamarlo o no

refactor_auth()
```

`budget_aware_execution` le pregunta al proveedor por una decisión de presupuesto/modo y, solo si el modo
lo permite, llama a tu función — nunca al proveedor en sí. Cada llamada también registra un evento
localmente (nunca el texto crudo de la tarea) — ver [Historial y análisis](#-historial-y-análisis). La
superficie pública completa vive en [`goldenboy/__init__.py`](goldenboy/__init__.py); cualquier cosa que
no esté ahí listada es accesible mediante su propio submódulo, pero no forma parte del contrato de
estabilidad que sí tiene la API de nivel superior.

Para la API completa de decisión explicada, usa `DecisionEngine` directamente:

```python
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.decision_engine import DecisionEngine

decision = DecisionEngine().decide("Refactor the auth module", MockProvider(initial_percentage=15))
print(decision.action, decision.confidence, decision.reason)
```

---

## 🌐 Protocolo

Cada decisión que produce Golden Boy — desde Python, la CLI o TypeScript — tiene una única forma JSON
versionada y neutral respecto al lenguaje: el **Protocolo Golden Boy**. El esquema completo, la política
de versionado, y por qué no hay servidor, están en [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

```bash
goldenboy analyze "Refactor the auth module" --budget 6 --json
```

```jsonc
{
  "schema_version": "1.0.0",
  "task": { "task_type": "refactor", "complexity_label": "LOW", "estimated_cost_percentage": 5.0, "...": "..." },
  "usage": { "remaining_percentage": 6.0, "confidence": "EXACT", "...": "..." },
  "risk": { "mode": "LIMITED", "reason_code": "ESTIMATED_COST_EXCEEDS_USABLE_BUDGET" },
  "action": "reduce_scope",
  "confidence": 0.774,
  "reason": "Task classified as refactor (LOW complexity, ...). Recommended action: REDUCE_SCOPE.",
  "recommendation": ["Constrain remaining work to P0/P1 items.", "Explicitly defer P2-P4 items and say so."]
}
```

`GoldenBoyDecision.from_dict`/`from_json` en `goldenboy/protocol.py` validan estrictamente cualquier
payload construido de esta manera — un campo faltante o una versión mayor de esquema incompatible lanza
`ProtocolError`, nunca un `KeyError` crudo. `sdk/typescript/src/validate.ts` impone el mismo contrato en
el lado de TypeScript.

---

## 📘 SDK de TypeScript

[`sdk/typescript`](sdk/typescript) es un cliente ligero, no una segunda implementación — lanza la CLI
real de `goldenboy` y analiza su salida `--json` mediante la misma validación de protocolo descrita
arriba. Cero dependencias en tiempo de ejecución; las pruebas se ejecutan en el test runner integrado de
Node, incluyendo pruebas de integración reales (no simuladas) contra la CLI real.

```ts
import { GoldenBoyClient } from "@goldenboy/sdk";

const client = new GoldenBoyClient(); // usa `goldenboy` desde PATH
const decision = await client.analyze("Refactor the authentication system", { budget: 6 });

console.log(decision.action);       // "reduce_scope"
console.log(decision.confidence);   // 0.774
console.log(decision.reason);       // construido con los mismos números reales que la salida de Python/CLI
```

```bash
cd sdk/typescript
npm install && npm run build && npm test   # 14 pruebas, incluyendo integración real con la CLI
```

Ver [`sdk/typescript/README.md`](sdk/typescript/README.md) para la API completa y notas de diseño.

---

## 📡 Historial y análisis

Cada llamada decorada con `budget_aware_execution` añade un evento a un registro local de solo-anexado
(`.goldenboy/history.jsonl`, ignorado por git — la misma convención que el archivo de checkpoint). Un
evento nunca guarda el texto crudo de la tarea, solo su longitud y un hash SHA-256 truncado (ver
[`goldenboy/core/history.py`](goldenboy/core/history.py) y [`SECURITY.md`](SECURITY.md)).

```bash
goldenboy validate   # Dataset Quality: filas, ratios de corrupción/duplicados/valores inválidos, GOOD/ACCEPTABLE/POOR/NO_DATA
goldenboy export     # config + checkpoint + historial (informe de calidad, análisis, eventos) como un único documento JSON
```

```python
from goldenboy.analytics import data_quality
from goldenboy.analytics.engine import analyze
from goldenboy.core.history import HistoryStore

store = HistoryStore()
print(data_quality.validate(store).render())   # un informe real -- "NO_DATA" si aún no hay nada registrado
print(analyze(store).render())                  # agregados de costo/finalización/fallo, o "N/A"
```

En una instalación nueva, ambos informan honestamente cero filas — ver el ejemplo `validate` en la
[Demo](#-demo) de arriba. Nada aquí es un placeholder a la espera de ser "desbloqueado": es código real
que funciona y empieza a producir agregados reales en el momento en que tu agente ejecuta de verdad
tareas decoradas.

---

## 🔁 Repetición y backtesting

`goldenboy.replay` responde a una sola pregunta: *¿habría tomado mejores decisiones una política de
asignación de recursos diferente en estas tareas pasadas reales?* Esto es un **backtest de asignación de
recursos de un agente de IA**, no uno financiero. Se comparan cinco políticas en igualdad de condiciones —
dos líneas base de umbral fijo (15%/20%), una heurística basada solo en complejidad, una heurística
basada solo en uso, y `GoldenBoyPolicy` (que envuelve al `RiskEngine` real, sin modificar) — a través de
`goldenboy.core.policies` y `goldenboy.replay.engine`.

```bash
$ goldenboy replay
Backtest: 0 event(s) available (need at least 10).
N/A — insufficient validated data.
```

Esa es la salida real y actual en una instalación nueva — y se supone que debe serlo. No hay ningún
dataset incluido o sintético que sustituya al uso real; `docs/DATASETS.md` documenta por qué los
benchmarks públicos como SWE-bench no lo sustituyen (miden la corrección de la generación de código, no
las decisiones de asignación de recursos conscientes del presupuesto). En cuanto tu propio
`.goldenboy/history.jsonl` tenga al menos 10 eventos, `goldenboy replay` puntúa a cada política de verdad:

```
Policy                        Precision     Recall   Accuracy  PrematureStop  UnnecessaryContinue
---------------------------------------------------------------------------------------------------
fixed_threshold_15pct            ...           ...       ...          ...              ...
golden_boy_risk_engine           ...           ...       ...          ...              ...

Limitations:
  - Off-policy evaluation from logged outcomes: an event's recorded outcome reflects the decision
    Golden Boy actually made at the time, not the alternate policy being scored here. This is a
    descriptive comparison on existing data, not a causal guarantee of future behavior.
  - ...
```

`walk_forward_folds()` divide los eventos cronológicamente sin fugas entre los límites de cada pliegue —
infraestructura ya probada y lista para una futura política aprendida (las cinco políticas de hoy son
todas fijas/deterministas, así que dividir aún no cambia sus puntuaciones; ver el docstring del módulo
`goldenboy/replay/engine.py`). El informe siempre imprime sus propias limitaciones metodológicas junto a
cualquier número — ver [`goldenboy/replay/engine.py`](goldenboy/replay/engine.py).

---

## 🔌 Integraciones

Los adaptadores de proveedor informan el uso; nunca ejecutan tu código. El trabajo real siempre se
ejecuta a través del decorador `budget_aware_execution` de arriba.

| Proveedor | Lee | Notas |
|---|---|---|
| `MockProvider` | Un porcentaje sintético, en memoria | Para demos y pruebas — sin llamadas de red. |
| `AnthropicAdapter` | Cabeceras de respuesta `anthropic-ratelimit-tokens-remaining` / `-limit` | Requiere `goldenboy[anthropic]`. Refleja el límite de tasa *compartido* de la organización, no solo esta llamada. |
| `OpenAIAdapter` | Cabeceras de respuesta `x-ratelimit-remaining-tokens` / `-limit-tokens` | Requiere `goldenboy[openai]`. Misma advertencia de límite compartido que arriba. |
| Skill de Claude Code | La cifra `<total_tokens>` que Claude Code inyecta en el contexto | No requiere proceso Python — ver abajo. |
| SDK de TypeScript | La salida `--json` de la CLI `goldenboy` sobre un proceso hijo | Sin servidor HTTP — ver [Protocolo](#-protocolo). |

```python
from goldenboy.adapters.anthropic_adapter import AnthropicAdapter
from goldenboy.integration import budget_aware_execution
from goldenboy.core.priorities import Priority

adapter = AnthropicAdapter()
adapter.refresh_usage()

@budget_aware_execution(adapter, "1", "Refactor auth module", Priority.P1)
def refactor_auth():
    ...
```

Ambos adaptadores solo actualizan su lectura mediante una llamada explícita a `refresh_usage()`, y rastrean
cuánto tiempo ha pasado desde entonces usando un reloj inyectable — pasado `stale_after_seconds` (300s por
defecto), la confianza envejece de `ESTIMATED` a `STALE` por sí sola. Antes del primer refresco, la
confianza es `UNKNOWN` — `DecisionEngine` (no el propio `RiskEngine`) también trata eso de forma
conservadora, de la misma manera que trata `STALE`.

**Claude Code** recibe en cambio una integración a nivel de prompt:
[`skills/goldenboy/SKILL.md`](skills/goldenboy/SKILL.md) enseña a un agente LLM a leer la cifra de uso
restante que Claude Code inyecta directamente en el contexto y a razonar sobre su propio modo de
ejecución, con exactamente el mismo vocabulario `SAFE`/`CAUTION`/`LIMITED`/`CRITICAL` que
`goldenboy.core.risk.ExecutionMode` — mantenido en sincronía a mano, no mediante código compartido, ya que
un lado es Python y el otro es un prompt.

---

## 🏗 Arquitectura

<details>
<summary><b>Haz clic para expandir el árbol del paquete</b></summary>

```
goldenboy/
├── __init__.py            # small, deliberate public API
├── cli.py                  # status / plan / run / resume / doctor / analyze / validate / replay / benchmark / export
├── protocol.py              # the Golden Boy Protocol -- GoldenBoyDecision schema + validation
├── integration.py           # budget_aware_execution decorator + history recording
├── adapters/
│   ├── base.py               # ProviderAdapter interface + shared staleness logic
│   ├── mock.py                # synthetic provider for demos/tests
│   ├── anthropic_adapter.py
│   └── openai_adapter.py
├── core/
│   ├── budget.py               # Budget, UsageConfidence
│   ├── estimator.py            # task cost estimation
│   ├── risk.py                  # RiskEngine → ExecutionMode
│   ├── executor.py              # AdaptiveExecutor
│   ├── checkpoint.py            # CheckpointManager
│   ├── config.py                 # GoldenBoyConfig
│   ├── priorities.py             # Priority, ExecutionUnit
│   ├── task_types.py             # TaskType, DecisionAction vocabularies
│   ├── task_classifier.py         # TaskClassifier -- deterministic keyword classification
│   ├── decision_engine.py         # DecisionEngine -- the full explained GoldenBoyDecision
│   ├── history.py                  # HistoryStore, TaskEvent -- local event log
│   ├── policies.py                  # baseline policies + GoldenBoyPolicy, for replay
│   ├── benchmark.py                  # shared benchmark implementation (CLI + scripts/benchmark.py)
│   └── errors.py                      # GoldenBoyError, ConfigError, CheckpointError
├── analytics/
│   ├── data_quality.py         # Dataset Quality report over the local history log
│   └── engine.py                 # cost/completion/failure-rate aggregates
└── replay/
    └── engine.py               # run_backtest, walk_forward_folds

sdk/typescript/               # thin TypeScript client -- see the SDK section above
├── src/{types,client,validate,errors,index}.ts
└── test/                      # real integration tests against the actual CLI

docs/
├── PROTOCOL.md              # Golden Boy Protocol schema + versioning policy
├── DATASETS.md               # dataset/research landscape review
└── LANGUAGE_STRATEGY.md       # why Python, why TypeScript where it is, why not Rust yet
```

</details>

---

## ⚙️ Configuración

Todos los umbrales de política viven en `GoldenBoyConfig`, con este orden de anulación:

```
explicit constructor arg  >  GOLDENBOY_* environment variable  >  .goldenboy/config.json  >  default
```

| Campo | Variable de entorno | Por defecto | Significado |
|---|---|---|---|
| `safety_margin` | `GOLDENBOY_SAFETY_MARGIN` | `3.0` | Puntos porcentuales reservados por debajo del presupuesto restante informado antes de considerarlo agotado. |
| `caution_ratio` | `GOLDENBOY_CAUTION_RATIO` | `0.5` | Proporción costo-estimado/presupuesto-utilizable en la que el riesgo pasa de SAFE a CAUTION. |
| `base_cost_per_unit` | `GOLDENBOY_BASE_COST_PER_UNIT` | `2.0` | Costo de respaldo cuando las unidades de un plan no declaran uno. |
| `max_budget_tokens` | `GOLDENBOY_MAX_BUDGET_TOKENS` | `100000` | Cantidad de tokens tratada como "100% del presupuesto" al convertir una estimación cruda de tokens en un porcentaje. |
| `stale_after_seconds` | `GOLDENBOY_STALE_AFTER_SECONDS` | `300.0` | Cuánto tiempo una lectura de proveedor refrescada permanece `ESTIMATED` antes de envejecer a `STALE`. |

Los valores fuera de rango, el JSON malformado y las variables de entorno `GOLDENBOY_*` no interpretables
lanzan todos un `ConfigError` claro — en la CLI, un mensaje `error:` de una línea y salida `1`, nunca un
stack trace.

---

## 🧭 Principios de diseño

- **Ligero** — la instalación principal no tiene dependencias de terceros obligatorias en tiempo de ejecución; los SDK de proveedor y el propio tooling del SDK de TypeScript son opcionales.
- **Adaptativo** — el comportamiento de ejecución cambia con el presupuesto restante *y* con cuánto se puede confiar en ese número: una lectura `STALE` o `UNKNOWN` nunca puede producir un veredicto `SAFE`.
- **Determinista** — entradas idénticas producen decisiones idénticas. El estimador, el clasificador y el motor de riesgo no tienen aleatoriedad oculta; la obsolescencia del adaptador está regida por un reloj inyectable, así que es comprobable sin necesidad de esperar.
- **Proveedor opcional** — `import goldenboy` nunca requiere tener instalado `anthropic` ni `openai`.
- **El agente primero** — Golden Boy decide con qué agresividad debe proceder un agente según el presupuesto restante. El agente que lo invoca sigue siendo responsable de entender y descomponer la tarea.
- **Fallar de forma segura** — una configuración malformada, checkpoints corruptos y entradas inválidas producen un error específico y legible por humanos, y un código de salida, nunca un traceback crudo ni pérdida silenciosa de datos.
- **Evidencia por encima de la complejidad** — no hay números de benchmark, resultados de backtest ni datasets históricos inventados en ningún lugar. `goldenboy replay`/`goldenboy.analytics` informan `N/A`/`NO_DATA` en lugar de inventar una línea base; ver [`docs/DATASETS.md`](docs/DATASETS.md) y los no-objetivos explícitos de [`ROADMAP.md`](ROADMAP.md).

---

## 📦 Sobre la descomposición de tareas

> El costo estimado que muestran `plan`/`run`/`analyze` se calcula a partir del texto real de la tarea y
> el contexto del repositorio — ese número es real. El desglose por unidades de `plan`/`run` es
> **ilustrativo**: no es una descomposición de tu tarea generada por un LLM. Golden Boy mantiene
> deliberadamente su núcleo libre de dependencias y fuera del negocio de entender *cómo* hacer una tarea;
> la descomposición real de la tarea sigue siendo responsabilidad del agente que lo invoca (ver
> [Principios de diseño](#-principios-de-diseño)). `TaskClassifier` te dice *qué tipo* de tarea parece
> ser, no cómo dividirla en pasos.

---

## ⚠️ Limitaciones

- Las estimaciones de costo son heurísticas (longitud del prompt + un escaneo acotado del repo) — no son garantías de facturación, ni un modelo de lo que un agente realmente cargaría en su contexto.
- `TaskClassifier` es un comparador determinista de palabras clave, no un modelo entrenado — su puntuación de confianza refleja la fuerza de la coincidencia, no una probabilidad calibrada. Aún no tiene datos reales etiquetados con los que entrenar (ver `docs/DATASETS.md`).
- `goldenboy replay`/`goldenboy.analytics` informan `N/A`/`NO_DATA` hasta que se registren localmente al menos 10 eventos reales — no hay ningún dataset incluido que sustituya eso.
- Las métricas de la repetición son evaluación off-policy a partir de resultados registrados: el resultado registrado de un evento refleja la decisión que Golden Boy realmente tomó en ese momento, no la de la política alternativa que se está puntuando — una comparación descriptiva, no una garantía causal (ver [Repetición y backtesting](#-repetición-y-backtesting)).
- El uso del proveedor (cabeceras de rate-limit) puede cambiar fuera del control de Golden Boy entre refrescos; para eso existe exactamente la confianza `STALE`.
- El desglose por unidades de `plan`/`run` es ilustrativo, no una descomposición de tareas (ver arriba).
- Golden Boy no reemplaza el propio juicio del agente de codificación que lo invoca — solo informa cuánto intentar.

---

## ✅ Validación

Golden Boy v1.1.0 está validado, a fecha de 2026-09-14, contra:

- **186 pruebas en Python**, 95% de cobertura de línea (`pytest --cov`) — frente a 88 pruebas / 93% en v1.0.0
- **14 pruebas en TypeScript** (`npm test` en `sdk/typescript`), incluyendo pruebas de integración reales (no simuladas) contra la CLI realmente instalada
- Ruff y mypy limpios (mypy verificado tanto bajo 1.19.1 como 2.3.1)
- `pip-audit`: 0 vulnerabilidades conocidas
- Python 3.9–3.13, en GitHub Actions
- Un wheel y un sdist construidos e instalados en un entorno virtual independiente y nuevo, con cada comando de la CLI (incluyendo los nuevos) ejercitado contra él
- Una instalación solo-núcleo (`pip install goldenboy`) que no trae cero dependencias de terceros en tiempo de ejecución — verificado en vivo mediante `pip list` contra una instalación en entorno limpio, no simplemente afirmado

CI (`.github/workflows/ci.yml`, 8 jobs):

| Job | Resultado |
|---|---|
| security (pip-audit) | ✓ |
| test (3.9) | ✓ |
| test (3.10) | ✓ |
| test (3.11) | ✓ |
| test (3.12) | ✓ |
| test (3.13) | ✓ |
| build (instalación de wheel + cada comando de CLI + verificación de cordura del benchmark) | ✓ |
| sdk-typescript (integración real contra la CLI instalada) | ✓ |

---

## 📊 Benchmarks

Medido una vez, localmente (Apple M1 Pro, macOS arm64, Python 3.13.7, 2026-09-13) vía `goldenboy
benchmark` / `scripts/benchmark.py` (una sola implementación compartida — ver
`goldenboy/core/benchmark.py`) — no forma parte del criterio de éxito/fallo de la CI (la CI solo
comprueba que los números no sean negativos y que el estimator sea determinista), no es una garantía.
Vuelve a ejecutarlo tú mismo antes de confiar en estos números para algo.

| Operación | Media | Mediana | n |
|---|---|---|---|
| `Estimator.estimate_task()` (en caliente, este repo) | 9.30ms | 8.79ms | 20 |
| Determinismo de `Estimator.estimate_task()` | PASS — 1 resultado distinto en 10 llamadas idénticas | | 10 |
| `RiskEngine.assess()` | <0.001ms | <0.001ms | 1000 |
| Arranque en frío de la CLI (`goldenboy status`) | 93.46ms | 93.33ms | 5 |

`RiskEngine.assess()` es aritmética pura sobre valores ya calculados, así que es submicrosegundo por
construcción. La latencia del Estimator escala con el tamaño del repositorio (acotada por los límites
`_MAX_SCAN_FILES` / `_MAX_FILE_BYTES`), no con la longitud del prompt. El arranque en frío de la CLI es
sobre todo overhead del intérprete/importación de Python — es lo que realmente se siente al ejecutar
cualquier comando `goldenboy`. La metodología completa, las advertencias, y el razonamiento de migración
a Rust construido sobre estos números: [`BENCHMARKS.md`](BENCHMARKS.md) y
[`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md).

---

## 🗺 Hoja de ruta

**Entregado, probado, real:**

- ✓ Estimación de costo consciente de la tarea, modos de ejecución adaptativos, checkpoint/aplazar/reanudar, confianza de uso incl. detección de STALE
- ✓ CLI (`plan`/`run`/`status`/`resume`/`doctor`/`analyze`/`validate`/`replay`/`benchmark`/`export`)
- ✓ Adaptadores de proveedor Anthropic/OpenAI, integración de skill de Claude Code
- ✓ Protocolo Golden Boy (versionado, neutral respecto al lenguaje) + SDK de TypeScript
- ✓ Clasificación de tareas (`TaskClassifier`) + `DecisionEngine` (acción/confianza/razón explicadas)
- ✓ Historial local (`HistoryStore`) + informes de calidad de datos/análisis
- ✓ Políticas de referencia + motor de backtest `goldenboy.replay` + división walk-forward

| Dirección | Estado |
|---|---|
| Un resultado de backtest real y poblado (no `N/A`) | Bloqueado hasta que se acumulen datos de uso real — no se puede producir honestamente hoy |
| Un clasificador de tareas / política aprendida | Investigación — primero se necesitan datos reales de resultados etiquetados |
| Dividir `cli.py` en un paquete `cli/` | Planeado — aplazado este ciclo (riesgo de regresión frente a beneficio; ver `ROADMAP.md`) |
| Benchmarking contra un repositorio sintético deliberadamente grande | Planeado |
| Integraciones adicionales de agentes (p. ej. Codex) | Investigación — solo con una señal de uso real y documentada sobre la cual construir |

Nada de lo anterior se declara listo para producción a menos que también esté cubierto por pruebas. El
desglose completo de Done/Planned/Research, incluyendo los no-objetivos explícitos (sin base de datos,
sin panel web, sin servidor, sin ML ni Rust prematuros), en [`ROADMAP.md`](ROADMAP.md).

---

## 🤝 Contribuir

Las contribuciones son bienvenidas. [`CONTRIBUTING.md`](CONTRIBUTING.md) tiene los pasos de
configuración, las verificaciones que un PR debe pasar (`pytest`, `ruff`, `mypy`, `python -m build` —
todas exigidas en CI), y los principios de ingeniería a los que se somete la revisión: arquitectura
existente primero, causa raíz sobre síntoma, sin completitud falsa, etiquetado honesto de confianza, y sin
números de política codificados fuera de `GoldenBoyConfig`.

---

## 🛠 Desarrollo

```bash
git clone https://github.com/amuldi/GoldenBoy.git
cd GoldenBoy
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest --cov=goldenboy --cov-report=term-missing
ruff check goldenboy tests scripts run_tests.py
mypy
```

Para el SDK de TypeScript:

```bash
cd sdk/typescript
npm install
npm run typecheck && npm run build && npm test
```

---

## 📚 Más documentación

| Doc | Cubre |
|---|---|
| [`docs/PROTOCOL.md`](docs/PROTOCOL.md) | El esquema del Protocolo Golden Boy, la política de versionado, y por qué no hay servidor. |
| [`docs/DATASETS.md`](docs/DATASETS.md) | Revisión del panorama de datasets/investigación (SWE-bench, HumanEval, LiveCodeBench, RepoBench, investigación sobre consumo de tokens) y por qué ninguno sustituye a `HistoryStore`. |
| [`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md) | Por qué Python sigue siendo el núcleo, dónde se usa TypeScript, y la futura frontera de migración a Rust. |
| [`CHANGELOG.md`](CHANGELOG.md) | Qué cambió de versión en versión. |
| [`ROADMAP.md`](ROADMAP.md) | Desglose completo de Done / Planned / Research, incluyendo no-objetivos explícitos. |
| [`BENCHMARKS.md`](BENCHMARKS.md) | Números de rendimiento medidos, metodología, y lo que aún no se ha medido. |
| [`SECURITY.md`](SECURITY.md) | Cómo se manejan las credenciales y el historial local, y cómo reportar una vulnerabilidad. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Configuración, verificaciones, y los principios de ingeniería a los que se somete la revisión. |
| [`sdk/typescript/README.md`](sdk/typescript/README.md) | Referencia de la API del SDK de TypeScript y notas de diseño. |

---

## 📄 Licencia

[MIT](LICENSE).

<p align="center">
  ⭐ Si Golden Boy evita que tu agente se quede sin presupuesto, una estrella ayuda a que más gente lo encuentre.
</p>
