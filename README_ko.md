<p align="center">
  <a href="README.md">English</a> | <a href="README_zh.md">中文</a> | <a href="README_ja.md">日本語</a> | <b>한국어</b> | <a href="README_ar.md">العربية</a> | <a href="README_es.md">Español</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/amuldi/GoldenBoy/main/assets/golden-boy.png" width="220" alt="Golden Boy">
</p>

<h1 align="center">Golden Boy</h1>
<p align="center"><b>AI 에이전트 리소스 인텔리전스 — AI 사용량을 엉뚱한 작업에 낭비하지 않도록.</b></p>

<p align="center">
  <img src="https://github.com/amuldi/GoldenBoy/actions/workflows/ci.yml/badge.svg" alt="CI status">
  <img src="https://img.shields.io/badge/python-3.9--3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9–3.13">
  <img src="https://img.shields.io/badge/coverage-95%25-2ea44f?style=flat-square" alt="Coverage 95%">
  <img src="https://img.shields.io/badge/dependencies-zero-2ea44f?style=flat-square" alt="Zero required dependencies">
  <img src="https://img.shields.io/badge/TypeScript_SDK-node_%3E%3D18-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript SDK, Node >= 18">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#-golden-boy란">Golden Boy란</a> &nbsp;&middot;&nbsp;
  <a href="#-실제-사용-예시">사용 예시</a> &nbsp;&middot;&nbsp;
  <a href="#-핵심-기능">핵심 기능</a> &nbsp;&middot;&nbsp;
  <a href="#-작동-원리">작동 원리</a> &nbsp;&middot;&nbsp;
  <a href="#-설치">설치</a> &nbsp;&middot;&nbsp;
  <a href="#-cli-레퍼런스">CLI</a> &nbsp;&middot;&nbsp;
  <a href="#-프로토콜">프로토콜</a> &nbsp;&middot;&nbsp;
  <a href="#-typescript-sdk">TypeScript SDK</a> &nbsp;&middot;&nbsp;
  <a href="#-리플레이와-백테스팅">백테스팅</a> &nbsp;&middot;&nbsp;
  <a href="#-검증">검증</a> &nbsp;&middot;&nbsp;
  <a href="#-로드맵">로드맵</a> &nbsp;&middot;&nbsp;
  <a href="#-기여하기">기여하기</a>
</p>

> 이 문서는 [영어 원문](README.md)의 번역본입니다. 코드 블록·명령어·CLI 출력·JSON은 원문 그대로(영어) 유지했습니다 — 실제로 복사해서 그대로 실행할 수 있도록 하기 위해서입니다. 번역과 원문이 다르면 영어 원문이 우선합니다.

---

## 💡 Golden Boy란?

AI 코딩 에이전트는 실제로 남은 사용량이 얼마인지와 무관하게 모든 작업을 똑같이 취급하는 경향이 있습니다.
잔여 예산 15%에서 시작한 큰 작업은 대개 같은 식으로 끝납니다 — 편집 도중 중단되고, 무엇을 끝냈고
무엇을 못 끝냈는지에 대한 기록도 없이 말이죠.

**Golden Boy**는 에이전트와 실제 작업 사이에 자리하는 의사결정 레이어입니다: 이 작업이 *어떤 종류*인지
파악하고, 비용을 추정하고, 남은 예산과 비교하며 — *그 예산 수치를 얼마나 신뢰할 수 있는지*까지 함께 —
에이전트에게 얼마나 공격적으로 진행해야 할지 알려줍니다: 그냥 실행, 계속 진행, 범위 축소, 마무리 후 검증,
또는 중단하고 체크포인트 저장. 모든 권고에는 신뢰도 점수와 그 호출에서 실제로 계산된 숫자로 만들어진
이유가 함께 제공되며, Python·CLI·TypeScript 어디서 호출하든 동일한 버전 관리된 JSON 형태
([Golden Boy Protocol](#-프로토콜))로 나옵니다.

| | |
|---|---|
| ✅ **하는 일** | 작업 분류, 비용 추정, 예산+신뢰도 추적, 액션 결정(실행/계속/범위 축소/마무리/검증/중단/질문), 미완료 작업 체크포인트 저장, 로컬에 실행 기록 저장, 그 기록으로 다른 정책들을 백테스트. |
| 🚫 **하지 않는 일** | 작업을 코딩 계획으로 분해하거나, 호출 에이전트를 대체하거나, 코딩 에이전트/IDE/LLM 프로바이더 역할을 하거나, 서버를 구동하는 것. [설계 원칙](#-설계-원칙)과 [작업 분해에 대하여](#-작업-분해에-대하여) 참고. |

---

## 🧠 실제 사용 예시

```
사용자: "인증 시스템을 리팩터링하고 테스트를 업데이트해줘."
```

아래 값은 전부 `goldenboy analyze`의 실제 라이브 출력입니다 — 가짜 예시가 아닙니다:

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

이 출력은 미리 짜둔 시나리오가 아닙니다: 작업 유형은 `TaskClassifier`가 프롬프트 텍스트를 실제로 스캔해서,
비용은 `Estimator`가 이번 실행의 저장소+프롬프트를 실제로 스캔해서, 리스크 모드는 `RiskEngine`이 그
비용을 여러분이 전달한 모의 예산과 실제로 비교해서 나온 결과입니다. 예산이나 작업 텍스트를 바꾸면
모든 필드가 그에 맞춰 바뀝니다 — `--json`으로 나오는 정확한 JSON은 [프로토콜](#-프로토콜) 섹션 참고.

---

## ✨ 핵심 기능

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🧠 작업 인텔리전스</h3>
      <div>
        • 13종 분류기(버그 수정, 리팩터링, 테스트, 아키텍처 변경 등)<br>
        • 결정론적이고 투명함 — 가짜 보정 확률이 아닌 휴리스틱 매칭 강도 점수<br>
        • 실제 비용 추정치에서 도출된 복잡도 라벨(LOW/MEDIUM/HIGH/VERY_HIGH)
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🚦 근거가 있는 의사결정</h3>
      <div>
        • <b>RUN · CONTINUE · REDUCE_SCOPE · FINISH · VERIFY · STOP · ASK_USER</b><br>
        • 모든 결정에는 신뢰도 점수와 실제 숫자로 만든 이유가 함께 제공<br>
        • 안전하게 행동하기에 신뢰도가 너무 낮으면 추측 대신 <code>ASK_USER</code>
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🔋 예산 및 신뢰도 추적</h3>
      <div>
        • 남은 예산을 퍼센트로, 그리고 <b>EXACT / ESTIMATED / STALE / UNKNOWN</b> 신뢰도<br>
        • <code>STALE</code> 또는 <code>UNKNOWN</code> 값은 절대 조용히 <code>SAFE</code>로 둔갑하지 않음<br>
        • 어댑터의 오래됨은 주입 가능한 시계로 판단 — 결정론적이며 테스트에 <code>sleep()</code> 없음
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>💾 체크포인트 및 재개</h3>
      <div>
        • 미룬 작업은 저장되며 조용히 사라지지 않음<br>
        • <code>goldenboy resume</code>으로 마지막 체크포인트부터 재개<br>
        • 체크포인트 스키마는 버전 관리 — 호환되지 않는 미래 포맷은 깔끔하게 실패
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>📡 로컬 히스토리 및 분석</h3>
      <div>
        • 데코레이트된 호출마다 이벤트 하나를 로컬에 기록 — 원문 작업 텍스트는 저장 안 함<br>
        • 실제 Dataset Quality 리포트(행 수, 손상/중복/무효 비율)<br>
        • 여러분의 실제 사용 이력에 대한 비용/완료/실패율 집계
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔁 리플레이 및 백테스팅</h3>
      <div>
        • 실제 히스토리로 채점하는 5개의 베이스라인 정책: 정밀도, 재현율, 조기 중단률<br>
        • 워크포워드 방식의 누출 없는 시간순 분할<br>
        • 이벤트 10개 미만이면 정직하게 <code>N/A</code> — 조작된 표를 절대 보여주지 않음
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🌐 Golden Boy Protocol</h3>
      <div>
        • 하나의 버전 관리된, 언어 중립적인 JSON 결정 스키마<br>
        • 엄격한 검증 — 원시 <code>KeyError</code>가 아닌 구체적인 오류<br>
        • Python, CLI, TypeScript에서 동일한 페이로드
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔌 에이전트 통합</h3>
      <div>
        • <code>budget_aware_execution</code> 데코레이터로 어떤 Python 함수든 감쌀 수 있음<br>
        • <code>AnthropicAdapter</code> / <code>OpenAIAdapter</code>가 실제 rate-limit 헤더를 읽음<br>
        • TypeScript SDK와 프롬프트 레벨의 <b>Claude Code</b> 스킬
      </div>
    </td>
  </tr>
</table>

---

## 🔄 작동 원리

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

| 모드 | 의미 | 에이전트 동작 |
|---|---|---|
| 🟢 `SAFE` | 추정 비용보다 여유롭게 많음 | P0–P4를 정상적으로 실행 |
| 🟡 `CAUTION` | 충분은 하지만 작업이 큰 비중을 차지함 | 계속하되 보수적으로, 새 범위를 열지 않음 |
| 🟠 `LIMITED` | 추정 비용이 사용 가능한 예산을 초과 | P0/P1로 제한하고 무엇을 건너뛰는지 알림 |
| 🔴 `CRITICAL` | 예산이 이미 안전 마진 이하 | 현재 P0 작업만 마무리, 체크포인트, 중단 |

모드는 두 단계의 순차 체크로 결정됩니다 — 예산이 이미 소진됐는지(`safety_margin` 이하) →
`CRITICAL`; 추정 비용이 사용 가능한 예산을 아예 초과하는지 → `LIMITED` — 그 외에는 추정 비용 대
사용 가능 예산의 비율을, 설정 가능한 `caution_ratio`(기본값 `0.5`)로 나눠 판단합니다. `STALE` 예산
값은 절대 `SAFE` 판정을 내지 못하며 — 원시 숫자가 아무리 여유로워 보여도 최소 `CAUTION`으로
올라갑니다. `DecisionEngine`은 `UNKNOWN` 신뢰도 예산(아직 한 번도 갱신되지 않은 어댑터)에도 같은
보수적 규칙을, 변경되지 않은 `RiskEngine` 위에 명시적인 별도 정책으로 적용합니다 — 자세한 내용은
[`goldenboy/core/risk.py`](goldenboy/core/risk.py)와 [`goldenboy/core/decision_engine.py`](goldenboy/core/decision_engine.py) 참고.

---

## ⚖️ 도입 전후

<table>
  <tr>
    <td width="50%" valign="top">
      <b>❌ Golden Boy 없이</b>
      <p>에이전트가 "인증 시스템 전체를 리팩터링해줘"라는 요청을 받으면 바로 시작해서 탐색/구현/테스트
      전반에 걸쳐 공격적으로 소비하다가, 예산이 바닥나면 작업 도중 중단됩니다 — 무엇이 끝났는지에 대한
      기록도 없이.</p>
    </td>
    <td width="50%" valign="top">
      <b>✅ Golden Boy와 함께</b>
      <p>같은 요청도 실행 범위가 확정되기 <i>전</i>에 분류·비용 추정·예산 확인을 거칩니다 — 나중에
      돌이켜서 추측하는 게 아니라 실제 신뢰도 점수가 붙은 진짜 결정입니다. 실제로 무슨 일이 있었는지가
      로컬에 기록되므로, 다음번 비슷한 작업은 그 기록의 혜택을 받습니다.</p>
    </td>
  </tr>
</table>

---

## 🎬 데모

전체 흐름 — 계획을 세우고, 줄어드는 예산에 맞춰 적응적으로 실행하고, 환경을 진단합니다. 아래 내용은
모두 이 저장소에서 캡처한 실제 출력입니다(연출되거나 축약되지 않았습니다):

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

예산이 안전 마진 아래로 떨어지자 실행기는 현재 작업만 마무리하고 나머지를 체크포인트로 저장한 뒤
계속 소비하는 대신 중단했습니다.

</details>

<details>
<summary><b>$ goldenboy validate</b> (신규 설치, 아직 히스토리 없음)</summary>

```
--- Golden Boy Validate ---
Config:     OK — safety_margin=3.0, caution_ratio=0.5, base_cost_per_unit=2.0, max_budget_tokens=100000, stale_after_seconds=300.0
Checkpoint: OK — none present

Dataset Quality
Rows:                 0
Status: NO_DATA — insufficient validated data (no history recorded yet).
```

존재하지 않는 데이터를 채우기 위해 숫자를 지어내지 않습니다 — [히스토리와 분석](#-히스토리와-분석)
참고.

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

API 키는 존재 여부만 보고되며 값 자체는 절대 노출되지 않습니다 — `doctor`, `status`, `validate` 모든
진단 명령이 `--json`도 지원합니다.

</details>

---

## 🚀 설치

```bash
pip install goldenboy
goldenboy --help
```

또는 소스에서:

```bash
git clone https://github.com/amuldi/GoldenBoy.git
cd GoldenBoy
pip install -e .
```

코어 설치는 **필수 서드파티 의존성이 없습니다**. 선택적 extra들이 특정 기능을 추가합니다:

```bash
pip install "goldenboy[tiktoken]"   # 정확한 토큰 카운트(없으면 더 거친 휴리스틱으로 대체)
pip install "goldenboy[anthropic]"  # AnthropicAdapter
pip install "goldenboy[openai]"     # OpenAIAdapter
```

TypeScript 에이전트/툴은 CLI를 직접 호출하는 대신 [`sdk/typescript`](sdk/typescript)를 사용할 수
있습니다 — [TypeScript SDK](#-typescript-sdk) 참고.

---

## ⚡ 빠른 시작

```bash
goldenboy analyze "Refactor the authentication system"   # 전체 권고: 유형, 리스크, 액션, 이유
goldenboy status                                          # 현재 예산과 대기 중인 체크포인트
goldenboy validate                                         # 설정 + 체크포인트 + 로컬 데이터 품질 리포트
goldenboy doctor                                            # 환경, 설정, 체크포인트 진단
```

---

## 🖥 CLI 레퍼런스

| 명령어 | 목적 |
|---|---|
| `goldenboy analyze <task>` | 전체 작업 인텔리전스 권고: 유형, 복잡도, 리스크, 액션, 신뢰도, 이유. `--progress 0.0-1.0`, `--json`. |
| `goldenboy plan <task>` | 작업 텍스트 + 저장소 크기로 실제 비용을 추정하고 결과 리스크 모드를 표시. |
| `goldenboy run <task>` | 모의 예산에 맞춰 예산 인지 데모 계획을 적응적으로 실행. |
| `goldenboy status` | 현재 예산과 대기 중인 체크포인트 확인. `--json`. |
| `goldenboy resume` | 이전 체크포인트부터 실행 재개. |
| `goldenboy doctor` | Python 버전, 선택적 의존성, 프로바이더 키 설정, 설정, 체크포인트 진단. `--json`. |
| `goldenboy validate` | 설정 + 체크포인트 + 로컬 히스토리 데이터 품질 검증; 실제 문제가 있으면 exit 1. `--json`. |
| `goldenboy replay` | 로컬(또는 `--dataset PATH`) 히스토리로 베이스라인 정책 백테스트. `--json`. |
| `goldenboy benchmark` | 이 머신에서 지금, estimator/risk-engine/CLI 시작 지연시간을 측정. `--json`. |
| `goldenboy export` | 설정 + 체크포인트 + 히스토리를 재현 가능한 JSON 문서 하나로 내보내기. `--output PATH`. |

모의 예산을 쓰는 명령이라면 어디든 `--budget`으로 시작 예산을 조절할 수 있고, [데모](#-데모)에서
보여준 유닛별 내부 결정 로그를 보려면 서브커맨드 앞에 `-v`/`--verbose`를 붙이세요.

---

## 🐍 Python 통합

```python
from goldenboy import AdaptiveExecutor, MockProvider, budget_aware_execution, Priority

provider = MockProvider(initial_percentage=40.0)

@budget_aware_execution(provider, "1", "Refactor the auth module", Priority.P1)
def refactor_auth():
    ...  # 실제 작업은 여기에 — Golden Boy가 호출할지 말지를 결정합니다

refactor_auth()
```

`budget_aware_execution`은 프로바이더에게 예산/모드 결정을 요청하고, 모드가 허용할 때만 여러분의
함수를 호출합니다 — 프로바이더 자체를 호출하지 않습니다. 모든 호출은 로컬에 이벤트 하나도 함께
기록합니다(원문 작업 텍스트는 저장하지 않음) — [히스토리와 분석](#-히스토리와-분석) 참고. 전체
공개 API는 [`goldenboy/__init__.py`](goldenboy/__init__.py)에 있으며, 거기 없는 것은 각자의
서브모듈로 접근 가능하지만 최상위 API만큼의 안정성 보장 대상은 아닙니다.

전체 설명 포함 결정 API를 원한다면 `DecisionEngine`을 직접 사용하세요:

```python
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.decision_engine import DecisionEngine

decision = DecisionEngine().decide("Refactor the auth module", MockProvider(initial_percentage=15))
print(decision.action, decision.confidence, decision.reason)
```

---

## 🌐 프로토콜

Golden Boy가 만들어내는 모든 결정 — Python, CLI, TypeScript 어디서든 — 은 하나의 버전 관리된,
언어 중립적인 JSON 형태입니다: **Golden Boy Protocol**. 전체 스키마, 버전 관리 정책, 왜 서버가
없는지는 [`docs/PROTOCOL.md`](docs/PROTOCOL.md)에 있습니다.

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

`goldenboy/protocol.py`의 `GoldenBoyDecision.from_dict`/`from_json`은 이 방식으로 만들어진 모든
페이로드를 엄격히 검증합니다 — 필드 누락이나 호환되지 않는 메이저 스키마 버전이면 원시
`KeyError`가 아니라 `ProtocolError`를 발생시킵니다. `sdk/typescript/src/validate.ts`는
TypeScript 쪽에서 동일한 계약을 강제합니다.

---

## 📘 TypeScript SDK

[`sdk/typescript`](sdk/typescript)는 얇은 클라이언트일 뿐, 두 번째 구현체가 아닙니다 — 실제
`goldenboy` CLI를 실행해서 그 `--json` 출력을 위와 동일한 프로토콜 검증으로 파싱합니다. 런타임
의존성 없음; 테스트는 Node의 내장 테스트 러너로 실행되며, 실제(모킹 없는) CLI 통합 테스트도
포함합니다.

```ts
import { GoldenBoyClient } from "@goldenboy/sdk";

const client = new GoldenBoyClient(); // PATH의 `goldenboy` 사용
const decision = await client.analyze("Refactor the authentication system", { budget: 6 });

console.log(decision.action);       // "reduce_scope"
console.log(decision.confidence);   // 0.774
console.log(decision.reason);       // Python/CLI 출력과 동일한 실제 숫자로 구성됨
```

```bash
cd sdk/typescript
npm install && npm run build && npm test   # 14개 테스트, 실제 CLI 통합 포함
```

전체 API와 설계 노트는 [`sdk/typescript/README.md`](sdk/typescript/README.md) 참고.

---

## 📡 히스토리와 분석

`budget_aware_execution`으로 데코레이트된 호출마다 로컬의 append-only 로그
(`.goldenboy/history.jsonl`, gitignore 처리됨 — 체크포인트 파일과 같은 방식)에 이벤트 하나가
추가됩니다. 이벤트는 작업의 원문 텍스트를 절대 저장하지 않고, 길이와 잘린 SHA-256 해시만 저장합니다
([`goldenboy/core/history.py`](goldenboy/core/history.py)와 [`SECURITY.md`](SECURITY.md) 참고).

```bash
goldenboy validate   # Dataset Quality: 행 수, 손상/중복/무효값 비율, GOOD/ACCEPTABLE/POOR/NO_DATA
goldenboy export     # 설정 + 체크포인트 + 히스토리(품질 리포트, 분석, 이벤트)를 JSON 문서 하나로
```

```python
from goldenboy.analytics import data_quality
from goldenboy.analytics.engine import analyze
from goldenboy.core.history import HistoryStore

store = HistoryStore()
print(data_quality.validate(store).render())   # 실제 리포트 -- 기록된 게 없으면 "NO_DATA"
print(analyze(store).render())                  # 비용/완료/실패율 집계, 없으면 "N/A"
```

신규 설치 상태에서는 둘 다 정직하게 0행을 보고합니다 — 위 [데모](#-데모)의 `validate` 예시 참고.
여기 있는 것 중 "잠금 해제"를 기다리는 플레이스홀더는 없습니다: 여러분의 에이전트가 데코레이트된
작업을 실제로 실행하는 순간부터 실제 집계를 만들어내는, 진짜 작동하는 코드입니다.

---

## 🔁 리플레이와 백테스팅

`goldenboy.replay`는 한 가지 질문에 답합니다: *다른 리소스 배분 정책이었다면 이 실제 과거 작업들에
대해 더 나은 결정을 내렸을까?* 이것은 **AI 에이전트 리소스 배분 백테스트**이지 금융 백테스트가
아닙니다. 5개의 정책이 동일한 조건에서 비교됩니다 — 두 개의 고정 임계값 베이스라인(15%/20%),
복잡도 전용 휴리스틱, 사용량 전용 휴리스틱, 그리고 실제 수정되지 않은 `RiskEngine`을 감싸는
`GoldenBoyPolicy` — `goldenboy.core.policies`와 `goldenboy.replay.engine`을 통해서요.

```bash
$ goldenboy replay
Backtest: 0 event(s) available (need at least 10).
N/A — insufficient validated data.
```

이게 신규 설치 상태에서의 실제 출력이며, 원래 그래야 합니다. 실사용을 대신할 번들 데이터셋이나
합성 데이터셋은 없습니다; `docs/DATASETS.md`에 SWE-bench 같은 공개 벤치마크가 왜 이를 대체할 수
없는지(코드 생성 정확도를 측정할 뿐, 예산 인지 리소스 결정을 측정하지 않음) 문서화되어 있습니다.
여러분의 `.goldenboy/history.jsonl`에 최소 10개의 이벤트가 쌓이면, `goldenboy replay`는 실제로
모든 정책을 채점합니다:

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

`walk_forward_folds()`는 폴드 경계를 넘는 누출 없이 이벤트를 시간순으로 분할합니다 — 미래의
학습 기반 정책을 위해 이미 테스트되고 준비된 인프라입니다(오늘의 5개 정책은 모두
고정/결정론적이라 폴딩이 아직 점수를 바꾸지 않습니다; `goldenboy/replay/engine.py`의 모듈
docstring 참고). 리포트는 어떤 숫자를 보여주든 항상 자신의 방법론적 한계를 함께 출력합니다 —
[`goldenboy/replay/engine.py`](goldenboy/replay/engine.py) 참고.

---

## 🔌 통합

프로바이더 어댑터는 사용량을 보고할 뿐 여러분의 코드를 절대 실행하지 않습니다. 실제 작업은 항상
위의 `budget_aware_execution` 데코레이터를 통해 실행됩니다.

| 프로바이더 | 읽는 것 | 참고 |
|---|---|---|
| `MockProvider` | 합성 인메모리 퍼센트 | 데모와 테스트용 — 네트워크 호출 없음. |
| `AnthropicAdapter` | `anthropic-ratelimit-tokens-remaining` / `-limit` 응답 헤더 | `goldenboy[anthropic]` 필요. 조직의 *공유* rate limit을 반영하며, 이 호출 하나만의 것이 아님. |
| `OpenAIAdapter` | `x-ratelimit-remaining-tokens` / `-limit-tokens` 응답 헤더 | `goldenboy[openai]` 필요. 위와 같은 공유-한도 주의사항. |
| Claude Code 스킬 | Claude Code가 컨텍스트에 주입하는 `<total_tokens>` 수치 | Python 프로세스 불필요 — 아래 참고. |
| TypeScript SDK | 자식 프로세스로 실행한 `goldenboy` CLI의 `--json` 출력 | HTTP 서버 없음 — [프로토콜](#-프로토콜) 참고. |

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

두 어댑터 모두 명시적인 `refresh_usage()` 호출을 통해서만 값을 갱신하며, 주입 가능한 시계로
그 시점 이후 얼마나 지났는지 추적합니다 — `stale_after_seconds`(기본 300초)를 지나면 신뢰도가
`ESTIMATED`에서 `STALE`로 자동으로 노화됩니다. 첫 갱신 전에는 신뢰도가 `UNKNOWN`인데 —
`RiskEngine` 자체가 아니라 `DecisionEngine`이 이것도 `STALE`과 같은 방식으로 보수적으로 다룹니다.

**Claude Code**는 대신 프롬프트 레벨 통합을 사용합니다:
[`skills/goldenboy/SKILL.md`](skills/goldenboy/SKILL.md)는 LLM 에이전트에게 Claude Code가
컨텍스트에 직접 주입하는 잔여 사용량 수치를 읽고 자신의 실행 모드를 스스로 판단하도록 가르치며,
`goldenboy.core.risk.ExecutionMode`와 정확히 같은 `SAFE`/`CAUTION`/`LIMITED`/`CRITICAL`
용어를 사용합니다 — 코드를 공유하는 게 아니라 수작업으로 동기화합니다. 한쪽은 Python이고
다른 쪽은 프롬프트이기 때문입니다.

---

## 🏗 아키텍처

<details>
<summary><b>패키지 트리 펼치기</b></summary>

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

## ⚙️ 설정

모든 정책 임계값은 `GoldenBoyConfig`에 있으며, 다음 우선순위로 적용됩니다:

```
explicit constructor arg  >  GOLDENBOY_* environment variable  >  .goldenboy/config.json  >  default
```

| 필드 | 환경 변수 | 기본값 | 의미 |
|---|---|---|---|
| `safety_margin` | `GOLDENBOY_SAFETY_MARGIN` | `3.0` | 보고된 잔여 예산이 소진됐다고 간주되기 전 남겨두는 퍼센트 포인트. |
| `caution_ratio` | `GOLDENBOY_CAUTION_RATIO` | `0.5` | 리스크가 SAFE에서 CAUTION으로 넘어가는 추정비용/사용가능예산 비율. |
| `base_cost_per_unit` | `GOLDENBOY_BASE_COST_PER_UNIT` | `2.0` | 계획의 유닛이 비용을 선언하지 않았을 때의 대체 비용. |
| `max_budget_tokens` | `GOLDENBOY_MAX_BUDGET_TOKENS` | `100000` | 원시 토큰 추정치를 퍼센트로 변환할 때 "예산의 100%"로 취급하는 토큰 수. |
| `stale_after_seconds` | `GOLDENBOY_STALE_AFTER_SECONDS` | `300.0` | 갱신된 프로바이더 값이 `ESTIMATED`로 유지되다가 `STALE`로 넘어가기까지의 시간. |

범위를 벗어난 값, 잘못된 JSON, 파싱 불가능한 `GOLDENBOY_*` 환경 변수는 모두 명확한 `ConfigError`를
발생시킵니다 — CLI에서는 원시 스택 트레이스가 아닌 한 줄짜리 `error:` 메시지와 exit `1`로.

---

## 🧭 설계 원칙

- **가벼움** — 코어 설치는 필수 서드파티 런타임 의존성이 없으며, 프로바이더 SDK와 TypeScript SDK 자체 툴링은 선택 사항입니다.
- **적응성** — 실행 동작은 남은 예산에 따라, *그리고* 그 수치를 얼마나 신뢰할 수 있는지에 따라 바뀝니다: `STALE` 또는 `UNKNOWN` 값은 절대 `SAFE` 판정을 낼 수 없습니다.
- **결정론적** — 동일한 입력은 동일한 결정을 만듭니다. estimator, classifier, risk engine 모두 숨겨진 무작위성이 없으며, 어댑터의 노후화는 주입 가능한 시계로 구동되어 sleep 없이 테스트 가능합니다.
- **프로바이더 선택적** — `import goldenboy`는 `anthropic`이나 `openai` 설치를 절대 요구하지 않습니다.
- **에이전트 우선** — Golden Boy는 남은 예산을 기반으로 에이전트가 얼마나 공격적으로 진행해야 할지 결정합니다. 호출하는 에이전트는 작업을 이해하고 분해하는 책임을 계속 집니다.
- **안전한 실패** — 잘못된 설정, 손상된 체크포인트, 잘못된 입력은 구체적이고 사람이 읽을 수 있는 오류와 종료 코드를 만들 뿐, 원시 트레이스백이나 조용한 데이터 손실을 만들지 않습니다.
- **복잡함보다 증거** — 벤치마크 수치, 백테스트 결과, 히스토리 데이터셋 어디에서도 조작은 없습니다. `goldenboy replay`/`goldenboy.analytics`는 기준선을 지어내는 대신 `N/A`/`NO_DATA`를 보고합니다; [`docs/DATASETS.md`](docs/DATASETS.md)와 [`ROADMAP.md`](ROADMAP.md)의 명시적 비목표 참고.

---

## 📦 작업 분해에 대하여

> `plan`/`run`/`analyze`가 보여주는 추정 비용은 실제 작업 텍스트와 저장소 컨텍스트로 계산됩니다 —
> 그 숫자는 진짜입니다. `plan`/`run`의 유닛 분해는 **예시용**입니다: 여러분의 작업을 LLM이 실제로
> 분해한 결과가 아닙니다. Golden Boy는 의도적으로 코어를 의존성 없이 유지하며 작업을 *어떻게* 할지
> 이해하는 영역에는 관여하지 않습니다; 실제 작업 분해는 계속 호출 에이전트의 책임입니다
> ([설계 원칙](#-설계-원칙) 참고). `TaskClassifier`는 이 작업이 *어떤 종류*로 보이는지 알려줄
> 뿐, 어떻게 단계로 나눌지는 알려주지 않습니다.

---

## ⚠️ 한계

- 비용 추정치는 휴리스틱(프롬프트 길이 + 제한된 저장소 스캔)이며 — 과금 보증이 아니고, 에이전트가 실제로 컨텍스트에 로드할 내용의 모델도 아닙니다.
- `TaskClassifier`는 결정론적 키워드 매처이지 학습된 모델이 아닙니다 — 신뢰도 점수는 보정된 확률이 아닌 매칭 강도를 반영합니다. 아직 학습에 쓸 라벨링된 실데이터가 없습니다(`docs/DATASETS.md` 참고).
- `goldenboy replay`/`goldenboy.analytics`는 로컬에 실제 이벤트 최소 10개가 기록될 때까지 `N/A`/`NO_DATA`를 보고합니다 — 이를 대체할 번들 데이터셋은 없습니다.
- 리플레이의 지표는 로그된 결과로부터의 오프-폴리시 평가입니다: 이벤트에 기록된 결과는 Golden Boy가 그 당시 실제로 내린 결정을 반영하는 것이지, 지금 채점 중인 대체 정책의 결과가 아닙니다 — 인과적 보장이 아닌 서술적 비교입니다([리플레이와 백테스팅](#-리플레이와-백테스팅) 참고).
- 프로바이더 사용량(rate-limit 헤더)은 갱신 사이에 Golden Boy의 통제 밖에서 바뀔 수 있습니다; 그게 바로 `STALE` 신뢰도가 존재하는 이유입니다.
- `plan`/`run`의 유닛 분해는 예시용이지 작업 분해가 아닙니다(위 참고).
- Golden Boy는 호출하는 코딩 에이전트 자체의 판단을 대체하지 않습니다 — 얼마나 시도할지에 대한 정보만 제공합니다.

---

## ✅ 검증

Golden Boy v1.1.0은 2026-09-14 기준으로 다음을 통해 검증되었습니다:

- **Python 테스트 186개**, 95% 라인 커버리지(`pytest --cov`) — v1.0.0의 88개 테스트/93%에서 증가
- **TypeScript 테스트 14개**(`sdk/typescript`에서 `npm test`), 실제 설치된 CLI에 대한 실제(모킹 없는) 통합 테스트 포함
- Ruff와 mypy 클린(mypy는 1.19.1과 2.3.1 양쪽에서 확인)
- `pip-audit`: 알려진 취약점 0개
- Python 3.9–3.13, GitHub Actions에서
- 독립된 신규 가상환경에 설치한 wheel과 sdist, 새로 추가된 것을 포함한 모든 CLI 명령을 실제로 실행해서 확인
- 코어 전용 설치(`pip install goldenboy`)가 서드파티 런타임 의존성을 0개 설치함 — 단순 주장이 아니라 클린룸 설치에서 `pip list`로 라이브 검증

CI(`.github/workflows/ci.yml`, 8개 잡):

| 잡 | 결과 |
|---|---|
| security (pip-audit) | ✓ |
| test (3.9) | ✓ |
| test (3.10) | ✓ |
| test (3.11) | ✓ |
| test (3.12) | ✓ |
| test (3.13) | ✓ |
| build (wheel 설치 + 모든 CLI 명령 + 벤치마크 sanity check) | ✓ |
| sdk-typescript (설치된 CLI와의 실제 통합) | ✓ |

---

## 📊 벤치마크

한 번, 로컬에서 측정(Apple M1 Pro, macOS arm64, Python 3.13.7, 2026-09-13), `goldenboy benchmark` /
`scripts/benchmark.py`로(구현체는 하나 — `goldenboy/core/benchmark.py` 참고) — CI의
통과/실패 게이트의 일부가 아니며(CI는 숫자가 음수가 아닌지와 estimator가 결정론적인지만
확인합니다), 보증이 아닙니다. 이 숫자에 뭔가를 의존하기 전에 직접 다시 돌려보세요.

| 연산 | 평균 | 중앙값 | n |
|---|---|---|---|
| `Estimator.estimate_task()` (웜, 이 저장소) | 9.30ms | 8.79ms | 20 |
| `Estimator.estimate_task()` 결정론성 | PASS — 동일 호출 10회 중 결과 1종류 | | 10 |
| `RiskEngine.assess()` | <0.001ms | <0.001ms | 1000 |
| CLI 콜드 스타트 (`goldenboy status`) | 93.46ms | 93.33ms | 5 |

`RiskEngine.assess()`는 이미 계산된 값들에 대한 순수 산술 연산이므로 구조적으로 서브마이크로초
단위입니다. Estimator의 지연시간은 저장소 크기에 비례해 늘어나며(`_MAX_SCAN_FILES` /
`_MAX_FILE_BYTES` 상한으로 제한됨) 프롬프트 길이와는 무관합니다. CLI 콜드 스타트는 대부분
Python 인터프리터/임포트 오버헤드입니다 — `goldenboy` 명령 하나를 실행할 때 실제로 체감하는
부분입니다. 전체 방법론, 주의사항, 이 숫자들을 근거로 한 Rust 이전 논리는
[`BENCHMARKS.md`](BENCHMARKS.md)와 [`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md)에.

---

## 🗺 로드맵

**출시됨, 테스트됨, 진짜:**

- ✓ 작업 인지 비용 추정, 적응형 실행 모드, 체크포인트/보류/재개, STALE 감지를 포함한 사용량 신뢰도
- ✓ CLI (`plan`/`run`/`status`/`resume`/`doctor`/`analyze`/`validate`/`replay`/`benchmark`/`export`)
- ✓ Anthropic/OpenAI 프로바이더 어댑터, Claude Code 스킬 통합
- ✓ Golden Boy Protocol(버전 관리, 언어 중립) + TypeScript SDK
- ✓ 작업 분류(`TaskClassifier`) + `DecisionEngine`(설명이 붙은 액션/신뢰도/이유)
- ✓ 로컬 히스토리(`HistoryStore`) + 데이터 품질/분석 리포트
- ✓ 베이스라인 정책 + `goldenboy.replay` 백테스트 엔진 + 워크포워드 분할

| 방향 | 상태 |
|---|---|
| 실제로 채워진 백테스트 결과(N/A가 아닌) | 실사용 데이터가 쌓이길 대기 중 — 지금은 정직하게 만들어낼 수 없음 |
| 학습된 작업 분류기 / 정책 | 리서치 — 먼저 라벨링된 실제 결과 데이터가 필요 |
| `cli.py`를 `cli/` 패키지로 분리 | 계획됨 — 이번 사이클엔 보류(회귀 리스크 대비 이득; `ROADMAP.md` 참고) |
| 의도적으로 큰 합성 저장소 대상 벤치마킹 | 계획됨 |
| 추가 에이전트 통합(예: Codex) | 리서치 — 기반으로 삼을 실제이고 문서화된 사용량 시그널이 있을 때만 |

위 어떤 것도 테스트로 커버되지 않으면 프로덕션 준비 완료로 주장하지 않습니다. Done/Planned/Research
전체 분류와 명시적 비목표(데이터베이스 없음, 웹 대시보드 없음, 서버 없음, 성급한 ML이나 Rust 없음)는
[`ROADMAP.md`](ROADMAP.md)에.

---

## 🤝 기여하기

기여를 환영합니다. [`CONTRIBUTING.md`](CONTRIBUTING.md)에 설정 단계, PR이 통과해야 하는 체크
(`pytest`, `ruff`, `mypy`, `python -m build` — CI에서 모두 강제됨), 그리고 리뷰 기준인 엔지니어링
원칙(기존 아키텍처 우선, 증상보다 근본 원인, 가짜 완성도 금지, 정직한 신뢰도 표기, `GoldenBoyConfig`
밖에 정책 숫자 하드코딩 금지)이 있습니다.

---

## 🛠 개발

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

TypeScript SDK는:

```bash
cd sdk/typescript
npm install
npm run typecheck && npm run build && npm test
```

---

## 📚 더 많은 문서

| 문서 | 내용 |
|---|---|
| [`docs/PROTOCOL.md`](docs/PROTOCOL.md) | Golden Boy Protocol 스키마, 버전 관리 정책, 서버가 없는 이유. |
| [`docs/DATASETS.md`](docs/DATASETS.md) | 데이터셋/리서치 현황 리뷰(SWE-bench, HumanEval, LiveCodeBench, RepoBench, 토큰 소비 리서치)와 이들이 왜 `HistoryStore`를 대체하지 못하는지. |
| [`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md) | 왜 Python이 코어로 남는지, TypeScript는 어디에 쓰이는지, 미래의 Rust 이전 경계. |
| [`CHANGELOG.md`](CHANGELOG.md) | 릴리스별 변경 사항. |
| [`ROADMAP.md`](ROADMAP.md) | Done / Planned / Research 전체 분류, 명시적 비목표 포함. |
| [`BENCHMARKS.md`](BENCHMARKS.md) | 측정된 성능 수치, 방법론, 아직 측정하지 않은 것. |
| [`SECURITY.md`](SECURITY.md) | 자격 증명과 로컬 히스토리를 어떻게 다루는지, 취약점 제보 방법. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 설정, 체크, 리뷰 기준인 엔지니어링 원칙. |
| [`sdk/typescript/README.md`](sdk/typescript/README.md) | TypeScript SDK API 레퍼런스와 설계 노트. |

---

## 📄 라이선스

[MIT](LICENSE).

<p align="center">
  ⭐ Golden Boy가 여러분 에이전트의 예산 소진을 막아준다면, 별 하나가 더 많은 사람이 찾는 데 도움이 됩니다.
</p>
