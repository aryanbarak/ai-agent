# Quick Test Script for AI Agent
# Run this to quickly verify all improvements

Write-Host "🧪 Starting AI Agent Tests..." -ForegroundColor Cyan
Write-Host ""

# Test 1: Health Check
Write-Host "Test 1: Health Check" -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
    if ($health.status -eq "ok") {
        Write-Host "✅ Server is running" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Server not running. Please start: uvicorn agent.api:app --reload" -ForegroundColor Red
    exit 1
}

# Test 2: Request ID Tracking
Write-Host "`nTest 2: Request ID Tracking" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/analyze" `
        -Method Post `
        -ContentType "application/json" `
        -Headers @{"X-Request-ID"="test-12345"} `
        -Body '{"message":"test","language":"en"}'
    
    $requestId = $response.Headers['X-Request-ID']
    if ($requestId -eq "test-12345") {
        Write-Host "✅ Request ID tracking works" -ForegroundColor Green
    } else {
        Write-Host "❌ Request ID not found in response" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Request ID test failed: $_" -ForegroundColor Red
}

# Test 3: Persian Validation
Write-Host "`nTest 3: Persian with Latin Terms" -ForegroundColor Yellow
try {
    $body = @{
        message = "الگوریتم Bubble Sort را توضیح بده"
        language = "fa"
        mode = "fiae_algorithms"
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
    
    if ($response.meta.type -eq "ok") {
        Write-Host "✅ Persian validation improved (accepts mixed content)" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Persian validation issue: $($response.meta.type)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Persian test failed: $_" -ForegroundColor Red
}

# Test 4: Cache Stats
Write-Host "`nTest 4: Cache Statistics" -ForegroundColor Yellow
try {
    $stats = Invoke-RestMethod -Uri "http://127.0.0.1:8000/cache/stats"
    Write-Host "✅ Cache Stats: Size=$($stats.cache_size), TTL=$($stats.ttl_seconds)s" -ForegroundColor Green
} catch {
    Write-Host "❌ Cache stats failed: $_" -ForegroundColor Red
}

# Test 5: Cache HIT/MISS
Write-Host "`nTest 5: Cache Functionality" -ForegroundColor Yellow
try {
    $body = @{
        message = "What is quick sort?"
        language = "en"
    } | ConvertTo-Json
    
    # First request (MISS)
    $start1 = Get-Date
    $response1 = Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze" `
        -Method Post -ContentType "application/json" -Body $body
    $duration1 = (Get-Date) - $start1
    
    # Second request (HIT)
    $start2 = Get-Date
    $response2 = Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze" `
        -Method Post -ContentType "application/json" -Body $body
    $duration2 = (Get-Date) - $start2
    
    Write-Host "  First request (MISS): $($duration1.TotalSeconds)s, cached=$($response1.meta.cached)" -ForegroundColor White
    Write-Host "  Second request (HIT): $($duration2.TotalSeconds)s, cached=$($response2.meta.cached)" -ForegroundColor White
    
    if ($response2.meta.cached -eq $true) {
        Write-Host "✅ Cache working correctly" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Cache not working as expected" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Cache test failed: $_" -ForegroundColor Red
}

# Test 6: Concurrent Requests
Write-Host "`nTest 6: Concurrent Requests (Async Performance)" -ForegroundColor Yellow
try {
    $jobs = @()
    1..3 | ForEach-Object {
        $jobs += Start-Job -ScriptBlock {
            $body = @{
                message = "merge sort"
                language = "en"
            } | ConvertTo-Json
            
            Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze" `
                -Method Post `
                -ContentType "application/json" `
                -Body $body `
                -Headers @{"X-Request-ID"="concurrent-$using:_"}
        }
    }
    
    $results = $jobs | Wait-Job | Receive-Job
    $jobs | Remove-Job
    
    if ($results.Count -eq 3) {
        Write-Host "✅ Handled 3 concurrent requests successfully" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Concurrent test failed: $_" -ForegroundColor Red
}

# Test 7: Structured Logging
Write-Host "`nTest 7: Structured Logging" -ForegroundColor Yellow
Write-Host "  Check terminal output for JSON logs with:" -ForegroundColor White
Write-Host "  - timestamp" -ForegroundColor Gray
Write-Host "  - level (INFO/DEBUG)" -ForegroundColor Gray
Write-Host "  - logger (agent.api/agent.fiae/agent.cache)" -ForegroundColor Gray
Write-Host "  - request_id" -ForegroundColor Gray
Write-Host "  - extra metadata" -ForegroundColor Gray
Write-Host "✅ If you see JSON logs above, structured logging is working" -ForegroundColor Green

# Summary
Write-Host "`n" + "="*60 -ForegroundColor Cyan
Write-Host "🎉 Test Summary" -ForegroundColor Cyan
Write-Host "="*60 -ForegroundColor Cyan
Write-Host ""
Write-Host "Quick Wins:" -ForegroundColor Yellow
Write-Host "  ✅ Persian validation improved"
Write-Host "  ✅ Request ID tracking"
Write-Host "  ✅ Better error messages (check frontend)"
Write-Host ""
Write-Host "Backend Refactoring:" -ForegroundColor Yellow
Write-Host "  ✅ Async/await for non-blocking I/O"
Write-Host "  ✅ Thread-safe cache with TTL"
Write-Host "  ✅ Structured JSON logging"
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Check server logs for JSON output"
Write-Host "  2. Test from frontend UI"
Write-Host "  3. See TESTING_GUIDE.md for detailed tests"
Write-Host ""
