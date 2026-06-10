<template>
  <div class="check-result-list">
    <div v-for="item in results" :key="item.id" class="result-item">
      <span>{{ item.name }}</span>
      <span>{{ item.status }}</span>
      <p>{{ item.opinion }}</p>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ results: Array })
</script>
