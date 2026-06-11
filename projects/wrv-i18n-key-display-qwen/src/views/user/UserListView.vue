<template>
  <div class="user-list">
    <!-- 搜索栏 -->
    <el-card shadow="hover" class="search-card">
      <el-form :inline="true" :model="searchForm">
        <el-form-item :label="$t('user.username')">
          <el-input v-model="searchForm.username" :placeholder="$t('user.username')" clearable />
        </el-form-item>
        <el-form-item :label="$t('user.phone')">
          <el-input v-model="searchForm.phone" :placeholder="$t('user.phone')" clearable />
        </el-form-item>
        <el-form-item :label="$t('user.status')">
          <el-select v-model="searchForm.status" :placeholder="$t('system.common.search')" clearable>
            <el-option :label="$t('user.active')" value="active" />
            <el-option :label="$t('user.inactive')" value="inactive" />
            <el-option :label="$t('user.locked')" value="locked" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">{{ $t('system.common.search') }}</el-button>
          <el-button @click="handleReset">{{ $t('system.common.reset') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 操作按钮 + 表格 -->
    <el-card shadow="hover">
      <div class="toolbar">
        <el-button type="primary" @click="handleAdd">
          {{ $t('system.common.add') }}
        </el-button>
        <el-button type="danger" :disabled="!selectedRows.length" @click="handleBatchDelete">
          {{ $t('system.common.batchDelete') }}
        </el-button>
        <el-button @click="handleExport">{{ $t('system.common.export') }}</el-button>
      </div>

      <el-table :data="tableData" @selection-change="onSelectionChange" border stripe>
        <el-table-column type="selection" width="48" />
        <el-table-column prop="username" :label="$t('user.username')" min-width="120" />
        <el-table-column prop="nickname" :label="$t('user.nickname')" min-width="100" />
        <el-table-column prop="email" :label="$t('user.email')" min-width="180" />
        <el-table-column prop="phone" :label="$t('user.phone')" min-width="130" />
        <el-table-column prop="department" :label="$t('user.department')" min-width="100" />
        <el-table-column prop="role" :label="$t('user.role')" min-width="100" />
        <el-table-column :label="$t('system.common.status')" min-width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">
              {{ $t(`user.${row.status}`) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" :label="$t('system.common.createTime')" min-width="170" />
        <el-table-column :label="$t('system.common.action')" fixed="right" width="200">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="handleEdit(row)">
              {{ $t('system.common.edit') }}
            </el-button>
            <el-button text type="warning" size="small" @click="handleResetPwd(row)">
              {{ $t('user.resetPassword') }}
            </el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">
              {{ $t('system.common.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :page-text="$t('system.common.total', { total: pagination.total })"
        />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? $t('user.editUser') : $t('user.addUser')"
      width="520px"
    >
      <el-form ref="dialogFormRef" :model="dialogForm" :rules="dialogRules" label-width="90px">
        <el-form-item :label="$t('user.username')" prop="username">
          <el-input v-model="dialogForm.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item :label="$t('user.nickname')" prop="nickname">
          <el-input v-model="dialogForm.nickname" />
        </el-form-item>
        <el-form-item :label="$t('user.email')" prop="email">
          <el-input v-model="dialogForm.email" />
        </el-form-item>
        <el-form-item :label="$t('user.phone')" prop="phone">
          <el-input v-model="dialogForm.phone" />
        </el-form-item>
        <el-form-item :label="$t('user.gender')" prop="gender">
          <el-radio-group v-model="dialogForm.gender">
            <el-radio value="male">{{ $t('user.male') }}</el-radio>
            <el-radio value="female">{{ $t('user.female') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="$t('user.department')" prop="department">
          <el-input v-model="dialogForm.department" />
        </el-form-item>
        <el-form-item v-if="!isEdit" :label="$t('system.login.password')" prop="password">
          <el-input v-model="dialogForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item :label="$t('system.common.remark')" prop="remark">
          <el-input v-model="dialogForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ $t('system.common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSubmit">{{ $t('system.common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t } = useI18n()

const searchForm = reactive({ username: '', phone: '', status: '' })
const selectedRows = ref([])
const pagination = reactive({ page: 1, pageSize: 10, total: 86 })

const tableData = ref([
  { id: 1, username: 'admin', nickname: '管理员', email: 'admin@example.com', phone: '13800000001', department: '技术部', role: '超级管理员', status: 'active', createTime: '2026-01-15 10:00:00' },
  { id: 2, username: 'zhangsan', nickname: '张三', email: 'zhangsan@example.com', phone: '13800000002', department: '运营部', role: '运营人员', status: 'active', createTime: '2026-02-20 14:30:00' },
  { id: 3, username: 'lisi', nickname: '李四', email: 'lisi@example.com', phone: '13800000003', department: '产品部', role: '普通用户', status: 'inactive', createTime: '2026-03-10 09:15:00' },
  { id: 4, username: 'wangwu', nickname: '王五', email: 'wangwu@example.com', phone: '13800000004', department: '技术部', role: '管理员', status: 'locked', createTime: '2026-04-05 16:45:00' }
])

function statusTagType(status) {
  return { active: 'success', inactive: 'info', locked: 'danger' }[status] || 'info'
}

function onSelectionChange(rows) {
  selectedRows.value = rows
}

function handleSearch() {
  // TODO: 调用搜索接口
}

function handleReset() {
  Object.assign(searchForm, { username: '', phone: '', status: '' })
}

function handleExport() {
  ElMessage.success(t('system.common.operationSuccess'))
}

// ---------- 对话框逻辑 ----------
const dialogVisible = ref(false)
const isEdit = ref(false)
const dialogFormRef = ref(null)
const dialogForm = reactive({
  username: '', nickname: '', email: '', phone: '', gender: 'male',
  department: '', password: '', remark: ''
})

const dialogRules = reactive({
  username: [
    { required: true, message: () => t('validation.required', { field: t('user.username') }), trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: () => t('user.emailRule'), trigger: 'blur' }
  ]
})

function handleAdd() {
  isEdit.value = false
  resetDialogForm()
  dialogVisible.value = true
}

function handleEdit(row) {
  isEdit.value = true
  Object.assign(dialogForm, row)
  dialogVisible.value = true
}

function resetDialogForm() {
  Object.assign(dialogForm, {
    username: '', nickname: '', email: '', phone: '', gender: 'male',
    department: '', password: '', remark: ''
  })
}

async function handleSubmit() {
  const valid = await dialogFormRef.value?.validate().catch(() => false)
  if (!valid) return
  ElMessage.success(t('system.common.operationSuccess'))
  dialogVisible.value = false
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(t('system.common.confirmDelete'), t('system.common.delete'), {
      confirmButtonText: t('system.common.confirm'),
      cancelButtonText: t('system.common.cancel'),
      type: 'warning'
    })
    ElMessage.success(t('system.common.operationSuccess'))
  } catch {
    // 用户取消
  }
}

async function handleBatchDelete() {
  try {
    await ElMessageBox.confirm(
      t('system.common.confirmBatchDelete', { count: selectedRows.value.length }),
      t('system.common.batchDelete'),
      {
        confirmButtonText: t('system.common.confirm'),
        cancelButtonText: t('system.common.cancel'),
        type: 'warning'
      }
    )
    ElMessage.success(t('system.common.operationSuccess'))
  } catch {
    // 用户取消
  }
}

function handleResetPwd(row) {
  ElMessage.success(t('system.common.operationSuccess'))
}
</script>

<style scoped>
.user-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.search-card :deep(.el-form-item) {
  margin-bottom: 0;
}
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
