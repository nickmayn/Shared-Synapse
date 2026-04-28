<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const router = useRouter()
const route = useRoute()
const { login } = useAuth()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await login(username.value, password.value)
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed. Check your credentials.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-shell">
    <div class="login-card">
      <p class="eyebrow">Shared Synapse</p>
      <h1>Sign in</h1>
      <p class="lede">Access your second brain.</p>
      <form @submit.prevent="handleLogin" class="login-form">
        <label>
          Username
          <input v-model="username" type="text" autocomplete="username" required />
        </label>
        <label>
          Password
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <p v-if="error" class="form-error">{{ error }}</p>
        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.login-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 2.5rem;
  width: min(420px, 100%);
  box-shadow: var(--shadow);
}

.login-card h1 {
  margin: 0 0 0.5rem;
  font-size: 1.8rem;
  font-family: 'Space Grotesk', sans-serif;
}

.lede {
  color: var(--muted);
  margin: 0 0 2rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.login-form label {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--ink);
}

.login-form input {
  padding: 0.65rem 0.9rem;
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 1rem;
  background: #fff;
  color: var(--ink);
  transition: border-color 0.15s;
}

.login-form input:focus {
  outline: none;
  border-color: var(--accent);
}

.form-error {
  color: #c0392b;
  font-size: 0.875rem;
  margin: 0;
}

.btn-primary {
  padding: 0.7rem 1.4rem;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-strong);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
