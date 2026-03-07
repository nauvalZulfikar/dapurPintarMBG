import api from './client'

export const getItems = (params = {}) => api.get('/items', { params })

export const createItem = (data) => api.post('/items', data)
