import api from './client'

export const getDelivery = (date) => api.get('/delivery', { params: { date } })
