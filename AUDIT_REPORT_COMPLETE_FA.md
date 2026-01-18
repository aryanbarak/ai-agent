# 📊 گزارش کامل تحلیل و بازبینی پروژه AI Agent

**تاریخ تحلیل:** ژانویه 2026  
**تحلیلگر:** Senior AI Architect & Lead Software Engineer  
**نسخه پروژه:** 0.1 (MVP)  
**وضعیت:** نیازمند Refactoring جدی

---

## 🎯 خلاصه اجرایی (Executive Summary)

پروژه **AI Agent** یک دستیار هوشمند برای کمک به آماده‌سازی آزمون FIAE است که شامل قابلیت‌های:
- تحلیل الگوریتمی مسائل
- برنامه‌ریزی روزانه با ماتریس Eisenhower
- مشاوره مسیر شغلی

**وضعیت فعلی:** پروژه در مرحله MVP قرار دارد و عملکرد اولیه خوبی دارد، اما برای production آماده نیست.

**امتیاز کلی:**
- 🏗️ معماری: **4/10** (نیاز به بازطراحی)
- 🔐 امنیت: **6/10** (قابل قبول اما نیاز به بهبود)
- ⚡ Performance: **5/10** (مشکلات concurrency)
- 🧪 Testability: **3/10** (تست نویسی بسیار دشوار)
- 📈 Scalability: **4/10** (محدودیت‌های جدی)

---

## 📋 فهرست مطالب

1. [تحلیل معماری](#1-تحلیل-معماری)
2. [بهینه‌سازی AI Agent](#2-بهینه‌سازی-ai-agent)
3. [کیفیت کد و Performance](#3-کیفیت-کد-و-performance)
4. [مسائل بحرانی](#4-مسائل-بحرانی)
5. [برنامه Refactoring](#5-برنامه-refactoring)
6. [نمونه کدهای بهبود یافته](#6-نمونه-کدهای-بهبود-یافته)

---

## 1️⃣ تحلیل معماری

### 1.1 ساختار فعلی پروژه

```
agent/
├── __init__.py
├── agent_contract.md      # قرارداد و محدودیت‌های agent
├── api.py                 # ❌ 598 خط - God Class
├── main.py                # CLI interface
├── memory/
│   └── memory.py          # SQLite operations
└── modules/
    ├── career.py          # مشاوره شغلی
    ├── fiae_analysis.py   # تحلیل نقاط ضعف
    ├── fiaetutor.py       # ❌ 399 خط - God Class
    └── planner.py         # برنامه‌ریزی روزانه
```

### 1.2 ارزیابی Modularity

#### ✅ نقاط قوت:
1. **تفکیک منطقی:** ماژول‌ها به صورت منطقی جدا شده‌اند
2. **Single Purpose Modules:** هر ماژول یک هدف مشخص دارد
3. **Data Layer Separation:** حافظه در پوشه جداگانه است

#### ❌ مشکلات جدی:

##### 1.2.1 **God Class در `fiaetutor.py`**

این فایل 399 خط دارد و مسئولیت‌های زیر را دارد:

```python
# ❌ مسئولیت 1: مدیریت کلاینت LLM
client = OpenAI(api_key=GEMINI_API_KEY, ...)

# ❌ مسئولیت 2: کش مدیریت
_CACHE: dict = {}

# ❌ مسئولیت 3: پردازش JSON
def _parse_json(content: str) -> Any | None:
    ...

# ❌ مسئولیت 4: ساخت Prompt
def _build_system_prompt(lang: str) -> str:
    ...

# ❌ مسئولیت 5: تشخیص زبان
def _language_ok(data: dict, lang: str) -> bool:
    ...

# ❌ مسئولیت 6: مدیریت خطا
def _looks_like_quota_error(text: str) -> bool:
    ...

# ❌ مسئولیت 7: منطق اصلی
def analyze_problem(...):
    ...
```

**این نقض آشکار Single Responsibility Principle است!**

##### 1.2.2 **God Class در `api.py`**

این فایل 598 خط دارد و شامل:

```python
# ❌ HTTP Routes
@app.post("/api/fiae/analyze")
def fiae_analyze(...): ...

# ❌ Business Logic
def compute_importance_urgency(name: str):
    # 50+ خط منطق کسب‌وکار در routing layer!
    ...

# ❌ Data Processing
def build_day_schedule(result: dict):
    # پردازش داده در routing layer!
    ...

# ❌ Hardcoded Knowledge
def _get_pseudocode_block(topic: str, lang: str):
    # 40+ خط pseudocode hardcoded!
    ...
```

**این باعث می‌شود:**
- تست نویسی غیرممکن باشد
- تغییرات کوچک کل فایل را تحت تأثیر قرار دهد
- کد غیرقابل استفاده مجدد باشد

### 1.3 Separation of Concerns

#### ❌ **مشکل: اختلاط لایه‌ها**

```
┌─────────────────────────────────────┐
│  فعلی (اشتباه):                     │
│  ┌────────────────────────────────┐ │
│  │   api.py (598 lines)           │ │
│  │  ┌──────────────────────────┐  │ │
│  │  │ HTTP Routing             │  │ │
│  │  │ Business Logic ❌        │  │ │
│  │  │ Data Processing ❌       │  │ │
│  │  │ Validation ❌            │  │ │
│  │  └──────────────────────────┘  │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

#### ✅ **راه حل: Clean Architecture**

```
┌───────────────────────────────────────────┐
│  درست (Layered):                          │
│  ┌──────────────────────────────────────┐ │
│  │ Presentation Layer (API Routes)      │ │
│  └──────────────────────────────────────┘ │
│              ↓ depends on                 │
│  ┌──────────────────────────────────────┐ │
│  │ Application Layer (Services)         │ │
│  └──────────────────────────────────────┘ │
│              ↓ depends on                 │
│  ┌──────────────────────────────────────┐ │
│  │ Domain Layer (Business Logic)        │ │
│  └──────────────────────────────────────┘ │
│              ↓ depends on                 │
│  ┌──────────────────────────────────────┐ │
│  │ Infrastructure (DB, LLM, Cache)      │ │
│  └──────────────────────────────────────┘ │
└───────────────────────────────────────────┘
```

### 1.4 عدم Dependency Injection

#### مشکل فعلی:

```python
# در fiaetutor.py
client = OpenAI(api_key=GEMINI_API_KEY, ...)  # ❌ Global

# در fiae_analysis.py
from agent.modules.fiaetutor import client  # ❌ Direct import

# در career.py
from agent.modules.fiaetutor import client  # ❌ Direct import
```

**مشکلات:**
1. **تست نویسی غیرممکن:** نمی‌توان client را mock کرد
2. **Coupling شدید:** تغییر در یک جا همه را می‌شکند
3. **Configuration سخت:** نمی‌توان برای environments مختلف تنظیم کرد

#### راه حل با Dependency Injection:

```python
# ✅ Protocol definition
class LLMProvider(Protocol):
    async def complete(self, messages, ...):
        ...

# ✅ Service با injected dependency
class FIAEAnalysisService:
    def __init__(self, llm_provider: LLMProvider):  # ✅ Injected!
        self.llm = llm_provider
    
    async def analyze(self, ...):
        result = await self.llm.complete(...)  # ✅ Uses injected provider

# ✅ در تست
async def test_analyze():
    mock_llm = MockLLMProvider()  # ✅ Easy to mock!
    service = FIAEAnalysisService(llm_provider=mock_llm)
    result = await service.analyze(...)
```

---

## 2️⃣ بهینه‌سازی AI Agent

### 2.1 مدیریت Context و Memory

#### ❌ **مشکل 1: عدم محدودیت Token**

```python
# در fiae_analysis.py
def _build_history_text(limit: int = 20) -> str:
    logs = get_recent_fiae_logs(limit=20)  # ❌ No token limit!
    
    for idx, (created_at, problem, answer) in enumerate(logs):
        short_answer = shorten(answer, width=500, ...)  # ❌ Still too much!
        parts.append(f"Problem: {problem}\nAntwort: {short_answer}")
    
    return "\n\n".join(parts)  # ❌ Could be 10k+ tokens!
```

**خطر:** اگر هر لاگ 500 کاراکتر باشد، 20 لاگ = 10,000 کاراکتر ≈ 2,500 token!

#### ✅ **راه حل:**

```python
class ContextManager:
    MAX_TOKENS = 4000
    
    async def build_history_context(
        self,
        limit: int = 20,
        max_tokens: int = 4000,
    ) -> str:
        logs = await self.repository.get_recent(limit)
        
        parts = []
        total_tokens = 0
        
        for log in logs:
            # ✅ Estimate tokens (rough: 1 token ≈ 4 chars)
            estimated_tokens = len(log.problem + log.answer) // 4
            
            if total_tokens + estimated_tokens > max_tokens:
                break  # ✅ Stop before exceeding limit
            
            parts.append(self._format_log(log))
            total_tokens += estimated_tokens
        
        return "\n\n".join(parts)
```

#### ❌ **مشکل 2: کش غیر Thread-Safe**

```python
# در fiaetutor.py
_CACHE: dict[tuple[str, str, str], dict[str, object]] = {}  # ❌ NOT thread-safe!

def analyze_problem(...):
    cache_key = (text, normalized_lang, normalized_mode)
    
    if cache_key in _CACHE:  # ❌ Race condition!
        return _CACHE[cache_key]
    
    # ... API call ...
    
    _CACHE[cache_key] = result  # ❌ Race condition!
```

**خطر در FastAPI:**
```
Request 1: Check cache (empty) → Start API call
Request 2: Check cache (empty) → Start API call  ❌ Duplicate!
Request 1: Save to cache
Request 2: Save to cache  ❌ Overwrite!
```

#### ✅ **راه حل: Thread-Safe Cache**

```python
class LRUCache:
    def __init__(self, max_size: int = 1000):
        self._cache = OrderedDict()
        self._lock = asyncio.Lock()  # ✅ Thread-safe!
    
    async def get(self, key: str):
        async with self._lock:  # ✅ Lock protects access
            if key in self._cache:
                value, expiry = self._cache[key]
                
                # ✅ Check expiry
                if expiry and time.time() > expiry:
                    del self._cache[key]
                    return None
                
                # ✅ Move to end (LRU)
                self._cache.move_to_end(key)
                return value
        
        return None
    
    async def set(self, key: str, value, ttl: int | None = None):
        async with self._lock:  # ✅ Lock protects access
            # ✅ Evict oldest if over limit
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            expiry = time.time() + ttl if ttl else None
            self._cache[key] = (value, expiry)
```

#### ❌ **مشکل 3: عدم Eviction Policy**

کش فعلی هیچ محدودیتی ندارد و می‌تواند بی‌نهایت بزرگ شود!

#### ✅ **راه حل:**
- ✅ LRU (Least Recently Used)
- ✅ TTL (Time To Live)
- ✅ Size Limit

### 2.2 مدیریت Prompt

#### ❌ **مشکل: Hardcoded Prompts**

```python
# در fiaetutor.py - خط 255
def _build_system_prompt(lang: str, strong: bool = False) -> str:
    return f"""
You are a strict but helpful FIAE exam coach.
Focus ONLY on:
- Algorithm thinking
...
"""  # ❌ 40+ خط prompt hardcoded در کد!
```

**مشکلات:**
1. تغییر prompt نیاز به deploy مجدد دارد
2. Version control دشوار است
3. A/B testing غیرممکن است
4. ترجمه و نگهداری سخت است

#### ✅ **راه حل: Prompt Template System**

```
prompts/
├── fiae_tutor.json
├── planner.json
└── career_advisor.json
```

```json
{
  "default": "de",
  "de": "Du bist ein strenger aber hilfreicher Coach...",
  "fa": "شما یک مربی سخت‌گیر اما مفید هستید...",
  "en": "You are a strict but helpful coach..."
}
```

```python
class PromptTemplateManager:
    def __init__(self, templates_dir: Path):
        self.templates = self._load_templates(templates_dir)
    
    def get_prompt(self, name: str, language: str, **vars):
        template = self.templates[name][language]
        return template.format(**vars)  # ✅ Variable substitution

# استفاده:
prompt = prompt_manager.get_prompt(
    "fiae_tutor",
    language="de",
    model_name="gemini-2.5-flash",
)
```

**مزایا:**
- ✅ تغییر بدون deploy
- ✅ Version control آسان
- ✅ A/B testing ممکن
- ✅ نگهداری ساده

### 2.3 مدیریت خطای LLM API

#### ❌ **مشکل فعلی:**

```python
# در fiaetutor.py - خط 349
try:
    completion = client.chat.completions.create(...)
    ...
except Exception as e:  # ❌ Catch همه چیز!
    message = str(e)
    if _looks_like_quota_error(message):
        return _empty_result(_quota_summary(lang), ...)
    return _empty_result(_error_summary(lang), ...)
```

**مشکلات:**
1. ❌ **هیچ Retry نمی‌کند**
2. ❌ **Timeout مشخص ندارد**
3. ❌ **Circuit Breaker ندارد**
4. ❌ **Fallback Strategy ندارد**

#### ✅ **راه حل جامع:**

```python
class GeminiProvider:
    def __init__(self, api_key: str, max_retries: int = 3):
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=30.0,  # ✅ Explicit timeout
            max_retries=0,  # ✅ We handle retries ourselves
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,  # ✅ Open after 5 failures
            recovery_timeout=60.0,  # ✅ Try again after 60s
        )
    
    async def complete(self, messages, ...):
        @self.circuit_breaker.call  # ✅ Circuit breaker protection
        async def _make_request():
            for attempt in range(self.max_retries):
                try:
                    result = await self.client.chat.completions.create(...)
                    return result  # ✅ Success
                
                except RateLimitError as e:
                    retry_after = self._extract_retry_after(str(e))
                    
                    if attempt < self.max_retries - 1:
                        wait = retry_after or (2 ** attempt)  # ✅ Exponential backoff
                        await asyncio.sleep(wait)
                        continue  # ✅ Retry
                    
                    raise LLMQuotaError(...)  # ✅ Specific exception
                
                except APITimeoutError:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # ✅ Exponential backoff
                        continue
                    
                    raise LLMTimeoutError(...)  # ✅ Specific exception
        
        return await _make_request()
```

**مزایا:**
- ✅ **Automatic Retry** با exponential backoff
- ✅ **Circuit Breaker** جلوی overload را می‌گیرد
- ✅ **Timeout** واضح
- ✅ **Specific Exceptions** برای handling بهتر

---

## 3️⃣ کیفیت کد و Performance

### 3.1 نقض SOLID Principles

#### ❌ **1. Single Responsibility Principle**

```python
# api.py - خط 340-410
def compute_importance_urgency(name: str) -> tuple[str, str]:
    # ❌ این تابع 70+ خط دارد و:
    # - دریافت کلمات کلیدی
    # - تشخیص زبان
    # - پردازش زمان
    # - منطق اولویت‌بندی
    # - Decision making
    
    minutes = extract_minutes(name)  # مسئولیت 1
    has_exam = has_any(name, EXAM_KEYWORDS_DE)  # مسئولیت 2
    urgent = has_any(name, URGENCY_KEYWORDS_DE)  # مسئولیت 3
    
    # ... 60+ خط منطق دیگر
```

**باید به چند کلاس تقسیم شود:**

```python
# ✅ تقسیم مسئولیت‌ها

class TimeExtractor:
    def extract_minutes(self, text: str) -> int | None:
        ...  # ✅ فقط استخراج زمان

class KeywordDetector:
    def __init__(self, keywords: dict[str, list[str]]):
        self.keywords = keywords
    
    def has_keyword(self, text: str, category: str) -> bool:
        ...  # ✅ فقط تشخیص کلمات کلیدی

class TaskPrioritizer:
    def __init__(self, time_extractor: TimeExtractor, keyword_detector: KeywordDetector):
        self.time_extractor = time_extractor
        self.keyword_detector = keyword_detector
    
    def compute_priority(self, task_name: str) -> tuple[str, str]:
        ...  # ✅ فقط منطق اولویت‌بندی
```

#### ❌ **2. Open/Closed Principle**

```python
# فرض کنید بخواهیم OpenAI را به جای Gemini استفاده کنیم:

# ❌ کد فعلی - باید fiaetutor.py را تغییر دهیم:
client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/...",  # ❌ Hardcoded!
)
```

**راه حل:**

```python
# ✅ با Protocol (Interface):

class LLMProvider(Protocol):
    async def complete(self, messages, ...): ...

class GeminiProvider(LLMProvider):  # ✅ Implementation 1
    ...

class OpenAIProvider(LLMProvider):  # ✅ Implementation 2 - No changes needed!
    ...

class ClaudeProvider(LLMProvider):  # ✅ Implementation 3 - Just add new!
    ...

# ✅ Service doesn't need to change:
class FIAEService:
    def __init__(self, llm: LLMProvider):  # ✅ Works with any provider!
        self.llm = llm
```

#### ❌ **3. Dependency Inversion Principle**

```python
# ❌ فعلی - وابستگی مستقیم به implementation:
from agent.modules.fiaetutor import client  # ❌ Direct dependency on concrete class

def analyze(...):
    result = client.chat.completions.create(...)  # ❌ Tightly coupled
```

**راه حل:**

```python
# ✅ وابستگی به abstraction:

class FIAEService:
    def __init__(self, llm_provider: LLMProvider):  # ✅ Depends on interface
        self.llm = llm_provider
    
    async def analyze(self, ...):
        result = await self.llm.complete(...)  # ✅ Loosely coupled
```

### 3.2 نقض DRY (Don't Repeat Yourself)

#### مثال 1: تکرار ساخت Client

```python
# fiaetutor.py
client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# fiae_analysis.py
from agent.modules.fiaetutor import client  # ❌ تکرار استفاده

# career.py
from agent.modules.fiaetutor import client  # ❌ تکرار استفاده
```

**هر سه فایل به یک client وابسته‌اند!**

#### مثال 2: تکرار منطق Validation

```python
# api.py - چندین جا:
if not problem.strip():
    return error

if not text:
    return empty_result

if not raw:
    return
```

**باید یک Validator مرکزی باشد:**

```python
class InputValidator:
    @staticmethod
    def validate_text(text: str, min_len: int = 1, max_len: int = 5000) -> str:
        text = text.strip()
        if not text:
            raise ValidationError("Text cannot be empty")
        if len(text) > max_len:
            raise ValidationError(f"Text too long (max {max_len})")
        return text
```

### 3.3 کد Synchronous که باید Async باشد

#### ❌ **مشکل فعلی:**

```python
# فقط یک handler async است:
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):  # ✅ Async
    ...

# اما تمام منطق زیرین sync است:
@app.post("/api/fiae/analyze")
def fiae_analyze(req: FiaeRequest):  # ❌ Sync function!
    result = analyze_problem(...)  # ❌ Sync call!
    return JSONResponse(content=result)

# در fiaetutor.py:
def analyze_problem(...):  # ❌ Sync function
    completion = client.chat.completions.create(...)  # ❌ Blocking I/O!
    return ...
```

**نتیجه:** در FastAPI، این blocking I/O ایجاد می‌کند!

```
Request 1 arrives → analyze_problem() blocks → 
Request 2 arrives → waits for Request 1 ❌
Request 3 arrives → waits for Request 1, 2 ❌
```

**Performance impact:**

| Concurrent Requests | Sync (فعلی) | Async (بهبود یافته) |
|---------------------|-------------|----------------------|
| 1 request | 2s | 2s |
| 10 requests | 20s ❌ | 2s ✅ |
| 100 requests | 200s ❌ | 2s ✅ |

#### ✅ **راه حل:**

```python
# ✅ همه چیز async:

@app.post("/api/fiae/analyze")
async def fiae_analyze(req: FiaeRequest):  # ✅ Async
    result = await fiae_service.analyze_problem(...)  # ✅ Await
    return JSONResponse(content=result)

# در service:
class FIAEAnalysisService:
    async def analyze_problem(self, ...):  # ✅ Async
        result = await self.llm.complete(...)  # ✅ Non-blocking!
        return result

# در provider:
class GeminiProvider:
    async def complete(self, ...):  # ✅ Async
        completion = await self.client.chat.completions.create(...)  # ✅ Async!
        return completion
```

**نتیجه:**
```
Request 1 arrives → starts async call → releases thread
Request 2 arrives → starts async call → releases thread
Request 3 arrives → starts async call → releases thread
All complete in ~2s! ✅
```

### 3.4 Type Safety

#### ❌ **مشکل:**

```python
# استفاده بیش از حد از dict و Any:
def analyze_problem(...) -> dict[str, object]:  # ❌ object is too generic
    return {
        "summary": ...,
        "steps": ...,
        "meta": ...,  # ❌ What's the structure of meta?
    }
```

**مشکلات:**
- IDE نمی‌تواند autocomplete کند
- Type checker نمی‌تواند errors پیدا کند
- Runtime errors محتمل است

#### ✅ **راه حل: Proper Type Hints**

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class AnalysisMeta:
    type: Literal["ok", "error", "quota"]
    lang: Literal["de", "fa", "en"]
    mode: str
    model: str
    cached: bool
    retry_after_seconds: int | None

@dataclass
class AnalysisResult:
    summary: str
    steps: list[str]
    example: str | None
    pseudocode: str | None
    visual: str | None
    meta: AnalysisMeta  # ✅ Specific type!

async def analyze_problem(...) -> AnalysisResult:  # ✅ Clear return type!
    ...
```

**مزایا:**
- ✅ IDE autocomplete
- ✅ Type checking
- ✅ Better documentation
- ✅ Fewer runtime errors

---

## 4️⃣ مسائل بحرانی (Critical Issues)

### 🔴 **1. Memory Leak - Unbounded Cache**

**محل:** `fiaetutor.py`, خط 24

```python
_CACHE: dict[tuple[str, str, str], dict[str, object]] = {}
```

**مشکل:**
- کش هیچ محدودیتی ندارد
- با هر request جدید، کش بزرگ‌تر می‌شود
- در production، RAM تمام می‌شود

**سناریو:**
```
Day 1: 100 requests → 100 cache entries → 5 MB
Day 2: 1000 requests → 1100 entries → 55 MB
Day 30: 30,000 requests → 30,000+ entries → 1.5 GB ❌
```

**اولویت:** 🔴 **بحرانی**

**راه حل:**
```python
class LRUCache:
    def __init__(self, max_size: int = 1000):  # ✅ محدودیت
        self._cache = OrderedDict()
        self.max_size = max_size
    
    async def set(self, key, value):
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # ✅ حذف قدیمی‌ترین
        self._cache[key] = value
```

---

### 🔴 **2. Race Condition - Thread Safety**

**محل:** `fiaetutor.py`, خط 336-343

```python
cache_key = (text, normalized_lang, normalized_mode)

if cache_key in _CACHE:  # ❌ Race condition point 1
    cached_result = copy.deepcopy(_CACHE[cache_key])
    return cached_result

# ... API call ...

_CACHE[cache_key] = copy.deepcopy(result)  # ❌ Race condition point 2
```

**مشکل:**
در محیط concurrent (FastAPI با چند worker):

```
Thread 1: Check cache → Not found
Thread 2: Check cache → Not found
Thread 1: Call API (costs $$)
Thread 2: Call API (costs $$)  ❌ Duplicate!
Thread 1: Save to cache
Thread 2: Save to cache  ❌ Overwrite!
```

**اولویت:** 🔴 **بحرانی در production**

**راه حل:**
```python
class LRUCache:
    def __init__(self):
        self._lock = asyncio.Lock()  # ✅ Thread-safe
    
    async def get(self, key):
        async with self._lock:  # ✅ Lock
            return self._cache.get(key)
    
    async def set(self, key, value):
        async with self._lock:  # ✅ Lock
            self._cache[key] = value
```

---

### 🔴 **3. No Retry Mechanism**

**محل:** `fiaetutor.py`, خط 349+

```python
try:
    content = _call_model([...])
except Exception as e:  # ❌ Gives up immediately!
    return _empty_result(_error_summary(lang), ...)
```

**مشکل:**
- یک network glitch → failure
- API temporary unavailable → failure
- هیچ تلاش مجددی نمی‌کند

**Impact:**
- کاربر خطا می‌بیند
- تجربه کاربری بد
- هزینه API بالا (duplicate requests از user)

**اولویت:** 🟠 **بالا**

**راه حل:**
```python
async def complete(self, ...):
    for attempt in range(self.max_retries):
        try:
            return await self.client.chat.completions.create(...)
        except TemporaryError as e:
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # ✅ Exponential backoff
                continue
            raise
```

---

### 🟡 **4. Database Connection Management**

**محل:** `memory/memory.py`, خط 11

```python
def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)  # ❌ No error handling!
    conn.row_factory = sqlite3.Row
    return conn
```

**مشکل:**
- اگر فایل corrupt باشد → crash
- اگر permission نباشد → crash
- اگر disk full باشد → crash

**اولویت:** 🟡 **متوسط**

**راه حل:**
```python
@asynccontextmanager
async def _get_connection(self):
    try:
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        yield conn
    except sqlite3.DatabaseError as e:
        raise DatabaseConnectionError(f"Database error: {e}")
    finally:
        if conn:
            await conn.close()  # ✅ Always close
```

---

### 🟢 **5. SQL Injection (Low Risk)**

**محل:** `memory/memory.py`, خط 48

```python
conn.execute(
    "INSERT INTO fiae_logs VALUES (?, ?, ?)",  # ✅ Parameterized - GOOD!
    (created_at, problem, answer),
)
```

**وضعیت:** ✅ **این قسمت درست است!**

اما توصیه: در آینده مراقب باشید از string concatenation استفاده نکنید:

```python
# ❌ هرگز این کار را نکنید:
query = f"SELECT * FROM logs WHERE user='{user}'"  # ❌ SQL Injection!

# ✅ همیشه parameterized queries:
query = "SELECT * FROM logs WHERE user=?"
cursor.execute(query, (user,))  # ✅ Safe
```

---

## 5️⃣ برنامه Refactoring

### فاز 1: Foundation (هفته 1-2)

#### 🎯 هدف: ایجاد ساختار پایه

**کارها:**

1. **ایجاد ساختار لایه‌بندی:**
   ```
   agent/
   ├── core/              # ✅ Config, exceptions, types
   ├── domain/            # ✅ Business models, protocols
   ├── infrastructure/    # ✅ LLM, database, cache
   ├── application/       # ✅ Services, use cases
   └── presentation/      # ✅ API, CLI
   ```

2. **تعریف Protocols:**
   - `LLMProvider`
   - `CacheProvider`
   - `FIAERepository`

3. **پیاده‌سازی Core Components:**
   - Async LLM Provider با retry
   - Thread-safe LRU Cache
   - Async SQLite Repository

4. **Configuration Management:**
   - Pydantic Settings
   - .env file support

**Output:** یک کتابخانه پایه که قابل استفاده مجدد است

---

### فاز 2: Service Layer (هفته 3-4)

#### 🎯 هدف: جداسازی Business Logic

**کارها:**

1. **ایجاد Services:**
   ```python
   FIAEAnalysisService
   PlannerService
   CareerAdvisorService
   ```

2. **Dependency Injection Container:**
   ```python
   class Container:
       def __init__(self, settings):
           self.llm_provider = GeminiProvider(...)
           self.cache = LRUCache(...)
           self.repository = AsyncSQLiteRepository(...)
           self.fiae_service = FIAEAnalysisService(
               llm=self.llm_provider,
               cache=self.cache,
               repository=self.repository,
           )
   ```

3. **Prompt Template System:**
   - JSON template files
   - PromptTemplateManager

**Output:** Business logic جدا از infrastructure

---

### فاز 3: API Refactoring (هفته 5-6)

#### 🎯 هدف: Clean API Endpoints

**کارها:**

1. **تبدیل همه endpoints به async:**
   ```python
   @app.post("/api/fiae/analyze")
   async def analyze(...):  # ✅ Async
       result = await service.analyze(...)
       return result
   ```

2. **Error Handling:**
   ```python
   @app.exception_handler(LLMQuotaError)
   async def quota_handler(request, exc):
       return JSONResponse(
           status_code=429,
           headers={"Retry-After": str(exc.retry_after)},
           ...
       )
   ```

3. **Proper Type Hints:**
   ```python
   class AnalyzeRequest(BaseModel):
       problem: str = Field(min_length=1, max_length=5000)
       language: Literal["de", "fa", "en"] = "de"
   ```

**Output:** Clean, type-safe API

---

### فاز 4: Testing (هفته 7)

#### 🎯 هدف: Test Coverage

**کارها:**

1. **Unit Tests:**
   ```python
   async def test_gemini_provider_retry():
       provider = GeminiProvider(...)
       # Mock API to fail first 2 times
       result = await provider.complete(...)
       assert result  # ✅ Should succeed after retry
   ```

2. **Integration Tests:**
   ```python
   async def test_fiae_service():
       container = create_test_container()
       result = await container.fiae_service.analyze(...)
       assert result["summary"]
   ```

3. **Load Tests:**
   ```bash
   # 100 concurrent requests
   locust -f tests/load_test.py --users 100
   ```

**Output:** >80% test coverage

---

### فاز 5: Monitoring & Observability (هفته 8)

#### 🎯 هدف: Production Readiness

**کارها:**

1. **Structured Logging:**
   ```python
   logger.info(
       "LLM call completed",
       extra={
           "model": model,
           "tokens": tokens_used,
           "duration_ms": duration,
           "cached": cached,
       }
   )
   ```

2. **Metrics:**
   ```python
   # Prometheus metrics
   llm_requests_total.inc()
   llm_request_duration.observe(duration)
   cache_hit_rate.set(hit_rate)
   ```

3. **Health Checks:**
   ```python
   @app.get("/health")
   async def health():
       return {
           "status": "ok",
           "database": await db.ping(),
           "llm": await llm.ping(),
           "cache": cache.is_healthy(),
       }
   ```

**Output:** Production-ready monitoring

---

## 6️⃣ نمونه کدهای بهبود یافته

تمام نمونه کدها در پوشه `refactoring_examples/` قرار دارند:

```
refactoring_examples/
├── README_REFACTORING.md          # ✅ راهنمای کامل
├── requirements.txt               # ✅ Dependencies جدید
├── core/
│   ├── config.py                  # ✅ Pydantic Settings
│   ├── container.py               # ✅ DI Container
│   └── exceptions.py              # ✅ Custom Exceptions
├── domain/
│   └── protocols.py               # ✅ Interfaces
├── infrastructure/
│   ├── llm/
│   │   ├── gemini.py              # ✅ Async + Retry + Circuit Breaker
│   │   ├── cache.py               # ✅ Thread-safe LRU
│   │   └── prompt_manager.py     # ✅ Template System
│   └── database/
│       └── sqlite_repository.py  # ✅ Async Repository
├── application/
│   └── services/
│       └── fiae_service.py       # ✅ Clean Business Logic
└── refactored_api.py             # ✅ Clean API Endpoints
```

---

## 📈 نتیجه‌گیری

### وضعیت فعلی:
- 🔴 **معماری:** نیاز به بازطراحی جدی
- 🔴 **Scalability:** محدودیت‌های بحرانی
- 🟡 **Performance:** مشکلات concurrency
- 🟢 **Functionality:** عملکرد پایه خوب

### بعد از Refactoring:
- ✅ **معماری:** Clean Architecture
- ✅ **Scalability:** Multi-worker ready
- ✅ **Performance:** 10x بهبود در concurrent load
- ✅ **Maintainability:** آسان برای توسعه

### تخمین زمان:
- **Refactoring کامل:** 8 هفته
- **MVP بهبود یافته:** 4 هفته
- **Production-ready:** 8-10 هفته

### توصیه نهایی:

**🎯 اولویت 1 (فوری):**
1. Fix memory leak (LRU Cache)
2. Add async/await
3. Add retry mechanism

**🎯 اولویت 2 (این ماه):**
4. Dependency Injection
5. Error handling
6. Type safety

**🎯 اولویت 3 (ماه بعد):**
7. Testing
8. Monitoring
9. Documentation

---

**موفق باشید! 🚀**
