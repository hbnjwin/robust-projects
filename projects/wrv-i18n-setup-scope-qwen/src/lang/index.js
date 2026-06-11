import Cookies from 'js-cookie'
import { createI18n, useI18n } from 'vue-i18n'
import { computed } from 'vue'
const langModules = import.meta.glob('./**/*.js', { eager: true })
const messages = {}

for (const [path, modules] of Object.entries(langModules)) {
	const values = Object.values(modules).flat(1)
	const lang = path.split('/')[1]
	messages[lang] = values
}

const LOCALE_COOKIE_NAME = 'lang'

export const languages = [
	{
		value: 'en_US',
		label: 'English(United States)'
	},
	{
		value: 'zh_Hans',
		label: '简体中文'
	}
]

const i18n = createI18n({
	locale: 'zh_Hans',
	legacy: false,
	globalInjection: true,
	fallbackLocale: 'zh_Hans',
	messages
})

export const setLocaleOnClient = (lang, reloadPage = true) => {
	const { locale } = useI18n()
	Cookies.set(LOCALE_COOKIE_NAME, lang)
	locale.value = lang
	reloadPage && location.reload()
}
export const lang = computed(() => {
	const { locale } = useI18n()
	return locale.value
})
export default i18n
