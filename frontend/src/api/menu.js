import api from './client'

export const optimizeMenu = (data) => api.post('/menu/optimize', data)
export const listFoods = () => api.get('/menu/foods')
export const getPriceStatus = () => api.get('/menu/prices/status')
export const triggerScrape = (maxItems = 0) =>
  api.post(`/menu/prices/scrape?max_items=${maxItems}`)
