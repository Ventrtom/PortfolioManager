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
} from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

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

  getKPIs: async (): Promise<KPIResponse> => {
    const response = await apiClient.get('/analytics/kpis');
    return response.data;
  },
};

export default apiClient;
