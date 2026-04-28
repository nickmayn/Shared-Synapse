<script setup>
import { useRouter } from 'vue-router'
import { useAuth } from './composables/useAuth.js'

const router = useRouter()
const { isAuthenticated, user, isAdmin, logout } = useAuth()

async function handleLogout() {
  await logout()
  router.push('/login')
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
        <span class="nav-username">{{ user?.username }}</span>
        <span class="nav-role">{{ user?.role }}</span>
        <button class="btn-logout" @click="handleLogout">Sign out</button>
      </div>
    </nav>
    <router-view />
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
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-left: auto;
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

.btn-logout {
  background: none;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.3rem 0.75rem;
  font-size: 0.8rem;
  cursor: pointer;
  color: var(--muted);
  transition: border-color 0.15s, color 0.15s;
}

.btn-logout:hover {
  border-color: var(--accent);
  color: var(--accent);
}
</style>
