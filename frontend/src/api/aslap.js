import api from './client'

// Phase 7 — ASLAP daily ops
export const getTodayChecklist = (target_date) =>
  api.get('/aslap/checklists/today', { params: target_date ? { target_date } : {} })
export const submitChecklist = (data) => api.post('/aslap/checklists/submit', data)
export const listChecklists = (params = {}) => api.get('/aslap/checklists', { params })

export const submitWaterQuality = (data) => api.post('/aslap/water-quality', data)
export const listWaterQuality = (params = {}) => api.get('/aslap/water-quality', { params })

export const createObservation = (data) => api.post('/aslap/observations', data)
export const listObservations = (params = {}) => api.get('/aslap/observations', { params })

export const createCommLog = (data) => api.post('/aslap/comm-logs', data)
export const listCommLogs = (params = {}) => api.get('/aslap/comm-logs', { params })

export const generateWeeklyReport = (data) => api.post('/aslap/reports/generate', data)
export const listWeeklyReports = () => api.get('/aslap/reports')
export const submitWeeklyReport = (id) => api.post(`/aslap/reports/${id}/submit`, {})
