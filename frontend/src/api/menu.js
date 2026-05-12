import api from './client'

export const optimizeMenu = (data) => api.post('/menu/optimize', data)
export const listFoods = () => api.get('/menu/foods')
export const getPriceStatus = () => api.get('/menu/prices/status')
export const getScrapeIsRunning = () => api.get('/menu/prices/is-running')
export const triggerScrape = (maxItems = 0) =>
  api.post(`/menu/prices/scrape?max_items=${maxItems}`)
export const getAkgPresets = () => api.get('/menu/akg-presets')

// Manual price override (accountant/admin only). Pass price=null to clear.
export const overridePrice = (foodCode, body) =>
  api.patch(`/menu/prices/${encodeURIComponent(foodCode)}`, body)

// Price history log (accountant/admin)
export const getPriceHistory = (foodCode) =>
  api.get(`/menu/prices/${encodeURIComponent(foodCode)}/history`)

// Nutrition override (ahli_gizi/admin)
export const listNutritionOverrides = () => api.get('/menu/foods/overrides')
export const setNutritionOverride = (foodCode, overrides) =>
  api.patch(`/menu/foods/${encodeURIComponent(foodCode)}/override`, { overrides })
export const clearNutritionOverride = (foodCode) =>
  api.delete(`/menu/foods/${encodeURIComponent(foodCode)}/override`)

// Variance report (accountant/admin)
export const getVarianceReport = (from, to) =>
  api.get('/reports/variance', { params: { from, to } })

// Food substitutes (any user with menu.view)
export const getSubstitutes = (foodName) =>
  api.get('/menu/substitutes', { params: { food_name: foodName } })

// Saved menus (ahli_gizi / admin)
export const listSavedMenus = () => api.get('/menu/saved')
export const getSavedMenu = (id) => api.get(`/menu/saved/${id}`)
export const saveMenu = (body) => api.post('/menu/saved', body)
export const deleteSavedMenu = (id) => api.delete(`/menu/saved/${id}`)
