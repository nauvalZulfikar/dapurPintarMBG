import api from './client'

export const listSuppliers = (includeInactive = false) =>
  api.get('/suppliers', { params: { include_inactive: includeInactive } })
export const getSupplier = (id) => api.get(`/suppliers/${id}`)
export const createSupplier = (data) => api.post('/suppliers', data)
export const updateSupplier = (id, data) => api.patch(`/suppliers/${id}`, data)
export const deleteSupplier = (id) => api.delete(`/suppliers/${id}`)
