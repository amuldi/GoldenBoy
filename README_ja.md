<p align="center">
  <a href="README.md">English</a> | <a href="README_zh.md">中文</a> | <b>日本語</b> | <a href="README_ko.md">한국어</a> | <a href="README_ar.md">العربية</a> | <a href="README_es.md">Español</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/amuldi/GoldenBoy/main/assets/golden-boy.png" width="220" alt="Golden Boy">
</p>

<h1 align="center">Golden Boy</h1>
<p align="center"><b>AIエージェント・リソースインテリジェンス — AIの使用量を見当違いの作業に費やさないために。</b></p>

<p align="center">
  <img src="https://github.com/amuldi/GoldenBoy/actions/workflows/ci.yml/badge.svg" alt="CI status">
  <img src="https://img.shields.io/badge/python-3.9--3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9–3.13">
  <img src="https://img.shields.io/badge/coverage-95%25-2ea44f?style=flat-square" alt="Coverage 95%">
  <img src="https://img.shields.io/badge/dependencies-zero-2ea44f?style=flat-square" alt="Zero required dependencies">
  <img src="https://img.shields.io/badge/TypeScript_SDK-node_%3E%3D18-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript SDK, Node >= 18">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#-golden-boyとは">Golden Boyとは</a> &nbsp;&middot;&nbsp;
  <a href="#-実例">実例</a> &nbsp;&middot;&nbsp;
  <a href="#-主な機能">主な機能</a> &nbsp;&middot;&nbsp;
  <a href="#-仕組み">仕組み</a> &nbsp;&middot;&nbsp;
  <a href="#-インストール">インストール</a> &nbsp;&middot;&nbsp;
  <a href="#-cliリファレンス">CLI</a> &nbsp;&middot;&nbsp;
  <a href="#-プロトコル">プロトコル</a> &nbsp;&middot;&nbsp;
  <a href="#-typescript-sdk">TypeScript SDK</a> &nbsp;&middot;&nbsp;
  <a href="#-リプレイとバックテスト">バックテスト</a> &nbsp;&middot;&nbsp;
  <a href="#-検証">検証</a> &nbsp;&middot;&nbsp;
  <a href="#-ロードマップ">ロードマップ</a> &nbsp;&middot;&nbsp;
  <a href="#-コントリビュート">コントリビュート</a>
</p>

> 本ドキュメントは[英語版](README.md)の翻訳です。コードブロック・コマンド・CLI出力・JSONは
> そのまま(英語のまま)コピーして実行できるよう原文を維持しています。訳文と原文に相違がある場合は
> 英語版が優先されます。

---

## 💡 Golden Boyとは?

AIコーディングエージェントは、実際にどれだけ使用量が残っているかに関係なく、すべてのタスクを
同じように扱いがちです。残り予算15%で始まった大きなタスクは、たいてい同じ結末を迎えます——
編集の途中で中断され、何が完了して何が完了していないかの記録も残りません。

**Golden Boy**は、エージェントとその作業の間に立つ意思決定レイヤーです。タスクが*どんな種類*なのかを
見極め、コストを見積もり、残り予算と照らし合わせて確認します——*その予算値がどれだけ信頼できるか*も
含めて——そしてエージェントにどれだけ積極的に進めるべきかを伝えます:実行する、続ける、範囲を縮小する、
仕上げて検証する、あるいは停止してチェックポイントを保存する。すべての提案には信頼度スコアと、
その呼び出しで実際に計算された数値に基づく理由が付きます。Python、CLI、TypeScriptのどこから呼んでも、
同じバージョン管理されたJSON形式([Golden Boy Protocol](#-プロトコル))で返ってきます。

| | |
|---|---|
| ✅ **できること** | タスクの分類、コスト見積もり、予算と信頼度の追跡、アクションの決定(実行/継続/範囲縮小/仕上げ/検証/停止/確認)、先送りした作業のチェックポイント保存、実際に起きたことのローカル記録、その履歴を使った別ポリシーのバックテスト。 |
| 🚫 **できないこと** | タスクをコーディング計画に分解すること、呼び出し元のエージェントを置き換えること、コーディングエージェント/IDE/LLMプロバイダーとして振る舞うこと、サーバーを動かすこと。[設計原則](#-設計原則)と[タスク分解について](#-タスク分解について)を参照。 |

---

## 🧠 実例

```
ユーザー:「認証システムをリファクタリングして、テストを更新して」
```

以下の値はすべて`goldenboy analyze`の実際のライブ出力です——演出ではありません:

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

ここには演出されたシナリオは一切ありません:タスクタイプは`TaskClassifier`がプロンプトテキストを
実際にスキャンして、コストは`Estimator`が今回の実行のリポジトリ+プロンプトを実際にスキャンして、
リスクモードは`RiskEngine`がそのコストと渡されたモック予算を実際に比較して出た結果です。予算や
タスクテキストを変えれば、すべてのフィールドがそれに応じて変わります——`--json`が生成する
正確なJSONは[プロトコル](#-プロトコル)セクションを参照してください。

---

## ✨ 主な機能

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🧠 タスクインテリジェンス</h3>
      <div>
        • 13種類の分類器(バグ修正、リファクタリング、テスト、アーキテクチャ変更など)<br>
        • 決定論的かつ透明——偽の校正済み確率ではなく、ヒューリスティックなマッチ強度スコア<br>
        • 実際のコスト見積もりから導かれる複雑度ラベル(LOW/MEDIUM/HIGH/VERY_HIGH)
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🚦 理由付きの意思決定</h3>
      <div>
        • <b>RUN · CONTINUE · REDUCE_SCOPE · FINISH · VERIFY · STOP · ASK_USER</b><br>
        • すべての決定に信頼度スコアと、実際の数値に基づく理由が付く<br>
        • 安全に行動するには信頼度が低すぎる場合、推測ではなく<code>ASK_USER</code>を返す
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🔋 予算と信頼度の追跡</h3>
      <div>
        • 残り予算をパーセンテージで表示し、<b>EXACT / ESTIMATED / STALE / UNKNOWN</b>の信頼度を付加<br>
        • <code>STALE</code>や<code>UNKNOWN</code>の読み取り値が黙って<code>SAFE</code>を装うことは決してない<br>
        • アダプターの陳腐化は注入可能な時計で判定——決定論的で、テストに<code>sleep()</code>は不要
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>💾 チェックポイントと再開</h3>
      <div>
        • 先送りされた作業は保存され、黙って失われることはない<br>
        • <code>goldenboy resume</code>で直前のチェックポイントから再開<br>
        • チェックポイントのスキーマはバージョン管理——互換性のない将来フォーマットはきれいに失敗する
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>📡 ローカル履歴と分析</h3>
      <div>
        • デコレートされた呼び出しごとにイベントを1件ローカルに追加——生のタスクテキストは記録しない<br>
        • 実データに基づくDataset Qualityレポート(行数、破損/重複/無効の比率)<br>
        • あなた自身の実際の使用状況に基づくコスト/完了率/失敗率の集計
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔁 リプレイとバックテスト</h3>
      <div>
        • 実履歴に対して5つのベースラインポリシーを採点:適合率、再現率、早期停止率<br>
        • ウォークフォワード方式の、リークのない時系列分割<br>
        • イベントが10件未満なら正直に<code>N/A</code>——捏造した表は決して出さない
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🌐 Golden Boy Protocol</h3>
      <div>
        • バージョン管理された、言語中立なJSON決定スキーマがひとつ<br>
        • 厳格な検証——生の<code>KeyError</code>ではなく、具体的なエラーを返す<br>
        • Python、CLI、TypeScriptで同一のペイロード
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔌 エージェント統合</h3>
      <div>
        • <code>budget_aware_execution</code>デコレーターで任意のPython関数をラップ<br>
        • <code>AnthropicAdapter</code> / <code>OpenAIAdapter</code>が実際のレート制限ヘッダーを読み取る<br>
        • TypeScript SDKと、プロンプトレベルの<b>Claude Code</b>スキル
      </div>
    </td>
  </tr>
</table>

---

## 🔄 仕組み

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

| モード | 意味 | エージェントの挙動 |
|---|---|---|
| 🟢 `SAFE` | 見積もりコストより十分に余裕がある | P0〜P4を通常どおり実行 |
| 🟡 `CAUTION` | 十分だが、このタスクが大きな割合を占める | 続行するが保守的に、新たな範囲は開かない |
| 🟠 `LIMITED` | 見積もりコストが使用可能な予算を超える | P0/P1に制限し、何をスキップするか呼び出し元に伝える |
| 🔴 `CRITICAL` | 予算がすでにセーフティマージン以下 | 現在のP0ユニットを完了し、チェックポイントを保存して停止 |

モードは2段階の順序チェックで決まります——予算がすでに枯渇しているか(`safety_margin`以下)→
`CRITICAL`;見積もりコストが使用可能な予算をそもそも超えているか → `LIMITED`——それ以外は
見積もりコストと使用可能予算の比率を、設定可能な`caution_ratio`(デフォルト`0.5`)で判定します。
`STALE`な予算の読み取り値は決して`SAFE`判定を出しません——生の数値がどれだけ余裕があるように
見えても、最低`CAUTION`に格上げされます。`DecisionEngine`は`UNKNOWN`信頼度の予算(一度も
リフレッシュされていないアダプター)にも同じ保守的なルールを、変更されていない`RiskEngine`の
上に明示的な別ポリシーとして適用します——詳細は[`goldenboy/core/risk.py`](goldenboy/core/risk.py)と
[`goldenboy/core/decision_engine.py`](goldenboy/core/decision_engine.py)を参照。

---

## ⚖️ 導入前後の比較

<table>
  <tr>
    <td width="50%" valign="top">
      <b>❌ Golden Boyなし</b>
      <p>エージェントは「認証システム全体をリファクタリングして」という依頼を受けるとすぐに着手し、
      探索/実装/テストの全段階で積極的に消費し続け、予算が尽きるとタスクの途中で中断されます——
      何が完了したかの記録もないまま。</p>
    </td>
    <td width="50%" valign="top">
      <b>✅ Golden Boyあり</b>
      <p>同じ依頼でも、実行範囲が確定する<i>前</i>に分類・コスト見積もり・予算チェックを経ます——
      後から辻褄合わせで出す推測ではなく、実際の信頼度スコアが付いた本物の決定です。実際に何が
      起きたかがローカルに記録されるので、次の似たようなタスクはその恩恵を受けます。</p>
    </td>
  </tr>
</table>

---

## 🎬 デモ

一連の流れ——計画を立て、縮小していく予算に合わせて適応的に実行し、環境を診断します。以下は
すべてこのリポジトリでキャプチャした実際の出力です(演出や省略はありません):

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

実行中に予算がセーフティマージンを下回りました——エグゼキューターは現在のユニットを完了し、
残りをチェックポイントとして保存してから、消費を続ける代わりに停止しました。

</details>

<details>
<summary><b>$ goldenboy validate</b>(新規インストール、履歴なし)</summary>

```
--- Golden Boy Validate ---
Config:     OK — safety_margin=3.0, caution_ratio=0.5, base_cost_per_unit=2.0, max_budget_tokens=100000, stale_after_seconds=300.0
Checkpoint: OK — none present

Dataset Quality
Rows:                 0
Status: NO_DATA — insufficient validated data (no history recorded yet).
```

まだ存在しないデータを埋めるために数値を捏造することはありません——
[履歴と分析](#-履歴と分析)を参照。

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

APIキーは存在の有無だけが報告され、値そのものは決して表示されません——`doctor`、`status`、
`validate`のすべての診断コマンドは`--json`にも対応しています。

</details>

---

## 🚀 インストール

```bash
pip install goldenboy
goldenboy --help
```

またはソースから:

```bash
git clone https://github.com/amuldi/GoldenBoy.git
cd GoldenBoy
pip install -e .
```

コアインストールには**必須のサードパーティ依存はありません**。オプションのextraが特定の機能を
追加します:

```bash
pip install "goldenboy[tiktoken]"   # 正確なトークン数(なければより粗いヒューリスティックにフォールバック)
pip install "goldenboy[anthropic]"  # AnthropicAdapter
pip install "goldenboy[openai]"     # OpenAIAdapter
```

TypeScriptのエージェント/ツールはCLIを直接呼ぶ代わりに[`sdk/typescript`](sdk/typescript)を
使えます——[TypeScript SDK](#-typescript-sdk)を参照。

---

## ⚡ クイックスタート

```bash
goldenboy analyze "Refactor the authentication system"   # 完全な提案:タイプ、リスク、アクション、理由
goldenboy status                                          # 現在の予算と保留中のチェックポイント
goldenboy validate                                         # 設定 + チェックポイント + ローカルデータ品質レポート
goldenboy doctor                                            # 環境、設定、チェックポイントの診断
```

---

## 🖥 CLIリファレンス

| コマンド | 目的 |
|---|---|
| `goldenboy analyze <task>` | 完全なタスクインテリジェンス提案:タイプ、複雑度、リスク、アクション、信頼度、理由。`--progress 0.0-1.0`、`--json`。 |
| `goldenboy plan <task>` | タスクテキスト+リポジトリサイズから実コストを見積もり、結果のリスクモードを表示。 |
| `goldenboy run <task>` | モック予算に対して、予算を意識したデモ計画を適応的に実行。 |
| `goldenboy status` | 現在の予算と保留中のチェックポイントを確認。`--json`。 |
| `goldenboy resume` | 直前のチェックポイントから実行を再開。 |
| `goldenboy doctor` | Pythonバージョン、オプション依存、プロバイダーキーの設定、設定ファイル、チェックポイントを診断。`--json`。 |
| `goldenboy validate` | 設定+チェックポイント+ローカル履歴のデータ品質を検証。実際の問題があればexit 1。`--json`。 |
| `goldenboy replay` | ローカル(または`--dataset PATH`)の履歴に対してベースラインポリシーをバックテスト。`--json`。 |
| `goldenboy benchmark` | このマシン上で今すぐ、estimator/risk-engine/CLI起動のレイテンシを測定。`--json`。 |
| `goldenboy export` | 設定+チェックポイント+履歴を、再現可能なJSONドキュメント1つとしてエクスポート。`--output PATH`。 |

モック予算を使うコマンドには`--budget`を付けて開始予算を制御でき、[デモ](#-デモ)で示した
ユニットごとの内部決定ログを見るにはサブコマンドの前に`-v`/`--verbose`を付けてください。

---

## 🐍 Python統合

```python
from goldenboy import AdaptiveExecutor, MockProvider, budget_aware_execution, Priority

provider = MockProvider(initial_percentage=40.0)

@budget_aware_execution(provider, "1", "Refactor the auth module", Priority.P1)
def refactor_auth():
    ...  # 実際の作業はここに書く——呼び出すかどうかはGolden Boyが決める

refactor_auth()
```

`budget_aware_execution`はプロバイダーに予算/モードの判定を求め、モードが許可した場合にのみ
あなたの関数を呼び出します——プロバイダー自体を呼び出すことはありません。すべての呼び出しは
ローカルにイベントを1件記録します(生のタスクテキストは記録しません)——
[履歴と分析](#-履歴と分析)を参照。公開APIの全体は
[`goldenboy/__init__.py`](goldenboy/__init__.py)にあります。そこに載っていないものも各自の
サブモジュール経由でアクセス可能ですが、トップレベルAPIと同等の安定性保証の対象ではありません。

理由付きの完全な決定APIが必要な場合は、`DecisionEngine`を直接使ってください:

```python
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.decision_engine import DecisionEngine

decision = DecisionEngine().decide("Refactor the auth module", MockProvider(initial_percentage=15))
print(decision.action, decision.confidence, decision.reason)
```

---

## 🌐 プロトコル

Golden Boyが生成するすべての決定は——Python、CLI、TypeScriptのどこからでも——ひとつの
バージョン管理された、言語中立なJSON形式です:**Golden Boy Protocol**。完全なスキーマ、
バージョン管理ポリシー、サーバーがない理由は[`docs/PROTOCOL.md`](docs/PROTOCOL.md)に
あります。

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

`goldenboy/protocol.py`の`GoldenBoyDecision.from_dict`/`from_json`は、この方式で構築された
あらゆるペイロードを厳格に検証します——フィールドの欠落や互換性のないメジャーバージョンの場合、
生の`KeyError`ではなく`ProtocolError`を送出します。`sdk/typescript/src/validate.ts`は
TypeScript側で全く同じ契約を強制します。

---

## 📘 TypeScript SDK

[`sdk/typescript`](sdk/typescript)は薄いクライアントであり、二つ目の実装ではありません——
実際の`goldenboy` CLIを起動し、その`--json`出力を上記と同じプロトコル検証でパースします。
ランタイム依存はゼロ。テストはNode組み込みのテストランナーで実行され、実際のCLIに対する
本物の(モックなしの)統合テストも含まれます。

```ts
import { GoldenBoyClient } from "@goldenboy/sdk";

const client = new GoldenBoyClient(); // PATH上の`goldenboy`を使用
const decision = await client.analyze("Refactor the authentication system", { budget: 6 });

console.log(decision.action);       // "reduce_scope"
console.log(decision.confidence);   // 0.774
console.log(decision.reason);       // Python/CLI出力と同じ実データから構築される
```

```bash
cd sdk/typescript
npm install && npm run build && npm test   # 14件のテスト、実際のCLI統合を含む
```

完全なAPIと設計上のメモは[`sdk/typescript/README.md`](sdk/typescript/README.md)を参照。

---

## 📡 履歴と分析

`budget_aware_execution`でデコレートされた呼び出しごとに、ローカルの追記専用ログ
(`.goldenboy/history.jsonl`、gitignore済み——チェックポイントファイルと同じ慣例)に
イベントが1件追加されます。イベントはタスクの生テキストを決して保存せず、その長さと
切り詰められたSHA-256ハッシュのみを保存します
([`goldenboy/core/history.py`](goldenboy/core/history.py)と[`SECURITY.md`](SECURITY.md)を参照)。

```bash
goldenboy validate   # Dataset Quality: 行数、破損/重複/無効値の比率、GOOD/ACCEPTABLE/POOR/NO_DATA
goldenboy export     # 設定+チェックポイント+履歴(品質レポート、分析、イベント)を1つのJSON文書に
```

```python
from goldenboy.analytics import data_quality
from goldenboy.analytics.engine import analyze
from goldenboy.core.history import HistoryStore

store = HistoryStore()
print(data_quality.validate(store).render())   # 実際のレポート——何も記録されていなければ"NO_DATA"
print(analyze(store).render())                  # コスト/完了率/失敗率の集計、なければ"N/A"
```

新規インストール状態では、どちらも正直に0行と報告します——上の[デモ](#-デモ)の`validate`例を
参照。ここにあるものはどれも「解除待ち」のプレースホルダーではありません:あなたのエージェントが
実際にデコレートされたタスクを実行した瞬間から、本物の集計を生成し始める、実際に動くコードです。

---

## 🔁 リプレイとバックテスト

`goldenboy.replay`は一つの問いに答えます:*別のリソース配分ポリシーだったら、これらの実際の
過去のタスクに対してより良い決定を下せたか?*これは**AIエージェントのリソース配分バックテスト**
であり、金融のバックテストではありません。5つのポリシーが同じ条件下で比較されます——2つの
固定閾値ベースライン(15%/20%)、複雑度のみのヒューリスティック、使用量のみのヒューリスティック、
そして実際の変更されていない`RiskEngine`をラップする`GoldenBoyPolicy`——
`goldenboy.core.policies`と`goldenboy.replay.engine`によって実現されます。

```bash
$ goldenboy replay
Backtest: 0 event(s) available (need at least 10).
N/A — insufficient validated data.
```

これが新規インストール状態での実際の、現在の出力です——そしてそうあるべきです。実利用の代わりに
なるバンドル済みデータセットや合成データセットは存在しません。`docs/DATASETS.md`には、
SWE-benchのような公開ベンチマークがなぜこれの代わりにならないか(コード生成の正しさを測るもので
あり、予算を意識したリソース決定を測るものではないため)が文書化されています。あなた自身の
`.goldenboy/history.jsonl`に少なくとも10件のイベントが溜まれば、`goldenboy replay`は実際に
すべてのポリシーを採点します:

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

`walk_forward_folds()`は、フォールドの境界をまたぐリークなしにイベントを時系列で分割します——
将来の学習型ポリシーのために、すでにテスト済みで準備が整ったインフラです(現在の5つのポリシーは
すべて固定/決定論的なので、分割してもまだスコアは変わりません。詳細は
`goldenboy/replay/engine.py`のモジュールdocstringを参照)。レポートはどんな数値を示すときも、
必ず自身の方法論的な限界を併記します——[`goldenboy/replay/engine.py`](goldenboy/replay/engine.py)
を参照。

---

## 🔌 統合

プロバイダーアダプターは使用量を報告するだけで、あなたのコードを実行することは決してありません。
実際の作業は常に上記の`budget_aware_execution`デコレーター経由で実行されます。

| プロバイダー | 読み取る内容 | 備考 |
|---|---|---|
| `MockProvider` | 合成のインメモリなパーセンテージ | デモとテスト用——ネットワーク呼び出しなし。 |
| `AnthropicAdapter` | `anthropic-ratelimit-tokens-remaining` / `-limit`レスポンスヘッダー | `goldenboy[anthropic]`が必要。組織の*共有*レート制限を反映し、この呼び出し単体のものではない。 |
| `OpenAIAdapter` | `x-ratelimit-remaining-tokens` / `-limit-tokens`レスポンスヘッダー | `goldenboy[openai]`が必要。上記と同じ共有制限の注意点。 |
| Claude Codeスキル | Claude Codeがコンテキストに注入する`<total_tokens>`の値 | Pythonプロセス不要——下記参照。 |
| TypeScript SDK | 子プロセスとして実行した`goldenboy` CLIの`--json`出力 | HTTPサーバーなし——[プロトコル](#-プロトコル)を参照。 |

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

両方のアダプターは、明示的な`refresh_usage()`呼び出しを通じてのみ読み取り値を更新し、
注入可能な時計を使ってそれ以降どれだけ時間が経ったかを追跡します——
`stale_after_seconds`(デフォルト300秒)を過ぎると、信頼度は自動的に`ESTIMATED`から
`STALE`へと老化します。最初のリフレッシュ前は信頼度が`UNKNOWN`です——これを保守的に扱うのは
`RiskEngine`自体ではなく`DecisionEngine`で、扱い方は`STALE`と同じです。

**Claude Code**はプロンプトレベルの統合を使います:
[`skills/goldenboy/SKILL.md`](skills/goldenboy/SKILL.md)は、LLMエージェントにClaude Codeが
コンテキストに直接注入する残り使用量の値を読み取り、自身の実行モードを推論するよう教えます。
`goldenboy.core.risk.ExecutionMode`と全く同じ`SAFE`/`CAUTION`/`LIMITED`/`CRITICAL`の
語彙を使いますが——コードを共有するのではなく手作業で同期しています。片方はPythonで、
もう片方はプロンプトだからです。

---

## 🏗 アーキテクチャ

<details>
<summary><b>パッケージツリーを展開</b></summary>

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

## ⚙️ 設定

すべてのポリシー閾値は`GoldenBoyConfig`にあり、以下の優先順位で上書きされます:

```
explicit constructor arg  >  GOLDENBOY_* environment variable  >  .goldenboy/config.json  >  default
```

| フィールド | 環境変数 | デフォルト | 意味 |
|---|---|---|---|
| `safety_margin` | `GOLDENBOY_SAFETY_MARGIN` | `3.0` | 報告された残り予算が枯渇とみなされるまでに確保しておくパーセントポイント。 |
| `caution_ratio` | `GOLDENBOY_CAUTION_RATIO` | `0.5` | リスクがSAFEからCAUTIONに移行する、見積もりコスト/使用可能予算の比率。 |
| `base_cost_per_unit` | `GOLDENBOY_BASE_COST_PER_UNIT` | `2.0` | 計画のユニットが明示的なコストを宣言していない場合のフォールバックコスト。 |
| `max_budget_tokens` | `GOLDENBOY_MAX_BUDGET_TOKENS` | `100000` | 生のトークン見積もりをパーセンテージに変換する際、「予算の100%」とみなすトークン数。 |
| `stale_after_seconds` | `GOLDENBOY_STALE_AFTER_SECONDS` | `300.0` | リフレッシュされたプロバイダーの読み取り値が`ESTIMATED`のままでいる時間。これを過ぎると`STALE`に老化する。 |

範囲外の値、不正なJSON、パースできない`GOLDENBOY_*`環境変数は、すべて明確な`ConfigError`を
発生させます——CLIでは生のスタックトレースではなく、1行の`error:`メッセージとexit `1`として
表れます。

---

## 🧭 設計原則

- **軽量**——コアインストールには必須のサードパーティランタイム依存がなく、プロバイダーSDKとTypeScript SDK自体のツールチェーンはオプションです。
- **適応的**——実行の挙動は残り予算に応じて、*かつ*その数値をどれだけ信頼できるかに応じて変わります:`STALE`または`UNKNOWN`の読み取り値は`SAFE`判定を出すことができません。
- **決定論的**——同一の入力は同一の決定を生みます。estimator、classifier、risk engineには隠れたランダム性がなく、アダプターの陳腐化は注入可能な時計で駆動されるため、sleepなしでテスト可能です。
- **プロバイダーはオプション**——`import goldenboy`は`anthropic`や`openai`のインストールを決して要求しません。
- **エージェントファースト**——Golden Boyは残り予算に基づき、エージェントがどれだけ積極的に進めるべきかを決めます。呼び出すエージェントは、タスクを理解し分解する責任を引き続き負います。
- **安全に失敗する**——不正な設定、破損したチェックポイント、無効な入力は、具体的で人間が読めるエラーと終了コードだけを生成し、生のトレースバックや静かなデータ損失を決して生みません。
- **複雑さより証拠**——ベンチマーク数値、バックテスト結果、履歴データセットのいずれにおいても、捏造はどこにもありません。`goldenboy replay`/`goldenboy.analytics`は基準を作り出す代わりに`N/A`/`NO_DATA`を報告します。[`docs/DATASETS.md`](docs/DATASETS.md)と[`ROADMAP.md`](ROADMAP.md)の明示的な非目標も参照。

---

## 📦 タスク分解について

> `plan`/`run`/`analyze`が示す見積もりコストは、実際のタスクテキストとリポジトリのコンテキストから
> 計算されています——その数値は本物です。`plan`/`run`のユニット内訳は**例示用**です:あなたの
> タスクをLLMが実際に分解した結果ではありません。Golden Boyは意図的にコアを依存関係フリーに保ち、
> タスクを*どうやって*進めるかを理解する領域には関与しません。実際のタスク分解は引き続き呼び出し元
> エージェントの責任です([設計原則](#-設計原則)を参照)。`TaskClassifier`はこのタスクが
> *どんな種類*に見えるかを教えてくれるだけで、どうステップに分けるかは教えてくれません。

---

## ⚠️ 制限事項

- コスト見積もりはヒューリスティックです(プロンプトの長さ+限定的なリポジトリスキャン)——課金の保証ではなく、エージェントが実際にコンテキストへロードする内容のモデルでもありません。
- `TaskClassifier`は決定論的なキーワードマッチャーであり、訓練されたモデルではありません——その信頼度スコアはマッチの強さを反映するものであり、校正済みの確率ではありません。学習に使えるラベル付きの実世界データはまだ存在しません(`docs/DATASETS.md`を参照)。
- `goldenboy replay`/`goldenboy.analytics`は、ローカルに実際のイベントが少なくとも10件記録されるまで`N/A`/`NO_DATA`を報告します——それに代わるバンドル済みデータセットはありません。
- リプレイの各指標は、ログに記録された結果からのオフポリシー評価です:イベントに記録された結果は、Golden Boyがその時点で実際に下した決定を反映するものであり、現在採点中の代替ポリシーの結果ではありません——因果的な保証ではなく、記述的な比較です([リプレイとバックテスト](#-リプレイとバックテスト)を参照)。
- プロバイダーの使用量(レート制限ヘッダー)は、リフレッシュの間にGolden Boyの制御が及ばない範囲で変化する可能性があります。これこそが`STALE`信頼度が存在する理由です。
- `plan`/`run`のユニット内訳は例示用であり、タスク分解ではありません(上記参照)。
- Golden Boyは、呼び出し元のコーディングエージェント自身の判断を置き換えることはありません——どれだけ試みるべきかの情報を提供するだけです。

---

## ✅ 検証

Golden Boy v1.1.0は、2026-09-14時点で以下により検証されています:

- **Pythonテスト186件**、行カバレッジ95%(`pytest --cov`)——v1.0.0時点の88件/93%から増加
- **TypeScriptテスト14件**(`sdk/typescript`での`npm test`)、実際にインストールされたCLIに対する本物の(モックなしの)統合テストを含む
- Ruffとmypyともにクリーン(mypyは1.19.1と2.3.1の両方で確認済み)
- `pip-audit`:既知の脆弱性0件
- Python 3.9〜3.13、GitHub Actions上で
- 独立した新しい仮想環境にwheelとsdistをインストールし、新しいものを含むすべてのCLIコマンドを実際に実行して確認
- コアのみのインストール(`pip install goldenboy`)がサードパーティのランタイム依存をゼロにしていること——単なる主張ではなく、クリーンな環境で`pip list`を実行してライブに検証

CI(`.github/workflows/ci.yml`、8ジョブ):

| ジョブ | 結果 |
|---|---|
| security(pip-audit) | ✓ |
| test(3.9) | ✓ |
| test(3.10) | ✓ |
| test(3.11) | ✓ |
| test(3.12) | ✓ |
| test(3.13) | ✓ |
| build(wheelインストール+すべてのCLIコマンド+ベンチマークの健全性チェック) | ✓ |
| sdk-typescript(インストールされたCLIに対する本物の統合) | ✓ |

---

## 📊 ベンチマーク

一度、ローカルで測定(Apple M1 Pro、macOS arm64、Python 3.13.7、2026-09-13)、
`goldenboy benchmark` / `scripts/benchmark.py`経由(実装はひとつだけ——
`goldenboy/core/benchmark.py`を参照)——CIの合否ゲートの一部ではなく(CIは数値が非負であることと
estimatorが決定論的であることだけを確認します)、保証でもありません。この数値に何かを依存させる
前に、自分自身で再実行してください。

| 操作 | 平均 | 中央値 | n |
|---|---|---|---|
| `Estimator.estimate_task()`(ウォーム、このリポジトリ) | 9.30ms | 8.79ms | 20 |
| `Estimator.estimate_task()`の決定論性 | PASS——同一の呼び出し10回中、結果は1種類 | | 10 |
| `RiskEngine.assess()` | <0.001ms | <0.001ms | 1000 |
| CLIコールドスタート(`goldenboy status`) | 93.46ms | 93.33ms | 5 |

`RiskEngine.assess()`はすでに計算済みの値に対する純粋な算術演算なので、構造的にサブマイクロ秒
単位です。Estimatorのレイテンシはリポジトリサイズに応じて変わります(`_MAX_SCAN_FILES` /
`_MAX_FILE_BYTES`の上限で制限)が、プロンプトの長さには依存しません。CLIコールドスタートは
主にPythonインタープリタ/インポートのオーバーヘッドです——`goldenboy`コマンドを1つ実行する際に
実際に体感する部分です。完全な方法論、注意事項、そしてこれらの数値に基づくRust移行の論理は
[`BENCHMARKS.md`](BENCHMARKS.md)と[`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md)に
あります。

---

## 🗺 ロードマップ

**出荷済み、テスト済み、本物:**

- ✓ タスクを意識したコスト見積もり、適応的な実行モード、チェックポイント/先送り/再開、STALE検出を含む使用量信頼度
- ✓ CLI(`plan`/`run`/`status`/`resume`/`doctor`/`analyze`/`validate`/`replay`/`benchmark`/`export`)
- ✓ Anthropic/OpenAIプロバイダーアダプター、Claude Codeスキル統合
- ✓ Golden Boy Protocol(バージョン管理、言語中立)+ TypeScript SDK
- ✓ タスク分類(`TaskClassifier`)+ `DecisionEngine`(理由付きのアクション/信頼度/理由)
- ✓ ローカル履歴(`HistoryStore`)+ データ品質/分析レポート
- ✓ ベースラインポリシー + `goldenboy.replay`バックテストエンジン + ウォークフォワード分割

| 方向性 | ステータス |
|---|---|
| 実際に値が入ったバックテスト結果(`N/A`ではなく) | 実際の使用データが蓄積されるまで保留——今日は正直に生成できない |
| 学習型のタスク分類器/ポリシー | リサーチ中——まず実際のラベル付き結果データが必要 |
| `cli.py`を`cli/`パッケージに分割 | 計画済み——今サイクルは見送り(回帰リスク対効果;`ROADMAP.md`参照) |
| 意図的に大きな合成リポジトリでのベンチマーク | 計画済み |
| 追加のエージェント統合(Codexなど) | リサーチ中——依拠できる実際の、文書化された使用量シグナルがある場合のみ |

上記のいずれも、テストでカバーされていない限りプロダクション対応とは主張しません。
Done/Planned/Researchの完全な内訳、明示的な非目標(データベースなし、Webダッシュボードなし、
サーバーなし、時期尚早なMLやRustなし)を含む詳細は[`ROADMAP.md`](ROADMAP.md)にあります。

---

## 🤝 コントリビュート

コントリビュートを歓迎します。[`CONTRIBUTING.md`](CONTRIBUTING.md)にセットアップ手順、
PRが通過すべきチェック(`pytest`、`ruff`、`mypy`、`python -m build`——すべてCIで強制)、
そしてレビューが依拠するエンジニアリング原則(既存アーキテクチャ優先、症状より根本原因、
偽の完成度を作らない、信頼度を正直に示す、`GoldenBoyConfig`の外にポリシー数値を
ハードコードしない)があります。

---

## 🛠 開発

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

TypeScript SDKの場合:

```bash
cd sdk/typescript
npm install
npm run typecheck && npm run build && npm test
```

---

## 📚 その他のドキュメント

| ドキュメント | 内容 |
|---|---|
| [`docs/PROTOCOL.md`](docs/PROTOCOL.md) | Golden Boy Protocolのスキーマ、バージョン管理ポリシー、サーバーがない理由。 |
| [`docs/DATASETS.md`](docs/DATASETS.md) | データセット/リサーチ動向のレビュー(SWE-bench、HumanEval、LiveCodeBench、RepoBench、トークン消費に関するリサーチ)と、それらがなぜ`HistoryStore`の代わりにならないか。 |
| [`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md) | なぜPythonがコアであり続けるのか、TypeScriptはどこで使われているのか、将来のRust移行の境界線。 |
| [`CHANGELOG.md`](CHANGELOG.md) | リリースごとの変更内容。 |
| [`ROADMAP.md`](ROADMAP.md) | Done / Planned / Researchの完全な内訳、明示的な非目標を含む。 |
| [`BENCHMARKS.md`](BENCHMARKS.md) | 測定済みのパフォーマンス数値、方法論、まだ測定していないもの。 |
| [`SECURITY.md`](SECURITY.md) | 認証情報とローカル履歴の扱い方、脆弱性の報告方法。 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | セットアップ、チェック項目、レビューが依拠するエンジニアリング原則。 |
| [`sdk/typescript/README.md`](sdk/typescript/README.md) | TypeScript SDKのAPIリファレンスと設計上のメモ。 |

---

## 📄 ライセンス

[MIT](LICENSE)。

<p align="center">
  ⭐ Golden Boyがあなたのエージェントを予算切れから救ってくれたなら、スターがより多くの人に見つけてもらう助けになります。
</p>
