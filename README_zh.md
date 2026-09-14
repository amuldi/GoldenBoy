<p align="center">
  <a href="README.md">English</a> | <b>中文</b> | <a href="README_ja.md">日本語</a> | <a href="README_ko.md">한국어</a> | <a href="README_ar.md">العربية</a> | <a href="README_es.md">Español</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/amuldi/GoldenBoy/main/assets/golden-boy.png" width="220" alt="Golden Boy">
</p>

<h1 align="center">Golden Boy</h1>
<p align="center"><b>AI 智能体资源智能 — 把 AI 用量花在真正值得的工作上。</b></p>

<p align="center">
  <img src="https://github.com/amuldi/GoldenBoy/actions/workflows/ci.yml/badge.svg" alt="CI status">
  <img src="https://img.shields.io/badge/python-3.9--3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9–3.13">
  <img src="https://img.shields.io/badge/coverage-95%25-2ea44f?style=flat-square" alt="Coverage 95%">
  <img src="https://img.shields.io/badge/dependencies-zero-2ea44f?style=flat-square" alt="Zero required dependencies">
  <img src="https://img.shields.io/badge/TypeScript_SDK-node_%3E%3D18-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript SDK, Node >= 18">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#-什么是-golden-boy">这是什么</a> &nbsp;&middot;&nbsp;
  <a href="#-真实示例">真实示例</a> &nbsp;&middot;&nbsp;
  <a href="#-核心能力">核心能力</a> &nbsp;&middot;&nbsp;
  <a href="#-工作原理">工作原理</a> &nbsp;&middot;&nbsp;
  <a href="#-安装">安装</a> &nbsp;&middot;&nbsp;
  <a href="#-cli-参考">CLI</a> &nbsp;&middot;&nbsp;
  <a href="#-协议">协议</a> &nbsp;&middot;&nbsp;
  <a href="#-typescript-sdk">TypeScript SDK</a> &nbsp;&middot;&nbsp;
  <a href="#-回放与回测">回测</a> &nbsp;&middot;&nbsp;
  <a href="#-验证">验证</a> &nbsp;&middot;&nbsp;
  <a href="#-路线图">路线图</a> &nbsp;&middot;&nbsp;
  <a href="#-贡献">贡献</a>
</p>

> 本文档是[英文原版](README.md)的翻译。代码块、命令、CLI 输出和 JSON 均保持原文(英文)不变 ——
> 这样你可以直接复制运行。如译文与原文有出入,以英文原版为准。

---

## 💡 什么是 Golden Boy?

AI 编程智能体往往对每个任务一视同仁,不管实际还剩多少用量。一个在剩余预算 15% 时开始的大任务,
往往以同样的方式收场:在编辑中途被打断,而且没有留下任何"完成了什么、没完成什么"的记录。

**Golden Boy** 是一个位于智能体与其工作之间的决策层:它会判断这是*什么类型*的任务、估算它的成本、
对照剩余预算进行检查——*以及该预算读数到底有多可信*——然后告诉智能体应该多激进地推进:直接执行、
继续、缩小范围、收尾并验证,还是停下并保存检查点。每一条建议都附带一个置信度分数,以及基于本次
调用实际计算出的数字所构建的理由,并且无论你是从 Python、CLI 还是 TypeScript 调用,得到的都是
同一种带版本号的 JSON 结构([Golden Boy Protocol](#-协议))。

| | |
|---|---|
| ✅ **它做什么** | 对任务分类、估算成本、追踪预算与置信度、决定一个动作(运行/继续/缩小范围/收尾/验证/停止/询问)、为延后的工作保存检查点、在本地记录发生了什么,并让你用这些历史数据回测其他策略。 |
| 🚫 **它不做什么** | 把任务拆解成编码计划、取代调用它的智能体、扮演编码智能体/IDE/LLM 提供方,或运行服务器。参见[设计原则](#-设计原则)和[关于任务拆解](#-关于任务拆解)。 |

---

## 🧠 真实示例

```
用户:"重构认证系统并更新测试。"
```

下面的每一个数值都是 `goldenboy analyze` 的真实实时输出——不是摆拍:

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

这里没有任何模板化的编造:任务类型来自 `TaskClassifier` 对提示文本的实际扫描,成本来自
`Estimator` 对本次运行的仓库+提示词的实际扫描,风险模式来自 `RiskEngine` 对该成本与你传入的
模拟预算的实际比较。改变预算或任务文本,每个字段都会随之改变——加上 `--json` 后产生的确切 JSON
见[协议](#-协议)一节。

---

## ✨ 核心能力

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🧠 任务智能</h3>
      <div>
        • 13 种类型分类器(修复 bug、重构、测试、架构变更……)<br>
        • 确定性且透明——是启发式匹配强度分数,绝非伪装的校准概率<br>
        • 从真实成本估算中推导出的复杂度标签(LOW/MEDIUM/HIGH/VERY_HIGH)
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🚦 附带解释的决策</h3>
      <div>
        • <b>RUN · CONTINUE · REDUCE_SCOPE · FINISH · VERIFY · STOP · ASK_USER</b><br>
        • 每个决策都附带置信度分数,以及基于真实数字构建的理由<br>
        • 置信度过低无法安全行动时 → <code>ASK_USER</code>,而不是瞎猜
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🔋 预算与置信度追踪</h3>
      <div>
        • 剩余预算以百分比呈现,并附带 <b>EXACT / ESTIMATED / STALE / UNKNOWN</b> 置信度<br>
        • <code>STALE</code> 或 <code>UNKNOWN</code> 的读数绝不会悄悄伪装成 <code>SAFE</code><br>
        • 适配器的过期判断由可注入的时钟驱动——确定性,测试中没有 <code>sleep()</code>
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>💾 检查点与恢复</h3>
      <div>
        • 延后的工作会被保存,绝不会悄悄丢失<br>
        • <code>goldenboy resume</code> 从上一个检查点继续<br>
        • 检查点 schema 带版本号——不兼容的未来格式会干净地失败
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>📡 本地历史与分析</h3>
      <div>
        • 每次被装饰的调用都会在本地追加一条事件——绝不保存原始任务文本<br>
        • 真实的数据集质量报告(行数、损坏/重复/无效比例)<br>
        • 基于你自己真实使用数据的成本/完成率/失败率聚合
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔁 回放与回测</h3>
      <div>
        • 5 个基线策略根据真实历史打分:精确率、召回率、过早停止率<br>
        • 前向滚动、无泄漏的按时间顺序切分<br>
        • 事件不足 10 条时诚实地返回 <code>N/A</code>——绝不编造表格
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🌐 Golden Boy Protocol</h3>
      <div>
        • 一套带版本号、语言中立的 JSON 决策 schema<br>
        • 严格校验——出错时给出具体错误,而不是原始的 <code>KeyError</code><br>
        • Python、CLI、TypeScript 输出同一份数据
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔌 智能体集成</h3>
      <div>
        • <code>budget_aware_execution</code> 装饰器可包裹任意 Python 可调用对象<br>
        • <code>AnthropicAdapter</code> / <code>OpenAIAdapter</code> 读取真实的 rate-limit 响应头<br>
        • 一个 TypeScript SDK,以及一个提示词级别的 <b>Claude Code</b> 技能
      </div>
    </td>
  </tr>
</table>

---

## 🔄 工作原理

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

| 模式 | 含义 | 智能体行为 |
|---|---|---|
| 🟢 `SAFE` | 远高于预估成本 | 正常执行 P0–P4 |
| 🟡 `CAUTION` | 足够,但该任务占比较大 | 继续,但保持保守,不开新范围 |
| 🟠 `LIMITED` | 预估成本超过可用预算 | 限制在 P0/P1,并告知调用方跳过了什么 |
| 🔴 `CRITICAL` | 预算已经处于/低于安全边际 | 完成当前 P0 单元,保存检查点,停止 |

模式由两个顺序检查决定——预算是否已耗尽(低于 `safety_margin`)→ `CRITICAL`;预估成本是否已超过
全部可用预算 → `LIMITED`——否则按预估成本与可用预算的比值,以可配置的 `caution_ratio`(默认 `0.5`)
划分。`STALE` 的预算读数绝不允许产生 `SAFE` 判定——无论原始数字看起来多宽裕,都会被升级为至少
`CAUTION`;`DecisionEngine` 对 `UNKNOWN` 置信度的预算(从未刷新过的适配器)也应用同样的保守规则,
作为叠加在未改动的 `RiskEngine` 之上的一条明确、独立的策略——详见
[`goldenboy/core/risk.py`](goldenboy/core/risk.py) 和
[`goldenboy/core/decision_engine.py`](goldenboy/core/decision_engine.py)。

---

## ⚖️ 使用前后对比

<table>
  <tr>
    <td width="50%" valign="top">
      <b>❌ 没有 Golden Boy</b>
      <p>智能体收到"重构整个认证系统"的请求后立即开始,在探索/实现/测试各阶段大手大脚地消耗,
      预算耗尽时任务被中途打断——且没有留下已完成内容的记录。</p>
    </td>
    <td width="50%" valign="top">
      <b>✅ 有了 Golden Boy</b>
      <p>同样的请求会在执行范围被确定<i>之前</i>经过分类、成本估算和预算检查——这是一个附带
      真实置信度分数的真实决策,而不是事后才做的猜测。实际发生的情况会被记录在本地,
      让下一个类似任务从中受益。</p>
    </td>
  </tr>
</table>

---

## 🎬 演示

一个完整流程——制定计划,然后在预算不断缩减的情况下自适应执行,再诊断环境。以下每一行都是
从本仓库捕获的真实输出(未经排练或删减):

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

预算在运行途中跌破安全边际——执行器完成了当前单元,把其余部分保存为检查点,然后停止,
而不是继续消耗。

</details>

<details>
<summary><b>$ goldenboy validate</b>(全新安装,尚无历史记录)</summary>

```
--- Golden Boy Validate ---
Config:     OK — safety_margin=3.0, caution_ratio=0.5, base_cost_per_unit=2.0, max_budget_tokens=100000, stale_after_seconds=300.0
Checkpoint: OK — none present

Dataset Quality
Rows:                 0
Status: NO_DATA — insufficient validated data (no history recorded yet).
```

不会为了填补尚不存在的数据而编造数字——参见[历史与分析](#-历史与分析)。

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

只报告 API 密钥是否存在,绝不显示密钥本身——`doctor`、`status`、`validate` 每个诊断命令也都
支持 `--json`。

</details>

---

## 🚀 安装

```bash
pip install goldenboy
goldenboy --help
```

或者从源码安装:

```bash
git clone https://github.com/amuldi/GoldenBoy.git
cd GoldenBoy
pip install -e .
```

核心安装**没有任何必需的第三方依赖**。可选的 extras 会添加特定能力:

```bash
pip install "goldenboy[tiktoken]"   # 精确的 token 计数(没有它时回退到更粗糙的启发式方法)
pip install "goldenboy[anthropic]"  # AnthropicAdapter
pip install "goldenboy[openai]"     # OpenAIAdapter
```

TypeScript 智能体/工具可以使用 [`sdk/typescript`](sdk/typescript) 而不必直接调用 CLI——
参见 [TypeScript SDK](#-typescript-sdk)。

---

## ⚡ 快速开始

```bash
goldenboy analyze "Refactor the authentication system"   # 完整建议:类型、风险、动作、原因
goldenboy status                                          # 当前预算及任何待处理的检查点
goldenboy validate                                         # 配置 + 检查点 + 本地数据质量报告
goldenboy doctor                                            # 环境、配置与检查点诊断
```

---

## 🖥 CLI 参考

| 命令 | 用途 |
|---|---|
| `goldenboy analyze <task>` | 完整的任务智能建议:类型、复杂度、风险、动作、置信度、原因。`--progress 0.0-1.0`、`--json`。 |
| `goldenboy plan <task>` | 根据任务文本+仓库大小估算真实成本,并显示对应的风险模式。 |
| `goldenboy run <task>` | 针对模拟预算自适应地执行一个预算感知的演示计划。 |
| `goldenboy status` | 查看当前预算及任何待处理的检查点。`--json`。 |
| `goldenboy resume` | 从上一个检查点恢复执行。 |
| `goldenboy doctor` | 诊断 Python 版本、可选依赖、提供方密钥配置、配置文件、检查点。`--json`。 |
| `goldenboy validate` | 校验配置 + 检查点 + 本地历史数据质量;发现真实问题时以 exit 1 退出。`--json`。 |
| `goldenboy replay` | 针对本地(或 `--dataset PATH`)历史数据回测基线策略。`--json`。 |
| `goldenboy benchmark` | 立即在本机测量 estimator/risk-engine/CLI 启动延迟。`--json`。 |
| `goldenboy export` | 将配置 + 检查点 + 历史导出为一份可复现的 JSON 文档。`--output PATH`。 |

对任何使用模拟预算的命令加上 `--budget` 可以控制起始预算,在子命令前加上 `-v`/`--verbose`
可查看[演示](#-演示)中展示的内部逐单元决策日志。

---

## 🐍 Python 集成

```python
from goldenboy import AdaptiveExecutor, MockProvider, budget_aware_execution, Priority

provider = MockProvider(initial_percentage=40.0)

@budget_aware_execution(provider, "1", "Refactor the auth module", Priority.P1)
def refactor_auth():
    ...  # 你真正的工作写在这里——Golden Boy 决定是否调用它

refactor_auth()
```

`budget_aware_execution` 会向提供方询问预算/模式决策,只有在模式允许时才调用你的函数——
从不调用提供方本身。每次调用还会在本地记录一条事件(绝不记录原始任务文本)——参见
[历史与分析](#-历史与分析)。完整的公开 API 位于
[`goldenboy/__init__.py`](goldenboy/__init__.py);未列在其中的内容仍可通过各自的子模块访问,
但不属于顶层 API 的稳定性承诺范围。

若需要完整、带解释的决策 API,直接使用 `DecisionEngine`:

```python
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.decision_engine import DecisionEngine

decision = DecisionEngine().decide("Refactor the auth module", MockProvider(initial_percentage=15))
print(decision.action, decision.confidence, decision.reason)
```

---

## 🌐 协议

无论从 Python、CLI 还是 TypeScript 调用,Golden Boy 产出的每一个决策都是同一种带版本号、
语言中立的 JSON 结构:**Golden Boy Protocol**。完整 schema、版本管理策略,以及为何没有服务端,
见 [`docs/PROTOCOL.md`](docs/PROTOCOL.md)。

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

`goldenboy/protocol.py` 中的 `GoldenBoyDecision.from_dict`/`from_json` 会严格校验以这种方式
构建的任何负载——字段缺失或主版本号不兼容都会抛出 `ProtocolError`,而不是原始的 `KeyError`。
`sdk/typescript/src/validate.ts` 在 TypeScript 一侧强制执行完全相同的约定。

---

## 📘 TypeScript SDK

[`sdk/typescript`](sdk/typescript) 是一个轻量客户端,而非第二套实现——它会启动真正的
`goldenboy` CLI,并通过与上文相同的协议校验来解析其 `--json` 输出。零运行时依赖;
测试运行在 Node 内置的测试运行器上,并包含针对实际 CLI 的真实(非模拟)集成测试。

```ts
import { GoldenBoyClient } from "@goldenboy/sdk";

const client = new GoldenBoyClient(); // 使用 PATH 中的 `goldenboy`
const decision = await client.analyze("Refactor the authentication system", { budget: 6 });

console.log(decision.action);       // "reduce_scope"
console.log(decision.confidence);   // 0.774
console.log(decision.reason);       // 由与 Python/CLI 输出相同的真实数字构建
```

```bash
cd sdk/typescript
npm install && npm run build && npm test   # 14 个测试,含真实的 CLI 集成
```

完整 API 和设计说明见 [`sdk/typescript/README.md`](sdk/typescript/README.md)。

---

## 📡 历史与分析

每一次被 `budget_aware_execution` 装饰的调用,都会向本地的追加式日志
(`.goldenboy/history.jsonl`,已被 gitignore——与检查点文件同样的约定)追加一条事件。
事件绝不保存任务的原始文本,只保存其长度和一段截断的 SHA-256 哈希(见
[`goldenboy/core/history.py`](goldenboy/core/history.py) 和 [`SECURITY.md`](SECURITY.md))。

```bash
goldenboy validate   # 数据集质量:行数、损坏/重复/无效值比例、GOOD/ACCEPTABLE/POOR/NO_DATA
goldenboy export     # 将配置 + 检查点 + 历史(质量报告、分析、事件)导出为一份 JSON 文档
```

```python
from goldenboy.analytics import data_quality
from goldenboy.analytics.engine import analyze
from goldenboy.core.history import HistoryStore

store = HistoryStore()
print(data_quality.validate(store).render())   # 真实报告——如果还没记录任何东西就是 "NO_DATA"
print(analyze(store).render())                  # 成本/完成率/失败率聚合,没有数据则是 "N/A"
```

在全新安装状态下,两者都会诚实地报告 0 行——见上文[演示](#-演示)中的 `validate` 示例。
这里没有任何一项是等待"解锁"的占位符:一旦你的智能体真正运行了被装饰的任务,这些真实、可用的
代码就会立刻开始产出真实的聚合数据。

---

## 🔁 回放与回测

`goldenboy.replay` 回答一个问题:*换一个资源分配策略,在这些真实的过往任务上是否会做出更好的
决策?*这是一个**AI 智能体资源分配回测**,而不是金融回测。五个策略在完全相同的条件下进行比较——
两个固定阈值基线(15%/20%)、一个仅看复杂度的启发式、一个仅看用量的启发式,以及包裹了真实且未
修改的 `RiskEngine` 的 `GoldenBoyPolicy`——通过 `goldenboy.core.policies` 和
`goldenboy.replay.engine` 实现。

```bash
$ goldenboy replay
Backtest: 0 event(s) available (need at least 10).
N/A — insufficient validated data.
```

这就是全新安装状态下真实的、当前的输出——而且理应如此。没有任何捆绑或合成的数据集来冒充真实
使用数据;`docs/DATASETS.md` 记录了为什么 SWE-bench 这类公开基准无法替代它(它们衡量的是代码
生成的正确性,而不是预算感知的资源决策)。一旦你自己的 `.goldenboy/history.jsonl` 累积了至少
10 条事件,`goldenboy replay` 就会真实地为每个策略打分:

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

`walk_forward_folds()` 会把事件按时间顺序切分,且跨折之间没有泄漏——这是为未来某个学习型策略
准备好、已经过测试的基础设施(今天的五个策略都是固定/确定性的,所以切分暂时不会改变它们的分数;
详见 `goldenboy/replay/engine.py` 的模块文档字符串)。报告在展示任何数字的同时,总会打印其自身
的方法论局限——见 [`goldenboy/replay/engine.py`](goldenboy/replay/engine.py)。

---

## 🔌 集成

提供方适配器只负责报告用量,绝不会执行你的代码。真正的工作始终通过上面的
`budget_aware_execution` 装饰器运行。

| 提供方 | 读取内容 | 说明 |
|---|---|---|
| `MockProvider` | 一个合成的、内存中的百分比 | 用于演示和测试——没有网络调用。 |
| `AnthropicAdapter` | `anthropic-ratelimit-tokens-remaining` / `-limit` 响应头 | 需要 `goldenboy[anthropic]`。反映的是组织*共享*的速率限制,而非仅本次调用。 |
| `OpenAIAdapter` | `x-ratelimit-remaining-tokens` / `-limit-tokens` 响应头 | 需要 `goldenboy[openai]`。有着与上面相同的共享限制注意事项。 |
| Claude Code 技能 | Claude Code 注入到上下文中的 `<total_tokens>` 数值 | 无需 Python 进程——见下文。 |
| TypeScript SDK | 通过子进程运行的 `goldenboy` CLI 的 `--json` 输出 | 没有 HTTP 服务端——见[协议](#-协议)。 |

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

两个适配器都只通过显式的 `refresh_usage()` 调用来更新读数,并使用可注入的时钟追踪自那以来
过去了多久——超过 `stale_after_seconds`(默认 300 秒)后,置信度会自动从 `ESTIMATED`
老化到 `STALE`。在首次刷新之前,置信度是 `UNKNOWN`——对此进行保守处理的是 `DecisionEngine`
而非 `RiskEngine` 本身,处理方式与 `STALE` 相同。

**Claude Code** 使用的是提示词级别的集成:
[`skills/goldenboy/SKILL.md`](skills/goldenboy/SKILL.md) 教会 LLM 智能体读取 Claude Code
直接注入到上下文中的剩余用量数值,并自行推理其执行模式,使用与
`goldenboy.core.risk.ExecutionMode` 完全相同的 `SAFE`/`CAUTION`/`LIMITED`/`CRITICAL` 词汇表——
由人工手动保持同步,而非共享代码,因为一边是 Python,另一边是提示词。

---

## 🏗 架构

<details>
<summary><b>点击展开包结构树</b></summary>

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

## ⚙️ 配置

每一个策略阈值都存放在 `GoldenBoyConfig` 中,按以下顺序覆盖:

```
explicit constructor arg  >  GOLDENBOY_* environment variable  >  .goldenboy/config.json  >  default
```

| 字段 | 环境变量 | 默认值 | 含义 |
|---|---|---|---|
| `safety_margin` | `GOLDENBOY_SAFETY_MARGIN` | `3.0` | 在报告的剩余预算被视为耗尽之前预留的百分点数。 |
| `caution_ratio` | `GOLDENBOY_CAUTION_RATIO` | `0.5` | 风险从 SAFE 变为 CAUTION 时的预估成本/可用预算比值。 |
| `base_cost_per_unit` | `GOLDENBOY_BASE_COST_PER_UNIT` | `2.0` | 计划中未声明成本的单元所使用的回退成本。 |
| `max_budget_tokens` | `GOLDENBOY_MAX_BUDGET_TOKENS` | `100000` | 将原始 token 估算值换算为百分比时,视为"预算 100%"的 token 数。 |
| `stale_after_seconds` | `GOLDENBOY_STALE_AFTER_SECONDS` | `300.0` | 刷新后的提供方读数保持 `ESTIMATED` 多久后才老化为 `STALE`。 |

超出范围的值、格式错误的 JSON,以及无法解析的 `GOLDENBOY_*` 环境变量都会抛出明确的
`ConfigError`——在 CLI 中表现为一行 `error:` 消息并以 exit `1` 退出,而不是原始的堆栈跟踪。

---

## 🧭 设计原则

- **轻量**——核心安装没有任何必需的第三方运行时依赖;提供方 SDK 和 TypeScript SDK 自身的工具链都是可选的。
- **自适应**——执行行为会随剩余预算变化,*同时*也会随该数字的可信度变化:`STALE` 或 `UNKNOWN` 的读数绝不能产生 `SAFE` 判定。
- **确定性**——相同的输入产生相同的决策。estimator、classifier 和 risk engine 都没有隐藏的随机性;适配器的过期判断由可注入的时钟驱动,因此无需 sleep 即可测试。
- **提供方可选**——`import goldenboy` 从不要求安装 `anthropic` 或 `openai`。
- **智能体优先**——Golden Boy 根据剩余预算决定智能体应该多激进地推进。调用它的智能体依然负责理解并拆解任务。
- **安全失败**——格式错误的配置、损坏的检查点、无效的输入,都只会产生具体、可读的错误和退出码,绝不会产生原始的堆栈跟踪或静默的数据丢失。
- **证据优先于复杂度**——任何地方都没有编造的基准数字、回测结果或历史数据集。`goldenboy replay`/`goldenboy.analytics` 会报告 `N/A`/`NO_DATA`,而不是编造一个基线;参见 [`docs/DATASETS.md`](docs/DATASETS.md) 和 [`ROADMAP.md`](ROADMAP.md) 中明确列出的非目标。

---

## 📦 关于任务拆解

> `plan`/`run`/`analyze` 显示的预估成本是根据实际任务文本和仓库上下文计算出来的——那个数字是
> 真实的。`plan`/`run` 的单元拆解是**示意性的**:它不是 LLM 对你任务的真实拆解。Golden Boy 有意
> 让核心保持无依赖,不参与理解*如何*完成一个任务;真正的任务拆解仍然是调用方智能体的责任
> (参见[设计原则](#-设计原则))。`TaskClassifier` 告诉你这个任务*看起来是什么类型*,
> 而不是如何把它拆成步骤。

---

## ⚠️ 局限性

- 成本估算是启发式的(提示词长度 + 有限的仓库扫描)——不是计费保证,也不是对智能体实际会加载到上下文中内容的建模。
- `TaskClassifier` 是一个确定性的关键词匹配器,不是训练出来的模型——其置信度分数反映的是匹配强度,而非经过校准的概率。目前还没有可用于训练的、带标注的真实世界数据(见 `docs/DATASETS.md`)。
- `goldenboy replay`/`goldenboy.analytics` 在本地记录到至少 10 条真实事件之前都会报告 `N/A`/`NO_DATA`——没有捆绑的数据集来代替这一点。
- 回放的各项指标是基于日志结果的离策略评估(off-policy evaluation):事件记录的结果反映的是 Golden Boy 当时实际做出的决策,而不是当前正在打分的备选策略——这是一种描述性的比较,而非因果层面的保证(见[回放与回测](#-回放与回测))。
- 提供方用量(rate-limit 响应头)可能在两次刷新之间发生 Golden Boy 无法控制的变化;这正是 `STALE` 置信度存在的意义。
- `plan`/`run` 的单元拆解是示意性的,不是真正的任务拆解(见上文)。
- Golden Boy 不会取代调用它的编码智能体自身的判断——它只是为"应该尝试多少"提供参考信息。

---

## ✅ 验证

截至 2026-09-14,Golden Boy v1.1.0 已通过以下验证:

- **186 个 Python 测试**,95% 行覆盖率(`pytest --cov`)——相比 v1.0.0 的 88 个测试/93% 有所提升
- **14 个 TypeScript 测试**(`sdk/typescript` 中的 `npm test`),包含针对实际已安装 CLI 的真实(非模拟)集成测试
- Ruff 和 mypy 均干净通过(mypy 在 1.19.1 和 2.3.1 两个版本下都验证过)
- `pip-audit`:0 个已知漏洞
- Python 3.9–3.13,在 GitHub Actions 上
- 在一个独立、全新的虚拟环境中安装 wheel 和 sdist,并对其实际执行了每一个 CLI 命令(包括新增的)
- 仅核心安装(`pip install goldenboy`)拉取零第三方运行时依赖——通过对全新安装环境运行 `pip list` 现场验证,而不仅仅是口头断言

CI(`.github/workflows/ci.yml`,8 个任务):

| 任务 | 结果 |
|---|---|
| security(pip-audit) | ✓ |
| test(3.9) | ✓ |
| test(3.10) | ✓ |
| test(3.11) | ✓ |
| test(3.12) | ✓ |
| test(3.13) | ✓ |
| build(wheel 安装 + 每个 CLI 命令 + 基准测试合理性检查) | ✓ |
| sdk-typescript(针对已安装 CLI 的真实集成) | ✓ |

---

## 📊 基准测试

在本地测量一次(Apple M1 Pro,macOS arm64,Python 3.13.7,2026-09-13),通过
`goldenboy benchmark` / `scripts/benchmark.py`(同一份实现——见
`goldenboy/core/benchmark.py`)——不属于 CI 的通过/失败门槛(CI 只检查数字是否非负、
estimator 是否具有确定性),也不是任何保证。在依赖这些数字之前,请自行重新运行一遍。

| 操作 | 平均值 | 中位数 | n |
|---|---|---|---|
| `Estimator.estimate_task()`(热身状态,本仓库) | 9.30ms | 8.79ms | 20 |
| `Estimator.estimate_task()` 确定性 | PASS——10 次相同调用中只有 1 种结果 | | 10 |
| `RiskEngine.assess()` | <0.001ms | <0.001ms | 1000 |
| CLI 冷启动(`goldenboy status`) | 93.46ms | 93.33ms | 5 |

`RiskEngine.assess()` 是对已经计算好的值进行的纯算术运算,因此在结构上就是亚微秒级的。
Estimator 的延迟随仓库大小变化(受 `_MAX_SCAN_FILES` / `_MAX_FILE_BYTES` 上限约束),
而非提示词长度。CLI 冷启动主要是 Python 解释器/导入开销——这是你运行任意一个 `goldenboy`
命令时实际感受到的部分。完整方法论、注意事项,以及基于这些数字的 Rust 迁移思路,
见 [`BENCHMARKS.md`](BENCHMARKS.md) 和 [`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md)。

---

## 🗺 路线图

**已发布、已测试、真实可用:**

- ✓ 任务感知的成本估算、自适应执行模式、检查点/延后/恢复、包含 STALE 检测的用量置信度
- ✓ CLI(`plan`/`run`/`status`/`resume`/`doctor`/`analyze`/`validate`/`replay`/`benchmark`/`export`)
- ✓ Anthropic/OpenAI 提供方适配器、Claude Code 技能集成
- ✓ Golden Boy Protocol(带版本号、语言中立)+ TypeScript SDK
- ✓ 任务分类(`TaskClassifier`)+ `DecisionEngine`(附带解释的动作/置信度/原因)
- ✓ 本地历史(`HistoryStore`)+ 数据质量/分析报告
- ✓ 基线策略 + `goldenboy.replay` 回测引擎 + 前向滚动切分

| 方向 | 状态 |
|---|---|
| 一个真实、已填充的回测结果(而非 `N/A`) | 阻塞于真实使用数据的积累——今天无法诚实地产出 |
| 一个学习型的任务分类器/策略 | 研究中——首先需要真实的、带标注的结果数据 |
| 将 `cli.py` 拆分为 `cli/` 包 | 已规划——本周期暂缓(回归风险 vs. 收益;见 `ROADMAP.md`) |
| 针对刻意构造的大型仓库进行基准测试 | 已规划 |
| 更多智能体集成(例如 Codex) | 研究中——仅在有真实、有据可查的用量信号可供依据时才会进行 |

以上任何一项,若没有测试覆盖,都不会被宣称为生产就绪。完整的 Done/Planned/Research 分类,
包括明确的非目标(不做数据库、不做网页仪表盘、不做服务端、不做仓促的 ML 或 Rust),
见 [`ROADMAP.md`](ROADMAP.md)。

---

## 🤝 贡献

欢迎贡献。[`CONTRIBUTING.md`](CONTRIBUTING.md) 中有环境搭建步骤、PR 需要通过的检查
(`pytest`、`ruff`、`mypy`、`python -m build`——均在 CI 中强制执行),以及审查所依据的工程原则:
现有架构优先、根因优先于表症、拒绝虚假的完成度、诚实标注置信度、不在 `GoldenBoyConfig` 之外
硬编码策略数字。

---

## 🛠 开发

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

对于 TypeScript SDK:

```bash
cd sdk/typescript
npm install
npm run typecheck && npm run build && npm test
```

---

## 📚 更多文档

| 文档 | 内容 |
|---|---|
| [`docs/PROTOCOL.md`](docs/PROTOCOL.md) | Golden Boy Protocol 的 schema、版本管理策略,以及为何没有服务端。 |
| [`docs/DATASETS.md`](docs/DATASETS.md) | 数据集/研究现状回顾(SWE-bench、HumanEval、LiveCodeBench、RepoBench、token 消耗相关研究),以及为何它们都无法替代 `HistoryStore`。 |
| [`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md) | 为何 Python 仍是核心、TypeScript 用在哪里,以及未来的 Rust 迁移边界。 |
| [`CHANGELOG.md`](CHANGELOG.md) | 各版本之间的变更内容。 |
| [`ROADMAP.md`](ROADMAP.md) | 完整的 Done / Planned / Research 分类,包括明确的非目标。 |
| [`BENCHMARKS.md`](BENCHMARKS.md) | 已测量的性能数字、方法论,以及尚未测量的内容。 |
| [`SECURITY.md`](SECURITY.md) | 如何处理凭据与本地历史数据,以及如何报告漏洞。 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 环境搭建、检查项,以及审查所依据的工程原则。 |
| [`sdk/typescript/README.md`](sdk/typescript/README.md) | TypeScript SDK 的 API 参考与设计说明。 |

---

## 📄 许可证

[MIT](LICENSE)。

<p align="center">
  ⭐ 如果 Golden Boy 帮你的智能体避免了预算被耗尽,一个 star 能帮助更多人发现它。
</p>
