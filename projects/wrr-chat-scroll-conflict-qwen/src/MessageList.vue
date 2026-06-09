<template>
  <div class="message-list" ref="containerRef" @scroll="handleScroll">
    <div v-for="msg in messages" :key="msg.id" class="message-item">
      <div class="role">{{ msg.role }}</div>
      <div class="content" v-html="msg.content" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

const props = defineProps<{
  messages: Message[]
  isStreaming: boolean
}>()

const containerRef = ref<HTMLDivElement>()

const scrollToBottom = () => {
  if (!containerRef.value) return
  containerRef.value.scrollTop = containerRef.value.scrollHeight
}

// BUG: 没有跟踪用户是否主动滚动了
// 当用户往上翻看历史消息时，流式回复更新会强制把滚动位置拉到底部
// 用户正在阅读历史记录时体验很差

const handleScroll = () => {
  // BUG: 这个 scroll 事件处理函数是空的
  // 应该检测用户是否主动向上滚动
  // 如果用户不在底部附近，应该暂停自动滚动
}

// 监听消息变化，自动滚到底部
watch(
  () => props.messages.length,
  () => {
    nextTick(() => {
      // BUG: 无条件滚到底部，不管用户是否在查看历史消息
      scrollToBottom()
    })
  }
)

// 监听流式回复内容变化
watch(
  () => props.messages[props.messages.length - 1]?.content,
  () => {
    if (props.isStreaming) {
      nextTick(() => {
        // BUG: 流式更新时也是无条件滚到底部
        scrollToBottom()
      })
    }
  }
)
</script>
