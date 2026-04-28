<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getSynapse,
  getSynapseResources,
  searchLibraryResources,
  upsertSynapse,
} from '../api.js'

const route = useRoute()
const router = useRouter()

const LIBRARY_PAGE_SIZE = 8

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
const resourcesLoading = ref(false)
const libraryLoading = ref(false)
const libraryError = ref('')
const resources = ref({ skills: [], rules: [], tools: [], other: [], missing: [] })
const selectedSkills = ref([])
const selectedRules = ref([])
const selectedTools = ref([])
const activeResourceTab = ref('skills')
const resourceSearch = ref('')
const resourcePage = ref(1)
const libraryResults = ref({
  items: [],
  total: 0,
  page: 1,
  page_size: LIBRARY_PAGE_SIZE,
  total_pages: 1,
  counts: { skills: 0, rules: 0, tools: 0 },
})

const groupTypeMap = {
  skills: 'skill',
  rules: 'rule',
  tools: 'tool',
}

const resourceTabs = computed(() => ([
  { id: 'skills', label: 'Skills', count: selectedSkills.value.length },
  { id: 'rules', label: 'Rules', count: selectedRules.value.length },
  { id: 'tools', label: 'Tools', count: selectedTools.value.length },
]))

const activeTabLabel = computed(() => resourceTabs.value.find((tab) => tab.id === activeResourceTab.value)?.label || 'Resources')

function parseLines(raw) {
  if (!raw?.trim()) return null
  return raw.split('\n').map((line) => line.trim()).filter(Boolean)
}

function uniqueIds(values) {
  return [...new Set((values || []).filter(Boolean))]
}

function sortResources(items) {
  return [...items].sort((left, right) => (left.name || left.id).localeCompare(right.name || right.id))
}

function selectedBucket(group) {
  if (group === 'skills') return selectedSkills
  if (group === 'rules') return selectedRules
  return selectedTools
}

function isSelected(bucket, resourceId) {
  return bucket.value.includes(resourceId)
}

function rememberAttachedResource(group, resource) {
  if (!resource) return
  const existing = resources.value[group] || []
  if (existing.some((item) => item.id === resource.id)) return
  resources.value = {
    ...resources.value,
    [group]: sortResources([...existing, resource]),
  }
}

function toggleSelection(group, resourceId, resource = null) {
  const bucket = selectedBucket(group)
  const current = new Set(bucket.value)
  if (current.has(resourceId)) {
    current.delete(resourceId)
  } else {
    current.add(resourceId)
    rememberAttachedResource(group, resource)
  }
  bucket.value = [...current]
}

function resourceMatchesSearch(resource) {
  const query = resourceSearch.value.trim().toLowerCase()
  if (!query) return true
  return [resource.name, resource.description, resource.id, resource.source_path]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(query))
}

function attachedResources(group) {
  const bucket = selectedBucket(group)
  return sortResources(resources.value[group] || [])
    .filter((resource) => isSelected(bucket, resource.id))
    .filter(resourceMatchesSearch)
}

async function loadLibraryResources() {
  if (!isEdit.value) return
  libraryLoading.value = true
  libraryError.value = ''
  try {
    const data = await searchLibraryResources({
      type: groupTypeMap[activeResourceTab.value],
      query: resourceSearch.value,
      page: resourcePage.value,
      pageSize: LIBRARY_PAGE_SIZE,
    })
    libraryResults.value = {
      items: data.items || [],
      total: data.total || 0,
      page: data.page || 1,
      page_size: data.page_size || LIBRARY_PAGE_SIZE,
      total_pages: data.total_pages || 1,
      counts: data.counts || libraryResults.value.counts,
    }
  } catch (e) {
    libraryError.value = e.response?.data?.detail || 'Failed to load the local library.'
    libraryResults.value = {
      items: [],
      total: 0,
      page: 1,
      page_size: LIBRARY_PAGE_SIZE,
      total_pages: 1,
      counts: libraryResults.value.counts,
    }
  } finally {
    libraryLoading.value = false
  }
}

async function applyLibrarySearch() {
  resourcePage.value = 1
  await loadLibraryResources()
}

async function changeResourceTab(tabId) {
  if (activeResourceTab.value === tabId) return
  activeResourceTab.value = tabId
  resourcePage.value = 1
  await loadLibraryResources()
}

async function goToResourcePage(page) {
  resourcePage.value = page
  await loadLibraryResources()
}

async function load() {
  if (!isEdit.value) return
  loading.value = true
  resourcesLoading.value = true
  try {
    const [synapse, groupedResources] = await Promise.all([
      getSynapse(route.params.name),
      getSynapseResources(route.params.name),
    ])
    form.value = {
      name: synapse.name,
      description: synapse.description,
      activation: synapse.activation || 'optional',
      includes: (synapse.includes || []).join('\n'),
      tags: (synapse.tags || []).join('\n'),
      common_tasks: (synapse.common_tasks || []).join('\n'),
      recommended_tools: (synapse.recommended_tools || []).join('\n'),
      extends: (synapse.extends || []).join('\n'),
    }
    resources.value = {
      ...groupedResources,
      skills: sortResources(groupedResources.skills || []),
      rules: sortResources(groupedResources.rules || []),
      tools: sortResources(groupedResources.tools || []),
    }
    selectedSkills.value = (groupedResources.skills || []).map((resource) => resource.id)
    selectedRules.value = (groupedResources.rules || []).map((resource) => resource.id)
    selectedTools.value = (groupedResources.tools || []).map((resource) => resource.id)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load synapse.'
  } finally {
    loading.value = false
    resourcesLoading.value = false
  }
}

async function save() {
  error.value = ''
  saving.value = true
  try {
    const preservedIncludes = [
      ...(resources.value.other || []).map((resource) => resource.id),
      ...(resources.value.missing || []).map((resource) => resource.id),
    ]
    const payload = {
      name: form.value.name,
      description: form.value.description,
      activation: form.value.activation,
      includes: uniqueIds([
        ...selectedSkills.value,
        ...selectedRules.value,
        ...selectedTools.value,
        ...preservedIncludes,
      ]),
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

onMounted(async () => {
  if (!isEdit.value) return
  await Promise.all([load(), loadLibraryResources()])
})
</script>

<template>
  <main class="shell synapse-shell">
    <div class="page-header">
      <div>
        <p class="eyebrow">Synapse Management</p>
        <h1>{{ title }}</h1>
      </div>
      <router-link to="/synapses" class="btn-back">← Back</router-link>
    </div>

    <div v-if="loading" class="loading">Loading…</div>

    <template v-else>
      <section class="form-panel">
        <form class="edit-form" @submit.prevent="save">
          <p v-if="error" class="form-error">{{ error }}</p>

          <div class="form-grid">
            <label>
              Name <span class="req">*</span>
              <input v-model="form.name" :disabled="isEdit" required placeholder="e.g. my-neuron" />
            </label>

            <label>
              Activation
              <select v-model="form.activation">
                <option value="optional">Optional (must be activated)</option>
                <option value="core">Core (always active)</option>
              </select>
            </label>

            <label class="form-grid__wide">
              Description <span class="req">*</span>
              <input v-model="form.description" required placeholder="Short description of this synapse" />
            </label>

            <label class="form-grid__wide">
              Tags <span class="hint">(one per line)</span>
              <textarea v-model="form.tags" rows="3" placeholder="backend&#10;api&#10;core" />
            </label>
          </div>

          <div class="form-actions">
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? 'Saving…' : 'Save Synapse' }}
            </button>
            <router-link to="/synapses" class="btn-cancel">Cancel</router-link>
          </div>
        </form>
      </section>

      <section v-if="isEdit" class="resource-workspace">
        <div class="resource-header">
          <div>
            <p class="eyebrow">Synapse Resources</p>
            <h2>Skills, rules, and tools</h2>
            <p class="resource-copy">
              Use the tabs to inspect one resource type at a time, search within it, and move items in or out of this synapse.
            </p>
          </div>
        </div>

        <div v-if="resourcesLoading" class="loading">Loading attached resources…</div>

        <template v-else>
          <form class="resource-toolbar" @submit.prevent="applyLibrarySearch">
            <div class="resource-tabs" role="tablist" aria-label="Resource categories">
              <button
                v-for="tab in resourceTabs"
                :key="tab.id"
                type="button"
                class="resource-tab"
                :class="{ 'resource-tab--active': activeResourceTab === tab.id }"
                @click="changeResourceTab(tab.id)"
              >
                <span>{{ tab.label }}</span>
                <strong>{{ tab.count }}</strong>
              </button>
            </div>

            <div class="resource-toolbar__controls">
              <label class="resource-search">
                <span>Search {{ activeTabLabel.toLowerCase() }}</span>
                <input
                  v-model="resourceSearch"
                  type="text"
                  :placeholder="`Search ${activeTabLabel.toLowerCase()} by name, description, or path`"
                />
              </label>
              <button type="submit" class="btn-secondary" :disabled="libraryLoading">
                {{ libraryLoading ? 'Searching…' : 'Search Library' }}
              </button>
            </div>
          </form>

          <section class="resource-pane resource-library-panel">
            <div class="resource-pane__header">
              <h3>Add from shared library</h3>
              <span>{{ libraryResults.total }}</span>
            </div>

            <p class="resource-copy resource-copy--tight">
              Search the shared library and attach the exact skills, rules, or tools this synapse should use.
            </p>

            <p v-if="libraryError" class="form-error">{{ libraryError }}</p>
            <div v-else-if="libraryLoading" class="loading">Loading shared library…</div>

            <div v-else-if="libraryResults.items.length" class="resource-list">
              <article
                v-for="resource in libraryResults.items"
                :key="resource.id"
                class="resource-card"
                :class="{ 'resource-card--selected': isSelected(selectedBucket(activeResourceTab), resource.id) }"
              >
                <strong>{{ resource.name }}</strong>
                <p>{{ resource.description || resource.id }}</p>
                <small>{{ resource.source_path }}</small>
                <div class="resource-card__actions">
                  <button
                    v-if="!isSelected(selectedBucket(activeResourceTab), resource.id)"
                    type="button"
                    class="btn-chip"
                    @click="toggleSelection(activeResourceTab, resource.id, resource)"
                  >
                    Add {{ activeTabLabel.slice(0, -1) }}
                  </button>
                  <button
                    v-else
                    type="button"
                    class="btn-chip btn-chip--secondary btn-chip--active"
                    disabled
                  >
                    Attached
                  </button>
                </div>
              </article>
            </div>

            <p v-else class="resource-empty">No {{ activeTabLabel.toLowerCase() }} in the shared library match this search.</p>

            <div class="library-pagination">
              <button
                type="button"
                class="btn-secondary"
                :disabled="libraryLoading || libraryResults.page <= 1"
                @click="goToResourcePage(libraryResults.page - 1)"
              >
                Previous
              </button>
              <p>
                Page {{ libraryResults.page }} of {{ libraryResults.total_pages }}
                <span>·</span>
                {{ libraryResults.total }} total
              </p>
              <button
                type="button"
                class="btn-secondary"
                :disabled="libraryLoading || libraryResults.page >= libraryResults.total_pages"
                @click="goToResourcePage(libraryResults.page + 1)"
              >
                Next
              </button>
            </div>
          </section>

          <div class="resource-stage">
            <section class="resource-pane resource-pane--attached">
              <div class="resource-pane__header">
                <h3>Attached to this synapse</h3>
                <span>{{ attachedResources(activeResourceTab).length }}</span>
              </div>

              <div v-if="attachedResources(activeResourceTab).length" class="resource-list">
                <article
                  v-for="resource in attachedResources(activeResourceTab)"
                  :key="resource.id"
                  class="resource-card resource-card--selected"
                >
                  <strong>{{ resource.name }}</strong>
                  <p>{{ resource.description || resource.id }}</p>
                  <small>{{ resource.source_path }}</small>
                  <div class="resource-card__actions">
                    <button type="button" class="btn-chip btn-chip--danger" @click="toggleSelection(activeResourceTab, resource.id)">
                      Remove
                    </button>
                  </div>
                </article>
              </div>
              <p v-else class="resource-empty">No {{ activeTabLabel.toLowerCase() }} are currently attached for this search.</p>
            </section>
          </div>

          <section v-if="resources.other.length || resources.missing.length" class="resource-meta-panel">
            <div class="resource-pane__header">
              <h3>Other references</h3>
              <span>{{ resources.other.length + resources.missing.length }}</span>
            </div>
            <div v-if="resources.other.length" class="resource-list resource-list--compact">
              <article v-for="resource in resources.other" :key="resource.id" class="resource-card">
                <strong>{{ resource.name }}</strong>
                <p>{{ resource.description || resource.id }}</p>
                <small>{{ resource.source_path }}</small>
              </article>
            </div>
            <div v-if="resources.missing.length" class="resource-list resource-list--compact">
              <article v-for="resource in resources.missing" :key="resource.id" class="resource-card resource-card--missing">
                <strong>{{ resource.id }}</strong>
                <p>Referenced in includes but not found locally or in indexed documents.</p>
              </article>
            </div>
          </section>
        </template>
      </section>
    </template>

  </main>
</template>

<style scoped>
.synapse-shell {
  display: grid;
  gap: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.page-header h1,
.resource-header h2,
.resource-pane__header h3 {
  margin: 0;
  font-family: 'Space Grotesk', sans-serif;
}

.btn-back {
  min-width: 122px;
}

.form-panel,
.resource-workspace,
.resource-meta-panel {
  border-radius: 24px;
  border: 1px solid var(--line);
  background: var(--panel);
  box-shadow: var(--shadow);
  backdrop-filter: blur(16px);
}

.form-panel {
  padding: 1.4rem;
}

.edit-form {
  display: grid;
  gap: 1rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.form-grid__wide {
  grid-column: 1 / -1;
}

.resource-workspace {
  padding: 1.4rem;
  display: grid;
  gap: 1rem;
}

.resource-copy {
  margin: 0.65rem 0 0;
  color: var(--muted);
  line-height: 1.6;
  max-width: 72ch;
}

.resource-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 460px);
  gap: 1rem;
  align-items: end;
}

.resource-toolbar__controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: end;
}

.resource-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.resource-tab {
  min-height: 52px;
  padding: 0.8rem 1rem;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.68);
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  color: var(--ink);
}

.resource-tab strong,
.resource-pane__header span {
  min-width: 28px;
  min-height: 28px;
  display: inline-grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(20, 33, 61, 0.08);
  font-size: 0.8rem;
}

.resource-tab--active {
  border-color: var(--accent);
  background: rgba(247, 214, 200, 0.72);
  box-shadow: 0 12px 28px rgba(20, 33, 61, 0.08);
}

.resource-search {
  display: grid;
  gap: 0.45rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.resource-stage {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  align-items: start;
}

.resource-library-panel {
  display: grid;
  gap: 1rem;
}

.resource-copy--tight {
  margin-top: 0;
  max-width: none;
}

.resource-pane,
.resource-meta-panel {
  padding: 1rem;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.6);
}

.resource-pane {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 0;
}

.resource-pane__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.9rem;
}

.resource-list {
  display: grid;
  gap: 0.8rem;
  max-height: min(56vh, 38rem);
  overflow: auto;
  padding-right: 0.35rem;
}

.resource-list--compact {
  margin-top: 0.85rem;
  max-height: 14rem;
}

.resource-pane--attached .resource-list {
  max-height: min(48vh, 28rem);
}

.resource-card {
  padding: 0.95rem;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.84);
}

.resource-card--selected {
  border-color: rgba(239, 108, 61, 0.28);
  background: rgba(247, 214, 200, 0.35);
}

.resource-card--missing {
  border-style: dashed;
}

.resource-card strong {
  display: block;
  margin-bottom: 0.35rem;
}

.resource-card p {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}

.resource-card small {
  display: block;
  margin-top: 0.5rem;
  color: var(--muted);
}

.resource-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 0.85rem;
}

.resource-empty {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
}

.btn-chip {
  min-height: 38px;
  border: 1px solid rgba(239, 108, 61, 0.24);
  background: rgba(255, 255, 255, 0.96);
  color: var(--accent-strong);
  border-radius: 999px;
  padding: 0.45rem 0.82rem;
  font-size: 0.78rem;
  font-weight: 600;
  box-shadow: 0 8px 18px rgba(20, 33, 61, 0.08);
}

.btn-chip--secondary {
  border-color: var(--line);
  color: var(--ink);
}

.btn-chip--danger {
  border-color: rgba(185, 71, 31, 0.22);
  color: var(--accent-strong);
  background: rgba(247, 214, 200, 0.55);
}

.btn-chip--active {
  box-shadow: none;
}

.library-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--line);
  flex-wrap: wrap;
}

.library-pagination p {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
}

@media (max-width: 960px) {
  .form-grid,
  .resource-toolbar,
  .resource-toolbar__controls,
  .resource-stage {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
  }
}
</style>
