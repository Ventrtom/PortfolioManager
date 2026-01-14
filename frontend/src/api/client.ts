import axios from 'axios';
import type {
  Transaction,
  TransactionCreate,
  ParsedTransaction,
  Holding,
  PortfolioSummary,
  IndustryAllocation,
  SectorAllocation,
  PerformanceDataPoint,
  KPIResponse,
  KPIResponseWithMetadata,
  SnapshotHistoryItem,
  Stock,
  StockFilterCriteria,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Transaction API
export const transactionAPI = {
  getAll: async (): Promise<Transaction[]> => {
    const response = await apiClient.get('/transactions/');
    return response.data;
  },

  getById: async (id: number): Promise<Transaction> => {
    const response = await apiClient.get(`/transactions/${id}`);
    return response.data;
  },

  create: async (transaction: TransactionCreate): Promise<Transaction> => {
    const response = await apiClient.post('/transactions/', transaction);
    return response.data;
  },

  update: async (id: number, transaction: Partial<TransactionCreate>): Promise<Transaction> => {
    const response = await apiClient.put(`/transactions/${id}`, transaction);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/transactions/${id}`);
  },

  parse: async (inputText: string): Promise<ParsedTransaction> => {
    const response = await apiClient.post('/transactions/parse', null, {
      params: { input_text: inputText },
    });
    return response.data;
  },

  getSummary: async (): Promise<any> => {
    const response = await apiClient.get('/transactions/summary/stats');
    return response.data;
  },

  refreshCurrencies: async (transactionIds?: number[]): Promise<{
    updated: number;
    failed: number;
    errors: string[];
  }> => {
    const response = await apiClient.post('/transactions/refresh-currencies', {
      transaction_ids: transactionIds || null,
    });
    return response.data;
  },

  refreshRates: async (transactionId: number): Promise<Transaction> => {
    const response = await apiClient.post(`/transactions/${transactionId}/refresh-rates`);
    return response.data;
  },
};

// Portfolio API
export const portfolioAPI = {
  getSummary: async (): Promise<PortfolioSummary> => {
    const response = await apiClient.get('/portfolio/summary');
    return response.data;
  },

  getHoldings: async (): Promise<Holding[]> => {
    const response = await apiClient.get('/portfolio/holdings');
    return response.data;
  },

  getIndustryAllocation: async (): Promise<IndustryAllocation[]> => {
    const response = await apiClient.get('/portfolio/allocation/industry');
    return response.data;
  },

  getSectorAllocation: async (): Promise<SectorAllocation[]> => {
    const response = await apiClient.get('/portfolio/allocation/sector');
    return response.data;
  },

  refreshPrices: async (): Promise<Record<string, number>> => {
    const response = await apiClient.post('/portfolio/refresh-prices');
    return response.data;
  },
};

// Analytics API
export const analyticsAPI = {
  getPerformance: async (days: number = 365): Promise<PerformanceDataPoint[]> => {
    const response = await apiClient.get('/analytics/performance', {
      params: { days },
    });
    return response.data;
  },

  getKPIs: async (currency: string = 'CZK'): Promise<KPIResponseWithMetadata> => {
    const response = await apiClient.get('/analytics/kpis', {
      params: { currency },
    });
    return response.data;
  },

  recalculateKPIs: async (): Promise<KPIResponseWithMetadata> => {
    const response = await apiClient.post('/analytics/kpis/recalculate');
    return response.data;
  },

  getKPIHistory: async (limit: number = 100): Promise<SnapshotHistoryItem[]> => {
    const response = await apiClient.get('/analytics/kpis/history', {
      params: { limit },
    });
    return response.data;
  },
};

// Stock API
export const stockAPI = {
  getAll: async (filters?: StockFilterCriteria): Promise<Stock[]> => {
    const response = await apiClient.get('/stocks/', { params: filters });
    return response.data;
  },

  getByTicker: async (ticker: string): Promise<Stock> => {
    const response = await apiClient.get(`/stocks/${ticker}`);
    return response.data;
  },

  create: async (ticker: string): Promise<Stock> => {
    const response = await apiClient.post('/stocks/', { ticker });
    return response.data;
  },

  update: async (ticker: string, updates: Partial<Stock>): Promise<Stock> => {
    const response = await apiClient.put(`/stocks/${ticker}`, updates);
    return response.data;
  },

  delete: async (ticker: string): Promise<void> => {
    await apiClient.delete(`/stocks/${ticker}`);
  },

  triggerEnrichment: async (ticker: string): Promise<void> => {
    await apiClient.post(`/stocks/${ticker}/enrich`);
  },

  getSectors: async (): Promise<string[]> => {
    const response = await apiClient.get('/stocks/filters/sectors');
    return response.data;
  },

  getIndustries: async (): Promise<string[]> => {
    const response = await apiClient.get('/stocks/filters/industries');
    return response.data;
  },

  getFlagged: async (): Promise<Stock[]> => {
    const response = await apiClient.get('/stocks/flagged');
    return response.data;
  },

  updateSkipPriceFlag: async (
    ticker: string,
    skip: boolean,
    reason?: string
  ): Promise<{
    message: string;
    ticker: string;
    skip_price_fetch: boolean;
    skip_price_reason: string | null;
    skip_price_since: string | null;
  }> => {
    const response = await apiClient.patch(`/stocks/${ticker}/skip-price`, null, {
      params: { skip, reason },
    });
    return response.data;
  },
};

export default apiClient;
