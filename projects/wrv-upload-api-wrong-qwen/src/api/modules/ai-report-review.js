import appRequest from '../app-request.js'

export default {
	// 任务列表相关接口
	getTasksList(params) {
		return appRequest.get('/api/tasks/list', { params })
	},
	getTaskDetail(taskId) {
		return appRequest.get('/api/tasks/listDetail', { params: { id: taskId } })
	},

	// 任务执行相关接口
	executeCheckTask(taskId) {
		return appRequest.post('/api/tasks/executeCheckTask', null, { params: { taskId } })
	},
	executeEnhanceCheckTask(taskId) {
		return appRequest.post('/api/tasks/executeEnhanceCheckTask', null, { params: { taskId } })
	},
	queryTask(taskId, forceRefresh = false) {
		return appRequest.get('/api/tasks/queryTask', { params: { taskId, forceRefresh } })
	},

	// 工作流历史记录
	getWorkflowHistory(taskId, taskType = 'check') {
		return appRequest.get('/api/tasks/workflowHistory', { params: { taskId, taskType } })
	},

	// 任务进度相关接口 - 这些路径是正确的，因为TaskProgressController使用了完整的/api前缀
	getTaskProgress(taskType, taskId) {
		return appRequest.get(`/api/task-progress/${taskType}/${taskId}`)
	},
	getTaskInfo(taskType, taskId) {
		return appRequest.get(`/api/task-progress/${taskType}/${taskId}/info`)
	},
	getActiveTasks() {
		return appRequest.get('/api/task-progress/active')
	},

	// 报告上传相关接口
	postDocumentsUploadFile(params) {
		return appRequest.post('/api/documents/uploadFile', params)
	}
}
