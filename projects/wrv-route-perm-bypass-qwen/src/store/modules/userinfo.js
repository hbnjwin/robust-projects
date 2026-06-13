export const useUserinfoStore = defineStore(
	'userinfo',
	() => {
		const userInfo = ref({})

		/**
		 * 判断用户是否拥有指定权限
		 * @param {string} auth - 路由配置中定义的权限标识（如 'System'、'Rulebase' 等）
		 * @returns {boolean}
		 */
		const hasPermission = (auth) => {
			if (!auth) return true
			const roles = userInfo.value?.roles
			if (!Array.isArray(roles)) return false
			return roles.includes(auth)
		}

		return { userInfo, hasPermission }
	},
	{ persist: true }
)
