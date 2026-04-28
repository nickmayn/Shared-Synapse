<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listSynapses, activateSynapse, deactivateSynapse, deleteSynapse } from '../api.js'
import { useAuth } from '../composables/useAuth.js'

const router = useRouter()
const { isAdmin, isContributor } = useAuth()

const synapses = ref([])
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listSynapses()
    synapses.value = data.synapses || []
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load synapses.'
  } finally {
    loading.value = false
  }
}

async function toggle(synapse) {
  try {
    if (synapse.active) {
      await deactivateSynapse(synapse.name)
    } else {
      await activateSynapse(synapse.name)
    }
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || 'Action failed.')
  }
}

async function remove(synapse) {
  if (!confirm(`Delete synapse "${synapse.name}"? This cannot be undone.`)) return
  try {
    await deleteSynapse(synapse.name)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || 'Delete failed.')
  }
}

onMounted(load)
</script>

<template>
  <main class="shell">
    <div class="page-header">
      <div>
        <p class="eyebrow">Neuron Activation Model</p>
        <h1>Synapses</h1>
      </div>
      <router-link v-if="isAdmin" to="/synapses/new" class="btn-primary">+ New Synapse</router-link>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>

    <div v-if="loading" class="loading">Loading synapses…</div>

    <div v-else class="synapse-grid">
      <article v-for="s in synapses" :key="s.name" class="synapse-card" :class="{ active: s.active }">
        <div class="synapse-header">
          <div>
            <span class="synapse-badge" :class="s.activation === 'core' ? 'badge-core' : 'badge-optional'">
              {{ s.activation === 'core' ? 'Core' : 'Optional' }}
            </span>
            <span v-if="s.active" class="synapse-badge badge-active">Active</span>
          </div>
          <div class="synapse-actions" v-if="isContributor">
            <button
              v-if="s.activation !== 'core'"
              class="btn-sm"
              :class="s.active ? 'btn-deactivate' : 'btn-activate'"
              @click="toggle(s)"
            >
              {{ s.active ? 'Deactivate' : 'Activate' }}
            </button>
            <router-link v-if="isAdmin" :to="`/synapses/${s.name}/edit`" class="btn-sm btn-edit">Edit</router-link>
            <button v-if="isAdmin && s.activation !== 'core'" class="btn-sm btn-danger" @click="remove(s)">Delete</button>
          </div>
        </div>

        <h3>{{ s.name }}</h3>
        <p class="synapse-desc">{{ s.description }}</p>

        <div v-if="s.tags?.length" class="tag-list">
          <span v-for="tag in s.tags" :key="tag" class="tag">{{ tag }}</span>
        </div>

        <div v-if="s.includes?.length" class="synapse-meta">
          <strong>Includes:</strong> {{ s.includes.join(', ') }}
        </div>
      </article>
    </div>
  </main>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 2rem;
  gap: 1rem;
}

.page-header h1 {
  margin: 0;
  font-family: 'Space Grotesk', sans-serif;
}

.synapse-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.25rem;
}

.synapse-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 1.5rem;
  transition: box-shadow 0.2s;
}

.synapse-card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft);
}

.synapse-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.synapse-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.2rem 0.55rem;
  border-radius: 20px;
  margin-right: 0.4rem;
}

.badge-core { background: #e8f0fe; color: #1a56db; }
.badge-optional { background: #f3f4f6; color: #4b5563; }
.badge-active { background: var(--accent-soft); color: var(--accent-strong); }

.synapse-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.synapse-card h3 {
  margin: 0 0 0.5rem;
  font-family: 'Space Grotesk', sans-serif;
}

.synapse-desc {
  color: var(--muted);
  font-size: 0.875rem;
  margin: 0 0 1rem;
}

.tag-list {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}

.tag {
  font-size: 0.75rem;
  background: #f3f4f6;
  color: #374151;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.synapse-meta {
  font-size: 0.8rem;
  color: var(--muted);
  margin-top: 0.5rem;
}

.btn-sm {
  font-size: 0.78rem;
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  border: 1px solid var(--line);
  cursor: pointer;
  background: none;
  color: var(--ink);
  text-decoration: none;
  display: inline-block;
  transition: background 0.15s, color 0.15s;
}

.btn-activate { border-color: var(--accent); color: var(--accent); }
.btn-activate:hover { background: var(--accent); color: #fff; }
.btn-deactivate { border-color: #9ca3af; color: #6b7280; }
.btn-deactivate:hover { background: #f3f4f6; }
.btn-edit { border-color: #6366f1; color: #6366f1; }
.btn-edit:hover { background: #6366f1; color: #fff; }
.btn-danger { border-color: #dc2626; color: #dc2626; }
.btn-danger:hover { background: #dc2626; color: #fff; }

.btn-primary {
  padding: 0.65rem 1.25rem;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.15s;
}

.btn-primary:hover { background: var(--accent-strong); }

.loading { color: var(--muted); padding: 2rem 0; }
.form-error { color: #dc2626; margin-bottom: 1rem; }
</style>
