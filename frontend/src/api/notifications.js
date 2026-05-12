import api from './client'

export const listNotifications = (params = {}) =>
  api.get('/notifications', { params })
export const unreadCount = () => api.get('/notifications/unread-count')
export const markRead = (id) => api.post(`/notifications/${id}/read`, {})
export const markAllRead = () => api.post('/notifications/mark-all-read', {})
export const subscribePush = (data) => api.post('/notifications/subscriptions', data)
export const getPreferences = () => api.get('/notifications/preferences')
export const setPreferences = (preferences) => api.put('/notifications/preferences', { preferences })
