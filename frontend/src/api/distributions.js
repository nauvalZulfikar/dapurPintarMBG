import api from './client'

// Phase 5 — distribution dashboard + ASLAP ops
export const schoolsByWave = () => api.get('/distributions/schools-by-wave')
export const distributionsToday = (target_date) =>
  api.get('/distributions/today', { params: target_date ? { target_date } : {} })
export const createLeftover = (data) => api.post('/distributions/leftovers', data)
export const listLeftovers = (params = {}) => api.get('/distributions/leftovers', { params })

// Public — guru side
export const confirmReceipt = (tray_id, data) =>
  api.post(`/countdown/${tray_id}/confirm-receipt`, data)
export const listConfirmationsPublic = (tray_id) =>
  api.get(`/countdown/${tray_id}/confirmations`)

// Vehicle / Driver (master)
export const listVehicles = () => api.get('/vehicles')
export const createVehicle = (data) => api.post('/vehicles', data)
export const deleteVehicle = (id) => api.delete(`/vehicles/${id}`)
export const listDrivers = () => api.get('/drivers')
export const createDriver = (data) => api.post('/drivers', data)
export const deleteDriver = (id) => api.delete(`/drivers/${id}`)
