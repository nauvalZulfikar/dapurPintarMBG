import api from './client'

export const getSchools = () => api.get('/schools')
