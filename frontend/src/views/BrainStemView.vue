<script setup>
import { ref, onMounted } from 'vue'
import {
  getSynapse,
  importGithubCandidate,
  listGithubCandidates,
  searchGithubRepos,
} from '../api.js'
import { useAuth } from '../composables/useAuth.js'

const { isAdmin } = useAuth()
const brainstem = ref(null)
const loading = ref(true)
const error = ref('')
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

async function importCandidate(candidate) {
  importState.value = { path: candidate.path, notice: '', error: '' }
  try {
    const data = await importGithubCandidate({
      repo: selectedRepo.value,
      path: candidate.path,
      synapse_name: 'core-brainstem',
    })
    importState.value = {
      path: '',
      notice: `Added ${data.document.id} to core-brainstem.`,
      error: '',
    }
    await load()
    await loadCandidates()
  } catch (e) {
    importState.value = {
      path: '',
      notice: '',
      error: e.response?.data?.detail || 'Import failed.',
    }
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

    <section v-if="isAdmin" class="import-panel">
      <div class="import-panel__header">
        <div>
          <p class="eyebrow">Expand the Shared Brain</p>
          <h2>Import from public GitHub repos</h2>
          <p class="lede import-panel__lede">
            Search open-source repositories, inspect likely skills, rules, and tool definitions, and attach them directly to
            the always-on brain stem.
          </p>
        </div>
      </div>

      <form class="repo-search" @submit.prevent="searchRepos">
        <label class="repo-search__field">
          <span>Repository search</span>
          <input
            v-model="repoQuery"
            type="text"
            placeholder="e.g. fastapi auth rules, prompt engineering skills, dev tools"
          />
        </label>
        <button class="btn-primary" type="submit" :disabled="repoLoading || !repoQuery.trim()">
          {{ repoLoading ? 'Searching…' : 'Search GitHub' }}
        </button>
      </form>

      <p v-if="repoError" class="form-error">{{ repoError }}</p>

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

      <div v-if="selectedRepo" class="candidate-panel">
        <div class="candidate-toolbar">
          <label>
            <span>Type</span>
            <select v-model="candidateKind" @change="loadCandidates">
              <option value="all">All</option>
              <option value="skill">Skills</option>
              <option value="rule">Rules</option>
              <option value="tool">Tools</option>
            </select>
          </label>

          <label class="candidate-toolbar__search">
            <span>Filter paths</span>
            <input
              v-model="candidateQuery"
              type="text"
              placeholder="auth, security, tool, workflow"
              @keyup.enter.prevent="loadCandidates"
            />
          </label>

          <button type="button" class="btn-secondary" @click="loadCandidates" :disabled="candidatesLoading">
            {{ candidatesLoading ? 'Scanning…' : 'Scan repo' }}
          </button>
        </div>

        <p v-if="importState.notice" class="form-success">{{ importState.notice }}</p>
        <p v-if="importState.error" class="form-error">{{ importState.error }}</p>
        <p v-if="candidatesError" class="form-error">{{ candidatesError }}</p>

        <div v-if="candidates.length" class="candidate-list">
          <article v-for="candidate in candidates" :key="candidate.path" class="candidate-card">
            <div class="candidate-card__meta">
              <span class="synapse-badge" :class="`badge-${candidate.type}`">{{ candidate.type }}</span>
              <a :href="candidate.html_url" target="_blank" rel="noreferrer">Open source</a>
            </div>
            <h3>{{ candidate.name }}</h3>
            <p>{{ candidate.path }}</p>
            <button
              type="button"
              class="btn-primary"
              :disabled="importState.path === candidate.path"
              @click="importCandidate(candidate)"
            >
              {{ importState.path === candidate.path ? 'Adding…' : 'Add to brain stem' }}
            </button>
          </article>
        </div>
      </div>
    </section>
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

.import-panel {
  margin-top: 2.5rem;
  padding: 1.5rem;
  border-radius: 24px;
  border: 1px solid var(--line);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.78)),
    radial-gradient(circle at top right, rgba(20, 33, 61, 0.08), transparent 28%);
  box-shadow: var(--shadow);
}

.import-panel__header h2 {
  margin: 0;
  font-family: 'Space Grotesk', sans-serif;
}

.import-panel__lede {
  margin-top: 0.8rem;
  margin-bottom: 0;
}

.repo-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  margin-top: 1.5rem;
  align-items: end;
}

.repo-search__field,
.candidate-toolbar label {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.repo-search input,
.candidate-toolbar input,
.candidate-toolbar select {
  min-height: 48px;
  padding: 0.7rem 0.9rem;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.94);
  color: var(--ink);
  font: inherit;
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

.repo-result strong,
.candidate-card h3 {
  font-family: 'Space Grotesk', sans-serif;
}

.repo-result span,
.candidate-card p {
  color: var(--muted);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.repo-result span {
  -webkit-line-clamp: 3;
  min-height: calc(1.55em * 3);
}

.candidate-card p {
  -webkit-line-clamp: 2;
  min-height: calc(1.55em * 2);
}

.candidate-panel {
  margin-top: 1.5rem;
}

.candidate-toolbar {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: end;
}

.candidate-card {
  display: grid;
  gap: 0.8rem;
}

.candidate-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.candidate-card__meta a {
  color: var(--accent-strong);
  text-decoration: none;
  font-size: 0.82rem;
}

.badge-skill { background: #e0f2fe; color: #075985; }
.badge-rule { background: #fef3c7; color: #92400e; }
.badge-tool { background: #dcfce7; color: #166534; }

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

.btn-secondary {
  min-height: 48px;
  padding: 0.65rem 1rem;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--line);
  border-radius: 12px;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ink);
  cursor: pointer;
}

.btn-secondary:hover { border-color: var(--accent); }

.loading { color: var(--muted); }
.form-error { color: #dc2626; }
.form-success { color: #166534; }

@media (max-width: 860px) {
  .repo-search,
  .candidate-toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
