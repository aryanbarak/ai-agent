# Production Debug Checklist for barakzai.cloud

## 🔍 Problem: Black screen → Error message after refresh

### Symptoms from screenshots:
- Persian question: "الگوریتم انتخاب را توضیح بده"
- German question: "wie ist die selection sort algorithm"
- Both get error: "Entschuldigung, ich konnte keine Antwort generieren. Bitte versuchen Sie es erneut."

---

## 🚨 Priority Checks (in order):

### 1. Backend API Status
```bash
# SSH to AWS server
ssh -i ~/.ssh/your-key.pem ubuntu@your-ec2-ip

# Check if uvicorn/gunicorn is running
sudo systemctl status ai-agent
# OR
ps aux | grep uvicorn

# Check backend logs
sudo journalctl -u ai-agent -n 100 --no-pager
# OR
tail -f /path/to/logs/uvicorn.log
```

**Expected**: Backend should be running on port 8000

---

### 2. Environment Variables
```bash
# Check if GEMINI_API_KEY is set
cat /etc/systemd/system/ai-agent.service
# OR
cat ~/.env  # if using .env file

# Verify the key is loaded
sudo systemctl show ai-agent | grep Environment
```

**Expected**: Should see `GEMINI_API_KEY=AIza...`

---

### 3. CORS Configuration
The backend needs to expose `X-Request-ID` header.

Check `agent/api.py` has:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://barakzai.cloud"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],  # ← CRITICAL!
)
```

---

### 4. Nginx Configuration
```bash
# Check nginx config
sudo cat /etc/nginx/sites-enabled/dailyflow
sudo cat /etc/nginx/sites-enabled/ai-agent

# Test nginx config
sudo nginx -t

# Check nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

**Expected Nginx config for backend**:
```nginx
location /api {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # CORS headers (if backend doesn't handle)
    add_header Access-Control-Expose-Headers "X-Request-ID";
}
```

---

### 5. Frontend API Configuration
Check `src/config/aiAgent.ts`:
```typescript
export const AI_AGENT_CONFIG = {
  baseUrl: "https://barakzai.cloud/api",  // ← Should match production domain
  endpoints: {
    analyze: "/analyze",
    health: "/health",
  },
};
```

---

### 6. Browser Console Errors
```javascript
// Open browser DevTools (F12) on barakzai.cloud/learn-ai
// Check Console tab for errors like:

// ❌ CORS error:
// "Access to fetch at 'https://barakzai.cloud/api/analyze' from origin 'https://barakzai.cloud' 
//  has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present"

// ❌ Network error:
// "Failed to fetch"
// "ERR_CONNECTION_REFUSED"

// ❌ 500 Internal Server Error:
// Check backend logs for Python traceback

// ❌ 502 Bad Gateway:
// Backend is not running or nginx can't reach it
```

---

## 🔧 Common Fixes:

### Fix 1: Backend Not Running
```bash
# Restart backend service
sudo systemctl restart ai-agent
sudo systemctl status ai-agent

# If using PM2
pm2 restart ai-agent
pm2 logs ai-agent
```

---

### Fix 2: Missing GEMINI_API_KEY
```bash
# Edit systemd service
sudo nano /etc/systemd/system/ai-agent.service

# Add under [Service]
Environment="GEMINI_API_KEY=AIzaSy..."

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart ai-agent
```

---

### Fix 3: CORS Not Exposing X-Request-ID
Edit `agent/api.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://barakzai.cloud",
        "http://localhost:5173",  # for dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],  # ← ADD THIS
)
```

Then:
```bash
# Rebuild and redeploy
git pull
sudo systemctl restart ai-agent
```

---

### Fix 4: Async OpenAI Issues in Production
If the async changes broke production, check:
```bash
# Verify openai package version
pip list | grep openai
# Should be: openai==1.61.1 or higher

# Check if AsyncOpenAI works
python3 -c "from openai import AsyncOpenAI; print('OK')"
```

---

### Fix 5: Frontend Environment Variables
Check `.env.production` or build config:
```env
VITE_AI_AGENT_BASE_URL=https://barakzai.cloud/api
```

Rebuild frontend:
```bash
cd /path/to/dailyflow
npm run build
# Copy dist/ to nginx webroot
```

---

## 🧪 Quick Test Commands:

### Test Backend Health:
```bash
curl https://barakzai.cloud/api/health
# Expected: {"status":"ok","version":"1.0.0"}
```

### Test Backend Analyze Endpoint:
```bash
curl -X POST https://barakzai.cloud/api/analyze \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-123" \
  -d '{"message":"test","language":"en","mode":"fiae_general"}'
  
# Expected: JSON response with "answer" field
# Check for X-Request-ID in response headers:
curl -i -X POST https://barakzai.cloud/api/analyze \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-123" \
  -d '{"message":"test","language":"en","mode":"fiae_general"}'
```

### Test CORS:
```bash
curl -X OPTIONS https://barakzai.cloud/api/analyze \
  -H "Origin: https://barakzai.cloud" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type,X-Request-ID" \
  -v
  
# Expected headers in response:
# Access-Control-Allow-Origin: https://barakzai.cloud
# Access-Control-Expose-Headers: X-Request-ID
```

---

## 📋 Debugging Steps:

1. **SSH to AWS server** and check all services are running
2. **Check backend logs** for Python errors/tracebacks
3. **Verify GEMINI_API_KEY** is set in environment
4. **Test API directly** with curl commands above
5. **Check browser console** for JavaScript errors
6. **Verify nginx** is proxying correctly to backend
7. **Check CORS headers** are properly set

---

## 💡 Most Likely Causes (ranked):

1. ⭐⭐⭐ **Backend not running** or crashed on startup
2. ⭐⭐⭐ **GEMINI_API_KEY missing** in production environment
3. ⭐⭐ **CORS not exposing X-Request-ID** header
4. ⭐⭐ **Nginx misconfiguration** (wrong proxy_pass)
5. ⭐ **Frontend pointing to wrong API URL**
6. ⭐ **AsyncOpenAI import error** (wrong Python version or package not installed)

---

## 🚀 Next Steps:

Run these commands on your AWS server and share the output:

```bash
# 1. Check backend status
sudo systemctl status ai-agent

# 2. Check recent logs
sudo journalctl -u ai-agent -n 50 --no-pager

# 3. Test health endpoint
curl http://127.0.0.1:8000/health

# 4. Test analyze endpoint locally
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"message":"test","language":"en","mode":"fiae_general"}'
```

Then check browser console (F12) on https://barakzai.cloud/learn-ai and share any errors.
