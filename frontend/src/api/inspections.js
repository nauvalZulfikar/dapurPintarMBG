import api from './client'

// Phase 3 — Purchase Orders
export const listPurchaseOrders = (params = {}) => api.get('/purchase-orders', { params })
export const getPurchaseOrder = (id) => api.get(`/purchase-orders/${id}`)
export const createPurchaseOrder = (data) => api.post('/purchase-orders', data)
export const updatePurchaseOrder = (id, data) => api.patch(`/purchase-orders/${id}`, data)
export const deletePurchaseOrder = (id) => api.delete(`/purchase-orders/${id}`)

// Phase 3 — Joint Inspection
export const listInspections = (params = {}) => api.get('/inspections', { params })
export const getInspection = (id) => api.get(`/inspections/${id}`)
export const createInspection = (data) => api.post('/inspections', data)
export const submitSignoff = (id, data) => api.post(`/inspections/${id}/signoff`, data)
export const acceptInspectionLine = (insp_id, line_id, data) =>
  api.post(`/inspections/${insp_id}/lines/${line_id}/accept`, data)
export const rejectInspectionLine = (insp_id, line_id, data) =>
  api.post(`/inspections/${insp_id}/lines/${line_id}/reject`, data)
export const finalizeInspection = (id) => api.post(`/inspections/${id}/finalize`, {})

// Phase 3 — Disputes
export const listDisputes = (params = {}) => api.get('/disputes', { params })
export const resolveDispute = (id, data) => api.patch(`/disputes/${id}`, data)
