<template>
  <div class="voice-input-wrapper">
    <!-- 主按钮 -->
    <el-button
      :type="buttonType"
      :loading="isLoading"
      :disabled="isDisabled"
      :class="['voice-btn', { 'is-pulsing': isRecording }]"
      @click="toggleRecording"
    >
      <el-icon v-if="!isLoading" class="voice-icon">
        <Microphone />
      </el-icon>
      <span class="voice-label">{{ buttonLabel }}</span>
    </el-button>

    <!-- 重连进度提示 -->
    <transition name="el-fade-in">
      <div v-if="status === 'reconnecting'" class="reconnect-hint">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在重连 ({{ retryCount }}/{{ maxRetries }})...</span>
      </div>
    </transition>

    <!-- 识别结果展示区 -->
    <div v-if="showResult" class="result-area">
      <div class="result-text">
        <!-- 已确认文本 -->
        <span class="final-text">{{ finalText }}</span>
        <!-- 中间结果（灰色闪烁） -->
        <span v-if="interimText" class="interim-text">{{ interimText }}</span>
        <!-- 光标动画 -->
        <span v-if="isRecording" class="cursor">|</span>
      </div>
    </div>

    <!-- 断连恢复提示 -->
    <transition name="el-fade-in">
      <div v-if="isRecovered" class="recovered-hint">
        <el-icon><CircleCheck /></el-icon>
        <span>已恢复连接，之前的内容已保存</span>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, Loading, CircleCheck } from '@element-plus/icons-vue'
import { useSpeechRecognition } from '@/composables/useSpeechRecognition'
import type { SpeechRecognitionOptions, SpeechError } from '@/types/speech'

// ---------------------------------------------------------------------------
// Props & Emits
// ---------------------------------------------------------------------------
const props = withDefaults(defineProps<{
  /** Azure Speech 配置 */
  speechOptions: SpeechRecognitionOptions
  /** 识别结果变更回调（v-model 模式） */
  modelValue?: string
  /** 是否展示结果区域 */
  showResult?: boolean
}>(), {
  modelValue: '',
  showResult: true,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'result', text: string): void
  (e: 'error', error: SpeechError): void
}>()

// ---------------------------------------------------------------------------
// composable 实例
// ---------------------------------------------------------------------------
const {
  status,
  finalText,
  interimText,
  isRecording,
  lastError,
  start,
  stop,
  reset,
  getFullText,
  onResult,
  onError,
} = useSpeechRecognition(props.speechOptions)

// ---------------------------------------------------------------------------
// 重试计数（从 lastError 中提取）
// ---------------------------------------------------------------------------
const retryCount = ref(0)
const maxRetries = computed(() =>
  props.speechOptions.reconnect?.maxRetries ?? 5
)

watch(lastError, (err) => {
  if (err?.retryCount) {
    retryCount.value = err.retryCount
  }
})

// ---------------------------------------------------------------------------
// 恢复标记
// ---------------------------------------------------------------------------
const isRecovered = ref(false)

// ---------------------------------------------------------------------------
// Toast 防刷屏：错误消息去重 + 节流
// ---------------------------------------------------------------------------
let lastToastMessage = ''
let lastToastTime = 0
const TOAST_DEDUP_INTERVAL = 5000 // 5秒内相同消息不重复弹出

function showToast(error: SpeechError) {
  const now = Date.now()

  // 可恢复的错误：只在首次和最后一次弹 toast
  if (error.recoverable) {
    const isFirstAttempt = error.retryCount === 1
    const isLastAttempt = error.retryCount === maxRetries.value

    if (!isFirstAttempt && !isLastAttempt) return

    if (isLastAttempt) {
      ElMessage.warning({
        message: error.message,
        duration: 5000,
        grouping: true, // Element Plus 自动合并相同消息
      })
      return
    }
  }

  // 去重：相同消息 5 秒内不重复弹
  if (
    error.message === lastToastMessage &&
    now - lastToastTime < TOAST_DEDUP_INTERVAL
  ) {
    return
  }

  lastToastMessage = error.message
  lastToastTime = now

  if (error.recoverable) {
    ElMessage.warning({
      message: error.message,
      duration: 3000,
      grouping: true,
    })
  } else {
    ElMessage.error({
      message: error.message,
      duration: 5000,
      grouping: true,
    })
  }
}

// ---------------------------------------------------------------------------
// 事件绑定
// ---------------------------------------------------------------------------
onResult((result) => {
  const fullText = getFullText()
  emit('update:modelValue', fullText)
  emit('result', fullText)

  if (result.isRecovered && !isRecovered.value) {
    isRecovered.value = true
    // 3 秒后自动隐藏恢复提示
    setTimeout(() => { isRecovered.value = false }, 3000)
  }
})

onError((error) => {
  showToast(error)
  emit('error', error)
})

// ---------------------------------------------------------------------------
// 按钮状态映射
// ---------------------------------------------------------------------------
const buttonType = computed(() => {
  switch (status.value) {
    case 'recognizing': return 'danger'
    case 'reconnecting': return 'warning'
    case 'error': return 'info'
    default: return 'primary'
  }
})

const buttonLabel = computed(() => {
  switch (status.value) {
    case 'connecting': return '连接中...'
    case 'recognizing': return '停止识别'
    case 'reconnecting': return '重连中...'
    case 'error': return '重新开始'
    default: return '语音输入'
  }
})

const isLoading = computed(() =>
  status.value === 'connecting' || status.value === 'reconnecting'
)

const isDisabled = computed(() => false) // 始终可点击

// ---------------------------------------------------------------------------
// 切换录音
// ---------------------------------------------------------------------------
async function toggleRecording() {
  if (isRecording.value) {
    await stop()
  } else {
    if (status.value === 'error') {
      reset()
      isRecovered.value = false
    }
    const success = await start()
    if (success) {
      isRecovered.value = false
    }
  }
}

// ---------------------------------------------------------------------------
// 暴露方法供父组件调用
// ---------------------------------------------------------------------------
defineExpose({
  start,
  stop,
  reset,
  getFullText,
  status,
  finalText,
  interimText,
})
</script>

<style scoped>
.voice-input-wrapper {
  display: inline-flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.voice-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 120px;
}

.voice-btn.is-pulsing {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(245, 108, 108, 0); }
}

.voice-icon {
  font-size: 16px;
}

.voice-label {
  font-size: 14px;
}

.reconnect-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--el-color-warning);
}

.result-area {
  max-width: 480px;
  min-height: 40px;
  padding: 8px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  background: var(--el-fill-color-lighter);
  font-size: 14px;
  line-height: 1.6;
}

.result-text {
  white-space: pre-wrap;
  word-break: break-all;
}

.final-text {
  color: var(--el-text-color-primary);
}

.interim-text {
  color: var(--el-text-color-secondary);
  opacity: 0.7;
}

.cursor {
  display: inline-block;
  color: var(--el-color-primary);
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.recovered-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-color-success);
}
</style>
