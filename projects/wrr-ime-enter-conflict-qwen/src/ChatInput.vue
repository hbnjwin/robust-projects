<template>
  <div class="chat-input">
    <el-input
      v-model="inputText"
      type="textarea"
      :rows="3"
      placeholder="输入消息，按回车发送"
      @keydown.enter="handleEnter"
      @compositionstart="handleCompositionStart"
      @compositionend="handleCompositionEnd"
    />
    <el-button type="primary" @click="handleSend" :disabled="!inputText.trim()">
      发送
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  (e: 'send', message: string): void
}>()

const inputText = ref('')
let isComposing = false

const handleCompositionStart = () => {
  isComposing = true
}

const handleCompositionEnd = () => {
  // BUG: 在某些浏览器（Chrome）中，compositionend 事件在 keydown 之后触发
  // 时序：keydown(Enter) -> compositionend -> keyup(Enter)
  // 所以当用户按回车确认选词时，keydown 先执行，此时 isComposing 还是 true
  // 但实际上 handleEnter 已经被调用了
  isComposing = false
}

const handleEnter = (e: KeyboardEvent) => {
  // BUG: 这里检查 isComposing 来判断是否在输入法状态
  // 但由于 Chrome 的事件顺序问题，compositionend 在 keydown 之后才触发
  // 导致用户按回车确认选词时，isComposing 已经被 compositionend 设为 false
  // 但因为 keydown 先触发，此时 isComposing 还是 true —— 看似正确
  // 实际问题：e.isComposing 属性在 keydown 事件中更准确，但代码没有用它
  // 而是用了自己维护的 isComposing 变量
  if (isComposing) return

  // BUG: 没有阻止默认的换行行为
  // e.preventDefault() 缺失导致 textarea 会换行
  handleSend()
}

const handleSend = () => {
  const text = inputText.value.trim()
  if (!text) return
  emit('send', text)
  inputText.value = ''
}
</script>
