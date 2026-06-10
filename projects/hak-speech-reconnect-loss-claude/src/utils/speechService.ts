import * as speechsdk from 'microsoft-cognitiveservices-speech-sdk'
import {
  SpeechState,
  type SpeechConfig as AppSpeechConfig,
  type ReconnectConfig,
  type SpeechServiceCallbacks,
  type SpeechSessionState,
} from '@/types/speech'

const DEFAULT_RECONNECT: Required<ReconnectConfig> = {
  maxAttempts: 5,
  baseDelay: 1000,
  maxDelay: 16000,
  networkTimeout: 30000,
}

/**
 * Azure Speech SDK 服务封装
 *
 * 核心解决：
 * 1. WebSocket 断线后自动重连，新 recognizer 正确接管已确认文本
 * 2. 断线时保留已确认的识别结果（recognized），仅丢失未完成的临时文本
 * 3. 指数退避重连 + 最大重试次数，避免无限重试和 error toast 刷屏
 * 4. UI 状态准确反映实际识别状态
 */
export class SpeechService {
  private config: AppSpeechConfig
  private reconnectConfig: Required<ReconnectConfig>
  private callbacks: SpeechServiceCallbacks

  private recognizer: speechsdk.SpeechRecognizer | null = null
  private _state: SpeechState = SpeechState.Idle
  private _confirmedText = ''
  private _interimText = ''

  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private isDisposing = false
  private isUserStopping = false

  // 错误节流：相同错误 30 秒内不重复回调
  private lastErrorMsg = ''
  private lastErrorTime = 0
  private readonly errorThrottleMs = 30000

  constructor(
    config: AppSpeechConfig,
    callbacks: SpeechServiceCallbacks = {},
    reconnectConfig: ReconnectConfig = {},
  ) {
    this.config = config
    this.callbacks = callbacks
    this.reconnectConfig = { ...DEFAULT_RECONNECT, ...reconnectConfig }
  }

  // ── 公开状态 ──────────────────────────────────────────

  get state(): SpeechState {
    return this._state
  }

  get confirmedText(): string {
    return this._confirmedText
  }

  get interimText(): string {
    return this._interimText
  }

  get fullText(): string {
    const interim = this._interimText
    if (!this._confirmedText && !interim) return ''
    if (!interim) return this._confirmedText
    return this._confirmedText ? `${this._confirmedText}${interim}` : interim
  }

  getSessionState(): SpeechSessionState {
    return {
      state: this._state,
      confirmedText: this._confirmedText,
      interimText: this._interimText,
      fullText: this.fullText,
      reconnectAttempt: this.reconnectAttempts,
      maxReconnectAttempts: this.reconnectConfig.maxAttempts,
      errorMessage: this.lastErrorMsg,
    }
  }

  // ── 启动 / 停止 ──────────────────────────────────────

  async start(): Promise<void> {
    if (this._state === SpeechState.Listening) return
    this.resetReconnect()
    this.isUserStopping = false
    await this.createAndStart()
  }

  async stop(): Promise<void> {
    this.isUserStopping = true
    this.cancelReconnectTimer()
    await this.disposeRecognizer()
    // 停止时把未确认的临时文本合并到已确认文本中，避免丢失
    if (this._interimText) {
      this._confirmedText += this._interimText
      this._interimText = ''
    }
    this.setState(SpeechState.Idle)
  }

  /** 完全销毁，释放所有资源 */
  dispose(): void {
    this.isUserStopping = true
    this.cancelReconnectTimer()
    this.disposeRecognizer()
    this._confirmedText = ''
    this._interimText = ''
    this.setState(SpeechState.Idle)
  }

  /** 重置已保存的文本（比如用户清空了文本框） */
  resetText(): void {
    this._confirmedText = ''
    this._interimText = ''
  }

  /** 允许外部设置已确认文本（比如文本框被用户手动编辑） */
  setConfirmedText(text: string): void {
    this._confirmedText = text
  }

  // ── 内部：创建 recognizer 并启动 ────────────────────

  private async createAndStart(): Promise<void> {
    try {
      const sdkConfig = speechsdk.SpeechConfig.fromSubscription(
        this.config.subscriptionKey,
        this.config.region,
      )
      sdkConfig.speechRecognitionLanguage = this.config.language ?? 'zh-CN'

      const audioConfig = speechsdk.AudioConfig.fromDefaultMicrophoneInput()
      const recognizer = new speechsdk.SpeechRecognizer(sdkConfig, audioConfig)

      this.bindEvents(recognizer)

      await new Promise<void>((resolve, reject) => {
        recognizer.startContinuousRecognitionAsync(
          () => resolve(),
          (err) => reject(new Error(err)),
        )
      })

      this.recognizer = recognizer
      this._interimText = ''
      this.setState(SpeechState.Listening)

      // 重连成功
      if (this.reconnectAttempts > 0) {
        this.callbacks.onReconnected?.()
        this.resetReconnect()
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      this.handleStartFailure(msg)
    }
  }

  private bindEvents(recognizer: speechsdk.SpeechRecognizer): void {
    // 中间结果：实时更新临时文本
    recognizer.recognizing = (_sender, event) => {
      this._interimText = event.result.text ?? ''
      this.callbacks.onRecognizing?.(this._interimText, this.fullText)
    }

    // 最终结果：累积到已确认文本
    recognizer.recognized = (_sender, event) => {
      if (
        event.result.reason === speechsdk.ResultReason.RecognizedSpeech &&
        event.result.text
      ) {
        this._confirmedText += event.result.text
        this._interimText = ''
        this.callbacks.onRecognized?.(event.result.text, this.fullText)
      }
    }

    // 取消事件：连接断开的核心处理入口
    recognizer.canceled = (_sender, event) => {
      if (this.isDisposing || this.isUserStopping) return

      if (event.reason === speechsdk.CancellationReason.Error) {
        const isConnectionError = this.isConnectionRelatedError(event.errorCode)

        if (isConnectionError) {
          // 连接错误 → 尝试重连
          // 关键：此时 confirmedText 不清空，保留断线前已确认的文本
          this._interimText = '' // 临时文本无法恢复，清空
          this.attemptReconnect(event.errorDetails)
        } else {
          // 非连接错误（如认证失败），不重连
          this.emitThrottledError(event.errorDetails, false)
          this.setState(SpeechState.Error)
        }
      }
    }

    recognizer.sessionStopped = () => {
      if (!this.isDisposing && !this.isUserStopping && this._state === SpeechState.Listening) {
        // 会话异常停止（非用户主动），尝试重连
        this._interimText = ''
        this.attemptReconnect('会话意外终止')
      }
    }
  }

  // ── 内部：重连逻辑 ─────────────────────────────────

  private async attemptReconnect(errorDetail: string): Promise<void> {
    // 先释放旧 recognizer（但不改 confirmedText）
    await this.disposeRecognizer()

    this.reconnectAttempts++
    const { maxAttempts } = this.reconnectConfig

    if (this.reconnectAttempts > maxAttempts) {
      // 超过最大重试次数，停止
      this.emitThrottledError(
        `重连失败，已尝试 ${maxAttempts} 次: ${errorDetail}`,
        false,
      )
      this.setState(SpeechState.Error)
      return
    }

    this.setState(SpeechState.Reconnecting)
    this.callbacks.onReconnecting?.(this.reconnectAttempts, maxAttempts)
    this.emitThrottledError(
      `连接断开，正在重连 (${this.reconnectAttempts}/${maxAttempts})...`,
      true,
    )

    const delay = this.calcBackoffDelay()

    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null
      if (this.isUserStopping) return
      await this.createAndStart()
    }, delay)
  }

  private handleStartFailure(errorMsg: string): void {
    if (this.isUserStopping) return

    // 如果是重连过程中启动失败，继续尝试
    if (this._state === SpeechState.Reconnecting) {
      this.attemptReconnect(errorMsg)
      return
    }

    // 首次启动失败
    this.emitThrottledError(errorMsg, false)
    this.setState(SpeechState.Error)
  }

  private calcBackoffDelay(): number {
    const { baseDelay, maxDelay } = this.reconnectConfig
    // 指数退避 + 随机抖动避免惊群
    const exponential = baseDelay * Math.pow(2, this.reconnectAttempts - 1)
    const capped = Math.min(exponential, maxDelay)
    const jitter = capped * 0.2 * Math.random()
    return capped + jitter
  }

  private resetReconnect(): void {
    this.reconnectAttempts = 0
    this.cancelReconnectTimer()
  }

  private cancelReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  // ── 内部：Recognizer 生命周期 ──────────────────────

  private async disposeRecognizer(): Promise<void> {
    if (!this.recognizer) return
    this.isDisposing = true
    const ref = this.recognizer
    this.recognizer = null

    try {
      await new Promise<void>((resolve) => {
        ref.stopContinuousRecognitionAsync(
          () => resolve(),
          () => resolve(), // 即使停止失败也不阻塞
        )
      })
    } catch {
      // 忽略停止时的错误
    }

    try {
      ref.close()
    } catch {
      // 忽略关闭时的错误
    }

    this.isDisposing = false
  }

  // ── 内部：错误节流 ─────────────────────────────────

  private isConnectionRelatedError(errorCode: speechsdk.CancellationErrorCode): boolean {
    return (
      errorCode === speechsdk.CancellationErrorCode.ConnectionFailure ||
      errorCode === speechsdk.CancellationErrorCode.ServiceTimeout ||
      errorCode === speechsdk.CancellationErrorCode.ServiceError
    )
  }

  private emitThrottledError(message: string, isRetrying: boolean): void {
    const now = Date.now()

    // 相同错误消息在节流时间内不重复回调
    if (
      message === this.lastErrorMsg &&
      now - this.lastErrorTime < this.errorThrottleMs
    ) {
      return
    }

    this.lastErrorMsg = message
    this.lastErrorTime = now
    this.callbacks.onError?.(message, isRetrying)
  }

  // ── 内部：状态管理 ─────────────────────────────────

  private setState(state: SpeechState): void {
    if (this._state === state) return
    this._state = state
    this.callbacks.onStateChange?.(state)
  }
}
