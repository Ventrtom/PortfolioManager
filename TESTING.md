# Testing Guide

This document describes the automated testing setup for Portfolio Manager.

## Test Scripts

### 1. End-to-End Tests (`test-e2e.ps1`)

Comprehensive test suite that validates the entire application stack.

**Usage:**
```powershell
.\test-e2e.ps1
```

**With verbose output:**
```powershell
.\test-e2e.ps1 -Verbose
```

**What it tests:**
- Prerequisites (Python, Node.js, npm)
- Project structure (all required files and directories)
- Backend virtual environment
- Frontend node_modules and key dependencies
- Backend service startup and health
- Frontend service startup
- All API endpoints (health, docs, transactions, portfolio)
- Frontend accessibility and content
- Proper cleanup of test services

**Output:**
- Console output with color-coded results
- JSON file with detailed test results (saved as `test-results-YYYYMMDD-HHMMSS.json`)
- Exit code 0 on success, 1 on failure

### 2. Quick Tests (`test-quick.ps1`)

Fast validation script for quick checks during development.

**Usage:**
```powershell
.\test-quick.ps1
```

**What it tests:**
- Prerequisites availability
- Dependencies installation
- Backend startup and health endpoint
- Frontend startup
- Key API endpoints

**Execution time:** ~30 seconds (vs. ~60 seconds for full E2E tests)

## When to Run Tests

### Before Committing Code
Run the full E2E test suite to ensure nothing is broken:
```powershell
.\test-e2e.ps1
```

### During Development
Use quick tests for faster iteration:
```powershell
.\test-quick.ps1
```

### After Making Changes To:
- Startup scripts (start.ps1, stop.ps1)
- Backend API endpoints
- Frontend components that affect loading
- Dependencies (requirements.txt, package.json)
- Project structure

### Continuous Integration
The test scripts can be integrated into CI/CD pipelines:
```powershell
# In your CI script
.\test-e2e.ps1
if ($LASTEXITCODE -ne 0) {
    exit 1
}
```

## Test Results

### Understanding the Output

**Green [PASS]**: Test passed successfully
**Red [FAIL]**: Test failed - review the error message
**Yellow [WARN]**: Warning - may not be critical but worth checking

### Test Result Files

Each E2E test run creates a JSON file with detailed results:
- Location: `test-results-YYYYMMDD-HHMMSS.json`
- Contains: Test name, pass/fail status, message, timestamp
- Useful for debugging and tracking test history

Example:
```json
[
  {
    "TestName": "Python Installation",
    "Passed": true,
    "Message": "Python 3.13.5",
    "Timestamp": "2025-01-10 14:30:45"
  }
]
```

## Troubleshooting Test Failures

### "Backend failed to start"
1. Check if port 8000 is already in use: `Get-NetTCPConnection -LocalPort 8000`
2. Verify virtual environment exists: `Test-Path backend\venv`
3. Check Python dependencies: `.\backend\venv\Scripts\pip.exe list`

### "Frontend failed to start"
1. Check if port 5173 is already in use: `Get-NetTCPConnection -LocalPort 5173`
2. Verify node_modules exists: `Test-Path frontend\node_modules`
3. Try manual start: `cd frontend; npm run dev`

### "API endpoint failed"
1. Check backend logs in the minimized window
2. Test endpoint manually: `Invoke-WebRequest -Uri http://localhost:8000/health`
3. Verify database is accessible

### Tests hang or timeout
1. Increase timeout values in test scripts if system is slow
2. Check antivirus isn't blocking processes
3. Ensure no firewall rules blocking localhost connections

## Adding New Tests

To add tests to `test-e2e.ps1`:

```powershell
Write-TestCase "Your test description"
try {
    # Your test logic here
    $result = Test-Something

    if ($result) {
        Write-TestPass "Test passed with result: $result"
        Record-TestResult "Your Test Name" $true $result
    } else {
        Write-TestFail "Test failed"
        Record-TestResult "Your Test Name" $false "Failure reason"
    }
} catch {
    Write-TestFail "Test error: $_"
    Record-TestResult "Your Test Name" $false $_
}
```

## Best Practices

1. **Run tests before pushing code** to catch issues early
2. **Review test results files** to track patterns in failures
3. **Update tests** when adding new features or endpoints
4. **Keep services stopped** between test runs for clean state
5. **Use quick tests** during active development
6. **Use full E2E tests** before commits and releases

## Integration with Git

Add to your `.git/hooks/pre-commit` to run tests automatically:
```bash
#!/bin/sh
powershell.exe -ExecutionPolicy Bypass -File ./test-quick.ps1
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

## Future Enhancements

Planned improvements for the test suite:
- [ ] Database transaction tests
- [ ] Natural language parser tests
- [ ] Portfolio calculation validation
- [ ] Browser automation tests (Selenium/Playwright)
- [ ] Performance benchmarks
- [ ] API load testing
- [ ] Integration with GitHub Actions
