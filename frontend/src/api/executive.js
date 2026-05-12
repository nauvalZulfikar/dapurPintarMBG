import api from './client'

export const kpiToday = (target_date) =>
  api.get('/executive/kpi', { params: target_date ? { target_date } : {} })
export const complianceScore = (days = 30) =>
  api.get('/executive/compliance-score', { params: { days } })
export const kpiTrend = (metric = 'porsi_confirmed', days = 30) =>
  api.get('/executive/trend', { params: { metric, days } })
export const multiKitchen = (target_date) =>
  api.get('/executive/multi-kitchen', { params: target_date ? { target_date } : {} })
export const platformOverview = () => api.get('/executive/platform')
export const complianceBundle = (from_date, to_date) =>
  api.get('/compliance/bundle', { params: { from_date, to_date } })
