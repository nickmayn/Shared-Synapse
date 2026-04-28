<script setup>
defineProps({
  result: {
    type: Object,
    required: true,
  },
  selected: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['select'])
</script>

<template>
  <button
    type="button"
    class="discovery-card"
    :class="{ 'discovery-card--selected': selected }"
    @click="$emit('select', result)"
  >
    <div class="discovery-card__meta">
      <span class="candidate-badge" :class="{
        'badge-github': result.provider === 'github',
        'badge-skill': result.provider === 'skills',
        'badge-hosted': result.provider === 'hosted',
      }">
        {{ result.provider === 'github' ? 'GitHub' : (result.provider === 'skills' ? 'skills.sh' : 'Hosted MCP') }}
      </span>
      <small v-if="result.provider === 'github'">{{ result.language || 'Mixed' }} · {{ result.stargazers_count }} stars</small>
      <small v-else-if="result.provider === 'skills'">{{ result.installs }} installs</small>
      <small v-else>{{ result.source }} connector</small>
    </div>
    <strong>{{ result.provider === 'github' ? result.full_name : result.name }}</strong>
    <p>{{ result.provider === 'github' ? (result.description || 'No description provided.') : (result.description || result.source) }}</p>
  </button>
</template>

<style scoped>
.discovery-card {
  text-align: left;
  display: grid;
  gap: 0.55rem;
  padding: 0.95rem;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.84);
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.discovery-card:hover,
.discovery-card--selected {
  transform: translateY(-1px);
  border-color: var(--accent);
  box-shadow: 0 16px 34px rgba(20, 33, 61, 0.1);
}

.discovery-card__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.discovery-card strong {
  font-family: 'Space Grotesk', sans-serif;
}

.discovery-card p {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
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

.badge-github {
  background: rgba(20, 33, 61, 0.1);
  color: var(--ink);
}

.badge-hosted {
  background: rgba(26, 127, 55, 0.14);
  color: #1a7f37;
}
</style>