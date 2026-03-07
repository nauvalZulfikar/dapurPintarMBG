import api from './client'

export const getTrays = (params = {}) => api.get('/trays', { params })
