import axios from 'axios'
import NProgress from 'nprogress'
import router from '@/router'
import oauth2 from '@/utils/oauth2'

NProgress.configure({ showSpinner: false })

const service = axios.create({
	timeout: 0
})

const baseReq = [
	'/api/sysOperator/sms',
	'/api/sysOperator/verifyUser',
	'/api/sysOperator/verifyMobilePhoneVerificationCode'
]

service.interceptors.request.use((req) => {
	NProgress.start()
	if (!baseReq.includes(req.url)) {
		const accessToken = oauth2.getAccessToken()
		if (accessToken) {
			req.headers['Authorization'] = 'Bearer ' + accessToken
		}
	}
	return req
})

service.interceptors.response.use(
	(res) => {
		NProgress.done()
		if (res.status !== 200) {
			return Promise.reject(res.data)
		}
		return res
	},
	(err) => {
		NProgress.done()
		const status = err.response?.status
		if (status == 401) {
			oauth2.remove('oauth')
			router.push({ name: 'Auth.Send', replace: true })
		}
		return Promise.reject(err)
	}
)

export default service
