import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const kid = localStorage.getItem('active_kitchen_id')
  if (kid && !config.headers['X-Kitchen-Id']) {
    config.headers['X-Kitchen-Id'] = kid
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('active_kitchen_id')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
