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
import axios from 'axios'

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

const handleQuery = () => {
  queryParams.pageNo = 1
  getList()
}

const resetQuery = () => {
  queryParams.status = undefined
  queryParams.username = ''
  queryParams.pageNo = 1
  getList()
}

// BUG: keep-alive 组件被重新激活时，表单 queryParams 被 Vue 的响应式系统恢复
// 但如果用户在其他标签页通过 URL 参数修改了筛选条件
// 或者表单被 resetQuery 重置了但没有重新获取数据
// 导致表单显示的筛选条件和实际展示的数据不一致
onActivated(() => {
  // BUG: 这里只重新获取数据，但没有从 URL query 参数恢复 queryParams
  // 用户看到的筛选表单是 keep-alive 缓存的旧状态
  // 但 getList 用的是被 resetQuery 修改后的 queryParams
  // 表格数据刷新了但表单显示的是旧的筛选条件
  getList()
})

// 初始加载
getList()
</script>
