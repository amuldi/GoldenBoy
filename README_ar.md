<p align="center">
  <a href="README.md">English</a> | <a href="README_zh.md">中文</a> | <a href="README_ja.md">日本語</a> | <a href="README_ko.md">한국어</a> | <b>العربية</b> | <a href="README_es.md">Español</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/amuldi/GoldenBoy/main/assets/golden-boy.png" width="220" alt="Golden Boy">
</p>

<h1 align="center">Golden Boy</h1>
<p align="center"><b>ذكاء موارد لوكلاء الذكاء الاصطناعي — لا تُنفق ميزانية الذكاء الاصطناعي على العمل الخاطئ.</b></p>

<p align="center">
  <img src="https://github.com/amuldi/GoldenBoy/actions/workflows/ci.yml/badge.svg" alt="CI status">
  <img src="https://img.shields.io/badge/python-3.9--3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9–3.13">
  <img src="https://img.shields.io/badge/coverage-95%25-2ea44f?style=flat-square" alt="Coverage 95%">
  <img src="https://img.shields.io/badge/dependencies-zero-2ea44f?style=flat-square" alt="Zero required dependencies">
  <img src="https://img.shields.io/badge/TypeScript_SDK-node_%3E%3D18-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript SDK, Node >= 18">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#-ما-هو-golden-boy">ما هو</a> &nbsp;&middot;&nbsp;
  <a href="#-مثال-واقعي">مثال واقعي</a> &nbsp;&middot;&nbsp;
  <a href="#-القدرات-الأساسية">القدرات الأساسية</a> &nbsp;&middot;&nbsp;
  <a href="#-كيف-يعمل">كيف يعمل</a> &nbsp;&middot;&nbsp;
  <a href="#-التثبيت">التثبيت</a> &nbsp;&middot;&nbsp;
  <a href="#-مرجع-cli">CLI</a> &nbsp;&middot;&nbsp;
  <a href="#-البروتوكول">البروتوكول</a> &nbsp;&middot;&nbsp;
  <a href="#-حزمة-typescript-sdk">حزمة TypeScript</a> &nbsp;&middot;&nbsp;
  <a href="#-إعادة-التشغيل-والاختبار-الرجعي">الاختبار الرجعي</a> &nbsp;&middot;&nbsp;
  <a href="#-التحقق">التحقق</a> &nbsp;&middot;&nbsp;
  <a href="#-خارطة-الطريق">خارطة الطريق</a> &nbsp;&middot;&nbsp;
  <a href="#-المساهمة">المساهمة</a>
</p>

> هذا المستند هو ترجمة لـ[النسخة الإنجليزية](README.md). تم الإبقاء على كتل الأكواد والأوامر
> ومخرجات CLI وJSON كما هي (بالإنجليزية) حتى يمكن نسخها وتشغيلها كما هي مباشرة. عند وجود اختلاف
> بين الترجمة والنص الأصلي، تكون النسخة الإنجليزية هي المرجع.

---

## 💡 ما هو Golden Boy؟

تميل وكلاء البرمجة المعتمدة على الذكاء الاصطناعي إلى التعامل مع كل مهمة بنفس الطريقة، بغض النظر
عن مقدار الاستخدام المتبقي فعليًا. غالبًا ما تنتهي مهمة كبيرة بدأت بميزانية متبقية 15% بنفس
الطريقة: تتوقف في منتصف التعديل، دون أي سجل لما تم إنجازه وما لم يتم.

**Golden Boy** هي طبقة قرار تقف بين الوكيل وعمله: تحدد *نوع* هذه المهمة، وتقدّر تكلفتها، وتقارنها
بالميزانية المتبقية — *ومدى موثوقية تلك القراءة أصلًا* — ثم تخبر الوكيل بمدى الجرأة التي يجب أن
يتقدم بها: تنفيذها، الاستمرار، تقليص النطاق، الإنهاء والتحقق، أو التوقف وحفظ نقطة تفتيش. كل توصية
تأتي مع درجة ثقة وسبب مبني على الأرقام الفعلية المحسوبة في تلك الاستدعاء، بنفس صيغة JSON المُصدَّرة
([بروتوكول Golden Boy](#-البروتوكول)) سواء استدعيتها من Python أو CLI أو TypeScript.

| | |
|---|---|
| ✅ **ما تفعله** | تصنيف المهمة، تقدير تكلفتها، تتبع الميزانية + الثقة، تحديد إجراء (تشغيل/استمرار/تقليص النطاق/إنهاء/تحقق/توقف/سؤال)، حفظ نقطة تفتيش للعمل المؤجل، تسجيل ما حدث محليًا، والسماح لك باختبار سياسات بديلة رجعيًا مقابل هذا السجل. |
| 🚫 **ما لا تفعله** | تفكيك مهمة إلى خطة برمجية، أو استبدال الوكيل المستدعي، أو العمل كوكيل برمجي/بيئة تطوير/مزوّد نماذج لغوية، أو تشغيل خادم. راجع [مبادئ التصميم](#-مبادئ-التصميم) و[حول تفكيك المهام](#-حول-تفكيك-المهام). |

---

## 🧠 مثال واقعي

```
المستخدم: "أعد هيكلة نظام المصادقة وحدّث الاختبارات."
```

كل قيمة أدناه هي مخرجات حقيقية ومباشرة من `goldenboy analyze` — وليست نموذجًا وهميًا:

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

لا شيء هنا سيناريو مُعدّ مسبقًا: نوع المهمة جاء من `TaskClassifier` الذي يفحص نص التعليمة فعليًا،
والتكلفة من `Estimator` الذي يفحص فعليًا مستودع الكود + التعليمة في هذا التشغيل، ووضع الخطورة من
`RiskEngine` الذي يقارن فعليًا تلك التكلفة بالميزانية الوهمية التي مررتها. غيّر الميزانية أو نص
المهمة وستتغير كل الحقول تبعًا لذلك — راجع [البروتوكول](#-البروتوكول) لمعرفة صيغة JSON الدقيقة
التي تنتج مع `--json`.

---

## ✨ القدرات الأساسية

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🧠 ذكاء المهام</h3>
      <div>
        • مصنّف بـ13 نوعًا (إصلاح خلل، إعادة هيكلة، اختبار، تغيير معماري، …)<br>
        • حتمي وشفاف — درجة قوة تطابق استدلالية، وليست احتمالًا معايرًا وهميًا أبدًا<br>
        • تصنيف التعقيد (LOW/MEDIUM/HIGH/VERY_HIGH) مستمَد من تقدير التكلفة الفعلي
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🚦 قرارات مُبرَّرة</h3>
      <div>
        • <b>RUN · CONTINUE · REDUCE_SCOPE · FINISH · VERIFY · STOP · ASK_USER</b><br>
        • كل قرار يأتي مع درجة ثقة وسبب مبني على أرقام حقيقية<br>
        • عندما تكون الثقة منخفضة جدًا للتصرف بأمان ← <code>ASK_USER</code> بدلًا من التخمين
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🔋 تتبع الميزانية والثقة</h3>
      <div>
        • الميزانية المتبقية كنسبة مئوية، مع مستوى ثقة <b>EXACT / ESTIMATED / STALE / UNKNOWN</b><br>
        • قراءة <code>STALE</code> أو <code>UNKNOWN</code> لا يمكن أبدًا أن تتنكر بصمت كـ<code>SAFE</code><br>
        • قِدَم المحوّل يُحدَّد بساعة قابلة للحقن — حتمي، بلا <code>sleep()</code> في الاختبارات
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>💾 نقاط التفتيش والاستئناف</h3>
      <div>
        • العمل المؤجل يُحفظ، ولا يُفقد بصمت أبدًا<br>
        • <code>goldenboy resume</code> يستأنف من آخر نقطة تفتيش<br>
        • مخطط نقطة التفتيش مُصدَّر — أي صيغة مستقبلية غير متوافقة تفشل بشكل نظيف
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>📡 السجل والتحليلات المحلية</h3>
      <div>
        • كل استدعاء مُزخرف يضيف حدثًا واحدًا محليًا — لا يُسجَّل أبدًا نص المهمة الخام<br>
        • تقرير حقيقي عن جودة البيانات (عدد الصفوف، نسب التلف/التكرار/عدم الصلاحية)<br>
        • تجميعات للتكلفة/نسبة الإنجاز/نسبة الفشل مبنية على استخدامك الفعلي
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔁 إعادة التشغيل والاختبار الرجعي</h3>
      <div>
        • 5 سياسات مرجعية تُقيَّم مقابل السجل الحقيقي: الدقة، الاستدعاء، معدل التوقف المبكر<br>
        • تقسيم زمني تدريجي (walk-forward) بلا أي تسرّب للبيانات<br>
        • <code>N/A</code> صادقة عند وجود أقل من 10 أحداث — لا جداول مُختلَقة أبدًا
      </div>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🌐 بروتوكول Golden Boy</h3>
      <div>
        • مخطط JSON واحد للقرار، مُصدَّر ومحايد لغويًا<br>
        • تحقق صارم — خطأ محدد، وليس <code>KeyError</code> خامًا أبدًا<br>
        • نفس الحمولة من Python وCLI وTypeScript
      </div>
    </td>
    <td width="50%" valign="top">
      <h3>🔌 تكاملات الوكلاء</h3>
      <div>
        • مُزخرِف <code>budget_aware_execution</code> يُغلّف أي دالة Python<br>
        • <code>AnthropicAdapter</code> / <code>OpenAIAdapter</code> يقرآن ترويسات حد المعدل الحقيقية<br>
        • حزمة TypeScript ومهارة على مستوى التعليمات لـ<b>Claude Code</b>
      </div>
    </td>
  </tr>
</table>

---

## 🔄 كيف يعمل

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

| الوضع | المعنى | سلوك الوكيل |
|---|---|---|
| 🟢 `SAFE` | أعلى بكثير من التكلفة المقدّرة | تنفيذ P0–P4 بشكل طبيعي |
| 🟡 `CAUTION` | كافٍ، لكن المهمة تستهلك حصة كبيرة | الاستمرار، لكن بحذر وبدون فتح نطاق جديد |
| 🟠 `LIMITED` | التكلفة المقدّرة تتجاوز الميزانية القابلة للاستخدام | التقييد بـP0/P1، وإبلاغ المستدعي بما يتم تخطّيه |
| 🔴 `CRITICAL` | الميزانية بالفعل عند/دون هامش الأمان | إنهاء وحدة P0 الحالية، حفظ نقطة تفتيش، التوقف |

يتم تحديد الوضع عبر فحصين متسلسلين — هل الميزانية مستنفدة بالفعل (دون `safety_margin`)؟ ←
`CRITICAL`؛ هل تتجاوز التكلفة المقدّرة كل ما هو قابل للاستخدام أصلًا؟ ← `LIMITED` — وإلا فبنسبة
التكلفة المقدّرة إلى الميزانية القابلة للاستخدام، مقسومة عند `caution_ratio` قابل للتهيئة (الافتراضي
`0.5`). قراءة الميزانية `STALE` لا يمكن أبدًا أن تُنتج حكم `SAFE` — تُرفَّع إلى `CAUTION` على الأقل،
بغض النظر عن مدى راحة الأرقام الخام؛ يطبّق `DecisionEngine` نفس القاعدة المتحفظة على الميزانيات ذات
ثقة `UNKNOWN` (محوّل لم يُحدَّث قط) كسياسة صريحة ومنفصلة فوق `RiskEngine` غير المعدَّل — راجع
[`goldenboy/core/risk.py`](goldenboy/core/risk.py) و
[`goldenboy/core/decision_engine.py`](goldenboy/core/decision_engine.py).

---

## ⚖️ قبل وبعد

<table>
  <tr>
    <td width="50%" valign="top">
      <b>❌ بدون Golden Boy</b>
      <p>يتلقى الوكيل طلب "أعد هيكلة نظام المصادقة بالكامل"، يبدأ فورًا، وينفق بقوة عبر مراحل
      الاستكشاف/التنفيذ/الاختبار، ثم يتوقف في منتصف المهمة عندما تنفد الميزانية — دون أي سجل لما
      تم إنجازه.</p>
    </td>
    <td width="50%" valign="top">
      <b>✅ مع Golden Boy</b>
      <p>يمر نفس الطلب بالتصنيف وتقدير التكلفة والتحقق من الميزانية <i>قبل</i> اعتماد نطاق التنفيذ —
      قرار حقيقي بدرجة ثقة حقيقية، وليس تخمينًا بعد وقوع الحدث. يُسجَّل ما حدث فعليًا محليًا، بحيث
      تستفيد المهمة المشابهة التالية منه.</p>
    </td>
  </tr>
</table>

---

## 🎬 عرض توضيحي

مسار كامل — التخطيط، ثم التنفيذ التكيفي مع ميزانية متناقصة، ثم تشخيص البيئة. كل سطر أدناه هو
مخرجات حقيقية، التُقطت من هذا المستودع (لا شيء مُعدّ أو مختصر):

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

انخفضت الميزانية دون هامش الأمان في منتصف التشغيل — أنهى المنفّذ وحدته الحالية، وحفظ الباقي كنقطة
تفتيش، وتوقف بدلًا من الاستمرار بالإنفاق.

</details>

<details>
<summary><b>$ goldenboy validate</b> (تثبيت جديد، لا يوجد سجل بعد)</summary>

```
--- Golden Boy Validate ---
Config:     OK — safety_margin=3.0, caution_ratio=0.5, base_cost_per_unit=2.0, max_budget_tokens=100000, stale_after_seconds=300.0
Checkpoint: OK — none present

Dataset Quality
Rows:                 0
Status: NO_DATA — insufficient validated data (no history recorded yet).
```

لا تُختلَق أي أرقام لملء بيانات غير موجودة بعد — راجع [السجل والتحليلات](#-السجل-والتحليلات).

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

يُبلَّغ فقط عن وجود مفتاح API، وليس عن قيمته أبدًا — كل أمر تشخيصي (`doctor`، `status`،
`validate`) يدعم أيضًا `--json`.

</details>

---

## 🚀 التثبيت

```bash
pip install goldenboy
goldenboy --help
```

أو من الكود المصدري:

```bash
git clone https://github.com/amuldi/GoldenBoy.git
cd GoldenBoy
pip install -e .
```

التثبيت الأساسي **لا يحتوي على أي اعتماديات إلزامية من جهات خارجية**. تضيف الإضافات الاختيارية
قدرات محددة:

```bash
pip install "goldenboy[tiktoken]"   # عدّ دقيق للرموز (يعود إلى طريقة استدلالية أخشن بدونه)
pip install "goldenboy[anthropic]"  # AnthropicAdapter
pip install "goldenboy[openai]"     # OpenAIAdapter
```

يمكن لوكلاء/أدوات TypeScript استخدام [`sdk/typescript`](sdk/typescript) بدلًا من استدعاء CLI
مباشرة — راجع [حزمة TypeScript](#-حزمة-typescript-sdk).

---

## ⚡ بداية سريعة

```bash
goldenboy analyze "Refactor the authentication system"   # توصية كاملة: النوع، الخطورة، الإجراء، السبب
goldenboy status                                          # الميزانية الحالية وأي نقطة تفتيش معلّقة
goldenboy validate                                         # الإعدادات + نقطة التفتيش + تقرير جودة البيانات المحلي
goldenboy doctor                                            # تشخيص البيئة والإعدادات ونقطة التفتيش
```

---

## 🖥 مرجع CLI

| الأمر | الغرض |
|---|---|
| `goldenboy analyze <task>` | توصية كاملة بذكاء المهام: النوع، التعقيد، الخطورة، الإجراء، الثقة، السبب. `--progress 0.0-1.0`، `--json`. |
| `goldenboy plan <task>` | تقدير التكلفة الحقيقية للمهمة من نصها + حجم المستودع، وعرض وضع الخطورة الناتج. |
| `goldenboy run <task>` | تنفيذ خطة توضيحية واعية بالميزانية بشكل تكيفي مقابل ميزانية وهمية. |
| `goldenboy status` | فحص الميزانية الحالية وأي نقطة تفتيش معلّقة. `--json`. |
| `goldenboy resume` | استئناف التنفيذ من نقطة التفتيش السابقة. |
| `goldenboy doctor` | تشخيص إصدار Python، الاعتماديات الاختيارية، إعدادات مفاتيح المزوّد، الإعدادات، نقطة التفتيش. `--json`. |
| `goldenboy validate` | التحقق من الإعدادات + نقطة التفتيش + جودة بيانات السجل المحلي؛ يخرج بـ1 عند وجود مشكلة حقيقية. `--json`. |
| `goldenboy replay` | اختبار رجعي لسياسات مرجعية مقابل السجل المحلي (أو `--dataset PATH`). `--json`. |
| `goldenboy benchmark` | قياس زمن استجابة estimator/risk-engine/بدء تشغيل CLI، على هذا الجهاز، الآن. `--json`. |
| `goldenboy export` | تصدير الإعدادات + نقطة التفتيش + السجل كمستند JSON واحد قابل لإعادة الإنتاج. `--output PATH`. |

أضف `--budget` لأي أمر يستخدم ميزانية وهمية للتحكم بالميزانية الابتدائية، و`-v`/`--verbose`
(قبل الأمر الفرعي) لسجل القرارات الداخلي لكل وحدة الموضّح في [العرض التوضيحي](#-عرض-توضيحي) أعلاه.

---

## 🐍 التكامل مع Python

```python
from goldenboy import AdaptiveExecutor, MockProvider, budget_aware_execution, Priority

provider = MockProvider(initial_percentage=40.0)

@budget_aware_execution(provider, "1", "Refactor the auth module", Priority.P1)
def refactor_auth():
    ...  # عملك الفعلي يُكتب هنا — Golden Boy يقرر ما إذا كان سيستدعيه أصلًا

refactor_auth()
```

يطلب `budget_aware_execution` من المزوّد قرارًا بشأن الميزانية/الوضع، ولا يستدعي دالتك إلا إذا
سمح الوضع بذلك — ولا يستدعي المزوّد نفسه أبدًا. كل استدعاء يسجّل أيضًا حدثًا واحدًا محليًا (بدون
نص المهمة الخام أبدًا) — راجع [السجل والتحليلات](#-السجل-والتحليلات). السطح العام الكامل موجود في
[`goldenboy/__init__.py`](goldenboy/__init__.py)؛ أي شيء غير مُدرَج هناك يمكن الوصول إليه عبر
وحدته الفرعية الخاصة، لكنه ليس جزءًا من عقد الاستقرار الذي تتمتع به الواجهة العليا.

لواجهة القرار الكاملة المُبرَّرة، استخدم `DecisionEngine` مباشرة:

```python
from goldenboy.adapters.mock import MockProvider
from goldenboy.core.decision_engine import DecisionEngine

decision = DecisionEngine().decide("Refactor the auth module", MockProvider(initial_percentage=15))
print(decision.action, decision.confidence, decision.reason)
```

---

## 🌐 البروتوكول

كل قرار ينتجه Golden Boy — من Python أو CLI أو TypeScript — هو صيغة JSON واحدة، مُصدَّرة ومحايدة
لغويًا: **بروتوكول Golden Boy**. المخطط الكامل وسياسة إدارة الإصدارات وسبب عدم وجود خادم موجودة في
[`docs/PROTOCOL.md`](docs/PROTOCOL.md).

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

تتحقق `GoldenBoyDecision.from_dict`/`from_json` في `goldenboy/protocol.py` بصرامة من أي حمولة
مبنية بهذه الطريقة — حقل مفقود أو إصدار رئيسي غير متوافق يُطلق `ProtocolError`، وليس `KeyError`
خامًا أبدًا. يفرض `sdk/typescript/src/validate.ts` نفس العقد بالضبط في جانب TypeScript.

---

## 📘 حزمة TypeScript SDK

[`sdk/typescript`](sdk/typescript) هي عميل خفيف، وليست تطبيقًا ثانيًا — فهي تشغّل CLI الحقيقي
لـ`goldenboy` وتحلّل مخرجاته `--json` عبر نفس تحقق البروتوكول الموصوف أعلاه. صفر اعتماديات وقت
تشغيل؛ تعمل الاختبارات على مُشغّل الاختبار المدمج في Node، بما في ذلك اختبارات تكامل حقيقية
(غير وهمية) مقابل CLI الفعلي.

```ts
import { GoldenBoyClient } from "@goldenboy/sdk";

const client = new GoldenBoyClient(); // يستخدم `goldenboy` من PATH
const decision = await client.analyze("Refactor the authentication system", { budget: 6 });

console.log(decision.action);       // "reduce_scope"
console.log(decision.confidence);   // 0.774
console.log(decision.reason);       // مبني على نفس الأرقام الحقيقية الموجودة في مخرجات Python/CLI
```

```bash
cd sdk/typescript
npm install && npm run build && npm test   # 14 اختبارًا، بما في ذلك تكامل حي مع CLI
```

راجع [`sdk/typescript/README.md`](sdk/typescript/README.md) للحصول على الواجهة الكاملة وملاحظات
التصميم.

---

## 📡 السجل والتحليلات

كل استدعاء مُزخرَف بـ`budget_aware_execution` يضيف حدثًا إلى سجل محلي يُضاف إليه فقط
(`.goldenboy/history.jsonl`، مُستثنى من git — نفس اتفاقية ملف نقطة التفتيش). الحدث لا يخزّن أبدًا
النص الخام للمهمة، بل طوله فقط وبصمة SHA-256 مختصرة (راجع
[`goldenboy/core/history.py`](goldenboy/core/history.py) و[`SECURITY.md`](SECURITY.md)).

```bash
goldenboy validate   # جودة البيانات: عدد الصفوف، نسب التلف/التكرار/القيم غير الصالحة، GOOD/ACCEPTABLE/POOR/NO_DATA
goldenboy export     # تصدير الإعدادات + نقطة التفتيش + السجل (تقرير الجودة، التحليلات، الأحداث) كمستند JSON واحد
```

```python
from goldenboy.analytics import data_quality
from goldenboy.analytics.engine import analyze
from goldenboy.core.history import HistoryStore

store = HistoryStore()
print(data_quality.validate(store).render())   # تقرير حقيقي -- "NO_DATA" إن لم يُسجَّل شيء بعد
print(analyze(store).render())                  # تجميعات التكلفة/الإنجاز/الفشل، أو "N/A"
```

عند التثبيت الجديد، يُبلّغ كلاهما بصدق عن صفر صفوف — راجع مثال `validate` في
[العرض التوضيحي](#-عرض-توضيحي) أعلاه. لا شيء هنا عبارة عن عنصر نائب ينتظر "فك القفل": إنه كود
حقيقي يعمل فعليًا ويبدأ في إنتاج تجميعات حقيقية بمجرد أن يشغّل وكيلك مهامًا مُزخرَفة فعليًا.

---

## 🔁 إعادة التشغيل والاختبار الرجعي

تجيب `goldenboy.replay` عن سؤال واحد: *هل كانت سياسة مختلفة لتوزيع الموارد ستتخذ قرارات أفضل في
هذه المهام الفعلية الماضية؟* هذا **اختبار رجعي لتوزيع موارد وكيل ذكاء اصطناعي**، وليس اختبارًا
ماليًا. تتم مقارنة خمس سياسات على قدم المساواة — خط أساس ثابت مزدوج (15%/20%)، طريقة استدلالية
تعتمد على التعقيد فقط، وأخرى تعتمد على الاستخدام فقط، و`GoldenBoyPolicy` (التي تُغلّف `RiskEngine`
الحقيقي غير المعدَّل) — عبر `goldenboy.core.policies` و`goldenboy.replay.engine`.

```bash
$ goldenboy replay
Backtest: 0 event(s) available (need at least 10).
N/A — insufficient validated data.
```

هذا هو المخرج الحقيقي والحالي عند التثبيت الجديد — وهكذا يجب أن يكون. لا توجد أي مجموعة بيانات
مُرفَقة أو اصطناعية تحل محل الاستخدام الحقيقي؛ يوثّق `docs/DATASETS.md` سبب عدم قدرة معايير عامة
مثل SWE-bench على تعويض ذلك (فهي تقيس صحة توليد الكود، وليس قرارات الموارد الواعية بالميزانية). بمجرد
أن يحتوي `.goldenboy/history.jsonl` الخاص بك على 10 أحداث على الأقل، تقوم `goldenboy replay` بتقييم
كل سياسة فعليًا:

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

تقسّم `walk_forward_folds()` الأحداث زمنيًا دون أي تسرّب عبر حدود التقسيمات — بنية تحتية جاهزة
ومختبرة لسياسة مستقبلية قائمة على التعلّم (السياسات الخمس الحالية جميعها ثابتة/حتمية، لذا لا يغيّر
التقسيم درجاتها بعد؛ راجع توثيق وحدة `goldenboy/replay/engine.py`). يطبع التقرير دائمًا قيوده
المنهجية الخاصة إلى جانب أي أرقام — راجع [`goldenboy/replay/engine.py`](goldenboy/replay/engine.py).

---

## 🔌 التكاملات

محوّلات المزوّد تُبلّغ عن الاستخدام فقط؛ لا تُنفّذ كودك أبدًا. العمل الفعلي يعمل دائمًا عبر مُزخرِف
`budget_aware_execution` أعلاه.

| المزوّد | يقرأ | ملاحظات |
|---|---|---|
| `MockProvider` | نسبة مئوية اصطناعية في الذاكرة | للعروض التوضيحية والاختبارات — بلا اتصالات شبكة. |
| `AnthropicAdapter` | ترويستا `anthropic-ratelimit-tokens-remaining` / `-limit` في الاستجابة | يتطلب `goldenboy[anthropic]`. يعكس حد المعدل *المشترك* للمؤسسة، وليس هذا الاستدعاء وحده. |
| `OpenAIAdapter` | ترويستا `x-ratelimit-remaining-tokens` / `-limit-tokens` في الاستجابة | يتطلب `goldenboy[openai]`. نفس تحذير الحد المشترك أعلاه. |
| مهارة Claude Code | رقم `<total_tokens>` الذي يحقنه Claude Code في السياق | لا حاجة لعملية Python — انظر أدناه. |
| حزمة TypeScript | مخرجات `--json` لـCLI الخاص بـ`goldenboy` عبر عملية فرعية | بلا خادم HTTP — راجع [البروتوكول](#-البروتوكول). |

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

يحدّث كلا المحوّلين قراءتهما فقط عبر استدعاء صريح لـ`refresh_usage()`، ويتتبعان مدة مرور الوقت منذ
ذلك باستخدام ساعة قابلة للحقن — بعد تجاوز `stale_after_seconds` (300 ثانية افتراضيًا)، تشيخ الثقة
تلقائيًا من `ESTIMATED` إلى `STALE`. قبل أول تحديث، تكون الثقة `UNKNOWN` — و`DecisionEngine` (وليس
`RiskEngine` نفسه) يعامل ذلك بتحفظ أيضًا، بنفس الطريقة التي يعامل بها `STALE`.

يحصل **Claude Code** على تكامل على مستوى التعليمات بدلًا من ذلك:
[`skills/goldenboy/SKILL.md`](skills/goldenboy/SKILL.md) يعلّم وكيل نموذج لغوي كبير قراءة رقم
الاستخدام المتبقي الذي يحقنه Claude Code مباشرة في السياق والاستدلال على وضع تنفيذه الخاص، باستخدام
نفس مفردات `SAFE`/`CAUTION`/`LIMITED`/`CRITICAL` تمامًا كما في
`goldenboy.core.risk.ExecutionMode` — يتم الحفاظ على تزامنهما يدويًا، وليس عبر كود مشترك، لأن أحد
الجانبين Python والآخر تعليمة نصية.

---

## 🏗 البنية

<details>
<summary><b>انقر لتوسيع شجرة الحزمة</b></summary>

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

## ⚙️ الإعدادات

كل عتبة سياسة موجودة في `GoldenBoyConfig`، بترتيب التجاوز التالي:

```
explicit constructor arg  >  GOLDENBOY_* environment variable  >  .goldenboy/config.json  >  default
```

| الحقل | متغير البيئة | الافتراضي | المعنى |
|---|---|---|---|
| `safety_margin` | `GOLDENBOY_SAFETY_MARGIN` | `3.0` | نقاط مئوية محجوزة دون الميزانية المتبقية المُبلَّغة قبل اعتبارها مستنفدة. |
| `caution_ratio` | `GOLDENBOY_CAUTION_RATIO` | `0.5` | نسبة التكلفة المقدّرة/الميزانية القابلة للاستخدام التي تنتقل عندها الخطورة من SAFE إلى CAUTION. |
| `base_cost_per_unit` | `GOLDENBOY_BASE_COST_PER_UNIT` | `2.0` | تكلفة احتياطية للوحدة التي لا تُعلن الخطة تكلفة لها. |
| `max_budget_tokens` | `GOLDENBOY_MAX_BUDGET_TOKENS` | `100000` | عدد الرموز المُعامَل كـ"100% من الميزانية" عند تحويل تقدير رموز خام إلى نسبة مئوية. |
| `stale_after_seconds` | `GOLDENBOY_STALE_AFTER_SECONDS` | `300.0` | مدة بقاء قراءة مزوّد مُحدَّثة كـ`ESTIMATED` قبل أن تشيخ إلى `STALE`. |

القيم خارج النطاق، وJSON غير صحيح، ومتغيرات البيئة `GOLDENBOY_*` غير القابلة للتحليل، كلها تُطلق
`ConfigError` واضحًا — في CLI، رسالة `error:` من سطر واحد وخروج بـ`1`، وليس تتبع مكدس خام أبدًا.

---

## 🧭 مبادئ التصميم

- **خفيف الوزن** — التثبيت الأساسي بلا أي اعتماديات وقت تشغيل إلزامية من جهات خارجية؛ حزم المزوّدين وأدوات حزمة TypeScript نفسها اختيارية.
- **تكيفي** — يتغير سلوك التنفيذ مع الميزانية المتبقية *و*مع مدى موثوقية ذلك الرقم: قراءة `STALE` أو `UNKNOWN` لا يمكن أبدًا أن تُنتج حكم `SAFE`.
- **حتمي** — المدخلات المتطابقة تُنتج قرارات متطابقة. لا يوجد عشوائية مخفية في estimator أو classifier أو risk engine؛ قِدَم المحوّل مُحرَّك بساعة قابلة للحقن، لذا يمكن اختباره دون انتظار.
- **المزوّد اختياري** — `import goldenboy` لا يتطلب أبدًا تثبيت `anthropic` أو `openai`.
- **الوكيل أولًا** — يقرر Golden Boy مدى جرأة الوكيل في التقدم بناءً على الميزانية المتبقية. يظل الوكيل المستدعي مسؤولًا عن فهم المهمة وتفكيكها.
- **الفشل الآمن** — الإعدادات غير الصحيحة، ونقاط التفتيش التالفة، والمدخلات غير الصالحة تُنتج جميعًا خطأً محددًا قابلًا للقراءة ورمز خروج، وليس تتبع مكدس خام أو فقدان بيانات صامت أبدًا.
- **الدليل فوق التعقيد** — لا توجد أرقام معايير مختلَقة أو نتائج اختبار رجعي أو مجموعات بيانات تاريخية في أي مكان. تُبلّغ `goldenboy replay`/`goldenboy.analytics` عن `N/A`/`NO_DATA` بدلًا من اختلاق خط أساس؛ راجع [`docs/DATASETS.md`](docs/DATASETS.md) والأهداف غير المُتَّبعة الصريحة في [`ROADMAP.md`](ROADMAP.md).

---

## 📦 حول تفكيك المهام

> التكلفة المقدّرة التي تعرضها `plan`/`run`/`analyze` تُحسَب من النص الفعلي للمهمة وسياق المستودع —
> ذلك الرقم حقيقي. تفصيل الوحدات في `plan`/`run` **توضيحي**: ليس تفكيكًا لمهمتك مُولَّدًا من نموذج
> لغوي كبير. يحرص Golden Boy عمدًا على إبقاء نواته خالية من الاعتماديات وبعيدة عن مهمة فهم *كيفية*
> إنجاز مهمة ما؛ يظل التفكيك الفعلي للمهمة مسؤولية الوكيل المستدعي (راجع
> [مبادئ التصميم](#-مبادئ-التصميم)). يخبرك `TaskClassifier` عن *نوع* المهمة الذي تبدو عليه، وليس
> كيفية تقسيمها إلى خطوات.

---

## ⚠️ القيود

- تقديرات التكلفة استدلالية (طول التعليمة + فحص محدود للمستودع) — ليست ضمانات فوترة، وليست نموذجًا لما سيحمّله الوكيل فعليًا في سياقه.
- `TaskClassifier` هو مطابق كلمات مفتاحية حتمي، وليس نموذجًا مُدرَّبًا — تعكس درجة ثقته قوة التطابق، وليس احتمالًا معايرًا. لا توجد بعد بيانات واقعية موسومة يمكن التدريب عليها (راجع `docs/DATASETS.md`).
- تُبلّغ `goldenboy replay`/`goldenboy.analytics` عن `N/A`/`NO_DATA` حتى يُسجَّل محليًا 10 أحداث حقيقية على الأقل — لا توجد مجموعة بيانات مُرفَقة تعوّض ذلك.
- مقاييس إعادة التشغيل هي تقييم خارج السياسة (off-policy) مبني على النتائج المُسجَّلة: النتيجة المُسجَّلة لحدث ما تعكس القرار الذي اتخذه Golden Boy فعليًا في ذلك الوقت، وليس نتيجة السياسة البديلة التي يجري تقييمها — مقارنة وصفية، وليست ضمانًا سببيًا (راجع [إعادة التشغيل والاختبار الرجعي](#-إعادة-التشغيل-والاختبار-الرجعي)).
- قد يتغير استخدام المزوّد (ترويسات حد المعدل) خارج سيطرة Golden Boy بين التحديثات؛ لهذا السبب بالتحديد توجد ثقة `STALE`.
- تفصيل الوحدات في `plan`/`run` توضيحي، وليس تفكيكًا حقيقيًا للمهام (انظر أعلاه).
- لا يستبدل Golden Boy حكم الوكيل البرمجي المستدعي نفسه — بل يوفر فقط معلومات عن مدى المحاولة المناسبة.

---

## ✅ التحقق

تم التحقق من Golden Boy v1.1.0، اعتبارًا من 2026-09-14، مقابل:

- **186 اختبار Python**، تغطية أسطر 95% (`pytest --cov`) — ارتفاعًا من 88 اختبارًا / 93% في v1.0.0
- **14 اختبار TypeScript** (`npm test` في `sdk/typescript`)، بما في ذلك اختبارات تكامل حقيقية (غير وهمية) مقابل CLI المثبّت فعليًا
- Ruff وmypy نظيفان (تم التحقق من mypy تحت كل من 1.19.1 و2.3.1)
- `pip-audit`: 0 ثغرات معروفة
- Python 3.9–3.13، على GitHub Actions
- عجلة (wheel) وحزمة مصدرية (sdist) مبنيتان ومثبّتتان في بيئة افتراضية جديدة ومستقلة، مع تنفيذ كل أمر CLI فعليًا (بما فيها الجديدة) مقابلها
- تثبيت أساسي فقط (`pip install goldenboy`) لا يجلب أي اعتماديات وقت تشغيل من جهات خارجية — تم التحقق منه حيًا عبر `pip list` مقابل تثبيت في بيئة نظيفة، وليس مجرد ادّعاء

CI (`.github/workflows/ci.yml`، 8 مهام):

| المهمة | النتيجة |
|---|---|
| security (pip-audit) | ✓ |
| test (3.9) | ✓ |
| test (3.10) | ✓ |
| test (3.11) | ✓ |
| test (3.12) | ✓ |
| test (3.13) | ✓ |
| build (تثبيت العجلة + كل أمر CLI + فحص سلامة المعايير) | ✓ |
| sdk-typescript (تكامل حقيقي مع CLI المثبّت) | ✓ |

---

## 📊 المعايير

قِيست مرة واحدة، محليًا (Apple M1 Pro، macOS arm64، Python 3.13.7، 2026-09-13) عبر
`goldenboy benchmark` / `scripts/benchmark.py` (تطبيق واحد مشترك — راجع
`goldenboy/core/benchmark.py`) — ليست جزءًا من معيار النجاح/الفشل في CI (يتحقق CI فقط من أن
الأرقام غير سالبة وأن estimator حتمي)، وليست ضمانًا. أعد تشغيلها بنفسك قبل الاعتماد على هذه
الأرقام في أي شيء.

| العملية | المتوسط | الوسيط | n |
|---|---|---|---|
| `Estimator.estimate_task()` (بعد الإحماء، هذا المستودع) | 9.30ms | 8.79ms | 20 |
| حتمية `Estimator.estimate_task()` | PASS — نتيجة واحدة مميزة عبر 10 استدعاءات متطابقة | | 10 |
| `RiskEngine.assess()` | <0.001ms | <0.001ms | 1000 |
| بدء تشغيل CLI البارد (`goldenboy status`) | 93.46ms | 93.33ms | 5 |

`RiskEngine.assess()` هي حسابات حسابية بحتة على قيم محسوبة بالفعل، لذا فهي دون الميكروثانية بحكم
البنية. زمن استجابة Estimator يتغير مع حجم المستودع (محدود بسقفي `_MAX_SCAN_FILES` /
`_MAX_FILE_BYTES`)، وليس بطول التعليمة. بدء تشغيل CLI البارد هو في معظمه عبء مترجم/استيراد Python —
وهو ما تشعر به فعليًا عند تشغيل أي أمر `goldenboy` منفرد. المنهجية الكاملة والتحفظات ومنطق الانتقال
إلى Rust المبني على هذه الأرقام: [`BENCHMARKS.md`](BENCHMARKS.md) و
[`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md).

---

## 🗺 خارطة الطريق

**تم إصداره، تم اختباره، حقيقي:**

- ✓ تقدير تكلفة واعٍ بالمهمة، أوضاع تنفيذ تكيفية، نقطة تفتيش/تأجيل/استئناف، ثقة استخدام تشمل اكتشاف STALE
- ✓ CLI (`plan`/`run`/`status`/`resume`/`doctor`/`analyze`/`validate`/`replay`/`benchmark`/`export`)
- ✓ محوّلات مزوّد Anthropic/OpenAI، تكامل مهارة Claude Code
- ✓ بروتوكول Golden Boy (مُصدَّر، محايد لغويًا) + حزمة TypeScript
- ✓ تصنيف المهام (`TaskClassifier`) + `DecisionEngine` (إجراء/ثقة/سبب مُبرَّرة)
- ✓ سجل محلي (`HistoryStore`) + تقارير جودة البيانات/التحليلات
- ✓ سياسات مرجعية + محرك اختبار رجعي `goldenboy.replay` + تقسيم تدريجي زمني

| الاتجاه | الحالة |
|---|---|
| نتيجة اختبار رجعي حقيقية ومملوءة (وليست `N/A`) | معلّقة على تراكم بيانات استخدام حقيقية — لا يمكن إنتاجها بصدق اليوم |
| مصنّف مهام / سياسة قائمة على التعلّم | بحث — يتطلب أولًا بيانات نتائج حقيقية وموسومة |
| تقسيم `cli.py` إلى حزمة `cli/` | مُخطَّط له — مؤجَّل لهذه الدورة (مخاطرة التراجع مقابل الفائدة؛ راجع `ROADMAP.md`) |
| اختبار معايير مقابل مستودع اصطناعي كبير عمدًا | مُخطَّط له |
| تكاملات وكلاء إضافية (مثل Codex) | بحث — فقط مع إشارة استخدام حقيقية وموثّقة يمكن البناء عليها |

لا شيء مما سبق يُدَّعى جاهزًا للإنتاج ما لم يكن مغطى أيضًا بالاختبارات. التفصيل الكامل لـ
Done/Planned/Research، بما في ذلك الأهداف غير المُتَّبعة الصريحة (بلا قاعدة بيانات، بلا لوحة تحكم
ويب، بلا خادم، بلا ML أو Rust سابقين لأوانهما)، في [`ROADMAP.md`](ROADMAP.md).

---

## 🤝 المساهمة

المساهمات مرحّب بها. يحتوي [`CONTRIBUTING.md`](CONTRIBUTING.md) على خطوات الإعداد، والفحوصات
التي يجب أن يجتازها أي طلب سحب (`pytest`، `ruff`، `mypy`، `python -m build` — جميعها إلزامية في
CI)، ومبادئ الهندسة التي تعتمد عليها المراجعة: البنية الحالية أولًا، السبب الجذري على العرض،
لا اكتمال زائف، وسم صادق للثقة، وعدم ترميز أرقام السياسة خارج `GoldenBoyConfig`.

---

## 🛠 التطوير

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

لحزمة TypeScript SDK:

```bash
cd sdk/typescript
npm install
npm run typecheck && npm run build && npm test
```

---

## 📚 المزيد من الوثائق

| الوثيقة | تغطي |
|---|---|
| [`docs/PROTOCOL.md`](docs/PROTOCOL.md) | مخطط بروتوكول Golden Boy، وسياسة إدارة الإصدارات، وسبب عدم وجود خادم. |
| [`docs/DATASETS.md`](docs/DATASETS.md) | مراجعة لمشهد مجموعات البيانات/الأبحاث (SWE-bench، HumanEval، LiveCodeBench، RepoBench، أبحاث استهلاك الرموز) وسبب عدم قدرة أي منها على تعويض `HistoryStore`. |
| [`docs/LANGUAGE_STRATEGY.md`](docs/LANGUAGE_STRATEGY.md) | سبب بقاء Python كنواة، وأين تُستخدم TypeScript، وحدود الانتقال المستقبلي إلى Rust. |
| [`CHANGELOG.md`](CHANGELOG.md) | ما تغيّر من إصدار إلى آخر. |
| [`ROADMAP.md`](ROADMAP.md) | التفصيل الكامل لـDone / Planned / Research، بما في ذلك الأهداف غير المُتَّبعة الصريحة. |
| [`BENCHMARKS.md`](BENCHMARKS.md) | أرقام الأداء المقاسة، والمنهجية، وما لم يُقَس بعد. |
| [`SECURITY.md`](SECURITY.md) | كيفية التعامل مع بيانات الاعتماد والسجل المحلي، وكيفية الإبلاغ عن ثغرة. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | الإعداد، والفحوصات، ومبادئ الهندسة التي تعتمد عليها المراجعات. |
| [`sdk/typescript/README.md`](sdk/typescript/README.md) | مرجع واجهة برمجة تطبيقات حزمة TypeScript وملاحظات التصميم. |

---

## 📄 الترخيص

[MIT](LICENSE).

<p align="center">
  ⭐ إذا كان Golden Boy يحمي وكيلك من استنفاد الميزانية، فإن نجمة واحدة تساعد المزيد من الأشخاص على اكتشافه.
</p>
