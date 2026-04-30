<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from './composables/useAuth.js'
import { createApiToken, listApiTokens, revokeApiToken } from './api.js'

const router = useRouter()
const { isAuthenticated, user, isAdmin, logout } = useAuth()
const menuOpen = ref(false)
const tokensOpen = ref(false)
const loadingTokens = ref(false)
const tokenList = ref([])
const tokenName = ref('')
const tokenError = ref('')
const tokenSuccess = ref('')
const newlyCreatedToken = ref('')

async function handleLogout() {
  await logout()
  router.push('/login')
}

async function openTokenManager() {
  tokensOpen.value = true
  menuOpen.value = false
  tokenError.value = ''
  tokenSuccess.value = ''
  newlyCreatedToken.value = ''
  await refreshTokens()
}

function closeTokenManager() {
  tokensOpen.value = false
  tokenName.value = ''
  tokenError.value = ''
  tokenSuccess.value = ''
  newlyCreatedToken.value = ''
}

async function refreshTokens() {
  loadingTokens.value = true
  tokenError.value = ''
  try {
    tokenList.value = await listApiTokens()
  } catch (e) {
    tokenError.value = e.response?.data?.detail || 'Failed to load API tokens.'
  } finally {
    loadingTokens.value = false
  }
}

async function handleCreateToken() {
  tokenError.value = ''
  tokenSuccess.value = ''
  newlyCreatedToken.value = ''
  const name = tokenName.value.trim()
  if (!name) {
    tokenError.value = 'Token name is required.'
    return
  }

  try {
    const response = await createApiToken(name)
    newlyCreatedToken.value = response.token
    tokenSuccess.value = 'Token created. Copy it now: it will not be shown again.'
    tokenName.value = ''
    await refreshTokens()
  } catch (e) {
    tokenError.value = e.response?.data?.detail || 'Failed to create API token.'
  }
}

async function handleRevokeToken(id) {
  tokenError.value = ''
  tokenSuccess.value = ''
  try {
    await revokeApiToken(id)
    tokenSuccess.value = 'Token revoked.'
    await refreshTokens()
  } catch (e) {
    tokenError.value = e.response?.data?.detail || 'Failed to revoke token.'
  }
}

async function copyToken() {
  if (!newlyCreatedToken.value) {
    return
  }
  await navigator.clipboard.writeText(newlyCreatedToken.value)
  tokenSuccess.value = 'Token copied to clipboard.'
}
</script>

<template>
  <div>
    <nav v-if="isAuthenticated" class="top-nav">
      <router-link to="/" class="nav-brand">⚡ Shared Synapse</router-link>
      <div class="nav-links">
        <router-link to="/">Explore</router-link>
        <router-link v-if="isAdmin" to="/library">Library</router-link>
        <router-link to="/synapses">Synapses</router-link>
        <router-link v-if="isAdmin" to="/admin/users">Users</router-link>
      </div>
      <div class="nav-user">
        <button class="user-menu-trigger" @click="menuOpen = !menuOpen">
          <span class="nav-username">{{ user?.username }}</span>
          <span class="nav-role">{{ user?.role }}</span>
        </button>
        <div v-if="menuOpen" class="user-menu">
          <button class="user-menu-action" @click="openTokenManager">Manage API tokens</button>
          <button class="user-menu-action danger" @click="handleLogout">Sign out</button>
        </div>
      </div>
    </nav>
    <router-view />

    <div v-if="tokensOpen" class="modal-overlay" @click.self="closeTokenManager">
      <div class="token-modal">
        <div class="modal-header">
          <h2>API Tokens</h2>
          <button class="btn-close" @click="closeTokenManager">Close</button>
        </div>
        <p class="modal-lede">Create personal access tokens for the VS Code extension or scripts.</p>

        <div class="token-form-row">
          <input
            v-model="tokenName"
            type="text"
            placeholder="Token name (for example: VS Code Laptop)"
          />
          <button class="btn-primary" @click="handleCreateToken">Create token</button>
        </div>

        <p v-if="tokenError" class="form-error">{{ tokenError }}</p>
        <p v-if="tokenSuccess" class="form-success">{{ tokenSuccess }}</p>

        <div v-if="newlyCreatedToken" class="new-token-box">
          <p class="new-token-label">New token</p>
          <code>{{ newlyCreatedToken }}</code>
          <button class="btn-secondary" @click="copyToken">Copy</button>
        </div>

        <div class="token-list">
          <p v-if="loadingTokens" class="loading">Loading tokens…</p>
          <p v-else-if="!tokenList.length" class="loading">No tokens created yet.</p>
          <div v-else v-for="token in tokenList" :key="token.id" class="token-row">
            <div class="token-meta">
              <strong>{{ token.name }}</strong>
              <span>{{ token.token_prefix }}…</span>
            </div>
            <button class="btn-cancel" @click="handleRevokeToken(token.id)">Revoke</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.top-nav {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.75rem 2rem;
  background: var(--panel);
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(8px);
}

.nav-brand {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 1rem;
  text-decoration: none;
  color: var(--ink);
  white-space: nowrap;
}

.nav-links {
  display: flex;
  gap: 1rem;
  flex: 1;
}

.nav-links a {
  text-decoration: none;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--muted);
  padding: 0.25rem 0.5rem;
  border-radius: 6px;
  transition: color 0.15s, background 0.15s;
}

.nav-links a:hover,
.nav-links a.router-link-active {
  color: var(--ink);
  background: var(--accent-soft);
}

.nav-user {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}

.user-menu-trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  border: 1px solid var(--line);
  background: var(--panel-strong);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
}

.nav-username {
  font-weight: 600;
  font-size: 0.875rem;
}

.nav-role {
  font-size: 0.75rem;
  background: var(--accent-soft);
  color: var(--accent-strong);
  padding: 0.2rem 0.5rem;
  border-radius: 20px;
  font-weight: 600;
  text-transform: capitalize;
}

.user-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 0.5rem);
  min-width: 220px;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.5rem;
  background: var(--panel-strong);
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: var(--shadow);
}

.user-menu-action {
  text-align: left;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--ink);
  padding: 0.55rem 0.7rem;
}

.user-menu-action:hover {
  background: var(--accent-soft);
}

.user-menu-action.danger:hover {
  background: rgba(180, 35, 24, 0.08);
  color: var(--danger);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: rgba(20, 33, 61, 0.5);
  backdrop-filter: blur(2px);
}

.token-modal {
  width: min(680px, 100%);
  background: var(--panel-strong);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: var(--shadow);
  padding: 1.1rem;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.modal-header h2 {
  margin: 0;
  font-family: 'Space Grotesk', sans-serif;
}

.modal-lede {
  color: var(--muted);
  margin: 0.5rem 0 1rem;
}

.token-form-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.new-token-box {
  display: grid;
  gap: 0.6rem;
  margin: 0.75rem 0;
  padding: 0.8rem;
  border-radius: 12px;
  border: 1px dashed var(--line-strong);
}

.new-token-label {
  margin: 0;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.new-token-box code {
  font-size: 0.88rem;
  background: rgba(20, 33, 61, 0.05);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.5rem;
  word-break: break-all;
}

.token-list {
  display: grid;
  gap: 0.6rem;
  margin-top: 0.8rem;
}

.token-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.7rem;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.65);
}

.token-meta {
  display: grid;
  gap: 0.1rem;
}

.token-meta span {
  color: var(--muted);
  font-size: 0.83rem;
}

@media (max-width: 760px) {
  .token-form-row {
    grid-template-columns: 1fr;
  }
}
</style>
