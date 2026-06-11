import axios from 'axios';
import NProgress from 'nprogress';
import router from '@/router';
import oauth2 from '@/utils/oauth2'
import MESSAGE from './system-msg';

NProgress.configure({ showSpinner: false });

const service = axios.create({
	// baseURL: import.meta.env.VITE_PROXY_URL,
	timeout: 0,
});

const baseReq = ['/api/sysOperator/sms', '/api/sysOperator/verifyUser', '/api/sysOperator/verifyMobilePhoneVerificationCode', '/api/departmentDoc/tree', '/api/employeeDoc/update'];

// 请求拦截器
service.interceptors.request.use((req) => {
	NProgress.start();
	let Authorization = '';
	if (baseReq.includes(req.url)) {
		Authorization = '';
	} else {
		Authorization = 'Bearer ' + oauth2.getAccessToken();
	}
	req.headers['Authorization'] = Authorization;
	return req;
});

// 响应拦截器
service.interceptors.response.use(
	(res) => {
		NProgress.done();
		let responseError = false;
		if (res.request.responseType === 'blob') {
			if (res.headers['content-type'].includes('json')) {
				responseError = true;
				const reader = new FileReader();
				reader.onload = () => {
					const result = JSON.parse(reader.result);
					ElMessage({ message: result.msg, type: 'error' });
				};
				reader.readAsText(res.data);
			}
		} else {
			// if (res.status !== 200 || res.data?.code != 0) {
			if (res.status !== 200) {
				responseError = true;
				ElMessage({ message: res.data.warning || res.data.message || res.data.msg, type: 'error' });
			}
		}

		return responseError ? Promise.reject(res.data) : res;
	},
	(err) => {
		NProgress.done();

		const status = err.response?.status ?? 'Tips';
		let message = Object.keys(MESSAGE).includes(String(status)) ? MESSAGE[status] : MESSAGE.default;
		const resMessage = err.response?.data?.msg;
		if (resMessage) {
			message = resMessage;
		}

		ElMessage({ message: `${status} @ ${message}`, type: 'info' });

		if (status == 401) {
			oauth2.remove('oauth');
			router.push({ name: 'Auth.Send', replace: true });
		}

		return Promise.reject(err);
	},
);

export default service;
