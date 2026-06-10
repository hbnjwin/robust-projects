<template>
  <div class="expert-database">
    <div class="filter-bar">
      <t-select v-model="filterParams.docType" placeholder="文档类型" clearable>
        <t-option value="reviewed" label="已审报告" />
        <t-option value="feasibility" label="可研报告" />
        <t-option value="pending" label="待审文档" />
      </t-select>
      <t-input v-model="filterParams.keyword" placeholder="搜索" @enter="fetchList" />
      <t-button @click="handleReset">重置</t-button>
    </div>
    <t-table :data="tableData" :columns="columns" :loading="loading"
      :sort="sortParams" @sort-change="onSortChange" />
    <table-pagination :total="total" :current="pagination.current"
      :pageSize="pagination.pageSize" @change="onPageChange" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { EXPERT_DATABASE } from '@/api'
import TablePagination from '@/components/table-pagination/index.vue'

const filterParams = reactive({ docType: '', keyword: '' })
const sortParams = ref({})
const pagination = reactive({ current: 1, pageSize: 20 })
const tableData = ref([])
const total = ref(0)
const loading = ref(false)
const columns = [
  { colKey: 'name', title: '文档名称', sortable: true },
  { colKey: 'type', title: '类型' },
  { colKey: 'status', title: '状态' },
  { colKey: 'createdAt', title: '上传时间', sortable: true },
]

const fetchList = async () => {
  loading.value = true
  const res = await EXPERT_DATABASE.getDocumentList({
    ...filterParams, ...pagination,
    sortBy: sortParams.value.sortBy, order: sortParams.value.descending ? 'desc' : 'asc'
  })
  tableData.value = res.list
  total.value = res.total
  loading.value = false
}

const onSortChange = (sort) => { sortParams.value = sort; fetchList() }
const onPageChange = (p) => { Object.assign(pagination, p); fetchList() }
const handleReset = () => {
  filterParams.docType = ''
  filterParams.keyword = ''
  fetchList()
}

onMounted(fetchList)
</script>
