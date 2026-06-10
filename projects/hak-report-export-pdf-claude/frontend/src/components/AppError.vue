<template>
  <div class="app-error">
    <div class="app-error__icon">!</div>
    <h2 class="app-error__title">{{ title }}</h2>
    <p class="app-error__message">{{ message }}</p>
    <button v-if="showRetry" class="app-error__retry" @click="$emit('retry')">
      重试
    </button>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  message?: string
  showRetry?: boolean
}>(), {
  title: '加载失败',
  message: '页面加载出现问题，请稍后重试',
  showRetry: true
})

defineEmits<{
  retry: []
}>()
</script>

<style scoped>
.app-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
}

.app-error__icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #fee2e2;
  color: #dc2626;
  font-size: 24px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.app-error__title {
  font-size: 18px;
  color: #1f2937;
  margin: 0 0 8px;
}

.app-error__message {
  font-size: 14px;
  color: #6b7280;
  margin: 0 0 24px;
}

.app-error__retry {
  padding: 8px 24px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.app-error__retry:hover {
  background: #2563eb;
}
</style>
