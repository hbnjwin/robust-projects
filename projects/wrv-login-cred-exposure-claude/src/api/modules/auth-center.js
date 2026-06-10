import appRequest from '../app-request.js';

export default {
	getCode(params) {
		return appRequest.get('/api/sysOperator/sms', { params });
	},
	getVerifyUser(params) {
		return appRequest.get('/api/sysOperator/verifyUser', { params });
	},
	getVerifyMobilePhoneVerificationCode(params) {
		return appRequest.get('/api/sysOperator/verifyMobilePhoneVerificationCode', { params });
	},
};
