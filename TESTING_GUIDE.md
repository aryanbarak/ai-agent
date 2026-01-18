# Test Plan for AI Agent Improvements

## Prerequisites
1. Start the backend server:
```bash
cd "C:\Projects\AI Agent"
& "C:/Projects/AI Agent/venv/Scripts/uvicorn.exe" agent.api:app --reload --host 127.0.0.1 --port 8000
```

2. Start the frontend (optional):
```bash
cd "C:\Projects\dailyflow"
npm run dev
```

---

## Test 1: Persian Validation (Quick Win 1)

### Before: Persian responses with Latin terms were rejected
### After: Mixed Persian + Latin terms accepted

**Test Command:**
```bash
curl -X POST "http://127.0.0.1:8000/analyze" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: test-persian-1" `
  -d '{
    "message": "الگوریتم Bubble Sort را توضیح بده",
    "language": "fa",
    "mode": "fiae_algorithms"
  }'
```

**Expected Result:**
- ✅ Should return Persian response with technical terms like "Bubble Sort", "O(n²)"
- ✅ `meta.type` should be "ok", not "error"
- ✅ No language mismatch errors

---

## Test 2: Request ID Tracking (Quick Win 2)

### Test that request IDs flow through the entire system

**Test Command:**
```bash
curl -X POST "http://127.0.0.1:8000/analyze" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: my-custom-request-123" `
  -d '{"message": "bubble sort", "language": "en"}' `
  -i
```

**Expected Result:**
- ✅ Response header contains: `X-Request-ID: my-custom-request-123`
- ✅ Response body `meta.request_id` = "my-custom-request-123"
- ✅ Logs show: `{"request_id": "my-custom-request-123", ...}`

**Check Logs:**
Look for JSON logs in terminal with request_id field

---

## Test 3: Better Error Messages (Quick Win 3)

### Test multilingual error handling

**Test Network Error (stop backend first):**
```bash
# Stop backend, then from frontend console:
await askLearnAI({message: "test", mode: "fiae_algorithms", language: "fa"})
```

**Expected Result:**
```json
{
  "title": "خطای اتصال",
  "message": "سرور AI در دسترس نیست.",
  "action": "لطفاً اتصال اینترنت خود را بررسی کنید.",
  "canRetry": true
}
```

---

## Test 4: Async Performance (Backend Refactoring)

### Test concurrent requests handling

**Create test file: `test_concurrent.ps1`**
```powershell
# Send 5 concurrent requests
$jobs = @()
1..5 | ForEach-Object {
    $jobs += Start-Job -ScriptBlock {
        $num = $using:_
        $body = @{
            message = "What is merge sort?"
            language = "en"
            mode = "fiae_algorithms"
        } | ConvertTo-Json
        
        $start = Get-Date
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze" `
            -Method Post `
            -ContentType "application/json" `
            -Body $body `
            -Headers @{"X-Request-ID"="concurrent-$num"}
        $end = Get-Date
        
        [PSCustomObject]@{
            RequestID = "concurrent-$num"
            Duration = ($end - $start).TotalSeconds
            Cached = $response.meta.cached
        }
    }
}

# Wait for all jobs and show results
$jobs | Wait-Job | Receive-Job | Format-Table -AutoSize
$jobs | Remove-Job
```

**Run test:**
```bash
.\test_concurrent.ps1
```

**Expected Result:**
- ✅ All 5 requests complete successfully
- ✅ First request NOT cached (`cached: false`)
- ✅ Requests 2-5 should be cached (`cached: true`)
- ✅ Cached requests much faster (< 0.1s vs 2-3s)

---

## Test 5: Thread-Safe Cache

### Test cache operations

**Test Cache Stats:**
```bash
curl http://127.0.0.1:8000/cache/stats
```

**Expected Result:**
```json
{
  "cache_size": 1,
  "expired_cleared": 0,
  "ttl_seconds": 3600
}
```

**Test Cache HIT:**
```bash
# First request (cache MISS)
curl -X POST "http://127.0.0.1:8000/analyze" `
  -H "Content-Type: application/json" `
  -d '{"message": "insertion sort", "language": "en"}'

# Second request (cache HIT)
curl -X POST "http://127.0.0.1:8000/analyze" `
  -H "Content-Type: application/json" `
  -d '{"message": "insertion sort", "language": "en"}'
```

**Check Logs:**
```json
{"level":"DEBUG","logger":"agent.cache","message":"Cache MISS",...}
{"level":"DEBUG","logger":"agent.cache","message":"Cache SET",...}
{"level":"DEBUG","logger":"agent.cache","message":"Cache HIT",...}
```

---

## Test 6: Structured Logging

### Verify JSON logs format

**Send a request:**
```bash
curl -X POST "http://127.0.0.1:8000/analyze" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: log-test-123" `
  -d '{"message": "quick sort", "language": "de"}'
```

**Check Terminal Output:**
Should see JSON logs like:
```json
{"timestamp":"2026-01-18T12:34:56Z","level":"INFO","logger":"agent.api","message":"POST /analyze - START","request_id":"log-test-123","extra":{"method":"POST","path":"/analyze"}}
{"timestamp":"2026-01-18T12:34:56Z","level":"DEBUG","logger":"agent.fiae","message":"Analyzing problem","extra":{"language":"de","mode":"fiae_algorithms","text_length":10}}
{"timestamp":"2026-01-18T12:34:58Z","level":"INFO","logger":"agent.api","message":"POST /analyze - COMPLETED","request_id":"log-test-123","extra":{"duration_seconds":2.123,"status_code":200}}
```

**Verify:**
- ✅ All logs are valid JSON
- ✅ Contains `timestamp`, `level`, `logger`, `message`
- ✅ Request ID present in all related logs
- ✅ Extra context included

---

## Test 7: Frontend Integration

### Test from DailyFlow UI

1. Open browser: http://localhost:8080
2. Navigate to "Learn with AI"
3. Set language to **FA** (فارسی)
4. Send message: "الگوریتم Bubble Sort چیست؟"

**Expected Result:**
- ✅ Response in Persian with technical terms
- ✅ No error about language mismatch
- ✅ ErrorAlert shows proper Persian messages on errors

**Test Error Handling:**
1. Stop backend server
2. Send a message from frontend
3. Should see:
```
عنوان: خطای اتصال
پیام: سرور AI در دسترس نیست.
عملیات: لطفاً اتصال اینترنت خود را بررسی کنید.
[Retry Button]
```

---

## Test 8: Cache TTL

### Test cache expiration (advanced)

**Modify cache TTL for testing:**
```python
# In fiaetutor.py, temporarily change:
_CACHE = AsyncCache(ttl_seconds=10)  # 10 seconds for testing
```

**Test:**
```bash
# Send request
curl -X POST "http://127.0.0.1:8000/analyze" -H "Content-Type: application/json" -d '{"message": "test", "language": "en"}'

# Wait 5 seconds, send again (should be cached)
Start-Sleep -Seconds 5
curl -X POST "http://127.0.0.1:8000/analyze" -H "Content-Type: application/json" -d '{"message": "test", "language": "en"}'

# Wait 11 seconds total, send again (cache expired)
Start-Sleep -Seconds 6
curl -X POST "http://127.0.0.1:8000/analyze" -H "Content-Type: application/json" -d '{"message": "test", "language": "en"}'
```

**Expected:**
- Request 2: `cached: true`
- Request 3: `cached: false` (expired)

---

## Test 9: Load Test (Optional)

### Test under load

**Install Apache Bench (if needed):**
```bash
# Or use existing tool
```

**Simple load test with PowerShell:**
```powershell
# Send 50 requests
1..50 | ForEach-Object -Parallel {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze" `
        -Method Post `
        -ContentType "application/json" `
        -Body '{"message":"test","language":"en"}' | Out-Null
    Write-Host "Request $_ completed"
} -ThrottleLimit 10
```

**Expected:**
- ✅ All requests succeed
- ✅ Server remains responsive
- ✅ No memory leaks
- ✅ Cache working correctly

---

## Test Summary Checklist

- [ ] Persian validation accepts mixed content
- [ ] Request IDs flow through system
- [ ] Error messages multilingual and user-friendly
- [ ] Async handles concurrent requests
- [ ] Cache HIT/MISS/SET working
- [ ] Cache TTL expires correctly
- [ ] Structured JSON logs
- [ ] Request timing logged
- [ ] Frontend integration works
- [ ] No performance degradation

---

## Troubleshooting

### Server won't start
```bash
# Check for errors
& "C:/Projects/AI Agent/venv/Scripts/python.exe" -m agent.api
```

### No JSON logs
```bash
# Check logger setup
& "C:/Projects/AI Agent/venv/Scripts/python.exe" -c "from agent.utils.logger import api_logger; api_logger.info('test')"
```

### Cache not working
```bash
# Check cache stats
curl http://127.0.0.1:8000/cache/stats
```

---

## Success Criteria

✅ All tests pass
✅ No errors in logs
✅ Performance improved with caching
✅ Concurrent requests handled correctly
✅ Error messages clear and actionable
