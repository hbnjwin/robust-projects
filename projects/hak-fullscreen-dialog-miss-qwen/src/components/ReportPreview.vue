<template>
  <div :id="FULLSCREEN_CONTAINER_ID" ref="containerRef" class="report-preview">
    <!-- Toolbar -->
    <div class="toolbar">
      <h2 class="toolbar__title">风电场月度运行报告 — 预览</h2>
      <div class="toolbar__actions">
        <el-button type="primary" @click="openAnnotationDialog">
          添加批注
        </el-button>
        <el-button type="success" @click="handleSubmitReview">
          提交审核
        </el-button>
        <el-button @click="toggleFullscreen">
          <el-icon>
            <FullScreen v-if="!isFullscreen" />
            <Close v-else />
          </el-icon>
          {{ isFullscreen ? '退出全屏' : '全屏阅读' }}
        </el-button>
      </div>
    </div>

    <!-- Report body -->
    <div class="report-body">
      <h3>一、发电量统计</h3>
      <p>本月风电场总发电量为 1,250 万千瓦时，同比增长 8.3%。</p>
      <h3>二、设备运行状态</h3>
      <p>全场 48 台风机中，47 台正常运行，1 台因齿轮箱故障停机检修。</p>
      <h3>三、安全生产</h3>
      <p>本月无安全事故发生，安全生产天数累计 365 天。</p>
    </div>

    <!--
      Fix #1: el-dialog
      By default el-dialog teleports its DOM to document.body. When a
      child div (not body) is in fullscreen, body descendants are NOT
      rendered in the fullscreen layer. We use :append-to to mount the
      dialog inside the fullscreen container during fullscreen mode.
    -->
    <el-dialog
      v-model="annotationDialogVisible"
      title="添加批注"
      width="500px"
      :append-to="getAppendTo()"
    >
      <el-form :model="annotationForm">
        <el-form-item label="批注位置">
          <el-select v-model="annotationForm.section" placeholder="选择章节">
            <el-option label="一、发电量统计" value="section1" />
            <el-option label="二、设备运行状态" value="section2" />
            <el-option label="三、安全生产" value="section3" />
          </el-select>
        </el-form-item>
        <el-form-item label="批注内容">
          <el-input
            v-model="annotationForm.content"
            type="textarea"
            :rows="4"
            placeholder="请输入批注内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="annotationDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveAnnotation">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessageBox, ElNotification } from 'element-plus'
import { FullScreen, Close } from '@element-plus/icons-vue'
import { useFullscreen } from '@/composables/useFullscreen'

const containerRef = ref<HTMLElement>()

const {
  isFullscreen,
  toggleFullscreen,
  getAppendTo,
  FULLSCREEN_CONTAINER_ID,
} = useFullscreen(containerRef)

// --- Annotation dialog ---
const annotationDialogVisible = ref(false)
const annotationForm = reactive({
  section: '',
  content: '',
})

function openAnnotationDialog() {
  annotationForm.section = ''
  annotationForm.content = ''
  annotationDialogVisible.value = true
}

function saveAnnotation() {
  annotationDialogVisible.value = false

  // Fix #2b: ElNotification — mount inside fullscreen container
  ElNotification({
    title: '批注已保存',
    message: `已为「${annotationForm.section}」添加批注`,
    type: 'success',
    appendTo: getAppendTo(),
  })
}

// --- Submit review ---
function handleSubmitReview() {
  // Fix #2a: ElMessageBox — mount inside fullscreen container
  ElMessageBox.confirm(
    '确认提交本报告进行审核？提交后将无法修改。',
    '提交确认',
    {
      confirmButtonText: '确认提交',
      cancelButtonText: '取消',
      type: 'warning',
      appendTo: getAppendTo(),
    },
  )
    .then(() => {
      ElNotification({
        title: '提交成功',
        message: '报告已提交审核',
        type: 'success',
        appendTo: getAppendTo(),
      })
    })
    .catch(() => {
      /* user cancelled */
    })
}
</script>

<style scoped>
.report-preview {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;
  background: #f5f7fa;
}

.toolbar__title {
  margin: 0;
  font-size: 18px;
}

.report-body {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  line-height: 1.8;
}
</style>
