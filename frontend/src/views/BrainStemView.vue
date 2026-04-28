<script setup>
import { ref, onMounted } from 'vue'
import { getSynapse } from '../api.js'
import { useAuth } from '../composables/useAuth.js'

const { isAdmin } = useAuth()
const brainstem = ref(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    brainstem.value = await getSynapse('core-brainstem')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load brain stem.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="shell">
    <div class="page-header">
      <div>
        <p class="eyebrow">Always-On Baseline</p>
        <h1>Core Brain Stem</h1>
      </div>
      <router-link v-if="isAdmin" to="/synapses/core-brainstem/edit" class="btn-primary">
        Edit Brain Stem
      </router-link>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <div v-if="loading" class="loading">Loading brain stem…</div>

    <template v-else-if="brainstem">
      <p class="lede">{{ brainstem.description }}</p>

      <div class="bs-grid">
        <section class="bs-panel">
          <h3>Includes</h3>
          <ul>
            <li v-for="item in brainstem.includes" :key="item">{{ item }}</li>
          </ul>
        </section>

        <section class="bs-panel">
          <h3>Common Tasks</h3>
          <ul>
            <li v-for="task in brainstem.common_tasks" :key="task">{{ task }}</li>
          </ul>
        </section>

        <section class="bs-panel">
          <h3>Tags</h3>
          <div class="tag-list">
            <span v-for="tag in brainstem.tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
        </section>
      </div>

      <div class="bs-status">
        <span class="synapse-badge badge-core">Core</span>
        <span class="synapse-badge badge-active">Always Active</span>
      </div>
    </template>
  </main>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.page-header h1 {
  margin: 0;
  font-family: 'Space Grotesk', sans-serif;
}

.lede {
  color: var(--muted);
  margin-bottom: 2rem;
  max-width: 640px;
}

.bs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1.25rem;
  margin-bottom: 1.5rem;
}

.bs-panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 1.25rem;
}

.bs-panel h3 {
  margin: 0 0 0.75rem;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
}

.bs-panel ul {
  margin: 0;
  padding-left: 1.25rem;
}

.bs-panel li {
  font-size: 0.875rem;
  color: var(--ink);
  margin-bottom: 0.3rem;
}

.tag-list { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.tag {
  font-size: 0.75rem;
  background: #f3f4f6;
  color: #374151;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.bs-status { display: flex; gap: 0.5rem; }

.synapse-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.2rem 0.55rem;
  border-radius: 20px;
}

.badge-core { background: #e8f0fe; color: #1a56db; }
.badge-active { background: var(--accent-soft); color: var(--accent-strong); }

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

.loading { color: var(--muted); }
.form-error { color: #dc2626; }
</style>
