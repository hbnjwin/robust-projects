<template>
  <div class="user-list">
    <el-form :model="queryParams" inline>
      <el-form-item label="状态">
        <el-select v-model="queryParams.status" clearable @change="handleQuery">
          <el-option label="正常" :value="0" />
          <el-option label="禁用" :value="1" />
        </el-select>
      </el-form-item>
      <el-form-item label="用户名">
        <el-input v-model="queryParams.username" clearable @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleQuery">搜索</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading">
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="nickname" label="昵称" />
      <el-table-column prop="status" label="状态" />
    </el-table>

    <el-pagination
      v-model:current-page="queryParams.pageNo"
      :page-size="queryParams.pageSize"
      :total="total"
      @current-change="getList"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onActivated } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const router = useRouter()

const queryParams = reactive({
  status: undefined as number | undefined,
  username: '',
  pageNo: 1,
  pageSize: 20
})

const tableData = ref<any[]>([])
const total = ref(0)
const loading = ref(false)

const getList = async () => {
  loading.value = true
  try {
    const { data } = await axios.get('/api/system/user/page', { params: queryParams })
    tableData.value = data.data.list
    total.value = data.data.total
  } finally {
    loading.value = false
  }
}

/** 从 URL query 参数恢复 queryParams（URL 为唯一数据源） */
const syncQueryFromUrl = () => {
  const query = route.query
  queryParams.status = query.status !== undefined ? Number(query.status) : undefined
  queryParams.username = (query.username as string) || ''
  queryParams.pageNo = query.pageNo ? Number(query.pageNo) : 1
  queryParams.pageSize = query.pageSize ? Number(query.pageSize) : 20
}

/** 将当前 queryParams 同步写入 URL（replace 模式，避免过多历史记录） */
const pushQueryToUrl = () => {
  const query: Record<string, any> = {}
  if (queryParams.status !== undefined) query.status = queryParams.status
  if (queryParams.username) query.username = queryParams.username
  if (queryParams.pageNo !== 1) query.pageNo = queryParams.pageNo
  if (queryParams.pageSize !== 20) query.pageSize = queryParams.pageSize
  router.replace({ query })
}

const handleQuery = () => {
  queryParams.pageNo = 1
  pushQueryToUrl()
  getList()
}

const resetQuery = () => {
  queryParams.status = undefined
  queryParams.username = ''
  queryParams.pageNo = 1
  pushQueryToUrl()
  getList()
}

// FIX: keep-alive 重新激活时，先从 URL 恢复 queryParams，再获取数据
// 确保筛选表单和表格数据始终一致
onActivated(() => {
  syncQueryFromUrl()
  getList()
})

// 初始加载：从 URL 恢复参数后获取数据
syncQueryFromUrl()
getList()
</script>
