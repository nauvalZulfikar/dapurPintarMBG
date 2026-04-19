import api from './client'

export const getItems = (params = {}) => api.get('/items', { params })

export const createItem = (data) => api.post('/items', data)

export const updateItem = (id, data) => api.put(`/items/${id}`, data)

export const deleteItem = (id) => api.delete(`/items/${id}`)
