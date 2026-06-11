import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import en from './en'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'en',
  missingWarn: false,
  fallbackWarn: false,
  messages: { 'zh-CN': zhCN, en }
})

export default i18n
