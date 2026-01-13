"""
Test all tickers against multiple data providers to identify issues
"""
import sys
import os
sys.path.insert(0, '.')

# Fix encoding for Windows console
if os.name == 'nt':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

import yfinance as yf
import requests
from datetime import date
import json
from models.database import SessionLocal, Stock
from sqlalchemy import distinct

# API Keys from .env
ALPHA_VANTAGE_API_KEY = "690106MKPFI7Y1G5"
FINNHUB_API_KEY = "d5hqkbpr01qu7bqpesfgd5hqkbpr01qu7bqpesg0"
FMP_API_KEY = "npjXZWsEwELzgSV1YXhTVPdvUfFh3UL5"

# Get all tickers
db = SessionLocal()
from models.database import Transaction
transaction_tickers = db.query(distinct(Transaction.ticker)).filter(Transaction.ticker.isnot(None)).all()
transaction_tickers = [t[0] for t in transaction_tickers if t[0]]
stock_tickers = db.query(Stock.ticker).all()
stock_tickers = [s[0] for s in stock_tickers]
all_tickers = sorted(set(transaction_tickers + stock_tickers))
db.close()

print(f"Testing {len(all_tickers)} tickers across 4 providers...\n")
print("=" * 80)

results = {}

for ticker in all_tickers:
    print(f"\n🔍 Testing: {ticker}")
    results[ticker] = {
        'yfinance': False,
        'alpha_vantage': False,
        'finnhub': False,
        'fmp': False,
        'details': {}
    }

    # Test 1: yfinance
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if info and len(info) > 1:  # yfinance returns {'trailingPegRatio': None} for invalid tickers
            results[ticker]['yfinance'] = True
            results[ticker]['details']['yfinance'] = f"✅ OK - {info.get('longName', 'N/A')}"
            print(f"  ✅ yfinance: {info.get('longName', ticker)}")
        else:
            results[ticker]['details']['yfinance'] = "❌ No data (likely delisted)"
            print(f"  ❌ yfinance: No data")
    except Exception as e:
        results[ticker]['details']['yfinance'] = f"❌ Error: {str(e)[:50]}"
        print(f"  ❌ yfinance: {str(e)[:50]}")

    # Test 2: Alpha Vantage
    try:
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if 'Global Quote' in data and data['Global Quote']:
            results[ticker]['alpha_vantage'] = True
            price = data['Global Quote'].get('05. price', 'N/A')
            results[ticker]['details']['alpha_vantage'] = f"✅ OK - Price: ${price}"
            print(f"  ✅ Alpha Vantage: ${price}")
        else:
            results[ticker]['details']['alpha_vantage'] = "❌ No data"
            print(f"  ❌ Alpha Vantage: No data")
    except Exception as e:
        results[ticker]['details']['alpha_vantage'] = f"❌ Error: {str(e)[:50]}"
        print(f"  ❌ Alpha Vantage: {str(e)[:50]}")

    # Test 3: Finnhub
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get('c'):  # current price
            results[ticker]['finnhub'] = True
            results[ticker]['details']['finnhub'] = f"✅ OK - Price: ${data['c']}"
            print(f"  ✅ Finnhub: ${data['c']}")
        else:
            results[ticker]['details']['finnhub'] = "❌ No data"
            print(f"  ❌ Finnhub: No data")
    except Exception as e:
        results[ticker]['details']['finnhub'] = f"❌ Error: {str(e)[:50]}"
        print(f"  ❌ Finnhub: {str(e)[:50]}")

    # Test 4: Financial Modeling Prep
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={FMP_API_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            results[ticker]['fmp'] = True
            price = data[0].get('price', 'N/A')
            name = data[0].get('name', 'N/A')
            results[ticker]['details']['fmp'] = f"✅ OK - {name}: ${price}"
            print(f"  ✅ FMP: {name} - ${price}")
        else:
            results[ticker]['details']['fmp'] = "❌ No data"
            print(f"  ❌ FMP: No data")
    except Exception as e:
        results[ticker]['details']['fmp'] = f"❌ Error: {str(e)[:50]}"
        print(f"  ❌ FMP: {str(e)[:50]}")

# Summary
print("\n" + "=" * 80)
print("\n📊 SUMMARY\n")

working_tickers = []
failed_all_providers = []
partial_success = []

for ticker, data in results.items():
    success_count = sum([data['yfinance'], data['alpha_vantage'], data['finnhub'], data['fmp']])
    if success_count == 0:
        failed_all_providers.append(ticker)
    elif success_count == 4:
        working_tickers.append(ticker)
    else:
        partial_success.append(ticker)

print(f"✅ Working on all providers ({len(working_tickers)}): {', '.join(working_tickers)}")
print(f"\n⚠️  Partial success ({len(partial_success)}): {', '.join(partial_success)}")
print(f"\n❌ Failed all providers ({len(failed_all_providers)}): {', '.join(failed_all_providers)}")

# Detailed breakdown for failed tickers
if failed_all_providers:
    print("\n" + "=" * 80)
    print("\n🔍 DETAILED ANALYSIS OF FAILED TICKERS\n")
    for ticker in failed_all_providers:
        print(f"\n{ticker}:")
        for provider, detail in results[ticker]['details'].items():
            print(f"  {provider}: {detail}")

# Save results to JSON
with open('ticker_test_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n\n✅ Full results saved to ticker_test_results.json")
