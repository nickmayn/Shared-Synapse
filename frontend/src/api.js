import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const http = axios.create({ baseURL: BASE_URL })

// Attach JWT to every request if present
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, attempt a token refresh once, then redirect to /login
http.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: refresh })
          localStorage.setItem('access_token', data.access_token)
          original.headers.Authorization = `Bearer ${data.access_token}`
          return http(original)
        } catch {
          // refresh failed – clear tokens and redirect
        }
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

// Auth
export const login = (username, password) =>
  http.post('/auth/login', { username, password }).then((r) => r.data)

export const logout = (refresh_token) =>
  http.post('/auth/logout', { refresh_token }).then((r) => r.data)

// Synapses
export const listSynapses = () => http.get('/api/synapses').then((r) => r.data)
export const getSynapse = (name) => http.get(`/api/synapses/${name}`).then((r) => r.data)
export const upsertSynapse = (name, body) =>
  http.put(`/api/synapses/${name}`, body).then((r) => r.data)
export const deleteSynapse = (name) =>
  http.delete(`/api/synapses/${name}`).then((r) => r.data)
export const activateSynapse = (name) =>
  http.post(`/api/synapses/${name}/activate`).then((r) => r.data)
export const deactivateSynapse = (name) =>
  http.post(`/api/synapses/${name}/deactivate`).then((r) => r.data)

// Users (admin)
export const listUsers = () => http.get('/admin/users').then((r) => r.data)
export const createUser = (body) => http.post('/admin/users', body).then((r) => r.data)
export const updateUserRole = (id, role) =>
  http.patch(`/admin/users/${id}/role`, { role }).then((r) => r.data)
export const deactivateUser = (id) =>
  http.patch(`/admin/users/${id}/deactivate`).then((r) => r.data)
export const activateUser = (id) =>
  http.patch(`/admin/users/${id}/activate`).then((r) => r.data)

export default http
