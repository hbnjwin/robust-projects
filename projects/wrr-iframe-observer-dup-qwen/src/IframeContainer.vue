<template>
  <div class="iframe-container" ref="containerRef">
    <iframe
      ref="iframeRef"
      :src="src"
      frameborder="0"
      :style="{ height: iframeHeight + 'px', width: '100%' }"
      @load="handleIframeLoad"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onActivated, onDeactivated, onUnmounted } from 'vue'

const props = defineProps<{
  src: string
  instanceId?: symbol
}>()

const containerRef = ref<HTMLDivElement>()
const iframeRef = ref<HTMLIFrameElement>()
const iframeHeight = ref(600)
let observer: MutationObserver | null = null
let resizeObserver: ResizeObserver | null = null

const updateHeight = () => {
  try {
    const iframeDoc = iframeRef.value?.contentDocument || iframeRef.value?.contentWindow?.document
    if (iframeDoc) {
      const height = iframeDoc.documentElement.scrollHeight
      if (height > 0) {
        iframeHeight.value = height
      }
    }
  } catch (e) {
    // 跨域 iframe 无法访问 contentDocument
  }
}

const setupObserver = () => {
  // BUG: 没有先清理旧的 observer 就创建新的
  // keep-alive 每次 activated 都会调用 setupObserver
  // 旧的 MutationObserver 还在监听，新的也在监听
  // 导致 updateHeight 被重复调用

  try {
    const iframeDoc = iframeRef.value?.contentDocument
    if (!iframeDoc) return

    observer = new MutationObserver(() => {
      updateHeight()
    })
    observer.observe(iframeDoc.body, {
      childList: true,
      subtree: true,
      attributes: true
    })
  } catch (e) {
    // 跨域时静默失败
  }
}

const handleIframeLoad = () => {
  updateHeight()
  setupObserver()
}

onMounted(() => {
  // 初始设置 ResizeObserver
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => {
      updateHeight()
    })
    resizeObserver.observe(containerRef.value)
  }
})

// BUG: onActivated 中再次调用 setupObserver
// 但没有先 disconnect 旧的 observer
onActivated(() => {
  // BUG: instanceId 使用 Symbol 类型做身份验证
  // 但 Symbol 在组件实例间不稳定，keep-alive 复用时可能失效
  if (props.instanceId && typeof props.instanceId === 'symbol') {
    setupObserver()  // BUG: 重复创建 observer
    updateHeight()
  }
})

onDeactivated(() => {
  // BUG: 这里应该 disconnect observer，但没有做
  // observer?.disconnect()
})

onUnmounted(() => {
  observer?.disconnect()
  resizeObserver?.disconnect()
})
</script>
