import api from './client'

export const optimizeMenu = (data) => api.post('/menu/optimize', data)
export const listFoods = () => api.get('/menu/foods')
