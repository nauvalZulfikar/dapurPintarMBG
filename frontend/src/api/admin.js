import api from './client'

export const crossKitchenOverview = (date) =>
  api.get('/admin/overview', { params: date ? { date } : {} })

export const listOrgs = () => api.get('/admin/organizations')
export const createOrg = (data) => api.post('/admin/organizations', data)
export const patchOrg = (id, data) => api.patch(`/admin/organizations/${id}`, data)
export const deactivateOrg = (id) => api.delete(`/admin/organizations/${id}`)

export const listKitchens = () => api.get('/admin/kitchens')
export const createKitchen = (data) => api.post('/admin/kitchens', data)
export const patchKitchen = (id, data) => api.patch(`/admin/kitchens/${id}`, data)
export const deleteKitchen = (id) => api.delete(`/admin/kitchens/${id}`)
export const rotateScannerKey = (id) => api.post(`/admin/kitchens/${id}/rotate-scanner-key`)
export const rotatePrintKey   = (id) => api.post(`/admin/kitchens/${id}/rotate-print-key`)

export const listUsers = () => api.get('/admin/users')
export const createUser = (data) => api.post('/admin/users', data)
export const patchUser = (id, data) => api.patch(`/admin/users/${id}`, data)
export const deleteUser = (id) => api.delete(`/admin/users/${id}`)

export const assignKitchen = (userId, kitchen_id, role) =>
  api.post(`/admin/users/${userId}/kitchens`, { kitchen_id, role })
export const unassignKitchen = (userId, kitchen_id) =>
  api.delete(`/admin/users/${userId}/kitchens/${kitchen_id}`)
