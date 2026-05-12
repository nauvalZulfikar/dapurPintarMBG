import api from './client'

// Operational endpoint (kitchen-scoped, active only) — used by Dashboard, etc.
export const getSchools = () => api.get('/schools')

// Admin CRUD (Phase 1)
export const listSchoolsAdmin = (includeInactive = false) =>
  api.get('/admin/schools', { params: { include_inactive: includeInactive } })
export const createSchool = (data) => api.post('/admin/schools', data)
export const updateSchool = (id, data) => api.patch(`/admin/schools/${id}`, data)
export const deleteSchool = (id) => api.delete(`/admin/schools/${id}`)
