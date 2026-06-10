<template>
  <div class="app-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>语音批注录入</span>
          <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
        </div>
      </template>

      <!-- 语音输入组件 -->
      <VoiceInputButton
        ref="voiceRef"
        :speech-options="speechOptions"
        :show-result="true"
        @update:model-value="onTextChange"
        @error="onSpeechError"
      />

      <!-- 审核批注文本框 -->
      <el-input
        v-model="annotationText"
        type="textarea"
        :rows="6"
        placeholder="语音识别结果将自动填入此处，也可手动编辑..."
        class="annotation-input"
      />

      <div class="actions">
        <el-button @click="clearAnnotation">清空</el-button>
        <el-button type="primary" :disabled="!annotationText" @click="submitAnnotation">
          提交批注
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import VoiceInputButton from '@/components/VoiceInputButton.vue'
import type { SpeechRecognitionOptions, SpeechError } from '@/types/speech'

// ---------------------------------------------------------------------------
// Azure Speech 配置（生产环境应从环境变量 / 后端获取）
// ---------------------------------------------------------------------------
const speechOptions: SpeechRecognitionOptions = {
  subscriptionKey: import.meta.env.VITE_SPEECH_KEY ?? 'your-subscription-key',
  serviceRegion: import.meta.env.VITE_SPEECH_REGION ?? 'eastasia',
  language: 'zh-CN',
  reconnect: {
    maxRetries: 5,        // 最多重试 5 次
    baseDelay: 1000,      // 初始 1 秒
    maxDelay: 16000,      // 上限 16 秒
    connectionTimeout: 10000, // 单次连接超时 10 秒
  },
}

// ---------------------------------------------------------------------------
// 状态
// ---------------------------------------------------------------------------
const voiceRef = ref<InstanceType<typeof VoiceInputButton> | null>(null)
const annotationText = ref('')

const currentStatus = computed(() => voiceRef.value?.status ?? 'idle')

const statusTagType = computed(() => {
  switch (currentStatus.value) {
    case 'recognizing': return 'success'
    case 'reconnecting': return 'warning'
    case 'error': return 'danger'
    default: return 'info'
  }
})

const statusLabel = computed(() => {
  switch (currentStatus.value) {
    case 'connecting': return '连接中'
    case 'recognizing': return '识别中'
    case 'reconnecting': return '重连中'
    case 'error': return '错误'
    default: return '就绪'
  }
})

// ---------------------------------------------------------------------------
// 回调
// ---------------------------------------------------------------------------
function onTextChange(text: string) {
  annotationText.value = text
}

function onSpeechError(error: SpeechError) {
  console.warn('[Speech]', error.type, error.message)
}

function clearAnnotation() {
  annotationText.value = ''
  voiceRef.value?.reset()
}

function submitAnnotation() {
  // TODO: 调用后端 API 提交批注
  console.log('提交批注:', annotationText.value)
}
</script>

<style scoped>
.app-container {
  max-width: 640px;
  margin: 40px auto;
  padding: 0 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.annotation-input {
  margin-top: 16px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
</style>
