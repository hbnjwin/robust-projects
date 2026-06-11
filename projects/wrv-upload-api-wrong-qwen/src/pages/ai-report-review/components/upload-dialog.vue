<template>
	<t-dialog
		:visible="dialog.visible"
		@update:visible="(val) => dialog.visible = val"
		header="报告上传"
		width="700px"
		:confirm-btn="null"
		:cancel-btn="null"
		class="custom-t-dialog"
		:closeOnOverlayClick="false"
	>
		<t-form ref="formRef" :data="dialog.form" layout="inline" class="search-form" label-width="120px" @reset="handleClose">
			<!-- <t-form-item label="文档类型：" name="docType" style="width: 100%">
				<t-select v-model="dialog.form.docType" clearable>
					<t-option v-for="item in docTypeOptions" :key="item.value" :value="item.value" :label="item.label"></t-option>
				</t-select>
			</t-form-item> -->
			<t-form-item label="报告上传：" style="width: 100%">
				<t-upload
					class="warahouse-upload"
					:files="dialog.form.filesList ? [dialog.form.filesList] : []"
					action=""
					theme="custom"
					:multiple="false"
					draggable
					:show-image-file-name="true"
					accept=".pdf,.docx,.xlsx,.doc"
					showUploadProgress
					autoUpload
					:on-select-change="handleUpload"
				>
					<template #default>
						<div flex-center flex-col>
							<img src="@/assets/image/data-upload/拖拽文件.png" alt="" />
							<div class="flex-align mt-12px">
								<span color="#1D2129">将文件拖拽到这里或</span>
								<span color="#165DFF" cursor-pointer>点击上传</span>
							</div>
							<div color="#4E5969" text="12px" mt-5px>支持DOCX、DOC、PDF、XLSX，每个文件不超过 100 MB。</div>
						</div>
					</template>
				</t-upload>
			</t-form-item>
			<t-form-item label="已传文件：" style="width: 100%">
				<div class="files flex-between" v-if="dialog.form.filesList">
					<div flex-start>
						<img :src="fileTypeToImage[dialog.form.filesList?.name.split('.').pop()]" style="width: 26px" alt="" />
						<div style="width: 400px" class="ellipsis m-l-8px" :title="dialog.form.filesList?.name">{{ dialog.form.filesList?.name }}</div>
					</div>
					<t-button shape="circle" variant="text">
						<i class="iconfont icon-guanbi" text="16px" @click="dialog.form.filesList = null"></i>
					</t-button>
				</div>
			</t-form-item>
		</t-form>
		<template #footer>
			<t-space>
				<t-button theme="default" @click="handleClose">取消</t-button>
				<t-button theme="primary" :loading="dialog.loading" @click="handleSubmit">保存</t-button>
			</t-space>
		</template>
	</t-dialog>
</template>
<script setup>
import { MessagePlugin } from 'tdesign-vue-next'
import { AI_REPORT_REVIEW } from '@/api'
import doc from '@/assets/image/data-upload/doc.png'
import jpg from '@/assets/image/data-upload/jpg.png'
import docx from '@/assets/image/data-upload/docx.png'
import pdf from '@/assets/image/data-upload/pdf.png'
import png from '@/assets/image/data-upload/png.png'
import xls from '@/assets/image/data-upload/xls.png'

const fileTypeToImage = { doc, jpg, docx, pdf, png, xls }

// const docTypeOptions = ref([
// 	{ label: '已审核', value: 0 },
// 	{ label: '待审核', value: 1 },
// 	{ label: '可研报告', value: 2 }
// ])
const dialog = reactive({
	visible: false,
	loading: false,
	form: {
		docType: 1,
		filesList: null
	}
})

const formRef = ref(null)
const handleClose = () => {
	formRef.value.clearValidate()
	dialog.visible = false
	dialog.loading = false
}

const emit = defineEmits(['success'])
const handleSubmit = () => {
	// if (dialog.form.docType === null) return MessagePlugin.warning('请选择文档类型')
	if (!dialog.form.filesList) return MessagePlugin.warning('请选择上传文件')
	dialog.loading = true
	const fd = new FormData()
	fd.append('file', dialog.form.filesList.raw)
	fd.append('docType', dialog.form.docType)
	AI_REPORT_REVIEW.postDocumentsUploadFile(fd)
		.then(({ data }) => {
			MessagePlugin.success(data.msg)
			handleClose()
			emit('success')
		})
		.catch((err) => {
			console.log(err)
			dialog.loading = false
		})
}

const handleUpload = (files, select) => {
	console.log(files, select)
	if (select.currentSelectedFiles[0].size > 100 * 1024 * 1024) return MessagePlugin.warning('文件大小不能超过100MB')
	dialog.form.filesList = select.currentSelectedFiles[0]
}

const show = () => {
	dialog.visible = true
}
defineExpose({ show })
</script>

<style lang="less" scoped>
:deep(.t-dialog__header-content) {
	font-size: 16px !important;
}
.warahouse-upload {
	width: 100%;
	:deep(.t-upload__dragger) {
		width: 100%;
		height: 190px;
		border-radius: 4px;
		background-clip: padding-box, border-box;
		background-origin: padding-box, border-box;
		border: 1px 1 transparent;
		background-image: linear-gradient(to right, #f8fbff, #f8fbff),
			linear-gradient(90deg, rgba(22, 93, 255, 1), rgba(59, 208, 255, 1), rgba(98, 146, 255, 1));
	}
}
.files {
	width: 100%;
	height: 50px;
	border: 1px solid #dcdfe6;
	border-radius: 4px;
	padding: 0 12px;
}
</style>
