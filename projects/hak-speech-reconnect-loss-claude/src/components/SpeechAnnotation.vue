<template>
  <div class="speech-annotation">
    <!-- 语音输入文本区域 -->
    <el-input
      v-model="displayText"
      type="textarea"
      :rows="4"
      :placeholder="textPlaceholder"
      :disabled="isReconnecting"
      @input="onTextInput"
    />

    <!-- 底部工具栏 -->
    <div class="speech-toolbar">
      <!-- 麦克风按钮 -->
      <el-button
        :type="buttonType"
        :icon="buttonIcon"
        circle
        size="large"
        :loading="isReconnecting"
        @click="toggle"
      />

      <!-- 状态文字 -->
      <span class="speech-status" :class="`speech-status--${state}`">
        {{ statusText }}
      </span>

      <!-- 清空按钮 -->
      <el-button
        v-if="fullText"
        text
        size="small"
        @click="onClear"
      >
        清空
      </el-button>
    </div>

    <!-- 重连提示条 -->
    <div v-if="isReconnecting" class="speech-reconnect-bar">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>
        网络连接断开，正在重连
        ({{ reconnectAttempt }}/{{ maxReconnectAttempts }})...
        已识别内容已保存
      </span>
    </div>

    <!-- 错误提示条（仅在非重连的错误状态显示） -->
    <div v-if="isError" class="speech-error-bar">
      <span>{{ errorMessage }}</span>
      <el-button type="primary" text size="small" @click="retry">
        重试
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useSpeechRecognition } from '@/composables/useSpeechRecognition'
import { SpeechState, type SpeechConfig, type ReconnectConfig } from '@/types/speech'

const props = withDefaults(defineProps<{
  config: SpeechConfig
  reconnectConfig?: ReconnectConfig
  placeholder?: string
}>(), {
  placeholder: '点击麦克风按钮，对着麦克风描述问题...',
})

const emit = defineEmits<{
  (e: 'update:text', value: string): void
  (e: 'stateChange', value: SpeechState): void
}>()

const {
  state,
  fullText,
  errorMessage,
  reconnectAttempt,
  maxReconnectAttempts,
  isListening,
  isReconnecting,
  isError,
  isActive,
  toggle,
  start,
  syncText,
  clearText,
} = useSpeechRecognition(props.config, props.reconnectConfig)

// 同步文本到父组件
watch(fullText, (text) => {
  emit('update:text', text)
})

watch(state, (s) => {
  emit('stateChange', s)
})

// 仅在真正的错误状态（非重连中）显示 toast
watch(errorMessage, (msg) => {
  if (msg && isError.value) {
    ElMessage.error({ message: msg, duration: 5000, grouping: true })
  }
})

const displayText = computed({
  get: () => fullText.value,
  set: (val: string) => {
    syncText(val)
  },
})

const textPlaceholder = computed(() =>
  isReconnecting.value ? '网络重连中，已识别内容已保存...' : props.placeholder,
)

const buttonType = computed(() => {
  if (isListening.value) return 'danger'
  if (isReconnecting.value) return 'warning'
  if (isError.value) return 'info'
  return 'primary'
})

const buttonIcon = computed(() => {
  if (isActive.value) return 'Microphone'
  return 'Microphone'
})

const statusText = computed(() => {
  switch (state.value) {
    case SpeechState.Listening:
      return '正在识别...'
    case SpeechState.Reconnecting:
      return '重连中...'
    case SpeechState.Error:
      return '识别已停止'
    default:
      return '点击开始语音识别'
  }
})

function onTextInput(value: string | number) {
  syncText(String(value))
}

function onClear() {
  clearText()
  emit('update:text', '')
}

async function retry() {
  await start()
}
</script>

<style scoped>
.speech-annotation {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.speech-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.speech-status {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.speech-status--listening {
  color: var(--el-color-danger);
}
.speech-status--reconnecting {
  color: var(--el-color-warning);
}
.speech-status--error {
  color: var(--el-color-info);
}

.speech-reconnect-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 4px;
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning-dark-2);
  font-size: 13px;
}

.speech-error-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 4px;
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
  font-size: 13px;
}
</style>
