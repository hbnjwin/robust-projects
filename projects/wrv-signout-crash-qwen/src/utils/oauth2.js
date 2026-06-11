const TOKEN_KEY = 'wind_report_token'

const oauth2 = {
	getOauth() {
		return localStorage.getItem(TOKEN_KEY)
	},
	setOauth(token) {
		localStorage.setItem(TOKEN_KEY, token)
	},
	removeOauth() {
		localStorage.removeItem(TOKEN_KEY)
	}
}

export default oauth2
