import { ref, computed, onUnmounted } from 'vue'
import { SpeechService } from '@/utils/speechService'
import {
  SpeechState,
  type SpeechConfig,
  type ReconnectConfig,
} from '@/types/speech'

export function useSpeechRecognition(
  config: SpeechConfig,
  reconnectConfig?: ReconnectConfig,
) {
  const state = ref<SpeechState>(SpeechState.Idle)
  const confirmedText = ref('')
  const interimText = ref('')
  const errorMessage = ref('')
  const reconnectAttempt = ref(0)
  const maxReconnectAttempts = ref(reconnectConfig?.maxAttempts ?? 5)

  const fullText = computed(() => {
    const interim = interimText.value
    if (!confirmedText.value && !interim) return ''
    if (!interim) return confirmedText.value
    return confirmedText.value ? `${confirmedText.value}${interim}` : interim
  })

  const isListening = computed(() => state.value === SpeechState.Listening)
  const isReconnecting = computed(() => state.value === SpeechState.Reconnecting)
  const isError = computed(() => state.value === SpeechState.Error)
  const isIdle = computed(() => state.value === SpeechState.Idle)
  const isActive = computed(
    () => state.value === SpeechState.Listening || state.value === SpeechState.Reconnecting,
  )

  const service = new SpeechService(
    config,
    {
      onStateChange(s) {
        state.value = s
      },
      onRecognized(_text, full) {
        confirmedText.value = service.confirmedText
        interimText.value = ''
        // 同步 fullText 语义，但 computed 会自动处理
        void full
      },
      onRecognizing(interim, _full) {
        interimText.value = interim
      },
      onError(msg, _isRetrying) {
        errorMessage.value = msg
      },
      onReconnecting(attempt, max) {
        reconnectAttempt.value = attempt
        maxReconnectAttempts.value = max
      },
      onReconnected() {
        reconnectAttempt.value = 0
        errorMessage.value = ''
      },
    },
    reconnectConfig,
  )

  async function start() {
    errorMessage.value = ''
    await service.start()
  }

  async function stop() {
    await service.stop()
    // 同步 service 内部合并后的 confirmedText
    confirmedText.value = service.confirmedText
    interimText.value = ''
  }

  async function toggle() {
    if (isActive.value) {
      await stop()
    } else {
      await start()
    }
  }

  /** 用户手动编辑文本框后同步回 service */
  function syncText(text: string) {
    confirmedText.value = text
    interimText.value = ''
    service.setConfirmedText(text)
  }

  /** 清空所有文本 */
  function clearText() {
    confirmedText.value = ''
    interimText.value = ''
    service.resetText()
  }

  onUnmounted(() => {
    service.dispose()
  })

  return {
    // 状态
    state,
    confirmedText,
    interimText,
    fullText,
    errorMessage,
    reconnectAttempt,
    maxReconnectAttempts,

    // 计算属性
    isListening,
    isReconnecting,
    isError,
    isIdle,
    isActive,

    // 方法
    start,
    stop,
    toggle,
    syncText,
    clearText,
  }
}
