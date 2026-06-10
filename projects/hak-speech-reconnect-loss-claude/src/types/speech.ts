export enum SpeechState {
  /** 空闲，未开始识别 */
  Idle = 'idle',
  /** 正在识别中 */
  Listening = 'listening',
  /** 连接断开，正在重连 */
  Reconnecting = 'reconnecting',
  /** 重连失败或不可恢复的错误 */
  Error = 'error',
}

export interface SpeechConfig {
  /** Azure Speech 服务的订阅密钥 */
  subscriptionKey: string
  /** Azure Speech 服务的区域 */
  region: string
  /** 识别语言，默认 zh-CN */
  language?: string
}

export interface ReconnectConfig {
  /** 最大重连次数，默认 5 */
  maxAttempts?: number
  /** 初始重连延迟（毫秒），默认 1000 */
  baseDelay?: number
  /** 最大重连延迟（毫秒），默认 16000 */
  maxDelay?: number
  /** 完全断网后停止重试的超时时间（毫秒），默认 30000 */
  networkTimeout?: number
}

export interface SpeechSessionState {
  /** 当前识别状态 */
  state: SpeechState
  /** 已确认的识别文本（不会因断线丢失） */
  confirmedText: string
  /** 当前正在识别的临时文本 */
  interimText: string
  /** 完整文本 = confirmedText + interimText */
  fullText: string
  /** 当前重连尝试次数 */
  reconnectAttempt: number
  /** 最大重连次数 */
  maxReconnectAttempts: number
  /** 错误信息 */
  errorMessage: string
}

export interface SpeechServiceCallbacks {
  /** 状态变化 */
  onStateChange?: (state: SpeechState) => void
  /** 收到已确认的识别结果 */
  onRecognized?: (text: string, fullText: string) => void
  /** 收到临时识别结果 */
  onRecognizing?: (interimText: string, fullText: string) => void
  /** 错误发生（已节流，不会刷屏） */
  onError?: (message: string, isRetrying: boolean) => void
  /** 重连状态变化 */
  onReconnecting?: (attempt: number, maxAttempts: number) => void
  /** 重连成功 */
  onReconnected?: () => void
}
