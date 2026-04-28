<script setup>
const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  detailState: {
    type: Object,
    default: null,
  },
  detailLoading: {
    type: Boolean,
    default: false,
  },
  detailError: {
    type: String,
    default: '',
  },
  detailCandidates: {
    type: Array,
    default: () => [],
  },
  detailKind: {
    type: String,
    default: 'all',
  },
  detailQuery: {
    type: String,
    default: '',
  },
  addingPath: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['close', 'update:detailKind', 'update:detailQuery', 'apply-filters', 'add-candidate'])

function updateKind(event) {
  emit('update:detailKind', event.target.value)
}

function updateQuery(event) {
  emit('update:detailQuery', event.target.value)
}
</script>

<template>
  <transition name="drawer-slide">
    <aside v-if="open" class="detail-drawer">
      <div class="detail-drawer__header">
        <div>
          <p class="eyebrow">{{ detailState?.provider === 'github' ? 'GitHub Repository' : (detailState?.provider === 'skills' ? 'skills.sh Skill' : 'Hosted MCP Connector') }}</p>
          <h2>{{ detailState?.provider === 'github' ? detailState?.full_name : (detailState?.name || detailState?.skill_id || detailState?.slug) }}</h2>
        </div>
        <button type="button" class="btn-close" @click="emit('close')">×</button>
      </div>

      <template v-if="detailState">
        <div class="detail-drawer__links">
          <a v-if="detailState.provider === 'github'" :href="detailState.html_url" target="_blank" rel="noreferrer">Open repo</a>
          <template v-else-if="detailState.provider === 'skills'">
            <a :href="detailState.page_url" target="_blank" rel="noreferrer">View on skills.sh</a>
            <a :href="detailState.github_url" target="_blank" rel="noreferrer">Open repo</a>
          </template>
          <template v-else>
            <a :href="detailState.page_url" target="_blank" rel="noreferrer">View on Glama</a>
          </template>
        </div>

        <p class="detail-drawer__copy">
          {{ detailState.provider === 'github'
            ? (detailState.description || 'No repository description provided.')
            : (detailState.provider === 'skills'
              ? (detailState.description || 'This skills.sh entry resolves into importable skill objects from the source repository.')
              : (detailState.description || 'This hosted MCP connector is already running remotely and can be connected directly from an MCP client.')) }}
        </p>

        <div class="detail-metrics">
          <div v-if="detailState.provider === 'github'">
            <small>Stars</small>
            <strong>{{ detailState.stargazers_count }}</strong>
          </div>
          <div>
            <small>{{ detailState.provider === 'github' ? 'Language' : (detailState.provider === 'skills' ? 'Source Repo' : 'Registry') }}</small>
            <strong>{{ detailState.provider === 'github' ? (detailState.language || 'Mixed') : detailState.source }}</strong>
          </div>
          <div v-if="detailState.provider === 'skills'">
            <small>Installs</small>
            <strong>{{ detailState.installs }}</strong>
          </div>
          <div v-if="detailState.provider === 'hosted'">
            <small>Slug</small>
            <strong>{{ detailState.slug }}</strong>
          </div>
        </div>

        <div v-if="detailState.provider === 'skills'" class="detail-command">
          <small>skills.sh install command</small>
          <code>{{ detailState.install_command }}</code>
        </div>

        <div v-if="detailState.provider === 'skills' && detailCandidates.length" class="detail-command">
          <small>Bundle import</small>
          <code>Add To Library imports the full resolved skill bundle, including nested skills from this repo.</code>
        </div>

        <div v-if="detailState.provider === 'skills' && detailCandidates.length" class="detail-actions">
          <button
            type="button"
            class="btn-primary"
            :disabled="Boolean(addingPath)"
            @click="emit('add-candidate', detailCandidates[0])"
          >
            {{ addingPath ? 'Adding…' : 'Add Bundle To Library' }}
          </button>
        </div>

        <div v-if="detailState.provider === 'hosted'" class="detail-command">
          <small>Hosted connector note</small>
          <code>Hosted MCP connectors are discovered here for direct use, not imported into the shared library.</code>
        </div>

        <form v-if="detailState.provider === 'github'" class="detail-filter-bar" @submit.prevent="emit('apply-filters')">
          <label>
            <span>Type</span>
            <select :value="detailKind" @change="updateKind">
              <option value="all">All</option>
              <option value="skill">Skills</option>
              <option value="rule">Rules</option>
              <option value="tool">Tools</option>
            </select>
          </label>
          <label>
            <span>Filter objects</span>
            <input :value="detailQuery" type="text" placeholder="auth, workflow, security, tool" @input="updateQuery" />
          </label>
          <button type="submit" class="btn-secondary" :disabled="detailLoading">
            {{ detailLoading ? 'Filtering…' : 'Apply' }}
          </button>
        </form>

        <p v-if="detailError" class="form-error">{{ detailError }}</p>
        <div v-else-if="detailLoading" class="loading">Loading importable resources…</div>

        <div v-else-if="detailCandidates.length" class="detail-candidate-list">
          <article v-for="candidate in detailCandidates" :key="candidate.path" class="detail-candidate-card">
            <div class="detail-candidate-card__meta">
              <span class="candidate-badge" :class="`badge-${candidate.type}`">{{ candidate.type }}</span>
              <a :href="candidate.html_url" target="_blank" rel="noreferrer">Open source</a>
            </div>
            <h3>{{ candidate.name }}</h3>
            <p>{{ candidate.path }}</p>
            <button
              v-if="detailState?.provider !== 'skills'"
              type="button"
              class="btn-primary"
              :disabled="addingPath === candidate.path"
              @click="emit('add-candidate', candidate)"
            >
              {{ addingPath === candidate.path ? 'Adding…' : 'Add To Library' }}
            </button>
          </article>
        </div>

        <p v-else class="resource-empty">{{ detailState.provider === 'hosted' ? 'This result is a hosted MCP connector for direct connection, not a library import candidate.' : 'No importable objects are available for this result.' }}</p>
      </template>
    </aside>
  </transition>
</template>

<style scoped>
.detail-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(540px, 100vw);
  padding: 1.2rem;
  background: rgba(251, 246, 242, 0.98);
  border-left: 1px solid var(--line);
  box-shadow: -24px 0 60px rgba(20, 33, 61, 0.14);
  overflow: auto;
  z-index: 140;
  backdrop-filter: blur(18px);
}

.detail-drawer__header,
.detail-drawer__links {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.detail-drawer__header h2,
.detail-candidate-card h3 {
  margin: 0;
  font-family: 'Space Grotesk', sans-serif;
}

.detail-drawer__links {
  margin-top: 1rem;
}

.detail-drawer__links a,
.detail-candidate-card__meta a {
  color: var(--accent-strong);
  text-decoration: none;
  font-weight: 600;
}

.detail-drawer__copy,
.detail-command small,
.resource-empty {
  margin: 1rem 0 0;
  color: var(--muted);
  line-height: 1.6;
}

.detail-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
}

.detail-metrics div,
.detail-command {
  padding: 0.85rem;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.84);
}

.detail-metrics small,
.detail-command small {
  display: block;
  color: var(--muted);
  margin-bottom: 0.3rem;
}

.detail-command {
  margin-top: 1rem;
}

.detail-actions {
  margin-top: 1rem;
}

.detail-command code {
  display: block;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-filter-bar {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: end;
  margin: 1rem 0;
}

.detail-filter-bar label {
  display: grid;
  gap: 0.45rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.detail-candidate-list {
  display: grid;
  gap: 0.9rem;
  margin-top: 1rem;
}

.detail-candidate-card {
  display: grid;
  gap: 0.8rem;
  padding: 0.95rem;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.84);
}

.detail-candidate-card__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.detail-candidate-card p {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
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

.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 180ms ease, opacity 180ms ease;
}

.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

@media (max-width: 960px) {
  .detail-filter-bar {
    grid-template-columns: 1fr;
  }

  .detail-drawer {
    width: 100vw;
  }
}
</style>