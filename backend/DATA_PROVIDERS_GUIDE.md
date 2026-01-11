# Multi-Provider Market Data System

## Overview

The Portfolio Manager uses a **multi-provider fallback system** to fetch stock market data. This ensures high reliability even when individual data sources experience rate limiting or outages.

## How It Works

### Automatic Fallback Chain

When enriching stock data, the system tries providers in this order:

1. **yfinance (Yahoo Finance)** - Primary provider, no API key needed
2. **Alpha Vantage** - Free tier fallback (if API key provided)
3. **Finnhub** - Free tier fallback (if API key provided)
4. **Financial Modeling Prep** - Free tier fallback (if API key provided)

**If one provider fails, the system automatically tries the next one.**

### Intelligent Rate Limiting

Each provider has built-in rate limiting to prevent API abuse:

- **yfinance**: 500ms between requests
- **Alpha Vantage**: 12 seconds between requests (free tier: 25/day)
- **Finnhub**: 1 second between requests (free tier: 60/minute)
- **Financial Modeling Prep**: 500ms between requests (free tier: 250/day)

### Caching

- Database caching for 7 days to minimize API calls
- Failed ticker cache with exponential backoff (prevents retry storms)
- Provider-specific failure tracking (skips failed providers temporarily)

## Setup Guide

### Minimum Setup (Works Out of the Box)

**No configuration needed!** The system works immediately with yfinance as the primary provider.

### Recommended Setup (Better Reliability)

For improved reliability when Yahoo Finance is rate limited, add free API keys for backup providers:

#### 1. Alpha Vantage (25 requests/day)

```bash
# Get free API key from: https://www.alphavantage.co/support/#api-key
# Add to backend/.env:
ALPHA_VANTAGE_API_KEY=your-key-here
```

**Why use it:** Good for occasional lookups when Yahoo Finance is down

#### 2. Finnhub (60 calls/minute)

```bash
# Get free API key from: https://finnhub.io/register
# Add to backend/.env:
FINNHUB_API_KEY=your-key-here
```

**Why use it:** High rate limit for bulk operations

#### 3. Financial Modeling Prep (250 requests/day)

```bash
# Get free API key from: https://site.financialmodelingprep.com/developer/docs/
# Add to backend/.env:
FMP_API_KEY=your-key-here
```

**Why use it:** Good balance of rate limits and data quality

### Full Setup with AI Resolution

For maximum success rate with unusual ticker symbols:

```bash
# Get API key from: https://console.anthropic.com/
# Add to backend/.env:
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

**Why use it:** Uses AI to research and resolve broker-specific ticker symbols (e.g., "GEO.US" → "GEO")

## Configuration

### Environment Variables

Create a `backend/.env` file based on `backend/.env.example`:

```bash
# Copy the example file
cp backend/.env.example backend/.env

# Edit with your API keys
# Note: All keys are OPTIONAL - system works with just yfinance
```

### Example .env File

```env
# Optional: AI ticker resolution
ANTHROPIC_API_KEY=sk-ant-your-key

# Optional: Backup data providers
ALPHA_VANTAGE_API_KEY=your-av-key
FINNHUB_API_KEY=your-finnhub-key
FMP_API_KEY=your-fmp-key
```

## Testing

### Check Active Providers

The system logs which providers are active on startup:

```
INFO:services.multi_provider_data_service:Initialized MultiProviderDataService with 4 active providers: ['yfinance', 'AlphaVantage', 'Finnhub', 'FMP']
```

### Test Stock Enrichment

1. Start the backend
2. Open the Stocks page in the UI
3. Add a new stock (e.g., "AAPL")
4. Check backend logs to see which provider succeeded

Example logs:

```
INFO:services.multi_provider_data_service:Trying yfinance for AAPL
INFO:services.multi_provider_data_service:✓ Successfully fetched AAPL from yfinance
```

If yfinance is rate limited:

```
WARNING:services.multi_provider_data_service:yfinance: Rate limited - AAPL
INFO:services.multi_provider_data_service:Trying AlphaVantage for AAPL
INFO:services.multi_provider_data_service:✓ Successfully fetched AAPL from AlphaVantage
```

## Provider Comparison

| Provider | Free Tier Limit | API Key Required | Best For |
|----------|----------------|------------------|----------|
| **yfinance** | Unlimited* | No | Daily use, bulk operations |
| **Alpha Vantage** | 25/day | Yes | Occasional fallback |
| **Finnhub** | 60/minute | Yes | High-volume periods |
| **FMP** | 250/day | Yes | Regular fallback |

*Subject to Yahoo Finance rate limiting

## Troubleshooting

### "Too Many Requests" Errors

**Symptom:** `429 Client Error: Too Many Requests`

**Solutions:**
1. Add backup API keys (Alpha Vantage, Finnhub, FMP)
2. Wait 15 minutes for yfinance rate limits to reset
3. System automatically switches to backup providers

### All Providers Failed

**Symptom:** "All providers failed for TICKER"

**Possible causes:**
1. Invalid ticker symbol → Try AI resolution (add ANTHROPIC_API_KEY)
2. All providers rate limited → Wait and retry
3. Network/firewall issues → Check internet connection

**Solution:**
- Add more API keys for redundancy
- Use the "Retry Enrichment" button in the UI
- Manually enter data if needed

### API Key Not Working

**Check:**
1. Key is in `backend/.env` file (not `.env.example`)
2. No extra spaces or quotes around the key
3. Backend was restarted after adding the key
4. Key is valid (not expired)

## Performance Tips

### Minimize API Calls

1. **Use caching:** Data is cached for 7 days automatically
2. **Bulk operations:** System handles rate limiting automatically
3. **Manual override:** For problematic tickers, manually enter data

### Optimize for Your Usage

**Light usage (< 10 stocks/day):**
- Just use yfinance (no additional setup needed)

**Medium usage (10-50 stocks/day):**
- Add Alpha Vantage OR Finnhub for backup

**Heavy usage (50+ stocks/day):**
- Add all providers (Alpha Vantage + Finnhub + FMP)
- Consider paid API tiers for higher limits

## Data Provider Details

### yfinance (Yahoo Finance)
- **Pros:** Free, no API key, comprehensive data
- **Cons:** Subject to rate limiting, unofficial API
- **Data:** Company info, prices, volume, market cap, sector, industry

### Alpha Vantage
- **Pros:** Official API, reliable
- **Cons:** Low free tier limit (25/day)
- **Data:** Company overview, fundamentals

### Finnhub
- **Pros:** High rate limit (60/min), good for bulk
- **Cons:** Limited free tier features
- **Data:** Company profile, basic financials

### Financial Modeling Prep
- **Pros:** Good balance of features and limits
- **Cons:** Some features require paid tier
- **Data:** Comprehensive company profiles, financials

## Support

If you encounter issues:
1. Check backend logs for detailed error messages
2. Verify API keys in `.env` file
3. Test with a common ticker (e.g., "AAPL") first
4. Try the "Retry Enrichment" button in the UI

For persistent issues, the system will flag stocks as "failed" and you can manually enter the data via inline editing.
