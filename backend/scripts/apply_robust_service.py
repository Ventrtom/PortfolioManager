"""
Replace market_data_service.py with robust implementation
This script updates the import to use RobustMarketDataService
"""
import shutil
import os

# Backup existing file
src = 'services/market_data_service.py'
backup = 'services/market_data_service.py.old'

if os.path.exists(src):
    print(f"Backing up {src} to {backup}")
    shutil.copy(src, backup)

# Copy robust service over
robust_src = 'services/robust_market_data_service.py'
print(f"Copying {robust_src} to {src}")
shutil.copy(robust_src, src)

print("\n✓ Market data service updated!")
print("\nNext steps:")
print("1. Restart your backend server")
print("2. The service will now:")
print("   - Skip known delisted tickers instantly")
print("   - Fall back to Alpha Vantage and Finnhub when yfinance is rate-limited")
print("   - Cache successful results")
print("   - Auto-mark new delisted tickers")
