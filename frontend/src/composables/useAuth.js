import { ref, computed } from 'vue'
import { login as apiLogin, logout as apiLogout } from '../api.js'

const _user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
const _token = ref(localStorage.getItem('access_token') || null)

export function useAuth() {
  const user = computed(() => _user.value)
  const isAuthenticated = computed(() => !!_token.value && !!_user.value)
  const role = computed(() => _user.value?.role || null)

  const isAdmin = computed(() => role.value === 'admin')
  const isContributor = computed(() => role.value === 'admin' || role.value === 'contributor')

  async function login(username, password) {
    const data = await apiLogin(username, password)
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    const userData = { username, role: data.role }
    localStorage.setItem('user', JSON.stringify(userData))
    _token.value = data.access_token
    _user.value = userData
    return data
  }

  async function logout() {
    const refresh = localStorage.getItem('refresh_token')
    if (refresh) {
      try { await apiLogout(refresh) } catch { /* ignore */ }
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    _token.value = null
    _user.value = null
  }

  return { user, isAuthenticated, role, isAdmin, isContributor, login, logout }
}
