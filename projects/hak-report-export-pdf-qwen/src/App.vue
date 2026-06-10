<template>
  <div id="app">
    <nav class="main-nav">
      <router-link to="/reports">报告审核系统</router-link>
    </nav>

    <main class="container">
      <Suspense>
        <template #default>
          <router-view />
        </template>
        <template #fallback>
          <LoadingSpinner />
        </template>
      </Suspense>
    </main>
  </div>
</template>

<script setup>
import LoadingSpinner from '@/components/LoadingSpinner.vue'
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f5f5f5;
  color: #333;
}

#app {
  min-height: 100vh;
}

.main-nav {
  background: #2c3e50;
  padding: 15px 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.main-nav a {
  color: white;
  text-decoration: none;
  font-size: 18px;
  font-weight: bold;
}

.main-nav a:hover {
  opacity: 0.8;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
</style>
