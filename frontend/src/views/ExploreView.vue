<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  importGithubCandidate,
  importLocalProjectResources,
  listGithubCandidates,
  listResources,
  listSynapses,
  searchGithubRepos,
} from '../api.js'

const repoQuery = ref('')
const repoResults = ref([])
const repoLoading = ref(false)
const repoError = ref('')
const selectedRepo = ref('')
const candidateKind = ref('all')
const candidateQuery = ref('')
const candidates = ref([])
const candidatesLoading = ref(false)
const candidatesError = ref('')
const importState = ref({ path: '', notice: '', error: '' })
const localInstallLoading = ref(false)
const library = ref({ skills: [], rules: [], tools: [] })
const synapseOptions = ref([])

const installDialogOpen = ref(false)
const installDialogLoading = ref(false)
const installDialogError = ref('')
const pendingCandidate = ref(null)
const pendingSynapseTarget = ref('core-brainstem')

const totalInstalled = computed(() =>
  library.value.skills.length + library.value.rules.length + library.value.tools.length,
)

const installDialogDescription = computed(() => {
  if (pendingSynapseTarget.value === 'core-brainstem') {
    return 'This import will be added to core-brainstem, which acts as the shared base for the system.'
  }
  return `This import will be added to core-brainstem and attached to ${pendingSynapseTarget.value}.`
})

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

async function loadSynapseOptions() {
  try {
    const data = await listSynapses()
    synapseOptions.value = [...(data.synapses || [])].sort((left, right) => left.name.localeCompare(right.name))
    if (!synapseOptions.value.some((synapse) => synapse.name === pendingSynapseTarget.value)) {
      pendingSynapseTarget.value = 'core-brainstem'
    }
  } catch {
    synapseOptions.value = []
  }
}

async function searchRepos() {
  repoLoading.value = true
  repoError.value = ''
  repoResults.value = []
  selectedRepo.value = ''
  candidates.value = []
  try {
    const data = await searchGithubRepos(repoQuery.value)
    repoResults.value = data.repos || []
    if (!repoResults.value.length) {
      repoError.value = 'No public repositories matched that search.'
    }
  } catch (e) {
    repoError.value = e.response?.data?.detail || 'Repository search failed.'
  } finally {
    repoLoading.value = false
  }
}

async function loadCandidates() {
  if (!selectedRepo.value) return
  candidatesLoading.value = true
  candidatesError.value = ''
  candidates.value = []
  try {
    const data = await listGithubCandidates(selectedRepo.value, candidateKind.value, candidateQuery.value)
    candidates.value = data.candidates || []
    if (!candidates.value.length) {
      candidatesError.value = 'No matching rules, skills, or tools were found in that repository.'
    }
  } catch (e) {
    candidatesError.value = e.response?.data?.detail || 'Failed to inspect that repository.'
  } finally {
    candidatesLoading.value = false
  }
}

async function selectRepo(repo) {
  selectedRepo.value = repo.full_name
  importState.value = { path: '', notice: '', error: '' }
  await loadCandidates()
}

function openInstallDialog(candidate) {
  pendingCandidate.value = candidate
  pendingSynapseTarget.value = 'core-brainstem'
  installDialogError.value = ''
  installDialogOpen.value = true
}

function closeInstallDialog() {
  installDialogOpen.value = false
  installDialogLoading.value = false
  installDialogError.value = ''
  pendingCandidate.value = null
}

async function confirmInstallCandidate() {
  if (!pendingCandidate.value) return
  installDialogLoading.value = true
  installDialogError.value = ''
  importState.value = { path: pendingCandidate.value.path, notice: '', error: '' }
  try {
    const data = await importGithubCandidate({
      repo: selectedRepo.value,
      path: pendingCandidate.value.path,
      synapse_name: pendingSynapseTarget.value,
    })
    importState.value = {
      path: '',
      notice: pendingSynapseTarget.value === 'core-brainstem'
        ? `Installed ${data.document.id} into core-brainstem.`
        : `Installed ${data.document.id} into core-brainstem and attached it to ${pendingSynapseTarget.value}.`,
      error: '',
    }
    await loadLibrary()
    closeInstallDialog()
  } catch (e) {
    installDialogError.value = e.response?.data?.detail || 'Install failed.'
    importState.value = { path: '', notice: '', error: installDialogError.value }
    installDialogLoading.value = false
  }
}

async function installProjectLibrary() {
  localInstallLoading.value = true
  importState.value = { path: '', notice: '', error: '' }
  try {
    const data = await importLocalProjectResources({
      types: ['skill', 'rule', 'tool'],
      synapse_name: 'core-brainstem',
    })
    importState.value = {
      path: '',
      notice: `Installed ${data.success} bundled resources into core-brainstem.`,
      error: data.failed ? `${data.failed} files could not be indexed.` : '',
    }
    await loadLibrary()
  } catch (e) {
    importState.value = {
      path: '',
      notice: '',
      error: e.response?.data?.detail || 'Project install failed.',
    }
  } finally {
    localInstallLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadLibrary(), loadSynapseOptions()])
})
</script>

<template>
  <main class="shell explore-shell">
    <section class="explore-hero">
      <div>
        <p class="eyebrow">Explore</p>
        <h1>Find better rules, skills, and tools without bloating the brain stem.</h1>
        <p class="lede explore-lede">
          Search public open-source repositories, filter down to the strongest building blocks, and choose where each one should land when you add it.
        </p>
      </div>
      <div class="library-summary">
        <p class="library-summary__eyebrow">Core Brain Stem</p>
        <strong>{{ totalInstalled }}</strong>
        <span>Total indexed resources available across your brain stem and synapses</span>
        <button type="button" class="btn-secondary" :disabled="localInstallLoading" @click="installProjectLibrary">
          {{ localInstallLoading ? 'Installing Into Brain Stem…' : 'Install Project Resources' }}
        </button>
        <small class="library-summary__note">Indexes bundled nested skills, rules, and tools from this repo into core-brainstem.</small>
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
      <form class="repo-search" @submit.prevent="searchRepos">
        <label class="repo-search__field">
          <span>Search the open-source ecosystem</span>
          <input
            v-model="repoQuery"
            type="text"
            placeholder="fastapi auth skills, security rules, prompt tools"
          />
        </label>
        <button class="btn-primary" type="submit" :disabled="repoLoading || !repoQuery.trim()">
          {{ repoLoading ? 'Searching…' : 'Search' }}
        </button>
      </form>

      <div class="filter-row">
        <label>
          <span>Type</span>
          <select v-model="candidateKind" @change="loadCandidates">
            <option value="all">All</option>
            <option value="skill">Skills</option>
            <option value="rule">Rules</option>
            <option value="tool">Tools</option>
          </select>
        </label>
        <label class="filter-row__search">
          <span>Filter paths</span>
          <input
            v-model="candidateQuery"
            type="text"
            placeholder="auth, security, workflow, tool"
            @keyup.enter.prevent="loadCandidates"
          />
        </label>
        <button type="button" class="btn-secondary" @click="loadCandidates" :disabled="!selectedRepo || candidatesLoading">
          {{ candidatesLoading ? 'Filtering…' : 'Apply Filters' }}
        </button>
      </div>

      <p class="filter-hint">
        Add opens a destination dialog so you can choose whether the import stays on the brain stem or also attaches to another synapse.
      </p>

      <p v-if="repoError" class="form-error">{{ repoError }}</p>
      <p v-if="importState.notice" class="form-success">{{ importState.notice }}</p>
      <p v-if="importState.error" class="form-error">{{ importState.error }}</p>

      <div v-if="repoResults.length" class="repo-results">
        <button
          v-for="repo in repoResults"
          :key="repo.full_name"
          type="button"
          class="repo-result"
          :class="{ 'repo-result--selected': selectedRepo === repo.full_name }"
          @click="selectRepo(repo)"
        >
          <strong>{{ repo.full_name }}</strong>
          <span>{{ repo.description || 'No description provided.' }}</span>
          <small>{{ repo.language || 'Mixed' }} · {{ repo.stargazers_count }} stars</small>
        </button>
      </div>

      <p v-if="candidatesError" class="form-error">{{ candidatesError }}</p>

      <div v-if="candidates.length" class="candidate-list">
        <article v-for="candidate in candidates" :key="candidate.path" class="candidate-card">
          <div class="candidate-card__meta">
            <span class="candidate-badge" :class="`badge-${candidate.type}`">{{ candidate.type }}</span>
            <a :href="candidate.html_url" target="_blank" rel="noreferrer">Open source</a>
          </div>
          <h3>{{ candidate.name }}</h3>
          <p>{{ candidate.path }}</p>
          <button
            type="button"
            class="btn-primary"
            :disabled="importState.path === candidate.path"
            @click="openInstallDialog(candidate)"
          >
            {{ importState.path === candidate.path ? 'Installing…' : 'Add' }}
          </button>
        </article>
      </div>
    </section>

    <div v-if="installDialogOpen" class="dialog-overlay" @click.self="closeInstallDialog">
      <div class="dialog-modal">
        <div class="dialog-modal__header">
          <div>
            <p class="eyebrow">Install Resource</p>
            <h2>{{ pendingCandidate?.name }}</h2>
          </div>
          <button type="button" class="btn-close" @click="closeInstallDialog">×</button>
        </div>

        <div class="dialog-form">
          <label>
            Destination
            <select v-model="pendingSynapseTarget">
              <option v-for="synapse in synapseOptions" :key="synapse.name" :value="synapse.name">
                {{ synapse.name === 'core-brainstem' ? 'core-brainstem (shared base)' : synapse.name }}
              </option>
            </select>
          </label>

          <p class="dialog-form__copy">{{ installDialogDescription }}</p>
          <p v-if="installDialogError" class="form-error">{{ installDialogError }}</p>

          <div class="form-actions">
            <button type="button" class="btn-primary" :disabled="installDialogLoading" @click="confirmInstallCandidate">
              {{ installDialogLoading ? 'Installing…' : 'Confirm Install' }}
            </button>
            <button type="button" class="btn-cancel btn-cancel--button" @click="closeInstallDialog">Cancel</button>
          </div>
        </div>
      </div>
    </div>
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
.candidate-card h3,
.repo-result strong,
.dialog-modal__header h2 {
  font-family: 'Space Grotesk', sans-serif;
}

.explore-hero h1 {
  margin: 0;
  font-size: clamp(2.6rem, 5vw, 4.4rem);
  line-height: 0.96;
  max-width: 11ch;
}

.explore-lede {
  margin-bottom: 0;
}

.library-summary,
.explore-panel {
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
.filter-hint,
.dialog-form__copy {
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
}

.repo-search,
.filter-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: end;
}

.filter-row {
  grid-template-columns: 180px minmax(0, 1fr) auto;
  margin-top: 1rem;
}

.repo-search__field,
.filter-row label,
.dialog-form label {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.repo-results,
.candidate-list {
  display: grid;
  gap: 0.9rem;
  margin-top: 1.25rem;
}

.repo-results {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.repo-result,
.candidate-card {
  text-align: left;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.82);
  padding: 1rem;
}

.repo-result {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.repo-result:hover,
.repo-result--selected {
  transform: translateY(-1px);
  border-color: var(--accent);
  box-shadow: 0 16px 34px rgba(20, 33, 61, 0.1);
}

.repo-result span,
.candidate-card p {
  color: var(--muted);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 3;
}

.candidate-card {
  display: grid;
  gap: 0.8rem;
}

.candidate-card__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.8rem;
}

.candidate-badge {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
}

.badge-skill {
  background: rgba(239, 108, 61, 0.16);
  color: var(--accent-strong);
}

.badge-rule {
  background: rgba(20, 33, 61, 0.1);
  color: var(--ink);
}

.badge-tool {
  background: rgba(99, 138, 110, 0.16);
  color: #31593a;
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(20, 33, 61, 0.32);
  display: grid;
  place-items: center;
  padding: 1rem;
  z-index: 220;
}

.dialog-modal {
  width: min(560px, 100%);
  padding: 1.25rem;
  border-radius: 24px;
  border: 1px solid var(--line);
  background: #fff;
  box-shadow: var(--shadow);
}

.dialog-modal__header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.dialog-form {
  display: grid;
  gap: 1rem;
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
  .explore-hero,
  .filter-row,
  .repo-search {
    grid-template-columns: 1fr;
  }
}
</style>
