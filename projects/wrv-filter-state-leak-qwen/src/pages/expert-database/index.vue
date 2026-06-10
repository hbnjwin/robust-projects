<template>
  <div class="expert-database">
    <div class="filter-bar">
      <!--
        filterDraft 绑定到 UI，@change 立即提交筛选。
        select 是离散选择，用户期望立即刷新表格。
      -->
      <t-select
        v-model="filterDraft.docType"
        placeholder="文档类型"
        clearable
        @change="commitFilters"
      >
        <t-option value="reviewed" label="已审报告" />
        <t-option value="feasibility" label="可研报告" />
        <t-option value="pending" label="待审文档" />
      </t-select>

      <!--
        keyword 输入框 @enter 提交，避免逐字触发请求。
      -->
      <t-input
        v-model="filterDraft.keyword"
        placeholder="搜索"
        @enter="commitFilters"
      />

      <t-button @click="resetAll">重置</t-button>
    </div>

    <t-table
      :data="tableData"
      :columns="columns"
      :loading="loading"
      :sort="sort"
      @sort-change="onSortChange"
    />

    <table-pagination
      :total="total"
      :current="pagination.current"
      :pageSize="pagination.pageSize"
      @change="onPageChange"
    />
  </div>
</template>

<script setup>
import { onMounted, onActivated } from 'vue'
import { EXPERT_DATABASE } from '@/api'
import TablePagination from '@/components/table-pagination/index.vue'
import { useTableState } from '@/composables/useTableState'

const columns = [
  { colKey: 'name', title: '文档名称', sortable: true },
  { colKey: 'type', title: '类型' },
  { colKey: 'status', title: '状态' },
  { colKey: 'createdAt', title: '上传时间', sortable: true },
]

const {
  filterDraft,
  sort,
  pagination,
  tableData,
  total,
  loading,
  commitFilters,
  fetchData,
  onSortChange,
  onPageChange,
  resetAll,
} = useTableState(
  (params) => EXPERT_DATABASE.getDocumentList(params),
  {
    defaultFilters: { docType: '', keyword: '' },
    sortableFields: ['name', 'createdAt'],
    defaultPageSize: 20,
  }
)

// 首次挂载时获取数据
onMounted(fetchData)

// keep-alive 重新激活时重新获取数据。
// 这是修复 Bug #1 和 Bug #3 的关键：
// 没有这个钩子，切走再切回时表格数据会保持旧值，
// 而 Vue 可能已经重置了 v-model 绑定，导致 UI 与数据不一致。
onActivated(fetchData)
</script>
