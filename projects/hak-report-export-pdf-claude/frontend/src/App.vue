<template>
  <!--
    Bug 3 修复兜底：Suspense 包裹 RouterView
    当 defineAsyncComponent (lazyView) 的 loadingComponent 未能覆盖到的场景，
    Suspense 提供最后一层保障，确保不出现空白闪烁。
  -->
  <div id="app-root">
    <RouterView v-slot="{ Component }">
      <template v-if="Component">
        <Suspense>
          <template #default>
            <component :is="Component" />
          </template>
          <template #fallback>
            <AppLoading />
          </template>
        </Suspense>
      </template>
    </RouterView>
  </div>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppLoading from '@/components/AppLoading.vue'
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f3f4f6;
  color: #111827;
  line-height: 1.5;
}

#app-root {
  min-height: 100vh;
}
</style>
