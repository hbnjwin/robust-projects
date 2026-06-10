import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import en from './en'

/**
 * 获取所有叶子 key（用于开发环境下检测缺失翻译）
 */
function getFlatKeys(obj, prefix = '') {
  return Object.entries(obj).reduce((keys, [k, v]) => {
    const fullKey = prefix ? `${prefix}.${k}` : k
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      keys.push(...getFlatKeys(v, fullKey))
    } else {
      keys.push(fullKey)
    }
    return keys
  }, [])
}

const zhKeys = getFlatKeys(zhCN)
const enKeys = getFlatKeys(en)

// 启动时检查中英文 key 是否完全对齐，方便开发阶段发现问题
if (import.meta.env?.DEV) {
  const zhSet = new Set(zhKeys)
  const enSet = new Set(enKeys)
  const missingInEn = zhKeys.filter(k => !enSet.has(k))
  const missingInZh = enKeys.filter(k => !zhSet.has(k))
  if (missingInEn.length) {
    console.warn('[i18n] Keys missing in en.js:', missingInEn)
  }
  if (missingInZh.length) {
    console.warn('[i18n] Keys missing in zh-CN.js:', missingInZh)
  }
}

const i18n = createI18n({
  locale: localStorage.getItem('lang') || 'zh-CN',
  fallbackLocale: 'zh-CN',
  legacy: false,           // Vue 3 Composition API 模式
  silentTranslationWarn: import.meta.env?.PROD, // 生产环境静默，开发环境仍输出警告
  missingWarn: import.meta.env?.DEV,
  fallbackWarn: import.meta.env?.DEV,
  messages: {
    'zh-CN': zhCN,
    en
  }
})

/**
 * 运行时切换语言，同时持久化到 localStorage
 */
export function setLocale(locale) {
  i18n.global.locale.value = locale
  localStorage.setItem('lang', locale)
  document.querySelector('html').setAttribute('lang', locale)
}

export function getLocale() {
  return i18n.global.locale.value
}

export default i18n
