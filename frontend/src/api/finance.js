import api from './client'

// 6A — Price trends
export const priceTrends = (food_code, days = 30) =>
  api.get('/finance/price-trends', { params: { food_code, days } })
export const priceTrendsSummary = (days = 30, limit = 50) =>
  api.get('/finance/price-trends/summary', { params: { days, limit } })

// 6B — Spike alerts
export const spikeAlerts = (threshold_pct = 15) =>
  api.get('/finance/spike-alerts', { params: { threshold_pct } })

// 6C — PO Generator
export const generatePOFromForecast = (data) =>
  api.post('/finance/po/generate-from-forecast', data)

// 6D — Expenses
export const listExpenses = (params = {}) =>
  api.get('/finance/expenses', { params })
export const createExpense = (data) => api.post('/finance/expenses', data)
export const deleteExpense = (id) => api.delete(`/finance/expenses/${id}`)

// 6D — Volunteer payments
export const listVolunteers = (params = {}) =>
  api.get('/finance/volunteers', { params })
export const createVolunteer = (data) => api.post('/finance/volunteers', data)

// 6D — Cost-per-porsi
export const costPerPorsi = (from_date, to_date) =>
  api.get('/finance/cost-per-porsi', { params: { from_date, to_date } })

// 6D — LRA
export const listLRAPeriods = () => api.get('/finance/lra/periods')
export const getLRAPeriod = (id) => api.get(`/finance/lra/periods/${id}`)
export const generateLRA = (data) => api.post('/finance/lra/generate', data)
export const submitLRA = (id) => api.post(`/finance/lra/periods/${id}/submit`, {})
