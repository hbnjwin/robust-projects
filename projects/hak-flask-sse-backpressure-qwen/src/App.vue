<template>
  <div id="app">
    <!--
      keep-alive with include filter: only cache components whose meta.keepAlive is true.
      ReportReview uses RichTextEditor which properly handles activated/deactivated lifecycle.
    -->
    <router-view v-slot="{ Component, route }">
      <keep-alive :include="cachedViews">
        <component :is="Component" :key="route.fullPath" />
      </keep-alive>
    </router-view>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

// Dynamically determine which views to cache based on route meta
const cachedViews = computed(() => {
  return route.meta?.keepAlive ? [route.name] : []
})
</script>
