<script setup>
const synapses = [
  {
    name: 'Core Brain Stem',
    status: 'Always active',
    description: 'The baseline team memory: durable rules, workflow constraints, and shared platform concepts.',
  },
  {
    name: 'Backend Neuron',
    status: 'Optional activation',
    description: 'Server, ingestion, MCP, and Chroma-backed retrieval behavior for Python work.',
  },
  {
    name: 'Frontend Neuron',
    status: 'Optional activation',
    description: 'Vue 3 interface work, design system direction, and runtime environment patterns.',
  },
]

const categories = [
  ['Skills', 'Reusable workflows that tell an agent how to execute a task well.'],
  ['Rules', 'Always-on constraints that define the quality and security floor.'],
  ['Tools', 'APIs, service connectors, and MCP-facing operational surfaces.'],
  ['Decisions', 'Architectural choices and rationale that explain why the system looks this way.'],
  ['Concepts', 'High-level explanations of the domain, platform, and mental model.'],
  ['Designs', 'Theme, palette, and visual-direction documents for product surfaces.'],
]
</script>

<template>
  <main class="shell">
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">Shared Synapse Console</p>
        <h1>Brain stem rules. Optional synapses. One shared memory layer.</h1>
        <p class="lede">
          The frontend is a control surface for the knowledge graph: activate neuron-specific synapses,
          inspect the core brain stem, and understand how concepts, tools, and designs connect.
        </p>
        <div class="hero-actions">
          <router-link to="/synapses" class="primary-link">Manage Synapses</router-link>
          <router-link to="/brainstem" class="secondary-link">View Brain Stem</router-link>
        </div>
      </div>
      <div class="hero-panel" aria-hidden="true">
        <div class="panel-orbit orbit-one"></div>
        <div class="panel-orbit orbit-two"></div>
        <div class="panel-core">
          <span>Core</span>
          <strong>Brain Stem</strong>
        </div>
      </div>
    </section>

    <section id="synapses" class="section">
      <div class="section-heading">
        <p class="eyebrow">Activation Model</p>
        <h2>Synapses connect the right neurons for the job.</h2>
      </div>
      <div class="card-grid">
        <article v-for="synapse in synapses" :key="synapse.name" class="card">
          <p class="card-status">{{ synapse.status }}</p>
          <h3>{{ synapse.name }}</h3>
          <p>{{ synapse.description }}</p>
        </article>
      </div>
    </section>

    <section id="categories" class="section alt-section">
      <div class="section-heading">
        <p class="eyebrow">Knowledge Map</p>
        <h2>Each category has one job.</h2>
      </div>
      <div class="category-grid">
        <article v-for="category in categories" :key="category[0]" class="category-card">
          <h3>{{ category[0] }}</h3>
          <p>{{ category[1] }}</p>
        </article>
      </div>
    </section>
  </main>
</template>
