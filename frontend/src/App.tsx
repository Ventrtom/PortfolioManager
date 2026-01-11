import { useState } from 'react';
import './App.css';
import Dashboard from './components/Dashboard';
import TransactionForm from './components/TransactionForm';
import TransactionList from './components/TransactionList';
import StockList from './components/StockList';

function App() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'transactions' | 'stocks'>('dashboard');
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleTransactionSuccess = () => {
    setRefreshTrigger((prev) => prev + 1);
    alert('Transaction added successfully!');
  };

  return (
    <div className="app">
      <nav className="navbar">
        <div className="nav-brand">
          <h1>Portfolio Manager</h1>
        </div>
        <div className="nav-links">
          <button
            className={currentView === 'dashboard' ? 'active' : ''}
            onClick={() => setCurrentView('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={currentView === 'transactions' ? 'active' : ''}
            onClick={() => setCurrentView('transactions')}
          >
            Transactions
          </button>
          <button
            className={currentView === 'stocks' ? 'active' : ''}
            onClick={() => setCurrentView('stocks')}
          >
            Stocks
          </button>
        </div>
      </nav>

      <main className="main-content">
        {currentView === 'dashboard' && (
          <Dashboard key={refreshTrigger} />
        )}

        {currentView === 'transactions' && (
          <div className="transactions-view">
            <TransactionForm onSuccess={handleTransactionSuccess} />
            <TransactionList refreshTrigger={refreshTrigger} />
          </div>
        )}

        {currentView === 'stocks' && <StockList />}
      </main>

      <footer className="footer">
        <p>Portfolio Manager v1.0 - Built with FastAPI & React</p>
      </footer>
    </div>
  );
}

export default App;
