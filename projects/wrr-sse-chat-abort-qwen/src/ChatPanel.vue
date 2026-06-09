<template>
  <div class="chat-panel">
    <div class="messages" ref="messagesRef">
      <div v-for="msg in messages" :key="msg.id" class="message">
        <span class="role">{{ msg.role }}:</span>
        <span class="content">{{ msg.content }}</span>
      </div>
      <div v-if="isStreaming" class="streaming-indicator">AI 正在回复...</div>
    </div>
    <div class="input-area">
      <el-input v-model="inputText" placeholder="输入消息..." @keydown.enter="sendMessage" />
      <el-button v-if="!isStreaming" type="primary" @click="sendMessage">发送</el-button>
      <el-button v-else type="danger" @click="stopStreaming">停止</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { fetchEventSource } from '@microsoft/fetch-event-source'

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const isStreaming = ref(false)
let abortController: AbortController | null = null
let currentAssistantMsg = ''

const sendMessage = async () => {
  if (!inputText.value.trim() || isStreaming.value) return

  const userMsg: ChatMessage = {
    id: Date.now(),
    role: 'user',
    content: inputText.value
  }
  messages.value.push(userMsg)
  inputText.value = ''

  isStreaming.value = true
  abortController = new AbortController()
  currentAssistantMsg = ''

  const assistantMsg: ChatMessage = {
    id: Date.now() + 1,
    role: 'assistant',
    content: ''
  }
  messages.value.push(assistantMsg)

  try {
    await fetchEventSource('/api/ai/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMsg.content }),
      signal: abortController.signal,
      onmessage(event) {
        currentAssistantMsg += event.data
        assistantMsg.content = currentAssistantMsg
      },
      onerror(err) {
        throw err
      }
    })
  } catch (e: any) {
    if (e.name !== 'AbortError') {
      console.error('SSE error:', e)
    }
  }
  // BUG: isStreaming 和 abortController 没有在 finally 中清理
  // 如果用户点击停止（abort），catch 块执行后这里的代码不会执行
  // 因为 fetchEventSource 在 abort 后 promise 不会 resolve
}

const stopStreaming = () => {
  if (abortController) {
    abortController.abort()
    // BUG: 只 abort 了但没有重置 isStreaming = false
    // 导致停止后界面还是显示"正在回复"，发送按钮不显示
    abortController = null
  }
}
</script>
