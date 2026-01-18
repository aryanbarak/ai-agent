# API Key Issue - راهنمای حل مشکل

## مشکل: API Key Expired

اگر این خطا را می‌بینید:
```
"API key expired. Please renew the API key."
```

یعنی کلید API Google Gemini شما منقضی شده است.

## راه حل

### 1. دریافت کلید جدید از Google AI Studio

1. به https://aistudio.google.com/app/apikey بروید
2. با اکانت Google خود وارد شوید
3. روی "Create API Key" کلیک کنید
4. کلید جدید را کپی کنید

### 2. تنظیم کلید جدید

#### برای Development (Local):

**Windows PowerShell:**
```powershell
$env:GEMINI_API_KEY="YOUR_NEW_API_KEY_HERE"
```

**Windows CMD:**
```cmd
set GEMINI_API_KEY=YOUR_NEW_API_KEY_HERE
```

**Linux/Mac:**
```bash
export GEMINI_API_KEY="YOUR_NEW_API_KEY_HERE"
```

#### برای Production (بستگی به سرویس deployment دارد):

- **Railway/Render/Vercel**: در Environment Variables تنظیم کنید
- **Docker**: در docker-compose.yml یا Dockerfile
- **Systemd**: در فایل service

### 3. Restart کردن Backend

```powershell
# در پوشه AI Agent
cd "C:\Projects\AI Agent"
& ".\venv\Scripts\Activate.ps1"
$env:GEMINI_API_KEY="YOUR_NEW_API_KEY"
uvicorn agent.api:app --reload --port 8000
```

### 4. تست کردن

برای تست اینکه API key کار می‌کند:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/status" -Method GET
```

خروجی باید این باشد:
```json
{
  "status": "ok",
  "api_key_configured": true,
  "api_key_preview": "AIzaSyA...SeE",
  "message": "API is ready"
}
```

## نکات مهم

1. **هرگز API key را در کد commit نکنید!**
2. از `.env` file برای ذخیره استفاده کنید (که در .gitignore باشد)
3. API key های Google AI Studio رایگان محدودیت دارند (60 requests per minute)
4. برای production از API key های مدیریت شده استفاده کنید

## Troubleshooting

### خطا هنوز وجود دارد
- مطمئن شوید که backend را restart کرده‌اید
- چک کنید که environment variable در همان terminal که uvicorn را run می‌کنید set شده باشد
- با endpoint `/api/status` تست کنید

### API key کار نمی‌کند
- مطمئن شوید که فضای خالی اضافی در ابتدا یا انتهای کلید نیست
- API key باید با `AIzaSy` شروع شود
- بررسی کنید که quota exceeded نشده باشید در https://aistudio.google.com

## لینک‌های مفید

- Google AI Studio: https://aistudio.google.com
- Gemini API Docs: https://ai.google.dev/gemini-api/docs
- API Quotas: https://ai.google.dev/gemini-api/docs/models/gemini#rate-limits
