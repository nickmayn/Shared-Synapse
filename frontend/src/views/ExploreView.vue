<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  getSkillsDirectoryDetail,
  importGithubCandidate,
  listGithubCandidates,
  listResources,
  searchGithubRepos,
  searchHostedMcpConnectors,
  searchSkillsDirectory,
} from '../api.js'
import ExploreDetailDrawer from '../components/ExploreDetailDrawer.vue'
import ExploreResultCard from '../components/ExploreResultCard.vue'

const SEARCH_PAGE_SIZE = 8

const repoQuery = ref('')
const sourceFilter = ref('all')
const typeFilter = ref('all')
const filtersOpen = ref(false)
const searchLoading = ref(false)
const searchError = ref('')
const searchResults = ref({ items: [], total: 0, page: 1, page_size: SEARCH_PAGE_SIZE, total_pages: 1 })
const providerTotals = ref({ github: 0, skills: 0, hosted: 0 })

const selectedResult = ref(null)
const drawerOpen = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const detailCandidates = ref([])
const detailState = ref(null)
const candidateKind = ref('all')
const candidateQuery = ref('')

const importState = ref({ path: '', notice: '', error: '' })
const toast = ref({ message: '', kind: 'success' })
const library = ref({ skills: [], rules: [], tools: [] })

let toastTimer = null

const totalInstalled = computed(() =>
  library.value.skills.length + library.value.rules.length + library.value.tools.length,
)

const selectedResultKey = computed(() => {
  if (!selectedResult.value) return ''
  if (selectedResult.value.provider === 'github') {
    return `github:${selectedResult.value.full_name}`
  }
  if (selectedResult.value.provider === 'skills') {
    return `skills:${selectedResult.value.id}`
  }
  return `hosted:${selectedResult.value.id}`
})

function emptySearchResults(page = 1) {
  return { items: [], total: 0, page, page_size: SEARCH_PAGE_SIZE, total_pages: 1 }
}

function resultKey(result) {
  if (result.provider === 'github') return `github:${result.full_name}`
  if (result.provider === 'skills') return `skills:${result.id}`
  return `hosted:${result.id}`
}

function interleaveResults(...groups) {
  const merged = []
  const maxLength = Math.max(...groups.map((group) => group.length), 0)
  for (let index = 0; index < maxLength; index += 1) {
    for (const group of groups) {
      if (group[index]) merged.push(group[index])
    }
  }
  return merged
}

function effectiveCandidateKind() {
  return typeFilter.value === 'all' ? candidateKind.value : typeFilter.value
}

function githubSearchQuery() {
  const normalizedQuery = repoQuery.value.trim()
  if (!normalizedQuery) return ''
  if (typeFilter.value === 'skill') return `${normalizedQuery} skill`
  if (typeFilter.value === 'tool') return `${normalizedQuery} mcp server`
  return normalizedQuery
}

async function loadLibrary() {
  try {
    const data = await listResources()
    library.value = {
      skills: data.skills || [],
      rules: data.rules || [],
      tools: data.tools || [],
    }
  } catch {
    library.value = { skills: [], rules: [], tools: [] }
  }
}

async function runSearch(page = 1) {
  const query = repoQuery.value.trim()
  if (!query) {
    searchResults.value = emptySearchResults(page)
    providerTotals.value = { github: 0, skills: 0, hosted: 0 }
    searchError.value = ''
    drawerOpen.value = false
    selectedResult.value = null
    detailState.value = null
    detailCandidates.value = []
    detailError.value = ''
    return
  }

  searchLoading.value = true
  searchError.value = ''
  searchResults.value = emptySearchResults(page)
  providerTotals.value = { github: 0, skills: 0, hosted: 0 }
  selectedResult.value = null
  drawerOpen.value = false
  detailState.value = null
  detailCandidates.value = []
  detailError.value = ''

  try {
    if (typeFilter.value !== 'all') {
      candidateKind.value = typeFilter.value
    }

    const fetchSize = page * SEARCH_PAGE_SIZE
    const githubQuery = githubSearchQuery()
    const shouldSearchGithub = !['skills', 'hosted'].includes(sourceFilter.value)
    const shouldSearchSkills = !['github', 'hosted'].includes(sourceFilter.value) && ['all', 'skill'].includes(typeFilter.value)
    const shouldSearchHosted = !['github', 'skills'].includes(sourceFilter.value) && ['all', 'tool'].includes(typeFilter.value)
    const [githubData, skillsData, hostedData] = await Promise.all([
      shouldSearchGithub ? searchGithubRepos(githubQuery, 1, fetchSize) : Promise.resolve({ repos: [], total: 0 }),
      shouldSearchSkills ? searchSkillsDirectory(query, 1, fetchSize) : Promise.resolve({ skills: [], total: 0 }),
      shouldSearchHosted ? searchHostedMcpConnectors(query, 1, fetchSize) : Promise.resolve({ connectors: [], total: 0 }),
    ])

    const githubItems = (githubData.repos || []).map((repo) => ({ ...repo, provider: 'github' }))
    const skillItems = (skillsData.skills || []).map((skill) => ({ ...skill, provider: 'skills' }))
    const hostedItems = (hostedData.connectors || []).map((connector) => ({ ...connector, provider: 'hosted' }))
    const merged = interleaveResults(githubItems, skillItems, hostedItems)
    const start = (page - 1) * SEARCH_PAGE_SIZE
    const total = (githubData.total || 0) + (skillsData.total || 0) + (hostedData.total || 0)

    searchResults.value = {
      items: merged.slice(start, start + SEARCH_PAGE_SIZE),
      total,
      page,
      page_size: SEARCH_PAGE_SIZE,
      total_pages: Math.max(1, Math.ceil(total / SEARCH_PAGE_SIZE)),
    }
    providerTotals.value = {
      github: githubData.total || 0,
      skills: skillsData.total || 0,
      hosted: hostedData.total || 0,
    }

    if (!searchResults.value.items.length) {
      searchError.value = 'No GitHub repositories, skills.sh entries, or hosted MCP connectors matched that search.'
    }
  } catch (e) {
    searchError.value = e.response?.data?.detail || 'Search failed.'
  } finally {
    searchLoading.value = false
  }
}

async function submitSearch() {
  await runSearch(1)
}

async function changeSearchPage(page) {
  await runSearch(page)
}

async function openResult(result) {
  const sameSelection = resultKey(result) === selectedResultKey.value
  if (sameSelection && drawerOpen.value) {
    drawerOpen.value = false
    return
  }

  selectedResult.value = result
  drawerOpen.value = true
  importState.value = { path: '', notice: '', error: '' }
  detailLoading.value = true
  detailError.value = ''
  detailCandidates.value = []

  try {
    if (result.provider === 'github') {
      detailState.value = { provider: 'github', ...result }
      const data = await listGithubCandidates(result.full_name, effectiveCandidateKind(), candidateQuery.value)
      detailCandidates.value = data.candidates || []
      if (!detailCandidates.value.length) {
        detailError.value = 'No matching rules, skills, or tools were found in that repository.'
      }
      return
    }

    if (result.provider === 'hosted') {
      detailState.value = { provider: 'hosted', ...result }
      return
    }

    const data = await getSkillsDirectoryDetail(result.source, result.skill_id)
    detailState.value = {
      provider: 'skills',
      ...result,
      ...data,
    }
    detailCandidates.value = data.candidates || []
    if (!detailCandidates.value.length) {
      detailError.value = 'No importable skill object could be resolved from that skills.sh entry.'
    }
  } catch (e) {
    detailError.value = e.response?.data?.detail || 'Failed to load result details.'
  } finally {
    detailLoading.value = false
  }
}

async function applyGithubCandidateFilters() {
  if (!selectedResult.value || selectedResult.value.provider !== 'github') return
  await openResult(selectedResult.value)
}

async function addCandidateToLibrary(candidate) {
  if (!detailState.value) return
  const isSkillsBundle = detailState.value.provider === 'skills'
  const bundleCandidates = isSkillsBundle ? detailCandidates.value.filter((item) => item.type === 'skill') : [candidate]
  const targetCandidates = bundleCandidates.length ? bundleCandidates : [candidate]
  importState.value = { path: isSkillsBundle ? '__skills_bundle__' : candidate.path, notice: '', error: '' }
  try {
    let lastDocumentId = ''
    for (const targetCandidate of targetCandidates) {
      const data = await importGithubCandidate({
        repo: detailState.value.provider === 'skills' ? detailState.value.source : detailState.value.full_name,
        path: targetCandidate.path,
      })
      lastDocumentId = data.document.id
    }

    const successMessage = isSkillsBundle
      ? `Added ${targetCandidates.length} skills from ${detailState.value.name || detailState.value.skill_id} to the shared library.`
      : `Added ${lastDocumentId} to the shared library.`

    importState.value = {
      path: '',
      notice: successMessage,
      error: '',
    }
    await loadLibrary()
    closeDrawer()
    showToast(successMessage)
  } catch (e) {
    importState.value = {
      path: '',
      notice: '',
      error: e.response?.data?.detail || 'Add failed.',
    }
  }
}

function closeDrawer() {
  drawerOpen.value = false
}

function showToast(message, kind = 'success') {
  toast.value = { message, kind }
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
  toastTimer = setTimeout(() => {
    toast.value = { message: '', kind: 'success' }
    toastTimer = null
  }, 3200)
}

onMounted(async () => {
  await loadLibrary()
})
</script>

<template>
  <main class="shell explore-shell">
    <section class="explore-hero">
      <div>
        <p class="eyebrow">Explore</p>
        <h1>Search external skills, rules, and tools before you add them to the library.</h1>
        <p class="lede explore-lede">
          Search GitHub and skills.sh from one place, inspect each result in a slide-out drawer, and add skills, rules, or tools straight into the shared library.
        </p>
      </div>
      <div class="library-summary">
        <p class="library-summary__eyebrow">Shared Library</p>
        <strong>{{ totalInstalled }}</strong>
        <span>Total indexed resources available for synapses to attach and use</span>
        <small class="library-summary__note">Use the Library view to index bundled project resources and attach any installed item to Brainstem or another synapse.</small>
        <div class="library-stats">
          <div>
            <small>Skills</small>
            <strong>{{ library.skills.length }}</strong>
          </div>
          <div>
            <small>Rules</small>
            <strong>{{ library.rules.length }}</strong>
          </div>
          <div>
            <small>Tools</small>
            <strong>{{ library.tools.length }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section class="explore-panel">
      <form class="repo-search" @submit.prevent="submitSearch">
        <label class="repo-search__field">
          <span>Search skills, rules and tools</span>
          <input
            v-model="repoQuery"
            type="text"
            placeholder="auth workflows, observability rules, CLI tools, design systems"
          />
        </label>
        <div class="search-actions">
          <button type="button" class="btn-secondary filter-toggle" @click="filtersOpen = !filtersOpen">
            Filters
          </button>
          <button class="btn-primary" type="submit" :disabled="searchLoading || !repoQuery.trim()">
            {{ searchLoading ? 'Searching…' : 'Search' }}
          </button>
        </div>
      </form>

      <div v-if="filtersOpen" class="search-filters">
        <label>
          <span>Source</span>
          <select v-model="sourceFilter">
            <option value="all">All sources</option>
            <option value="github">GitHub only</option>
            <option value="skills">skills.sh only</option>
            <option value="hosted">Hosted MCP only</option>
          </select>
        </label>
        <label>
          <span>Type</span>
          <select v-model="typeFilter">
            <option value="all">All types</option>
            <option value="skill">Skills</option>
            <option value="rule">Rules</option>
            <option value="tool">Tools</option>
          </select>
        </label>
      </div>

      <div class="source-summary">
        <p>
          GitHub <strong>{{ providerTotals.github }}</strong>
          <span>·</span>
          skills.sh <strong>{{ providerTotals.skills }}</strong>
          <span>·</span>
          hosted <strong>{{ providerTotals.hosted }}</strong>
        </p>
      </div>

      <p class="filter-hint">
        Clicking a card opens a hidden right drawer with the importable resources from that source. Clicking the same card again closes it.
      </p>

      <p v-if="typeFilter === 'tool'" class="filter-hint">
        Tools search is MCP-focused and blends GitHub MCP repositories with hosted MCP connectors.
      </p>

      <p v-if="searchError" class="form-error">{{ searchError }}</p>
      <p v-if="importState.notice" class="form-success">{{ importState.notice }}</p>
      <p v-if="importState.error" class="form-error">{{ importState.error }}</p>

      <div class="explore-workspace">
        <section class="results-pane">
          <div class="results-pane__header">
            <h2>Results</h2>
            <span>{{ searchResults.total }}</span>
          </div>

          <div v-if="searchLoading" class="loading">Searching GitHub and skills.sh…</div>

          <div v-else-if="searchResults.items.length" class="result-list">
            <ExploreResultCard
              v-for="result in searchResults.items"
              :key="resultKey(result)"
              :result="result"
              :selected="selectedResultKey === resultKey(result) && drawerOpen"
              @select="openResult"
            />
          </div>

          <p v-else class="resource-empty">Search to explore GitHub repositories and skills.sh entries in one result stream.</p>

          <div v-if="searchResults.items.length" class="results-pagination">
            <button
              type="button"
              class="btn-secondary"
              :disabled="searchLoading || searchResults.page <= 1"
              @click="changeSearchPage(searchResults.page - 1)"
            >
              Previous
            </button>
            <p>
              Page {{ searchResults.page }} of {{ searchResults.total_pages }}
              <span>·</span>
              {{ searchResults.total }} total
            </p>
            <button
              type="button"
              class="btn-secondary"
              :disabled="searchLoading || searchResults.page >= searchResults.total_pages"
              @click="changeSearchPage(searchResults.page + 1)"
            >
              Next
            </button>
          </div>
        </section>
      </div>
    </section>

    <ExploreDetailDrawer
      :open="drawerOpen"
      :detail-state="detailState"
      :detail-loading="detailLoading"
      :detail-error="detailError"
      :detail-candidates="detailCandidates"
      :detail-kind="candidateKind"
      :detail-query="candidateQuery"
      :adding-path="importState.path"
      @close="closeDrawer"
      @update:detail-kind="candidateKind = $event"
      @update:detail-query="candidateQuery = $event"
      @apply-filters="applyGithubCandidateFilters"
      @add-candidate="addCandidateToLibrary"
    />

    <transition name="toast-fade">
      <div v-if="toast.message" class="explore-toast" :class="`explore-toast--${toast.kind}`">
        {{ toast.message }}
      </div>
    </transition>
  </main>
</template>

<style scoped>
.explore-shell {
  display: grid;
  gap: 1.75rem;
}

.explore-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
  gap: 1.5rem;
  align-items: stretch;
}

.explore-hero h1,
.results-pane__header h2 {
  font-family: 'Space Grotesk', sans-serif;
}

.explore-hero h1 {
  margin: 0;
  font-size: clamp(2.6rem, 5vw, 4.4rem);
  line-height: 0.96;
  max-width: 12ch;
}

.explore-lede {
  margin-bottom: 0;
}

.library-summary,
.explore-panel,
.results-pane {
  border-radius: 26px;
  border: 1px solid var(--line);
  background: var(--panel);
  box-shadow: var(--shadow);
  backdrop-filter: blur(16px);
}

.library-summary {
  padding: 1.5rem;
  display: grid;
  gap: 0.8rem;
  align-content: start;
}

.library-summary__eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.78rem;
  color: var(--accent-strong);
}

.library-summary > strong {
  font-size: 3.2rem;
  line-height: 1;
}

.library-summary > span,
.library-summary__note,
.filter-hint {
  color: var(--muted);
  line-height: 1.55;
}

.library-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.library-stats div {
  padding: 0.9rem;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
}

.library-stats small {
  display: block;
  color: var(--muted);
  margin-bottom: 0.3rem;
}

.explore-panel {
  padding: 1.5rem;
  display: grid;
  gap: 1rem;
}

.repo-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: end;
}

.repo-search__field,
.search-filters label {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.search-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.filter-toggle {
  min-width: 110px;
}

.search-filters {
  display: grid;
  grid-template-columns: repeat(2, minmax(180px, 240px));
  gap: 1rem;
  padding: 1rem;
  border-radius: 20px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.68);
}

.source-summary p {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
}

.explore-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}

.results-pane {
  padding: 1rem;
}

.results-pane__header,
.results-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.results-pane__header h2 {
  margin: 0;
}

.results-pane__header span {
  min-width: 30px;
  min-height: 30px;
  display: inline-grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(20, 33, 61, 0.08);
  font-size: 0.82rem;
}

.result-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.9rem;
  margin-top: 1rem;
}

.resource-empty,
.results-pagination p {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
}

.results-pagination {
  padding-top: 1rem;
  border-top: 1px solid var(--line);
  margin-top: 1rem;
  flex-wrap: wrap;
}

.explore-toast {
  position: fixed;
  right: 1.5rem;
  bottom: 1.5rem;
  max-width: min(420px, calc(100vw - 2rem));
  padding: 0.95rem 1.1rem;
  border-radius: 18px;
  border: 1px solid rgba(26, 127, 55, 0.18);
  background: rgba(242, 252, 244, 0.96);
  color: #1a7f37;
  box-shadow: 0 18px 42px rgba(20, 33, 61, 0.14);
  z-index: 180;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 1040px) {
  .explore-hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .repo-search,
  .search-filters {
    grid-template-columns: 1fr;
  }

  .search-actions {
    justify-content: stretch;
  }
}
</style>
