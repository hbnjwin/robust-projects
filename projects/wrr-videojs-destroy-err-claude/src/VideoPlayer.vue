<template>
  <div class="video-player">
    <video ref="videoRef" class="video-js vjs-default-skin" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import videojs from 'video.js'
import type Player from 'video.js/dist/types/player'

const props = defineProps<{
  src: string
  poster?: string
}>()

const videoRef = ref<HTMLVideoElement>()
let player: Player | null = null

const initPlayer = () => {
  if (!videoRef.value) return

  player = videojs(videoRef.value, {
    controls: true,
    autoplay: false,
    preload: 'auto',
    fluid: true,
    sources: [{ src: props.src, type: 'video/mp4' }],
    poster: props.poster
  })
}

watch(() => props.src, (newSrc) => {
  if (player) {
    player.src({ src: newSrc, type: 'video/mp4' })
  }
})

onMounted(() => {
  initPlayer()
})

// BUG: onUnmounted 中调用 player.dispose() 时
// Vue 已经先把 DOM 元素移除了（因为路由切换触发了 unmount）
// video.js 的 dispose() 内部需要访问 DOM 元素来移除事件监听器
// 但此时 DOM 已经不存在了，导致 "Cannot read properties of null" 错误
onUnmounted(() => {
  if (player) {
    // BUG: 此时 videoRef.value 对应的 DOM 可能已被 Vue 移除
    // player.dispose() 会尝试操作已删除的 DOM 节点
    player.dispose()
    player = null
  }
})

// BUG: 应该在 onBeforeUnmount 中 dispose
// 或者用 player.dispose() 前先检查 player.el() 是否还存在
</script>
