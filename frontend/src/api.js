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

export const listApiTokens = () =>
  http.get('/auth/api-tokens').then((r) => r.data)

export const createApiToken = (name) =>
  http.post('/auth/api-tokens', { name }).then((r) => r.data)

export const revokeApiToken = (id) =>
  http.delete(`/auth/api-tokens/${id}`).then((r) => r.data)

// Synapses
export const listSynapses = () => http.get('/api/synapses').then((r) => r.data)
export const getSynapse = (name) => http.get(`/api/synapses/${name}`).then((r) => r.data)
export const getSynapseResources = (name) =>
  http.get(`/api/synapses/${name}/resources`).then((r) => r.data)
export const listResources = () => http.get('/api/resources').then((r) => r.data)
export const searchLibraryResources = ({ type = 'skill', query = '', page = 1, pageSize = 8 } = {}) =>
  http.get('/api/resources/search', {
    params: { type, query, page, page_size: pageSize },
  }).then((r) => r.data)
export const getResourceDetail = (type, id) =>
  http.get(`/api/resources/${type}/${id}`).then((r) => r.data)
export const updateResource = (type, id, body) =>
  http.put(`/api/resources/${type}/${id}`, body).then((r) => r.data)
export const deleteResource = (type, id) =>
  http.delete(`/api/resources/${type}/${id}`).then((r) => r.data)
export const upsertSynapse = (name, body) =>
  http.put(`/api/synapses/${name}`, body).then((r) => r.data)
export const deleteSynapse = (name) =>
  http.delete(`/api/synapses/${name}`).then((r) => r.data)
export const activateSynapse = (name) =>
  http.post(`/api/synapses/${name}/activate`).then((r) => r.data)
export const deactivateSynapse = (name) =>
  http.post(`/api/synapses/${name}/deactivate`).then((r) => r.data)

// GitHub import
export const searchGithubRepos = (query, page = 1, pageSize = 8) =>
  http.get('/api/import/github/repos', { params: { query, page, page_size: pageSize } }).then((r) => r.data)
export const listGithubCandidates = (repo, kind, query) =>
  http.get('/api/import/github/candidates', { params: { repo, kind, query } }).then((r) => r.data)
export const searchSkillsDirectory = (query, page = 1, pageSize = 8) =>
  http.get('/api/import/skills/search', { params: { query, page, page_size: pageSize } }).then((r) => r.data)
export const searchHostedMcpConnectors = (query, page = 1, pageSize = 5) =>
  http.get('/api/import/mcp/hosted/search', { params: { query, page, page_size: pageSize } }).then((r) => r.data)
export const getSkillsDirectoryDetail = (source, skillId) =>
  http.get('/api/import/skills/detail', { params: { source, skill_id: skillId } }).then((r) => r.data)
export const importGithubCandidate = (body) =>
  http.post('/api/import/github/import', body).then((r) => r.data)
export const importLocalProjectResources = (body = { types: ['skill', 'rule', 'tool'] }) =>
  http.post('/api/import/local/project', body).then((r) => r.data)

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
