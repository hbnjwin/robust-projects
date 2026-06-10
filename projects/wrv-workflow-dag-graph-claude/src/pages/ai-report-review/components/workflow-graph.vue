<template>
  <div class="workflow-graph">
    <div v-for="step in steps" :key="step.id" class="workflow-step">
      <span class="step-name">{{ step.stepName }}</span>
      <span class="step-status">{{ step.status }}</span>
      <span class="step-time">{{ step.timestamp }}</span>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ steps: Array })
</script>
