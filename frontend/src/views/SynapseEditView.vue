<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSynapse, upsertSynapse } from '../api.js'

const route = useRoute()
const router = useRouter()

const isEdit = computed(() => !!route.params.name)
const title = computed(() => (isEdit.value ? `Edit: ${route.params.name}` : 'New Synapse'))

const form = ref({
  name: '',
  description: '',
  activation: 'optional',
  includes: '',
  tags: '',
  common_tasks: '',
  recommended_tools: '',
  extends: '',
})

const error = ref('')
const saving = ref(false)
const loading = ref(false)

function parseLines(raw) {
  if (!raw?.trim()) return null
  return raw.split('\n').map((l) => l.trim()).filter(Boolean)
}

async function load() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const s = await getSynapse(route.params.name)
    form.value = {
      name: s.name,
      description: s.description,
      activation: s.activation || 'optional',
      includes: (s.includes || []).join('\n'),
      tags: (s.tags || []).join('\n'),
      common_tasks: (s.common_tasks || []).join('\n'),
      recommended_tools: (s.recommended_tools || []).join('\n'),
      extends: (s.extends || []).join('\n'),
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load synapse.'
  } finally {
    loading.value = false
  }
}

async function save() {
  error.value = ''
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      description: form.value.description,
      activation: form.value.activation,
      includes: parseLines(form.value.includes),
      tags: parseLines(form.value.tags),
      common_tasks: parseLines(form.value.common_tasks),
      recommended_tools: parseLines(form.value.recommended_tools),
      extends: parseLines(form.value.extends),
    }
    await upsertSynapse(form.value.name, payload)
    router.push('/synapses')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Save failed.'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="shell">
    <div class="page-header">
      <div>
        <p class="eyebrow">Synapse Management</p>
        <h1>{{ title }}</h1>
      </div>
      <router-link to="/synapses" class="btn-back">← Back</router-link>
    </div>

    <div v-if="loading" class="loading">Loading…</div>

    <form v-else @submit.prevent="save" class="edit-form">
      <p v-if="error" class="form-error">{{ error }}</p>

      <label>
        Name <span class="req">*</span>
        <input v-model="form.name" :disabled="isEdit" required placeholder="e.g. my-neuron" />
      </label>

      <label>
        Description <span class="req">*</span>
        <input v-model="form.description" required placeholder="Short description of this synapse" />
      </label>

      <label>
        Activation
        <select v-model="form.activation">
          <option value="optional">Optional (must be activated)</option>
          <option value="core">Core (always active)</option>
        </select>
      </label>

      <label>
        Includes <span class="hint">(one per line)</span>
        <textarea v-model="form.includes" rows="4" placeholder="shared-synapse-overview&#10;rule-security" />
      </label>

      <label>
        Extends <span class="hint">(one per line)</span>
        <textarea v-model="form.extends" rows="2" placeholder="core-brainstem" />
      </label>

      <label>
        Tags <span class="hint">(one per line)</span>
        <textarea v-model="form.tags" rows="3" placeholder="backend&#10;api&#10;core" />
      </label>

      <label>
        Common Tasks <span class="hint">(one per line)</span>
        <textarea v-model="form.common_tasks" rows="3" placeholder="add endpoint&#10;debug auth issue" />
      </label>

      <label>
        Recommended Tools <span class="hint">(one per line)</span>
        <textarea v-model="form.recommended_tools" rows="2" placeholder="api-gateway-config" />
      </label>

      <div class="form-actions">
        <button type="submit" class="btn-primary" :disabled="saving">
          {{ saving ? 'Saving…' : 'Save Synapse' }}
        </button>
        <router-link to="/synapses" class="btn-cancel">Cancel</router-link>
      </div>
    </form>
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

.btn-back {
  font-size: 0.875rem;
  color: var(--muted);
  text-decoration: none;
  padding: 0.4rem 0;
}

.btn-back:hover { color: var(--ink); }

.edit-form {
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.edit-form label {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.hint {
  font-weight: 400;
  color: var(--muted);
  font-size: 0.8rem;
}

.req { color: var(--accent); }

.edit-form input,
.edit-form select,
.edit-form textarea {
  padding: 0.65rem 0.9rem;
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 0.9rem;
  background: #fff;
  color: var(--ink);
  transition: border-color 0.15s;
  font-family: inherit;
  resize: vertical;
}

.edit-form input:focus,
.edit-form select:focus,
.edit-form textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.edit-form input:disabled {
  background: #f9fafb;
  color: var(--muted);
}

.form-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
  padding-top: 0.5rem;
}

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

.btn-cancel {
  color: var(--muted);
  text-decoration: none;
  font-size: 0.875rem;
}

.btn-cancel:hover { color: var(--ink); }

.form-error { color: #dc2626; }
.loading { color: var(--muted); }
</style>
