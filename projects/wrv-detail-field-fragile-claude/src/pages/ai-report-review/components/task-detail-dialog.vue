<template>
	<t-dialog
		:visible="visible"
		header="任务详情"
		width="800px"
		:footer="false"
		@close="handleClose"
		@update:visible="visible = $event"
	>
		<div v-if="taskDetail" class="task-detail-content">
			<!-- 基本信息 -->
			<div class="detail-section">
				<h3>基本信息</h3>
				<div class="info-grid">
					<div class="info-item">
						<label>任务标题：</label>
						<span>{{ taskDetail.title || '未知任务' }}</span>
					</div>
					<div class="info-item">
						<label>任务状态：</label>
						<t-tag :theme="getStatusTheme(taskDetail.status)">
							{{ getStatusText(taskDetail.status) }}
						</t-tag>
					</div>
					<div class="info-item">
						<label>任务类型：</label>
						<span>{{ taskDetail.taskType || 'check' }}</span>
					</div>
					<div class="info-item">
						<label>任务ID：</label>
						<span>{{ taskDetail.id || '无' }}</span>
					</div>
					<div class="info-item">
						<label>创建时间：</label>
						<span>{{ taskDetail.createdAt || '未知' }}</span>
					</div>
					<div class="info-item">
						<label>更新时间：</label>
						<span>{{ taskDetail.updatedAt || '未知' }}</span>
					</div>
					<div class="info-item">
						<label>检查项数量：</label>
						<span>{{ taskDetail.tasksCheckItemsList ? taskDetail.tasksCheckItemsList.length : 0 }}项</span>
					</div>
				</div>

				<!-- 检查结果统计 -->
				<div v-if="checkResultSummary" class="result-summary">
					<h4>检查结果统计</h4>
					<div class="summary-grid">
						<div class="summary-item">
							<label>总项目数：</label>
							<span>{{ checkResultSummary.totalItems }}项</span>
						</div>
						<div class="summary-item">
							<label>通过项目：</label>
							<span class="passed">{{ checkResultSummary.passedItems }}项</span>
						</div>
						<div class="summary-item">
							<label>警告项目：</label>
							<span class="warning">{{ checkResultSummary.warningItems }}项</span>
						</div>
						<div class="summary-item">
							<label>失败项目：</label>
							<span class="failed">{{ checkResultSummary.failedItems }}项</span>
						</div>
					</div>
				</div>
			</div>

			<!-- 检查项目列表 -->
			<div class="detail-section">
				<h3>检查项目</h3>
				<div class="check-items-container">
					<t-table
						v-if="checkItems.length > 0"
						:data="checkItems"
						:columns="checkItemColumns"
						row-key="id"
						size="small"
						:pagination="false"
						max-height="300px"
						stripe
						hover
					>
					</t-table>
					<div v-else class="no-check-items">
						<div class="empty-content">
							<p>暂无检查项目数据</p>
						</div>
					</div>
				</div>
			</div>

			<!-- 任务描述 -->
			<div class="detail-section" v-if="taskDetail.description">
				<h3>任务描述</h3>
				<p>{{ taskDetail.description }}</p>
			</div>

			<!-- 检查结果总结 -->
			<div class="detail-section" v-if="taskDetail.result">
				<h3>检查结果总结</h3>
				<div class="result-content">
					<pre>{{ taskDetail.result }}</pre>
				</div>
			</div>

			<!-- 错误信息 -->
			<div class="detail-section" v-if="taskDetail.errorMessage">
				<h3>错误信息</h3>
				<div class="error-content">
					<p class="error-text">{{ taskDetail.errorMessage }}</p>
				</div>
			</div>
		</div>

		<div v-else class="loading-content">
			<t-loading size="large" text="加载中..." />
		</div>
	</t-dialog>
</template>

<script setup>
import { ref, computed, defineEmits, defineExpose } from 'vue'

const emit = defineEmits(['close'])

const visible = ref(false)
const taskDetail = ref(null)

// 检查项目表格列定义
const checkItemColumns = [
	{
		colKey: 'itemName',
		title: '检查项目',
		width: 200,
		align: 'left'
	},
	{
		colKey: 'status',
		title: '检查状态',
		width: 120,
		align: 'center',
		cell: (h, { row }) => {
			const theme = getCheckStatusTheme(row.status)
			const text = getCheckStatusText(row.status)
			return h('t-tag', { theme, size: 'small' }, text)
		}
	},
	{
		colKey: 'description',
		title: '问题描述',
		align: 'left',
		ellipsis: true
	}
]

// 检查结果统计信息
const checkResultSummary = computed(() => {
	const checkResultList = taskDetail.value?.checkResultList
	if (!checkResultList || checkResultList.length === 0) {
		return null
	}
	return checkResultList[0] // 使用第一个检查结果的统计信息
})

// 检查项目数据
const checkItems = computed(() => {
	// 使用正确的字段名：tasksCheckItemsList
	const items = taskDetail.value?.tasksCheckItemsList ||
				  taskDetail.value?.taskCheckItemsList ||
				  taskDetail.value?.checkItems ||
				  taskDetail.value?.checkItemsList || []

	if (!items || items.length === 0) {
		return []
	}

	return items.map((item, index) => ({
		id: item.id || item.taskId || index,
		itemName: item.checkItemName || item.itemName || `检查项目 ${index + 1}`,
		status: item.status || 'pending',
		description: item.extractedContent || item.description || item.errorMessage || item.remark || `检查项ID: ${item.checkItemId || item.id}`
	}))
})


// 显示弹窗
const show = (detail) => {
	console.log('详情数据完整结构:', detail)
	console.log('detail的所有键:', Object.keys(detail || {}))
	console.log('tasksCheckItemsList:', detail?.tasksCheckItemsList)
	console.log('tasksCheckItemsList长度:', detail?.tasksCheckItemsList?.length)
	console.log('tasksCheckItemsList内容:', detail?.tasksCheckItemsList)

	taskDetail.value = detail
	console.log('设置后的taskDetail.value:', taskDetail.value)
	console.log('设置后的taskDetail.value.tasksCheckItemsList:', taskDetail.value?.tasksCheckItemsList)
	console.log('checkItems计算结果:', checkItems.value)
	visible.value = true
}

// 关闭弹窗
const handleClose = () => {
	visible.value = false
	taskDetail.value = null
	emit('close')
}

// 获取状态主题色
const getStatusTheme = (status) => {
	switch (status) {
		case 'queued':
			return 'warning'
		case 'started':
			return 'primary'
		case 'completed':
			return 'success'
		case 'failed':
			return 'danger'
		default:
			return 'default'
	}
}

// 获取状态文本
const getStatusText = (status) => {
	switch (status) {
		case 'queued':
			return '排队中'
		case 'started':
			return '执行中'
		case 'completed':
			return '已完成'
		case 'failed':
			return '失败'
		default:
			return '未知'
	}
}


// 获取检查项目状态主题色
const getCheckStatusTheme = (status) => {
	switch (status) {
		case 'pending':
			return 'warning'
		case 'checking':
			return 'primary'
		case 'passed':
			return 'success'
		case 'succeeded':
			return 'success'
		case 'failed':
			return 'danger'
		default:
			return 'default'
	}
}

// 获取检查项目状态文本
const getCheckStatusText = (status) => {
	switch (status) {
		case 'pending':
			return '待检查'
		case 'checking':
			return '检查中'
		case 'passed':
			return '通过'
		case 'succeeded':
			return '成功'
		case 'failed':
			return '不通过'
		default:
			return '未知'
	}
}

defineExpose({
	show,
	handleClose
})
</script>

<style lang="less" scoped>
.task-detail-content {
	.detail-section {
		margin-bottom: 24px;

		h3 {
			margin: 0 0 16px 0;
			font-size: 16px;
			font-weight: 600;
			color: #1f2937;
			border-bottom: 1px solid #e5e7eb;
			padding-bottom: 8px;
		}

		.info-grid {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 16px;

			.info-item {
				display: flex;
				align-items: center;

				label {
					font-weight: 500;
					color: #6b7280;
					min-width: 80px;
					margin-right: 8px;
				}

				span {
					color: #1f2937;
				}
			}
		}

		.result-content {
			background-color: #f9fafb;
			border: 1px solid #e5e7eb;
			border-radius: 6px;
			padding: 16px;

			pre {
				margin: 0;
				white-space: pre-wrap;
				word-break: break-word;
				font-family: 'Courier New', monospace;
				font-size: 14px;
				line-height: 1.5;
			}
		}

		.error-content {
			background-color: #fef2f2;
			border: 1px solid #fecaca;
			border-radius: 6px;
			padding: 16px;

			.error-text {
				margin: 0;
				color: #dc2626;
				font-size: 14px;
				line-height: 1.5;
			}
		}

		.result-summary {
			margin-top: 16px;
			padding: 16px;
			background-color: #f8f9fa;
			border-radius: 8px;
			border: 1px solid #e9ecef;

			h4 {
				margin: 0 0 12px 0;
				font-size: 14px;
				font-weight: 600;
				color: #495057;
			}

			.summary-grid {
				display: grid;
				grid-template-columns: 1fr 1fr;
				gap: 12px;

				.summary-item {
					display: flex;
					align-items: center;

					label {
						font-weight: 500;
						color: #6c757d;
						min-width: 80px;
						margin-right: 8px;
						font-size: 13px;
					}

					span {
						font-weight: 600;
						font-size: 13px;

						&.passed {
							color: #28a745;
						}

						&.warning {
							color: #ffc107;
						}

						&.failed {
							color: #dc3545;
						}
					}
				}
			}
		}

		p {
			margin: 0;
			color: #1f2937;
			line-height: 1.6;
		}

		.check-items-container {
			.no-check-items {
				padding: 40px 0;
				text-align: center;
				background-color: #fafafa;
				border-radius: 6px;
			}
		}
	}
}

.loading-content {
	display: flex;
	justify-content: center;
	align-items: center;
	height: 200px;
}
</style>
