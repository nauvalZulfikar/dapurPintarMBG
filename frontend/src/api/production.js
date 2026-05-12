import api from './client'

// Phase 4 — Production batches
export const todayMenu = (target_date) =>
  api.get('/production/today-menu', { params: target_date ? { target_date } : {} })
export const listBatches = (status) =>
  api.get('/production/batches', { params: status ? { status } : {} })
export const getBatch = (id) => api.get(`/production/batches/${id}`)
export const startBatch = (data) => api.post('/production/batches', data)
export const qcApprove = (id, data) => api.post(`/production/batches/${id}/qc`, data)
export const endBatch = (id, notes) => api.post(`/production/batches/${id}/end`, { notes })

// Phase 4 — Samples
export const listSamples = (status) => api.get('/samples', { params: status ? { status } : {} })

// Phase 4 — Tablet Processing scan (uses JWT, not scanner key)
export const scanProcessing = (code) => api.post('/scans', { code, step: 'Processing' })
