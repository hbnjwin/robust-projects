import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题 */
    title?: string
    /** 是否使用 keep-alive 缓存，默认 false */
    keepAlive?: boolean
    /** 图标名称 */
    icon?: string
  }
}
