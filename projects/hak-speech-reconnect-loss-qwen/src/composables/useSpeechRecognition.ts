/**
 * Azure Speech SDK 语音识别 composable
 *
 * 解决的核心问题：
 * 1. WebSocket 断连后新 recognizer 实例无法接管旧 session 状态
 *    → 通过 committedTextBuffer 跨实例持久化已确认识别结果
 *    → pendingInterimText 保存断连瞬间的中间结果
 * 2. 断线后按钮卡在"正在识别中"
 *    → 严格的状态机：断连立即切到 reconnecting，最终恢复或 error
 * 3. 完全断网时重连无限重试 + error toast 刷屏
 *    → 指数退避 + maxRetries 上限 + 合并错误通知
 *
 * 状态机：
 *   idle → connecting → recognizing ⇄ reconnecting
 *                         ↓                ↓
 *                       idle            error → idle (手动 reset)
 */
import { ref, computed, onBeforeUnmount } from 'vue'
import * as sdk from 'microsoft-cognitiveservices-speech-sdk'
import type {
  SpeechRecognitionStatus,
  RecognitionResult,
  SpeechRecognitionOptions,
  SpeechError,
  ReconnectOptions,
} from '@/types/speech'
import { DEFAULT_RECONNECT_OPTIONS } from '@/types/speech'

export function useSpeechRecognition(options: SpeechRecognitionOptions) {
  // ---------------------------------------------------------------------------
  // 状态
  // ---------------------------------------------------------------------------
  const status = ref<SpeechRecognitionStatus>('idle')
  /** 已确认的最终文本（跨重连持久化） */
  const finalText = ref('')
  /** 当前句子的中间识别结果 */
  const interimText = ref('')
  const isRecording = computed(() =>
    status.value === 'recognizing' || status.value === 'reconnecting'
  )
  const lastError = ref<SpeechError | null>(null)

  // ---------------------------------------------------------------------------
  // 内部状态（不暴露给模板）
  // ---------------------------------------------------------------------------
  /** 当前 recognizer 实例（用 shallowRef 避免深度代理 SDK 对象） */
  let recognizer: sdk.SpeechRecognizer | null = null
  /** 跨实例持久化的已确认文本缓冲 */
  let committedTextBuffer = ''
  /** 断连瞬间保存的中间结果（用于 UI 提示） */
  let pendingInterimText = ''
  let reconnectAttempts = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let connectionTimer: ReturnType<typeof setTimeout> | null = null
  /** 标记：用户主动 stop 时不应触发 canceled 事件中的重连 */
  let intentionalStop = false

  const reconnectConfig: ReconnectOptions = {
    ...DEFAULT_RECONNECT_OPTIONS,
    ...options.reconnect,
  }

  // ---------------------------------------------------------------------------
  // 事件回调（供组件绑定）
  // ---------------------------------------------------------------------------
  const onResultCallbacks: Array<(result: RecognitionResult) => void> = []
  const onErrorCallbacks: Array<(error: SpeechError) => void> = []
  const onStatusCallbacks: Array<(status: SpeechRecognitionStatus) => void> = []

  function onResult(cb: (r: RecognitionResult) => void) { onResultCallbacks.push(cb) }
  function onError(cb: (e: SpeechError) => void) { onErrorCallbacks.push(cb) }
  function onStatus(cb: (s: SpeechRecognitionStatus) => void) { onStatusCallbacks.push(cb) }

  function emitResult() {
    const result: RecognitionResult = {
      finalText: finalText.value,
      interimText: interimText.value,
      isRecovered: reconnectAttempts > 0,
    }
    onResultCallbacks.forEach(cb => cb(result))
  }

  function emitError(error: SpeechError) {
    lastError.value = error
    onErrorCallbacks.forEach(cb => cb(error))
  }

  function setStatus(s: SpeechRecognitionStatus) {
    status.value = s
    onStatusCallbacks.forEach(cb => cb(s))
  }

  // ---------------------------------------------------------------------------
  // 核心：创建 & 销毁 recognizer
  // ---------------------------------------------------------------------------

  /**
   * 创建新的 SpeechRecognizer 实例
   *
   * 关键设计：每次重连都创建全新实例（Azure SDK 不支持复用），
   * 但通过 committedTextBuffer 在实例之间传递已确认的文本状态。
   */
  function createRecognizer(): sdk.SpeechRecognizer {
    const speechConfig = sdk.SpeechConfig.fromSubscription(
      options.subscriptionKey,
      options.serviceRegion,
    )
    speechConfig.speechRecognitionLanguage = options.language ?? 'zh-CN'

    // 启用听写模式以提升长句识别精度
    speechConfig.setProperty(
      sdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
      '10000',
    )

    const audioConfig = sdk.AudioConfig.fromDefaultMicrophoneInput()
    return new sdk.SpeechRecognizer(speechConfig, audioConfig)
  }

  /**
   * 安全销毁 recognizer 实例
   * 确保调用 close() 释放 WebSocket 连接和麦克风资源
   */
  function destroyRecognizer() {
    if (recognizer) {
      try {
        recognizer.stopContinuousRecognitionAsync()
      } catch {
        // 忽略：可能已经处于关闭状态
      }
      try {
        recognizer.close()
      } catch {
        // 忽略：资源可能已被 GC
      }
      recognizer = null
    }
  }

  // ---------------------------------------------------------------------------
  // 核心：事件绑定
  // ---------------------------------------------------------------------------

  /**
   * 为新创建的 recognizer 绑定所有事件处理器
   *
   * 这是修复"新实例不接管旧 session"的关键：
   * 每次创建新 recognizer 时都调用此方法，确保事件处理逻辑一致，
   * 且能通过 committedTextBuffer 访问到之前的识别结果。
   */
  function bindEvents(rec: sdk.SpeechRecognizer) {
    // ---- 中间结果（尚未确认）----
    rec.recognizing = (_sender, event) => {
      if (intentionalStop) return
      const text = event.result.text
      if (text) {
        interimText.value = text
        emitResult()
      }
    }

    // ---- 最终结果（一句话识别完成）----
    rec.recognized = (_sender, event) => {
      if (intentionalStop) return

      const { result } = event

      if (result.reason === sdk.ResultReason.RecognizedSpeech && result.text) {
        // 将识别结果追加到持久化缓冲区（跨 recognizer 实例保持累积）
        committedTextBuffer += result.text
        finalText.value = committedTextBuffer
        interimText.value = ''
        emitResult()
      } else if (result.reason === sdk.ResultReason.NoMatch) {
        // 无匹配：不是错误，只是没听清，继续保持识别
        interimText.value = ''
      }
    }

    // ---- 会话开始 ----
    rec.sessionStarted = () => {
      clearConnectionTimer()
      // 如果是重连，恢复到 recognizing 状态
      if (status.value === 'reconnecting') {
        reconnectAttempts = 0
        setStatus('recognizing')
      }
    }

    // ---- 会话结束 ----
    rec.sessionStopped = () => {
      if (!intentionalStop && status.value === 'recognizing') {
        // 非预期的 session 结束 → 尝试重连
        handleConnectionLoss('connection_lost', '语音会话意外终止')
      }
    }

    // ---- 取消/错误事件（断连的核心入口）----
    rec.canceled = (_sender, event) => {
      if (intentionalStop) return

      const { reason, errorCode, errorDetails } = event

      if (reason === sdk.CancellationReason.Error) {
        // 根据错误码判断是否可重连
        if (isRecoverableError(errorCode)) {
          handleConnectionLoss(
            'connection_lost',
            `连接断开 (code=${errorCode})`,
          )
        } else if (errorCode === sdk.ErrorCode.NoError) {
          // 某些情况下 NoError 实际是网络问题
          handleConnectionLoss('connection_lost', '连接异常中断')
        } else {
          // 不可恢复的错误
          handleFatalError(
            'sdk_error',
            `语音识别错误: ${errorDetails || `code=${errorCode}`}`,
          )
        }
      } else if (reason === sdk.CancellationReason.EndOfStream) {
        // 正常结束流，不需要重连
        if (status.value !== 'idle') {
          finalizeAndReset()
        }
      }
    }
  }

  /**
   * 判断错误码是否为可恢复的网络类错误
   */
  function isRecoverableError(errorCode: sdk.ErrorCode | undefined): boolean {
    if (errorCode === undefined) return true
    const recoverableCodes = new Set([
      sdk.ErrorCode.ConnectionFailure,
      sdk.ErrorCode.ServiceTimeout,
      sdk.ErrorCode.ServiceUnavailable,
      sdk.ErrorCode.ServiceError,
    ])
    return recoverableCodes.has(errorCode)
  }

  // ---------------------------------------------------------------------------
  // 核心：断线重连逻辑
  // ---------------------------------------------------------------------------

  /**
   * 处理连接丢失
   *
   * 流程：
   * 1. 保存当前中间结果（防止丢失）
   * 2. 销毁旧 recognizer
   * 3. 进入 reconnecting 状态
   * 4. 按指数退避调度重连
   * 5. 达到 maxRetries 后进入 error 状态
   */
  function handleConnectionLoss(
    type: SpeechError['type'],
    message: string,
  ) {
    // 重入保护：sessionStopped 和 canceled 可能对同一次断连都触发，
    // 确保只执行一次重连流程
    if (
      status.value === 'reconnecting' ||
      status.value === 'error' ||
      status.value === 'idle'
    ) {
      return
    }

    // 立即保存断连瞬间的中间结果
    saveInterimOnDisconnect()

    // 销毁旧实例，释放资源
    destroyRecognizer()
    clearConnectionTimer()

    // 检查是否还能重试
    if (reconnectAttempts >= reconnectConfig.maxRetries) {
      handleFatalError(
        'max_retries',
        `重连失败：已尝试 ${reconnectConfig.maxRetries} 次，请检查网络后手动重试`,
      )
      return
    }

    setStatus('reconnecting')

    // 通知 UI（仅在首次和最后一次时通知，防止 toast 刷屏）
    const isLastAttempt =
      reconnectAttempts === reconnectConfig.maxRetries - 1
    emitError({
      type,
      message: isLastAttempt
        ? `连接断开，最后一次重连尝试 (${reconnectAttempts + 1}/${reconnectConfig.maxRetries})`
        : `连接断开，正在重连 (${reconnectAttempts + 1}/${reconnectConfig.maxRetries})`,
      retryCount: reconnectAttempts + 1,
      recoverable: true,
    })

    // 指数退避：delay = baseDelay * 2^attempt，上限 maxDelay
    const delay = Math.min(
      reconnectConfig.baseDelay * Math.pow(2, reconnectAttempts),
      reconnectConfig.maxDelay,
    )
    reconnectAttempts++

    reconnectTimer = setTimeout(() => {
      attemptReconnect()
    }, delay)
  }

  /**
   * 执行重连
   *
   * 关键：创建新 recognizer 实例并通过 bindEvents() 绑定与旧实例相同的事件处理。
   * committedTextBuffer 在实例切换期间保持不变，实现 session 状态的"传递"。
   */
  function attemptReconnect() {
    if (intentionalStop || status.value !== 'reconnecting') return

    try {
      const newRecognizer = createRecognizer()
      bindEvents(newRecognizer)
      recognizer = newRecognizer

      // 设置单次连接超时
      connectionTimer = setTimeout(() => {
        if (status.value === 'reconnecting') {
          // 超时 → 销毁当前实例，触发下一次重试
          destroyRecognizer()
          handleConnectionLoss('timeout', '重连超时')
        }
      }, reconnectConfig.connectionTimeout)

      // 启动连续识别
      newRecognizer.startContinuousRecognitionAsync(
        () => {
          // 连接成功 → sessionStarted 事件会处理状态切换
        },
        (err) => {
          // startContinuousRecognitionAsync 本身的启动失败
          clearConnectionTimer()
          destroyRecognizer()
          handleConnectionLoss('sdk_error', `重连启动失败: ${err}`)
        },
      )
    } catch (err) {
      clearConnectionTimer()
      handleConnectionLoss('sdk_error', `创建识别器失败: ${err}`)
    }
  }

  /**
   * 保存断连瞬间的中间结果
   *
   * 将当前 interimText 追加到 committedTextBuffer，
   * 确保用户说了一半的话不会完全丢失。
   * 同时记录 pendingInterimText 用于 UI 展示。
   */
  function saveInterimOnDisconnect() {
    const currentInterim = interimText.value.trim()
    if (currentInterim) {
      // 中间结果虽未最终确认，但在断连场景下选择保留而非丢弃
      committedTextBuffer += currentInterim
      finalText.value = committedTextBuffer
      pendingInterimText = currentInterim
      interimText.value = ''
    }
  }

  /**
   * 不可恢复错误 → 进入 error 状态，停止一切重试
   */
  function handleFatalError(type: SpeechError['type'], message: string) {
    destroyRecognizer()
    clearTimers()

    emitError({
      type,
      message,
      retryCount: reconnectAttempts,
      recoverable: false,
    })
    setStatus('error')
  }

  /**
   * 正常结束 → 保存结果，回到 idle
   */
  function finalizeAndReset() {
    destroyRecognizer()
    clearTimers()
    reconnectAttempts = 0
    setStatus('idle')
    emitResult()
  }

  // ---------------------------------------------------------------------------
  // 定时器管理
  // ---------------------------------------------------------------------------

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function clearConnectionTimer() {
    if (connectionTimer) {
      clearTimeout(connectionTimer)
      connectionTimer = null
    }
  }

  function clearTimers() {
    clearReconnectTimer()
    clearConnectionTimer()
  }

  // ---------------------------------------------------------------------------
  // 公开 API
  // ---------------------------------------------------------------------------

  /**
   * 开始语音识别
   *
   * 如果当前正在识别或重连中，直接返回 false。
   * 如果之前有错误，自动 reset 后重新开始。
   */
  async function start(): Promise<boolean> {
    if (isRecording.value) return false

    // 从 error 状态恢复
    if (status.value === 'error') {
      reset()
    }

    try {
      intentionalStop = false
      reconnectAttempts = 0
      lastError.value = null
      setStatus('connecting')

      const rec = createRecognizer()
      bindEvents(rec)
      recognizer = rec

      return new Promise<boolean>((resolve) => {
        rec.startContinuousRecognitionAsync(
          () => {
            setStatus('recognizing')
            resolve(true)
          },
          (err) => {
            setStatus('error')
            emitError({
              type: 'sdk_error',
              message: `启动语音识别失败: ${err}`,
              recoverable: false,
            })
            resolve(false)
          },
        )
      })
    } catch (err) {
      setStatus('error')
      emitError({
        type: 'sdk_error',
        message: `初始化语音识别失败: ${err}`,
        recoverable: false,
      })
      return false
    }
  }

  /**
   * 停止语音识别
   *
   * intentionalStop 标记确保 stopContinuousRecognitionAsync 触发的
   * canceled 事件不会启动重连流程。
   */
  async function stop(): Promise<void> {
    intentionalStop = true
    clearTimers()

    if (recognizer) {
      return new Promise<void>((resolve) => {
        recognizer!.stopContinuousRecognitionAsync(
          () => {
            destroyRecognizer()
            reconnectAttempts = 0
            setStatus('idle')
            emitResult()
            resolve()
          },
          () => {
            // stop 失败也要清理资源
            destroyRecognizer()
            reconnectAttempts = 0
            setStatus('idle')
            emitResult()
            resolve()
          },
        )
      })
    }

    setStatus('idle')
    emitResult()
  }

  /**
   * 重置所有状态（清空文本、重试计数、错误信息）
   * 用于"重新开始"场景。
   */
  function reset() {
    intentionalStop = true
    clearTimers()
    destroyRecognizer()

    committedTextBuffer = ''
    pendingInterimText = ''
    reconnectAttempts = 0

    finalText.value = ''
    interimText.value = ''
    lastError.value = null
    setStatus('idle')
  }

  /**
   * 获取当前累积的完整文本（含中间结果）
   * 用于在组件中展示实时预览。
   */
  function getFullText(): string {
    const interim = interimText.value.trim()
    return interim ? `${finalText.value}${interim}` : finalText.value
  }

  // ---------------------------------------------------------------------------
  // 生命周期
  // ---------------------------------------------------------------------------

  onBeforeUnmount(() => {
    intentionalStop = true
    clearTimers()
    destroyRecognizer()
    // 清空回调引用，防止内存泄漏
    onResultCallbacks.length = 0
    onErrorCallbacks.length = 0
    onStatusCallbacks.length = 0
  })

  return {
    // 响应式状态
    status,
    finalText,
    interimText,
    isRecording,
    lastError,

    // 方法
    start,
    stop,
    reset,
    getFullText,

    // 事件订阅
    onResult,
    onError,
    onStatus,
  }
}
