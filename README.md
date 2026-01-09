# Portfolio Manager

A comprehensive investment portfolio management system for tracking stock transactions, analyzing performance, and managing your investment portfolio with detailed analytics and KPIs.

## Features

### Phase 1 (Current)
- **Transaction Management**: Add, edit, and delete stock transactions (BUY/SELL/DIVIDEND/FEE/TAX)
- **Natural Language Input**: Parse transactions from natural language (e.g., "BUY - AAPL - 100 - @150.50 - 01/15/2025")
- **Portfolio Tracking**: Automatic calculation of holdings, cost basis (FIFO), and P&L
- **Real-time Prices**: Integration with yfinance for current stock prices and company data
- **Analytics & KPIs**:
  - Portfolio value and total return
  - Industry/sector allocation
  - Diversification metrics (concentration, Herfindahl index)
  - Volatility calculations (daily/annualized)
  - Dividend tracking and yield
- **Dashboard**: Visual overview with charts and key metrics
- **Responsive UI**: Modern React interface with Chart.js visualizations

### Future Phases
- Enhanced analytics and benchmarking
- AI agent integration for conversational interface
- Multi-asset support (real estate, commodities, bonds, crypto)
- What-if scenario simulations
- Portfolio optimization

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: ORM for database operations
- **SQLite**: Local database
- **yfinance**: Stock market data integration
- **Pandas/NumPy**: Financial calculations

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type-safe development
- **Vite**: Build tool
- **Chart.js**: Data visualization
- **Axios**: API client

## Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Ventrtom/PortfolioManager.git
cd PortfolioManager
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment (optional but recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install
```

## Running the Application

### Quick Start (Recommended)

The easiest way to start the application is using the startup script:

**PowerShell (Recommended):**
```powershell
.\start.ps1
```

**Command Prompt / Batch:**
```cmd
start.bat
```

The startup script will:
- ✓ Detect first-time setup and install dependencies automatically
- ✓ Start both backend and frontend services
- ✓ Perform health checks
- ✓ Open the application in your browser
- ✓ Handle graceful shutdown with Ctrl+C

**To stop the services:**
```powershell
.\stop.ps1
```
Or simply press `Ctrl+C` in the startup script window.

### Manual Start (Alternative)

If you prefer to start services manually:

**Terminal 1 - Backend:**
```bash
cd backend
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

uvicorn main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### Access Points

- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Usage

### Adding Transactions

#### Natural Language Input
Navigate to the "Transactions" tab and use natural language format:

Examples:
```
BUY - AAPL - 100 - @150.50 - 01/15/2025
SELL - MSFT - 50 - @380.25 - 02/20/2025
DIVIDEND - GOOGL - 25.50 - 03/15/2025
FEE - - 9.99 - 01/15/2025
```

#### Manual Entry
Switch to "Manual Entry" mode to fill out a structured form with all transaction details.

### Viewing Portfolio

The Dashboard tab provides:
- **Summary Cards**: Total value, returns, cost basis, holdings count, cash balance
- **Holdings Table**: Current positions with live prices and P&L
- **Industry Allocation Chart**: Pie chart showing portfolio distribution
- **KPI Cards**: Diversification, volatility, and dividend metrics

### Managing Transactions

- View all transactions in the "Transactions" tab
- Delete transactions using the delete button
- Edits can be made by deleting and re-adding (edit functionality coming soon)

## API Endpoints

### Transactions
- `POST /api/transactions/` - Create transaction
- `GET /api/transactions/` - List all transactions
- `GET /api/transactions/{id}` - Get single transaction
- `PUT /api/transactions/{id}` - Update transaction
- `DELETE /api/transactions/{id}` - Delete transaction
- `POST /api/transactions/parse` - Parse natural language input

### Portfolio
- `GET /api/portfolio/summary` - Portfolio summary
- `GET /api/portfolio/holdings` - Current holdings
- `GET /api/portfolio/allocation/industry` - Industry allocation
- `GET /api/portfolio/allocation/sector` - Sector allocation
- `POST /api/portfolio/refresh-prices` - Refresh all prices

### Analytics
- `GET /api/analytics/performance` - Performance history
- `GET /api/analytics/kpis` - All KPIs
- `GET /api/analytics/diversification` - Diversification metrics
- `GET /api/analytics/volatility` - Volatility metrics
- `GET /api/analytics/dividends` - Dividend summary

## Project Structure

```
PortfolioManager/
├── start.ps1               # PowerShell startup script
├── start.bat               # Batch startup script
├── stop.ps1                # Stop all services
├── backend/
│   ├── main.py                 # FastAPI app entry
│   ├── requirements.txt
│   ├── models/
│   │   ├── database.py        # SQLAlchemy models
│   │   └── schemas.py         # Pydantic schemas
│   ├── services/
│   │   ├── transaction_service.py
│   │   ├── portfolio_service.py
│   │   ├── analytics_service.py
│   │   └── market_data_service.py
│   ├── routes/
│   │   ├── transactions.py
│   │   ├── portfolio.py
│   │   └── analytics.py
│   └── utils/
│       ├── parser.py          # NL transaction parser
│       └── calculations.py    # Financial calculations
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── TransactionForm.tsx
│   │   │   ├── TransactionList.tsx
│   │   │   ├── HoldingsTable.tsx
│   │   │   ├── AllocationChart.tsx
│   │   │   └── PortfolioSummaryCard.tsx
│   │   └── utils/
│   │       └── formatters.ts
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Database Schema

### Transactions
- id, transaction_type, ticker, quantity, price, total_amount
- transaction_date, notes, created_at, updated_at

### Stocks
- ticker, company_name, sector, industry, currency, last_updated

### Stock Prices
- ticker, price, price_date

## Development

### Adding New Features

1. Backend: Create service in `backend/services/`
2. Add routes in `backend/routes/`
3. Frontend: Add components in `frontend/src/components/`
4. Update API client in `frontend/src/api/client.ts`

### Testing

Manual testing currently. Automated tests coming in future phases.

## Troubleshooting

### Backend won't start
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.8+)
- Verify port 8000 is not in use

### Frontend won't start
- Ensure dependencies are installed: `npm install`
- Check Node.js version: `node --version` (should be 16+)
- Clear node_modules and reinstall if needed

### Cannot fetch stock data
- Check internet connection
- yfinance may have rate limits - wait a few minutes
- Some tickers may not be available or require specific format

### Prices not updating
- Use the "Refresh" button on the dashboard
- Stock prices are cached for the current day
- Historical prices are fetched on-demand for calculations

## Contributing

This is a personal project, but suggestions and feedback are welcome! Open an issue on GitHub.

## License

MIT License - feel free to use and modify for your own portfolio management needs.

## Roadmap

- [ ] Phase 1: Core stock portfolio manager ✅
- [ ] Phase 2: Enhanced analytics & benchmarking
- [ ] Phase 3: AI agent integration
- [ ] Phase 4: Multi-asset support
- [ ] Phase 5: Advanced simulations & optimization

## Support

For issues or questions, please open an issue on GitHub or contact the developer.

---

Built with Claude Code
