import api from './client'

// Phase 2A — Reverse Optimizer
export const calcManualMenu = (items, ageGroup) =>
  api.post('/menu/calc', { items, age_group: ageGroup })

export const listAkgPresets = () => api.get('/menu/akg-presets')

// Phase 2A — Student requests
export const listStudentRequests = (status) =>
  api.get('/student-requests', { params: status ? { status } : {} })
export const createStudentRequest = (data) => api.post('/student-requests', data)
export const resolveStudentRequest = (id, data) => api.patch(`/student-requests/${id}`, data)

// Phase 2B — Approval workflow
export const listSavedMenusFiltered = (params = {}) =>
  api.get('/menu/saved', { params })
export const submitMenuForReview = (id, notes) =>
  api.post(`/menu/saved/${id}/submit`, { notes })
export const approveMenu = (id, notes) =>
  api.post(`/menu/saved/${id}/approve`, { notes })
export const rejectMenu = (id, notes) =>
  api.post(`/menu/saved/${id}/reject`, { notes })
export const lockMenu = (id, notes) =>
  api.post(`/menu/saved/${id}/lock`, { notes })
export const archiveMenu = (id) =>
  api.post(`/menu/saved/${id}/archive`, {})
export const revertMenuToDraft = (id) =>
  api.post(`/menu/saved/${id}/revert-to-draft`, {})

export const saveMenuPhase2 = (data) => api.post('/menu/saved', data)

// Phase 2B — Cycle check + Forecast
export const cycleCheck = (days = 20) =>
  api.get('/menu/cycle-check', { params: { days } })
export const menuForecast = (fromDate, toDate, schoolId) =>
  api.get('/menu/forecast', { params: { from_date: fromDate, to_date: toDate, ...(schoolId ? { school_id: schoolId } : {}) } })
