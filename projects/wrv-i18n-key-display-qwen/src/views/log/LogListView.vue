<template>
  <div class="log-list">
    <!-- 搜索栏 -->
    <el-card shadow="hover" class="search-card">
      <el-form :inline="true" :model="searchForm">
        <el-form-item :label="$t('log.operationType')">
          <el-select v-model="searchForm.type" :placeholder="$t('system.common.search')" clearable>
            <el-option :label="$t('log.loginLog')" value="login" />
            <el-option :label="$t('log.operationLog')" value="operation" />
            <el-option :label="$t('log.errorLog')" value="error" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('log.operator')">
          <el-input v-model="searchForm.operator" :placeholder="$t('log.operator')" clearable />
        </el-form-item>
        <el-form-item :label="$t('log.result')">
          <el-select v-model="searchForm.result" :placeholder="$t('system.common.search')" clearable>
            <el-option :label="$t('log.success')" value="success" />
            <el-option :label="$t('log.failed')" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">{{ $t('system.common.search') }}</el-button>
          <el-button @click="handleReset">{{ $t('system.common.reset') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover">
      <el-table :data="tableData" border stripe>
        <el-table-column prop="operator" :label="$t('log.operator')" min-width="100" />
        <el-table-column prop="type" :label="$t('log.operationType')" min-width="110">
          <template #default="{ row }">
            <el-tag>{{ $t(`log.${row.type}`) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" :label="$t('log.operationContent')" min-width="240" />
        <el-table-column prop="ip" :label="$t('log.ipAddress')" min-width="140" />
        <el-table-column :label="$t('log.result')" min-width="90">
          <template #default="{ row }">
            <el-tag :type="row.result === 'success' ? 'success' : 'danger'">
              {{ $t(`log.${row.result}`) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="time" :label="$t('log.operationTime')" min-width="170" />
        <el-table-column :label="$t('system.common.action')" fixed="right" width="100">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="handleDetail(row)">
              {{ $t('log.detail') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          :page-text="$t('system.common.total', { total: pagination.total })"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const { t } = useI18n()

const searchForm = reactive({ type: '', operator: '', result: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 342 })

const tableData = ref([
  { id: 1, operator: 'admin', type: 'loginLog', content: '登录系统', ip: '192.168.1.100', result: 'success', time: '2026-06-10 14:32:15' },
  { id: 2, operator: 'zhangsan', type: 'operationLog', content: '导出用户数据', ip: '192.168.1.101', result: 'success', time: '2026-06-10 13:15:42' },
  { id: 3, operator: 'admin', type: 'operationLog', content: '修改系统设置', ip: '192.168.1.100', result: 'success', time: '2026-06-10 11:48:30' },
  { id: 4, operator: 'unknown', type: 'loginLog', content: '登录失败 - 密码错误', ip: '10.0.0.55', result: 'failed', time: '2026-06-10 09:22:08' },
  { id: 5, operator: 'system', type: 'errorLog', content: '数据库连接超时', ip: '-', result: 'failed', time: '2026-06-10 08:00:01' }
])

function handleSearch() { /* TODO */ }

function handleReset() {
  Object.assign(searchForm, { type: '', operator: '', result: '' })
}

function handleDetail(row) {
  ElMessage.info(t('log.detail'))
}
</script>

<style scoped>
.log-list { display: flex; flex-direction: column; gap: 16px; }
.search-card :deep(.el-form-item) { margin-bottom: 0; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
