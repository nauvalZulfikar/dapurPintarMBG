import api from './client'

export const getOverview = (date) => api.get('/overview', { params: { date } })
