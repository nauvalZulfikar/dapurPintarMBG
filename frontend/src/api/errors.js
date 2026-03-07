import api from './client'

export const getScanErrors = (params = {}) => api.get('/scan-errors', { params })
