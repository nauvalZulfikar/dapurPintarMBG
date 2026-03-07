import api from './client'

export const getStats = (date) => api.get('/stats', { params: { date } })
