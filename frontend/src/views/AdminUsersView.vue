<script setup>
import { ref, onMounted } from 'vue'
import {
  listUsers,
  createUser,
  updateUserRole,
  deactivateUser,
  activateUser,
} from '../api.js'

const users = ref([])
const loading = ref(true)
const error = ref('')

const showCreateForm = ref(false)
const newUser = ref({ username: '', password: '', role: 'viewer' })
const createError = ref('')
const creating = ref(false)

const ROLES = ['admin', 'contributor', 'viewer']

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listUsers()
    users.value = data.users || []
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load users.'
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  createError.value = ''
  creating.value = true
  try {
    await createUser(newUser.value)
    newUser.value = { username: '', password: '', role: 'viewer' }
    showCreateForm.value = false
    await load()
  } catch (e) {
    createError.value = e.response?.data?.detail || 'Create failed.'
  } finally {
    creating.value = false
  }
}

async function changeRole(user, role) {
  try {
    await updateUserRole(user.id, role)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || 'Update failed.')
  }
}

async function toggleActive(user) {
  try {
    if (user.active) {
      await deactivateUser(user.id)
    } else {
      await activateUser(user.id)
    }
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || 'Action failed.')
  }
}

onMounted(load)
</script>

<template>
  <main class="shell">
    <div class="page-header">
      <div>
        <p class="eyebrow">Administration</p>
        <h1>User Management</h1>
      </div>
      <button class="btn-primary" @click="showCreateForm = !showCreateForm">
        {{ showCreateForm ? 'Cancel' : '+ New User' }}
      </button>
    </div>

    <div v-if="showCreateForm" class="create-form card">
      <h3>Create User</h3>
      <p v-if="createError" class="form-error">{{ createError }}</p>
      <form @submit.prevent="handleCreate">
        <label>
          Username
          <input v-model="newUser.username" required autocomplete="off" />
        </label>
        <label>
          Password
          <input v-model="newUser.password" type="password" required autocomplete="new-password" />
        </label>
        <label>
          Role
          <select v-model="newUser.role">
            <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
          </select>
        </label>
        <button type="submit" class="btn-primary" :disabled="creating">
          {{ creating ? 'Creating…' : 'Create' }}
        </button>
      </form>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <div v-if="loading" class="loading">Loading users…</div>

    <table v-else class="users-table">
      <thead>
        <tr>
          <th>Username</th>
          <th>Role</th>
          <th>Status</th>
          <th>Created</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id" :class="{ inactive: !user.active }">
          <td class="user-name">{{ user.username }}</td>
          <td>
            <select :value="user.role" @change="changeRole(user, $event.target.value)" class="role-select">
              <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
            </select>
          </td>
          <td>
            <span class="status-badge" :class="user.active ? 'badge-active' : 'badge-inactive'">
              {{ user.active ? 'Active' : 'Inactive' }}
            </span>
          </td>
          <td class="date-cell">{{ new Date(user.created_at).toLocaleDateString() }}</td>
          <td>
            <button class="btn-sm" :class="user.active ? 'btn-danger' : 'btn-activate'" @click="toggleActive(user)">
              {{ user.active ? 'Deactivate' : 'Activate' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </main>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
}

.page-header h1 {
  margin: 0;
  font-family: 'Space Grotesk', sans-serif;
}

.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 1.5rem;
  max-width: 480px;
  margin-bottom: 2rem;
}

.card h3 {
  margin: 0 0 1rem;
  font-family: 'Space Grotesk', sans-serif;
}

.card form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.card label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.card input,
.card select {
  padding: 0.6rem 0.85rem;
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 0.9rem;
  background: #fff;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.users-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  border-bottom: 2px solid var(--line);
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
}

.users-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
}

.users-table tr.inactive td {
  opacity: 0.5;
}

.user-name { font-weight: 600; }

.date-cell { color: var(--muted); font-size: 0.8rem; }

.role-select {
  padding: 0.3rem 0.5rem;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  font-size: 0.85rem;
  color: var(--ink);
}

.status-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  border-radius: 20px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.badge-active { background: #d1fae5; color: #065f46; }
.badge-inactive { background: #f3f4f6; color: #6b7280; }

.btn-primary {
  padding: 0.65rem 1.25rem;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-primary:hover:not(:disabled) { background: var(--accent-strong); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-sm {
  font-size: 0.78rem;
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  border: 1px solid var(--line);
  cursor: pointer;
  background: none;
  transition: background 0.15s, color 0.15s;
}

.btn-activate { border-color: var(--accent); color: var(--accent); }
.btn-activate:hover { background: var(--accent); color: #fff; }
.btn-danger { border-color: #dc2626; color: #dc2626; }
.btn-danger:hover { background: #dc2626; color: #fff; }

.form-error { color: #dc2626; margin-bottom: 1rem; }
.loading { color: var(--muted); }
</style>
