import appRequest from '../app-request.js';

export default {
	getCode(params) {
		return appRequest.get('/api/sysOperator/sms', { params });
	},
	getVerifyUser(data) {
		return appRequest.post('/api/sysOperator/verifyUser', data);
	},
	getVerifyMobilePhoneVerificationCode(params) {
		return appRequest.get('/api/sysOperator/verifyMobilePhoneVerificationCode', { params });
	},
};
