export const useUserinfoStore = defineStore(
	'userinfo',
	() => {
		const userInfo = ref({})
		return { userInfo }
	},
	{ persist: true }
)
