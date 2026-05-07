<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  createResource,
  deleteResource,
  getResourceDetail,
  getSynapse,
  listSynapses,
  searchLibraryResources,
  updateResource,
  upsertSynapse,
} from '../api.js'
import { useAuth } from '../composables/useAuth.js'

const { isAdmin } = useAuth()

const DEFAULT_LIBRARY_PAGE_SIZE = 12
const PAGE_SIZE_OPTIONS = [12, 24, 48]
const SEARCH_DEBOUNCE_MS = 250

const activeResourceTab = ref('skills')
const searchQuery = ref('')
const resourcePage = ref(1)
const pageSize = ref(DEFAULT_LIBRARY_PAGE_SIZE)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const removingResourceId = ref('')
const bulkDeleting = ref(false)
const selectedResourceIds = ref([])
const resources = ref({
  items: [],
  total: 0,
  page: 1,
  page_size: DEFAULT_LIBRARY_PAGE_SIZE,
  total_pages: 1,
  counts: { skills: 0, rules: 0, tools: 0 },
})

const editorOpen = ref(false)
const editorLoading = ref(false)
const editorSaving = ref(false)
const editorError = ref('')
const editorForm = ref({ type: '', id: '', name: '', description: '', content: '' })

const attachOpen = ref(false)
const attachLoading = ref(false)
const attachError = ref('')
const attachResources = ref([])
const synapseOptions = ref([])
const attachTarget = ref('')
let searchDebounceId = 0

const createOpen = ref(false)
const createSaving = ref(false)
const createError = ref('')
const createForm = ref({ id: '', name: '', description: '', content: '' })

const groupTypeMap = {
  skills: 'skill',
  rules: 'rule',
  tools: 'tool',
}

const resourceTabs = computed(() => {
  const counts = resources.value.counts || { skills: 0, rules: 0, tools: 0 }
  const tabs = [
    { id: 'skills', label: 'Skills' },
    { id: 'rules', label: 'Rules' },
    { id: 'tools', label: 'Tools' },
  ]
  return tabs.map((tab) => ({
    ...tab,
    count: tab.id === activeResourceTab.value ? resources.value.total || 0 : counts[tab.id] || 0,
  }))
})

const activeTabLabel = computed(() => resourceTabs.value.find((tab) => tab.id === activeResourceTab.value)?.label || 'Resources')
const selectedResources = computed(() => resources.value.items.filter((resource) => selectedResourceIds.value.includes(resource.id)))
const hasSelection = computed(() => selectedResources.value.length > 0)
const allVisibleSelected = computed(() => resources.value.items.length > 0 && resources.value.items.every((resource) => selectedResourceIds.value.includes(resource.id)))
const createContentPlaceholder = computed(() =>
  activeResourceTab.value === 'tools'
    ? '{"id": "my-tool", "name": "My Tool"}'
    : '# My Rule\n\nWrite content here…'
)
const attachDialogTitle = computed(() => {
  if (attachResources.value.length === 1) {
    return attachResources.value[0]?.name || attachResources.value[0]?.id || ''
  }
  return `${attachResources.value.length} resources`
})

function formatSynapseName(name) {
  return name === 'core-brainstem' ? 'Brainstem' : name
}

function pluralize(count, singular, plural = `${singular}s`) {
  return count === 1 ? singular : plural
}

function clearSelection() {
  selectedResourceIds.value = []
}

async function loadResources() {
  loading.value = true
  error.value = ''
  try {
    const data = await searchLibraryResources({
      type: groupTypeMap[activeResourceTab.value],
      query: searchQuery.value,
      page: resourcePage.value,
      pageSize: pageSize.value,
    })
    resources.value = {
      items: data.items || [],
      total: data.total || 0,
      page: data.page || 1,
      page_size: data.page_size || pageSize.value,
      total_pages: data.total_pages || 1,
      counts: data.counts || { skills: 0, rules: 0, tools: 0 },
    }
    clearSelection()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load the shared library.'
    resources.value = {
      items: [],
      total: 0,
      page: 1,
      page_size: pageSize.value,
      total_pages: 1,
      counts: { skills: 0, rules: 0, tools: 0 },
    }
    clearSelection()
  } finally {
    loading.value = false
  }
}

async function loadSynapseOptions() {
  try {
    const data = await listSynapses()
    synapseOptions.value = [...(data.synapses || [])]
      .sort((left, right) => left.name.localeCompare(right.name))
    if (!synapseOptions.value.some((synapse) => synapse.name === attachTarget.value)) {
      attachTarget.value = synapseOptions.value[0]?.name || ''
    }
  } catch {
    synapseOptions.value = []
    attachTarget.value = ''
  }
}

async function applySearch() {
  if (searchDebounceId) {
    window.clearTimeout(searchDebounceId)
    searchDebounceId = 0
  }
  resourcePage.value = 1
  await loadResources()
}

function scheduleSearch() {
  if (searchDebounceId) {
    window.clearTimeout(searchDebounceId)
  }
  resourcePage.value = 1
  searchDebounceId = window.setTimeout(() => {
    searchDebounceId = 0
    void loadResources()
  }, SEARCH_DEBOUNCE_MS)
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

async function removeSelectedResources() {
  if (!selectedResources.value.length) return

  bulkDeleting.value = true
  error.value = ''
  notice.value = ''

  try {
    await Promise.all(
      selectedResources.value.map((resource) => deleteResource(groupTypeMap[activeResourceTab.value], resource.id)),
    )
    const removedCount = selectedResources.value.length
    notice.value = `Removed ${removedCount} ${pluralize(removedCount, activeTabLabel.value.toLowerCase().slice(0, -1), activeTabLabel.value.toLowerCase())} from the shared library and detached them from any synapses that referenced them.`
    if (removedCount >= resources.value.items.length && resources.value.page > 1) {
      resourcePage.value -= 1
    }
    await loadResources()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to remove the selected resources.'
  } finally {
    bulkDeleting.value = false
  }
}

function toggleResourceSelection(resourceId) {
  if (selectedResourceIds.value.includes(resourceId)) {
    selectedResourceIds.value = selectedResourceIds.value.filter((id) => id !== resourceId)
    return
  }
  selectedResourceIds.value = [...selectedResourceIds.value, resourceId]
}

function toggleVisibleSelection() {
  if (allVisibleSelected.value) {
    clearSelection()
    return
  }
  selectedResourceIds.value = resources.value.items.map((resource) => resource.id)
}

function openAttachDialog(resourcesToAttach) {
  attachResources.value = Array.isArray(resourcesToAttach) ? resourcesToAttach : [resourcesToAttach]
  attachError.value = ''
  attachOpen.value = true
  if (!synapseOptions.value.length) {
    attachTarget.value = ''
  }
}

function openBulkAttachDialog() {
  if (!selectedResources.value.length) return
  openAttachDialog(selectedResources.value)
}

function closeAttachDialog() {
  attachOpen.value = false
  attachLoading.value = false
  attachError.value = ''
  attachResources.value = []
}

function openCreateDialog() {
  createForm.value = { id: '', name: '', description: '', content: '' }
  createError.value = ''
  createSaving.value = false
  createOpen.value = true
}

function closeCreateDialog() {
  createOpen.value = false
  createSaving.value = false
  createError.value = ''
}

async function saveCreate() {
  createSaving.value = true
  createError.value = ''
  try {
    const type = groupTypeMap[activeResourceTab.value]
    await createResource(type, {
      id: createForm.value.id.trim() || createForm.value.name.trim(),
      name: createForm.value.name.trim(),
      description: createForm.value.description.trim(),
      content: createForm.value.content,
    })
    notice.value = `Created ${createForm.value.name || createForm.value.id}.`
    await loadResources()
    closeCreateDialog()
  } catch (e) {
    createError.value = e.response?.data?.detail || 'Failed to create resource.'
  } finally {
    createSaving.value = false
  }
}

async function confirmAttachToSynapse() {
  if (!attachResources.value.length || !attachTarget.value) {
    attachError.value = 'Select a synapse before attaching a resource.'
    return
  }

  attachLoading.value = true
  attachError.value = ''
  error.value = ''
  notice.value = ''

  try {
    const synapse = await getSynapse(attachTarget.value)
    const includes = new Set(synapse.includes || [])
    for (const resource of attachResources.value) {
      includes.add(resource.id)
    }
    await upsertSynapse(synapse.name, {
      name: synapse.name,
      description: synapse.description,
      activation: synapse.activation || 'optional',
      includes: [...includes],
      tags: synapse.tags || [],
      common_tasks: synapse.common_tasks || [],
      recommended_tools: synapse.recommended_tools || [],
      extends: synapse.extends || [],
    })
    const attachedCount = attachResources.value.length
    notice.value = attachedCount === 1
      ? `Attached ${attachResources.value[0].id} to ${formatSynapseName(attachTarget.value)}.`
      : `Attached ${attachedCount} resources to ${formatSynapseName(attachTarget.value)}.`
    clearSelection()
    closeAttachDialog()
  } catch (e) {
    attachError.value = e.response?.data?.detail || 'Failed to attach resource to the synapse.'
  } finally {
    attachLoading.value = false
  }
}

watch(searchQuery, () => {
  scheduleSearch()
})

watch(pageSize, () => {
  resourcePage.value = 1
  void loadResources()
})

onBeforeUnmount(() => {
  if (searchDebounceId) {
    window.clearTimeout(searchDebounceId)
  }
})

onMounted(async () => {
  await Promise.all([loadResources(), loadSynapseOptions()])
})
</script>

<template>
  <main class="shell library-shell">
    <section class="library-header panel-surface">
      <div>
        <p class="eyebrow">Shared Library</p>
        <h1>Installed skills, rules, and tools</h1>
        <p class="library-copy">
          Manage what is already in the local shared library, edit resource content, remove anything stale, and attach installed resources directly to a synapse without leaving this screen.
        </p>
      </div>
      <button v-if="isAdmin" type="button" class="btn-primary" @click="openCreateDialog">
        + New {{ activeTabLabel.slice(0, -1) }}
      </button>
    </section>

    <section class="panel-surface library-browser">
      <form class="library-toolbar" @submit.prevent="applySearch">
        <div class="library-toolbar__row">
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

          <label class="resource-search toolbar-field--search" aria-label="Search library resources">
            <div class="resource-search__field">
              <input
                v-model="searchQuery"
                type="text"
                :placeholder="`Search installed ${activeTabLabel.toLowerCase()} by name, description, or path`"
              />
              <span class="resource-search__indicator" :class="{ 'resource-search__indicator--loading': loading }" aria-hidden="true" />
            </div>
          </label>

          <label class="toolbar-field toolbar-field--size">
            <span>Per page</span>
            <select v-model.number="pageSize">
              <option v-for="option in PAGE_SIZE_OPTIONS" :key="option" :value="option">{{ option }}</option>
            </select>
          </label>

          <label class="library-bulkbar__toggle">
            <input
              type="checkbox"
              :checked="allVisibleSelected"
              :disabled="!resources.items.length"
              @change="toggleVisibleSelection"
            />
            <span>Select all on page</span>
          </label>

          <div v-if="hasSelection" class="library-toolbar__actions">
            <button type="button" class="btn-chip" :disabled="!synapseOptions.length || attachLoading" @click="openBulkAttachDialog">
              Add Selected To Synapse
            </button>
            <button type="button" class="btn-chip btn-chip--danger" :disabled="bulkDeleting" @click="removeSelectedResources">
              {{ bulkDeleting ? 'Removing…' : 'Delete Selected' }}
            </button>
            <button type="button" class="btn-chip btn-chip--secondary" @click="clearSelection">
              Clear
            </button>
          </div>
        </div>
      </form>

      <p v-if="notice" class="form-success">{{ notice }}</p>
      <p v-if="error" class="form-error">{{ error }}</p>
      <div v-if="loading" class="loading">Loading library resources…</div>

      <div v-else-if="resources.items.length" class="library-grid">
        <article
          v-for="resource in resources.items"
          :key="resource.id"
          class="resource-card"
          :class="{ 'resource-card--selected': selectedResourceIds.includes(resource.id) }"
        >
          <label class="resource-card__select">
            <input
              type="checkbox"
              :checked="selectedResourceIds.includes(resource.id)"
              @change="toggleResourceSelection(resource.id)"
            />
          </label>
          <strong>{{ resource.name }}</strong>
          <p>{{ resource.description || resource.id }}</p>
          <small>{{ resource.source_path }}</small>
          <div class="resource-card__actions">
            <button type="button" class="btn-chip" :disabled="!synapseOptions.length || attachLoading" @click="openAttachDialog(resource)">
              Add To Synapse
            </button>
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

    <div v-if="attachOpen" class="editor-overlay" @click.self="closeAttachDialog">
      <div class="attach-modal">
        <div class="editor-modal__header">
          <div>
            <p class="eyebrow">Attach Resource</p>
            <h2>{{ attachDialogTitle }}</h2>
          </div>
          <button type="button" class="btn-close" @click="closeAttachDialog">×</button>
        </div>

        <div class="attach-form">
          <label>
            Synapse
            <select v-model="attachTarget">
              <option disabled value="">Select a synapse</option>
              <option v-for="synapse in synapseOptions" :key="synapse.name" :value="synapse.name">
                {{ formatSynapseName(synapse.name) }}
              </option>
            </select>
          </label>

          <p class="attach-copy">
            This keeps {{ attachResources.length === 1 ? 'the resource' : 'these resources' }} in the shared library and adds
            {{ attachResources.length === 1 ? ' its id' : ' their ids' }} to the selected synapse includes list.
          </p>
          <p v-if="attachError" class="form-error">{{ attachError }}</p>

          <div class="form-actions">
            <button type="button" class="btn-primary" :disabled="attachLoading || !attachTarget" @click="confirmAttachToSynapse">
              {{ attachLoading ? 'Attaching…' : 'Confirm Attach' }}
            </button>
            <button type="button" class="btn-cancel btn-cancel--button" @click="closeAttachDialog">Cancel</button>
          </div>
        </div>
      </div>
    </div>

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

    <div v-if="createOpen" class="editor-overlay" @click.self="closeCreateDialog">
      <div class="editor-modal">
        <div class="editor-modal__header">
          <div>
            <p class="eyebrow">Create New</p>
            <h2>New {{ activeTabLabel.slice(0, -1) }}</h2>
          </div>
          <button type="button" class="btn-close" @click="closeCreateDialog">×</button>
        </div>

        <form class="editor-form" @submit.prevent="saveCreate">
          <p v-if="createError" class="form-error">{{ createError }}</p>

          <label>
            Name <span class="field-required">*</span>
            <input v-model="createForm.name" required placeholder="Human-readable name" />
          </label>

          <label>
            ID <span class="field-hint">(optional – auto-generated from name if blank)</span>
            <input v-model="createForm.id" placeholder="e.g. my-new-rule" />
          </label>

          <label>
            Description
            <input v-model="createForm.description" placeholder="One-line summary" />
          </label>

          <label>
            Content <span class="field-hint">(Markdown for rules &amp; skills; JSON for tools)</span>
            <textarea v-model="createForm.content" rows="16" spellcheck="false" :placeholder="createContentPlaceholder" />
          </label>

          <div class="form-actions">
            <button type="submit" class="btn-primary" :disabled="createSaving || !createForm.name.trim()">
              {{ createSaving ? 'Creating…' : `Create ${activeTabLabel.slice(0, -1)}` }}
            </button>
            <button type="button" class="btn-cancel btn-cancel--button" @click="closeCreateDialog">Cancel</button>
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

.library-copy,
.attach-copy {
  margin: 0.65rem 0 0;
  color: var(--muted);
  line-height: 1.6;
  max-width: 68ch;
}

.library-toolbar {
  margin-bottom: 1rem;
}

.library-toolbar__row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  align-items: end;
}

.resource-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.resource-tab {
  min-height: 44px;
  padding: 0.6rem 0.9rem;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.68);
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--ink);
}

.toolbar-field--search {
  flex: 1 1 360px;
}

.resource-tab strong {
  min-width: 24px;
  min-height: 24px;
  display: inline-grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(20, 33, 61, 0.08);
  font-size: 0.75rem;
}

.resource-tab--active {
  border-color: var(--accent);
  background: rgba(247, 214, 200, 0.72);
  box-shadow: 0 12px 28px rgba(20, 33, 61, 0.08);
}

.toolbar-field {
  display: grid;
  gap: 0.45rem;
  font-size: 0.82rem;
  font-weight: 600;
}

.toolbar-field--size {
  min-width: 88px;
}

.toolbar-field select {
  min-height: 42px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.92);
  padding: 0.5rem 0.7rem;
  color: var(--ink);
}

.resource-search,
.attach-form label {
  display: grid;
  gap: 0;
  font-size: 0.85rem;
  font-weight: 600;
}

.resource-search__field {
  position: relative;
}

.resource-search__field input {
  min-height: 38px;
  padding-top: 0.35rem;
  padding-bottom: 0.35rem;
  padding-right: 2.2rem;
}

.toolbar-field--size select {
  min-height: 38px;
  padding: 0.35rem 0.55rem;
  font-size: 0.82rem;
}

.resource-search__indicator {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  width: 10px;
  height: 10px;
  margin-top: -5px;
  border-radius: 999px;
  background: rgba(20, 33, 61, 0.2);
}

.resource-search__indicator--loading {
  background: transparent;
  border: 2px solid rgba(239, 108, 61, 0.25);
  border-top-color: var(--accent-strong);
  animation: spin 0.9s linear infinite;
}

.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.9rem;
  margin-top: 1rem;
}

.resource-card {
  position: relative;
  padding: 0.95rem;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.84);
}

.resource-card--selected {
  border-color: rgba(239, 108, 61, 0.35);
  box-shadow: 0 10px 22px rgba(20, 33, 61, 0.08);
}

.resource-card__select {
  position: absolute;
  top: 0.6rem;
  right: 0.6rem;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.resource-card:hover .resource-card__select,
.resource-card--selected .resource-card__select {
  opacity: 1;
  pointer-events: auto;
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

.library-toolbar__actions {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.library-bulkbar__toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  min-height: 42px;
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
}

.library-bulkbar__toggle span {
  font-size: 0.82rem;
  font-weight: 600;
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

.editor-modal,
.attach-modal {
  width: min(860px, 100%);
  max-height: calc(100vh - 2rem);
  overflow: auto;
  padding: 1.25rem;
  border-radius: 24px;
  border: 1px solid var(--line);
  background: #fff;
  box-shadow: var(--shadow);
}

.attach-modal {
  width: min(520px, 100%);
}

.editor-form,
.attach-form {
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

.field-required {
  color: #dc2626;
}

.field-hint {
  color: var(--muted);
  font-weight: 400;
  font-size: 0.8rem;
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
  white-space: nowrap;
  transition: background 0.15s;
}

.btn-primary:hover { background: var(--accent-strong); }
.btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }

@media (max-width: 960px) {
  .library-toolbar__row {
    align-items: stretch;
  }

  .toolbar-field--size,
  .toolbar-field--search,
  .library-bulkbar__toggle,
  .library-toolbar__actions {
    width: 100%;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>