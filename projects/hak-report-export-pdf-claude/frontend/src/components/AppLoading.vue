<template>
  <div class="app-loading">
    <div class="skeleton-header">
      <div class="skeleton-line skeleton-line--title"></div>
      <div class="skeleton-line skeleton-line--subtitle"></div>
    </div>
    <div class="skeleton-body">
      <div class="skeleton-block"></div>
      <div class="skeleton-block skeleton-block--short"></div>
      <div class="skeleton-block"></div>
    </div>
  </div>
</template>

<style scoped>
.app-loading {
  padding: 24px;
  max-width: 960px;
  margin: 0 auto;
}

.skeleton-header {
  margin-bottom: 24px;
}

.skeleton-line {
  height: 16px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
  margin-bottom: 12px;
}

.skeleton-line--title {
  width: 40%;
  height: 24px;
}

.skeleton-line--subtitle {
  width: 60%;
}

.skeleton-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.skeleton-block {
  height: 120px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 8px;
}

.skeleton-block--short {
  height: 80px;
  width: 75%;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
