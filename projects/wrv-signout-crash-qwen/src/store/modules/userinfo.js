import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserinfoStore = defineStore('userinfo', () => {
	const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || '{}'))

	function setUserInfo(info) {
		userInfo.value = info
		localStorage.setItem('userInfo', JSON.stringify(info))
	}

	function clearUserInfo() {
		userInfo.value = {}
		localStorage.removeItem('userInfo')
	}

	return {
		userInfo,
		setUserInfo,
		clearUserInfo
	}
})
