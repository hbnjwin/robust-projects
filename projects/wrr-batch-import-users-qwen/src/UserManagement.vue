<template>
  <div>
    <el-table :data="users"><el-table-column prop="name" label="Name" /><el-table-column prop="email" label="Email" /></el-table>
    <el-button @click="showImport = true">Batch Import</el-button>
    <!-- TODO: implement batch import dialog -->
  </div>
</template>

<script>
export default {
  data() { return { users: [], showImport: false }; },
  methods: {
    // TODO: implement Excel parsing and batch import
  },
};
</script>
