import appRequest from '../app-request.js'

export default {
	// 专家库文档相关接口
	getDocumentsList(params) {
		return appRequest.get('/api/documents/list', { params })
	},
	deleteDocument(id) {
		return appRequest.delete(`/api/documents/${id}`)
	}
}
