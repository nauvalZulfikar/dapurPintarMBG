import api from './client'

export const getItems = (params = {}) => api.get('/items', { params })

export const getItemsForDefect = (params = {}) => api.get('/items', {
  params: { ...params, include_availability: true },
})

export const createItem = (data) => api.post('/items', data)

export const testPrintItem = () => api.post('/items/test-print')

export const createDefect = (formData) => api.post('/defects', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
})
export const listDefects = (params = {}) => api.get('/defects', { params })
export const deleteDefect = (id) => api.delete(`/defects/${id}`)
export const defectPhotoUrl = (id) => `/api/defects/${id}/photo`

export const updateItem = (id, data) => api.put(`/items/${id}`, data)

export const deleteItem = (id) => api.delete(`/items/${id}`)
