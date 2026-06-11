import Cookies from 'js-cookie'
import dayjs from 'dayjs'
const KEY = 'wind-report-review-web'
export default {
	isTokenExpired(minutes = 10) {
		// 过期时间
		const expiredTime = new Date(this.getExpiresAt()).getTime() / 1000
		const nowTime = new Date().getTime() / 1000
		const during = expiredTime - nowTime

		// |----------|-------\---|-----------------------|
		// 开始       set       开刷 到期                    refrestoken 到期
		return during < minutes * 60
	},
	getOauth() {
		try {
			return JSON.parse(Cookies.get(KEY))
		} catch {
			return ''
		}
	},
	// 主要是为了追加到期时间
	setOauth(oauth) {
		let temp = {
			...oauth,
			expires_at: dayjs().add(oauth.expires_in, 'seconds').format('YYYY-MM-DD HH:mm:ss')
		}
		Cookies.set(KEY, JSON.stringify(temp), {expires: oauth.expires_in / 86400})
	},
	getExpiresAt() {
		return this.getOauth().expires_at
	},
	getExpiresIn() {
		return this.getOauth().expires_in
	},
	getAccessToken() {
		return this.getOauth().access_token
	},
	getRefreshToken() {
		return this.getOauth().refresh_token
	},
	remove() {
		Cookies.remove(KEY)
		localStorage.clear()
	}
}
