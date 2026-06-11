export default {
	/* 合法uri*/
	URL(textval) {
		const reg =
			/^(https?|ftp):\/\/([a-zA-Z0-9.-]+(:[a-zA-Z0-9.&%$-]+)*@)*((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}|([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))(:[0-9]+)*(\/($|[a-zA-Z0-9.,?'\\+&%$#=~_-]+))*$/
		return reg.test(textval)
	},

	/* 小写字母*/
	lowerCase(str) {
		const reg = /^[a-z]+$/
		return reg.test(str)
	},

	/* 大写字母*/
	upperCase(str) {
		const reg = /^[A-Z]+$/
		return reg.test(str)
	},

	/**
	 * validate phone
	 * @param phone
	 * @returns {boolean}
	 */
	phone(phone) {
		const reg = /^(0|86|17951)?(13[0-9]|15[012356789]|166|17[3678]|18[0-9]|14[57])[0-9]{8}$/
		return reg.test(phone)
	},

	/**
	 * validate email
	 * @param email
	 * @returns {boolean}
	 */
	email(email) {
		const reg = /\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*/
		return reg.test(email)
	},

	/**
	 * validate ip
	 * @param ip
	 * @returns {boolean}
	 */
	IP(ip) {
		let reg =
			/^(\d{1,2}|1\d\d|2[0-4]\d|25[0-5])\.(\d{1,2}|1\d\d|2[0-4]\d|25[0-5])\.(\d{1,2}|1\d\d|2[0-4]\d|25[0-5])\.(\d{1,2}|1\d\d|2[0-4]\d|25[0-5])$/
		return reg.test(ip)
	},

	/**
	 * validate port
	 * @param {*} port
	 * @returns {boolean}
	 */
	port(port) {
		let reg = /^(\d)+$/g
		return reg.test(port) && parseInt(port) <= 65535 && parseInt(port) >= 0
	},

	/**
	 * validate password
	 * @param {*} password
	 * @returns {boolean}
	 */
	password(password) {
		// 大写, 小写, 数字, 特殊字符(4选3)
		let reg = /^(?![a-zA-Z]+$)(?![A-Z0-9]+$)(?![A-Z\W_]+$)(?![a-z0-9]+$)(?![a-z\W_]+$)(?![0-9\W_]+$)^[^\s\u4e00-\u9fa5]{8,16}$/
		return reg.test(password)
	},
	account(account) {
		let reg = /^[a-zA-Z][a-zA-Z0-9_]{5,16}$/
		return reg.test(account)
	}
}
