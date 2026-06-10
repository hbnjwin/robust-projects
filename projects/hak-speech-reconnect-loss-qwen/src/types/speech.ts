/**
 * 语音识别模块类型定义
 *
 * 覆盖 Azure Speech SDK 断线重连场景下的状态流转：
 *   idle → connecting → recognizing ⇄ reconnecting → idle
 *                                               ↘ error
 */

/** 语音识别状态 */
export type SpeechRecognitionStatus =
  | 'idle'          // 未启动
  | 'connecting'    // 首次连接中
  | 'recognizing'   // 正常识别中
  | 'reconnecting'  // 断线后正在重连
  | 'error'         // 不可恢复错误

/** 识别结果 */
export interface RecognitionResult {
  /** 已确认的最终文本（包含历史累积 + 本次会话） */
  finalText: string
  /** 当前句子的中间识别结果（尚未确认） */
  interimText: string
  /** 是否为重连后恢复的会话 */
  isRecovered: boolean
}

/** 重连配置 */
export interface ReconnectOptions {
  /** 最大重试次数，超过后放弃并进入 error 状态 */
  maxRetries: number
  /** 初始重试间隔（ms），后续按指数退避递增 */
  baseDelay: number
  /** 重试间隔上限（ms） */
  maxDelay: number
  /** 单次连接超时（ms），超时后立即触发下一次重试 */
  connectionTimeout: number
}

/** composable 配置 */
export interface SpeechRecognitionOptions {
  /** Azure Speech 订阅密钥 */
  subscriptionKey: string
  /** Azure Speech 服务区域，如 'eastasia' */
  serviceRegion: string
  /** 识别语言，默认 'zh-CN' */
  language?: string
  /** 重连策略配置（可选，有合理默认值） */
  reconnect?: Partial<ReconnectOptions>
}

/** 重连错误类型 */
export type ReconnectErrorType =
  | 'connection_lost'    // WebSocket 连接断开
  | 'max_retries'        // 达到最大重试次数
  | 'timeout'            // 单次连接超时
  | 'sdk_error'          // SDK 内部错误
  | 'no_speech'          // 长时间无语音输入
  | 'permission_denied'  // 麦克风权限被拒

/** 错误事件 */
export interface SpeechError {
  type: ReconnectErrorType
  message: string
  /** 当前重试次数（仅 connection_lost / timeout 时有意义） */
  retryCount?: number
  /** 是否可恢复（true 表示还会继续重试） */
  recoverable: boolean
}

/** 默认重连配置 */
export const DEFAULT_RECONNECT_OPTIONS: ReconnectOptions = {
  maxRetries: 5,
  baseDelay: 1000,
  maxDelay: 16000,
  connectionTimeout: 10000,
}
