"""
Manual test of problematic tickers from console output
Testing: KMI, WMB, COG, GEO, CPTA
"""
import sys
import os
sys.path.insert(0, '.')

# Fix Windows encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

import yfinance as yf
import requests
import json

# API Keys
ALPHA_VANTAGE_API_KEY = "690106MKPFI7Y1G5"
FINNHUB_API_KEY = "d5hqkbpr01qu7bqpesfgd5hqkbpr01qu7bqpesg0"
FMP_API_KEY = "npjXZWsEwELzgSV1YXhTVPdvUfFh3UL5"

# Tickers failing in console
TICKERS_TO_TEST = ['KMI', 'WMB', 'COG', 'GEO', 'CPTA']

print("=" * 80)
print("MANUAL TICKER TESTING")
print("=" * 80)

for ticker in TICKERS_TO_TEST:
    print(f"\n\n{'='*80}")
    print(f"Testing: {ticker}")
    print("=" * 80)

    # Test 1: yfinance
    print("\n1. YFINANCE TEST:")
    try:
        stock = yf.Ticker(ticker)

        # Try history
        print("   - Trying .history(period='1d')...")
        hist = stock.history(period="1d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            print(f"   [OK] SUCCESS via history: ${price:.2f}")
        else:
            print("   [FAIL] History empty")

            # Try info
            print("   - Trying .info...")
            info = stock.info
            if info and len(info) > 5:
                price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                if price:
                    print(f"   [OK] SUCCESS via info: ${price:.2f}")
                    print(f"   Company: {info.get('longName', 'N/A')}")
                else:
                    print("   [FAIL] No price in info")
            else:
                print(f"   [FAIL] Info empty or minimal: {len(info) if info else 0} fields")

    except Exception as e:
        print(f"   [FAIL] ERROR: {str(e)[:200]}")

    # Test 2: Alpha Vantage
    print("\n2. ALPHA VANTAGE TEST:")
    try:
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if 'Global Quote' in data and data['Global Quote']:
            price = data['Global Quote'].get('05. price')
            print(f"   [OK] SUCCESS: ${price}")
        elif 'Note' in data or 'Information' in data:
            print(f"   [WARN]  RATE LIMITED: {data.get('Note') or data.get('Information')}")
        else:
            print(f"   [FAIL] NO DATA: {json.dumps(data, indent=2)[:200]}")

    except Exception as e:
        print(f"   [FAIL] ERROR: {str(e)[:200]}")

    # Test 3: Finnhub
    print("\n3. FINNHUB TEST:")
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get('c') and data['c'] > 0:
            print(f"   [OK] SUCCESS: ${data['c']:.2f}")
            print(f"   Additional data: o={data.get('o')}, h={data.get('h')}, l={data.get('l')}")
        else:
            print(f"   [FAIL] NO DATA: {json.dumps(data, indent=2)}")

    except Exception as e:
        print(f"   [FAIL] ERROR: {str(e)[:200]}")

    # Test 4: Financial Modeling Prep (v4 endpoint)
    print("\n4. FMP TEST:")
    try:
        url = f"https://financialmodelingprep.com/api/v4/quote-short/{ticker}?apikey={FMP_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data and isinstance(data, list) and len(data) > 0:
            quote = data[0]
            price = quote.get('price')
            if price and price > 0:
                print(f"   [OK] SUCCESS: ${price}")
            else:
                print(f"   [FAIL] NO DATA: price={price}")
        else:
            print(f"   [FAIL] NO DATA: {json.dumps(data, indent=2)[:200]}")

    except Exception as e:
        print(f"   [FAIL] ERROR: {str(e)[:200]}")

print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("\nIf yfinance fails but other providers work, it's a rate limiting issue.")
print("If all providers fail, the ticker may be delisted or have symbol issues.")
