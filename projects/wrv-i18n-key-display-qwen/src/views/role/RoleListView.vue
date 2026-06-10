<template>
  <div class="role-list">
    <el-card shadow="hover">
      <div class="toolbar">
        <el-button type="primary" @click="handleAdd">{{ $t('system.common.add') }}</el-button>
      </div>

      <el-table :data="tableData" border stripe>
        <el-table-column prop="roleName" :label="$t('role.roleName')" min-width="140" />
        <el-table-column prop="roleCode" :label="$t('role.roleCode')" min-width="140" />
        <el-table-column prop="description" :label="$t('role.description')" min-width="200" />
        <el-table-column prop="createTime" :label="$t('system.common.createTime')" min-width="170" />
        <el-table-column :label="$t('system.common.action')" fixed="right" width="220">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="handleEdit(row)">
              {{ $t('system.common.edit') }}
            </el-button>
            <el-button text type="warning" size="small" @click="handlePermission(row)">
              {{ $t('role.assignPermission') }}
            </el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">
              {{ $t('system.common.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 权限配置抽屉 -->
    <el-drawer v-model="drawerVisible" :title="$t('role.assignPermission')" size="420px">
      <el-tree
        ref="treeRef"
        :data="permissionTree"
        show-checkbox
        node-key="id"
        :default-checked-keys="checkedKeys"
        :props="{ label: 'label', children: 'children' }"
      />
      <template #footer>
        <el-button @click="drawerVisible = false">{{ $t('system.common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSavePermission">{{ $t('system.common.save') }}</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t } = useI18n()

const tableData = ref([
  { id: 1, roleName: '超级管理员', roleCode: 'SUPER_ADMIN', description: '拥有系统所有权限', createTime: '2026-01-01 00:00:00' },
  { id: 2, roleName: '管理员', roleCode: 'ADMIN', description: '系统管理权限', createTime: '2026-01-01 00:00:00' },
  { id: 3, roleName: '运营人员', roleCode: 'OPERATOR', description: '运营相关功能权限', createTime: '2026-01-15 10:00:00' },
  { id: 4, roleName: '普通用户', roleCode: 'VIEWER', description: '基础查看权限', createTime: '2026-01-15 10:00:00' }
])

const drawerVisible = ref(false)
const treeRef = ref(null)
const checkedKeys = ref([1, 2])

const permissionTree = ref([
  {
    id: 1, label: '首页', children: [
      { id: 11, label: '查看数据概览' },
      { id: 12, label: '导出报表' }
    ]
  },
  {
    id: 2, label: '用户管理', children: [
      { id: 21, label: '查看列表' },
      { id: 22, label: '新增用户' },
      { id: 23, label: '编辑用户' },
      { id: 24, label: '删除用户' }
    ]
  },
  {
    id: 3, label: '角色管理', children: [
      { id: 31, label: '查看列表' },
      { id: 32, label: '新增角色' },
      { id: 33, label: '分配权限' }
    ]
  }
])

function handleAdd() {
  ElMessage.info(t('system.common.add'))
}

function handleEdit(row) {
  ElMessage.info(t('system.common.edit'))
}

function handlePermission(row) {
  drawerVisible.value = true
}

function handleSavePermission() {
  ElMessage.success(t('system.common.operationSuccess'))
  drawerVisible.value = false
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
</script>

<style scoped>
.role-list { display: flex; flex-direction: column; gap: 16px; }
.toolbar { display: flex; gap: 8px; margin-bottom: 16px; }
</style>
