<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  deleteResource,
  getResourceDetail,
  importLocalProjectResources,
  searchLibraryResources,
  updateResource,
} from '../api.js'

const LIBRARY_PAGE_SIZE = 12

const activeResourceTab = ref('skills')
const searchQuery = ref('')
const resourcePage = ref(1)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const localInstallLoading = ref(false)
const removingResourceId = ref('')
const resources = ref({
  items: [],
  total: 0,
  page: 1,
  page_size: LIBRARY_PAGE_SIZE,
  total_pages: 1,
  counts: { skills: 0, rules: 0, tools: 0 },
})

const editorOpen = ref(false)
const editorLoading = ref(false)
const editorSaving = ref(false)
const editorError = ref('')
const editorForm = ref({ type: '', id: '', name: '', description: '', content: '' })

const groupTypeMap = {
  skills: 'skill',
  rules: 'rule',
  tools: 'tool',
}

const resourceTabs = computed(() => ([
  { id: 'skills', label: 'Skills', count: resources.value.counts.skills || 0 },
  { id: 'rules', label: 'Rules', count: resources.value.counts.rules || 0 },
  { id: 'tools', label: 'Tools', count: resources.value.counts.tools || 0 },
]))

const activeTabLabel = computed(() => resourceTabs.value.find((tab) => tab.id === activeResourceTab.value)?.label || 'Resources')

async function loadResources() {
  loading.value = true
  error.value = ''
  try {
    const data = await searchLibraryResources({
      type: groupTypeMap[activeResourceTab.value],
      query: searchQuery.value,
      page: resourcePage.value,
      pageSize: LIBRARY_PAGE_SIZE,
    })
    resources.value = {
      items: data.items || [],
      total: data.total || 0,
      page: data.page || 1,
      page_size: data.page_size || LIBRARY_PAGE_SIZE,
      total_pages: data.total_pages || 1,
      counts: data.counts || { skills: 0, rules: 0, tools: 0 },
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load the shared library.'
    resources.value = {
      items: [],
      total: 0,
      page: 1,
      page_size: LIBRARY_PAGE_SIZE,
      total_pages: 1,
      counts: { skills: 0, rules: 0, tools: 0 },
    }
  } finally {
    loading.value = false
  }
}

async function applySearch() {
  resourcePage.value = 1
  await loadResources()
}

async function changeResourceTab(tabId) {
  if (activeResourceTab.value === tabId) return
  activeResourceTab.value = tabId
  resourcePage.value = 1
  await loadResources()
}

async function goToResourcePage(page) {
  resourcePage.value = page
  await loadResources()
}

async function installProjectLibrary() {
  localInstallLoading.value = true
  error.value = ''
  notice.value = ''
  try {
    const data = await importLocalProjectResources({
      types: ['skill', 'rule', 'tool'],
      synapse_name: 'core-brainstem',
    })
    notice.value = `Installed ${data.success} bundled resources into core-brainstem.`
    if (data.failed) {
      error.value = `${data.failed} files could not be indexed.`
    }
    await loadResources()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Project install failed.'
  } finally {
    localInstallLoading.value = false
  }
}

async function openEditor(resourceType, resourceId) {
  editorOpen.value = true
  editorLoading.value = true
  editorSaving.value = false
  editorError.value = ''
  try {
    const detail = await getResourceDetail(resourceType, resourceId)
    editorForm.value = {
      type: resourceType,
      id: resourceId,
      name: detail.name || resourceId,
      description: detail.description || '',
      content: detail.content || '',
    }
  } catch (e) {
    editorError.value = e.response?.data?.detail || 'Failed to load resource.'
  } finally {
    editorLoading.value = false
  }
}

function closeEditor() {
  editorOpen.value = false
  editorLoading.value = false
  editorSaving.value = false
  editorError.value = ''
}

async function saveEditor() {
  editorSaving.value = true
  editorError.value = ''
  try {
    await updateResource(editorForm.value.type, editorForm.value.id, {
      name: editorForm.value.name,
      description: editorForm.value.description,
      content: editorForm.value.content,
    })
    notice.value = `Updated ${editorForm.value.id}.`
    await loadResources()
    closeEditor()
  } catch (e) {
    editorError.value = e.response?.data?.detail || 'Failed to save resource.'
  } finally {
    editorSaving.value = false
  }
}

async function removeLibraryResource(resource) {
  removingResourceId.value = resource.id
  error.value = ''
  notice.value = ''
  try {
    await deleteResource(groupTypeMap[activeResourceTab.value], resource.id)
    notice.value = `Removed ${resource.id} from the shared library and detached it from any synapses that referenced it.`
    if (resources.value.items.length === 1 && resources.value.page > 1) {
      resourcePage.value -= 1
    }
    await loadResources()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to remove resource.'
  } finally {
    removingResourceId.value = ''
  }
}

onMounted(loadResources)
</script>

<template>
  <main class="shell library-shell">
    <section class="library-header panel-surface">
      <div>
        <p class="eyebrow">Shared Library</p>
        <h1>Installed skills, rules, and tools</h1>
        <p class="library-copy">
          Search the shared library, edit the resources you already installed, and remove anything that should no longer be available across synapses.
        </p>
      </div>
      <button type="button" class="btn-primary" :disabled="localInstallLoading" @click="installProjectLibrary">
        {{ localInstallLoading ? 'Installing…' : 'Install Project Resources' }}
      </button>
    </section>

    <section class="panel-surface library-browser">
      <form class="library-toolbar" @submit.prevent="applySearch">
        <div class="resource-tabs" role="tablist" aria-label="Library categories">
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

        <div class="library-toolbar__controls">
          <label class="resource-search">
            <span>Search {{ activeTabLabel.toLowerCase() }}</span>
            <input
              v-model="searchQuery"
              type="text"
              :placeholder="`Search ${activeTabLabel.toLowerCase()} by name, description, or path`"
            />
          </label>
          <button type="submit" class="btn-secondary" :disabled="loading">
            {{ loading ? 'Searching…' : 'Search' }}
          </button>
        </div>
      </form>

      <p v-if="notice" class="form-success">{{ notice }}</p>
      <p v-if="error" class="form-error">{{ error }}</p>
      <div v-if="loading" class="loading">Loading library resources…</div>

      <div v-else-if="resources.items.length" class="library-grid">
        <article v-for="resource in resources.items" :key="resource.id" class="resource-card">
          <strong>{{ resource.name }}</strong>
          <p>{{ resource.description || resource.id }}</p>
          <small>{{ resource.source_path }}</small>
          <div class="resource-card__actions">
            <button type="button" class="btn-chip btn-chip--secondary" @click="openEditor(groupTypeMap[activeResourceTab], resource.id)">
              View / Edit
            </button>
            <button
              type="button"
              class="btn-chip btn-chip--danger"
              :disabled="removingResourceId === resource.id"
              @click="removeLibraryResource(resource)"
            >
              {{ removingResourceId === resource.id ? 'Removing…' : 'Remove' }}
            </button>
          </div>
        </article>
      </div>

      <p v-else class="resource-empty">No {{ activeTabLabel.toLowerCase() }} in the shared library match this search.</p>

      <div class="library-pagination">
        <button
          type="button"
          class="btn-secondary"
          :disabled="loading || resources.page <= 1"
          @click="goToResourcePage(resources.page - 1)"
        >
          Previous
        </button>
        <p>
          Page {{ resources.page }} of {{ resources.total_pages }}
          <span>·</span>
          {{ resources.total }} total
        </p>
        <button
          type="button"
          class="btn-secondary"
          :disabled="loading || resources.page >= resources.total_pages"
          @click="goToResourcePage(resources.page + 1)"
        >
          Next
        </button>
      </div>
    </section>

    <div v-if="editorOpen" class="editor-overlay" @click.self="closeEditor">
      <div class="editor-modal">
        <div class="editor-modal__header">
          <div>
            <p class="eyebrow">Resource Editor</p>
            <h2>{{ editorForm.name || editorForm.id }}</h2>
          </div>
          <button type="button" class="btn-close" @click="closeEditor">×</button>
        </div>

        <div v-if="editorLoading" class="loading">Loading resource…</div>

        <form v-else class="editor-form" @submit.prevent="saveEditor">
          <p v-if="editorError" class="form-error">{{ editorError }}</p>

          <label>
            Name
            <input v-model="editorForm.name" required />
          </label>

          <label>
            Description
            <input v-model="editorForm.description" />
          </label>

          <label>
            Content
            <textarea v-model="editorForm.content" rows="16" spellcheck="false" />
          </label>

          <div class="form-actions">
            <button type="submit" class="btn-primary" :disabled="editorSaving">
              {{ editorSaving ? 'Saving…' : 'Save Resource' }}
            </button>
            <button type="button" class="btn-cancel btn-cancel--button" @click="closeEditor">Close</button>
          </div>
        </form>
      </div>
    </div>
  </main>
</template>

<style scoped>
.library-shell {
  display: grid;
  gap: 1.5rem;
}

.panel-surface {
  border-radius: 24px;
  border: 1px solid var(--line);
  background: var(--panel);
  box-shadow: var(--shadow);
  backdrop-filter: blur(16px);
}

.library-header,
.library-browser {
  padding: 1.4rem;
}

.library-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.library-header h1,
.editor-modal__header h2 {
  margin: 0;
  font-family: 'Space Grotesk', sans-serif;
}

.library-copy {
  margin: 0.65rem 0 0;
  color: var(--muted);
  line-height: 1.6;
  max-width: 68ch;
}

.library-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 460px);
  gap: 1rem;
  align-items: end;
}

.library-toolbar__controls {
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
  color: var(--ink);
}

.resource-tab strong {
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

.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.9rem;
  margin-top: 1rem;
}

.resource-card {
  padding: 0.95rem;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.84);
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
  margin: 1rem 0 0;
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

.library-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding-top: 1rem;
  margin-top: 1rem;
  border-top: 1px solid var(--line);
  flex-wrap: wrap;
}

.library-pagination p {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
}

.editor-overlay {
  position: fixed;
  inset: 0;
  background: rgba(20, 33, 61, 0.32);
  display: grid;
  place-items: center;
  padding: 1rem;
  z-index: 200;
}

.editor-modal {
  width: min(860px, 100%);
  max-height: calc(100vh - 2rem);
  overflow: auto;
  padding: 1.25rem;
  border-radius: 24px;
  border: 1px solid var(--line);
  background: #fff;
  box-shadow: var(--shadow);
}

.editor-form {
  display: grid;
  gap: 1rem;
}

.editor-modal__header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.btn-close {
  width: 44px;
  height: 44px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  font-size: 1.5rem;
  line-height: 1;
  color: var(--muted);
}

.btn-cancel--button {
  min-width: 112px;
}

@media (max-width: 960px) {
  .library-header,
  .library-toolbar,
  .library-toolbar__controls {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
}
</style>