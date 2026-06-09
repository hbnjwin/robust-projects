<template>
  <el-dialog :visible.sync="visible" title="Edit" @close="handleClose">
    <el-form :model="form" ref="editForm">
      <el-form-item label="Name"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="Email"><el-input v-model="form.email" /></el-form-item>
      <el-form-item label="Status"><el-select v-model="form.status"><el-option label="Active" value="active" /><el-option label="Inactive" value="inactive" /></el-select></el-form-item>
    </el-form>
    <span slot="footer"><el-button @click="visible = false">Cancel</el-button><el-button type="primary" @click="handleSubmit">Save</el-button></span>
  </el-dialog>
</template>

<script>
export default {
  data() {
    return { visible: false, form: { name: "", email: "", status: "" } };
  },
  methods: {
    open(record) { this.form = { ...record }; this.visible = true; },
    handleClose() { /* BUG: form data not reset on close */ },
    handleSubmit() { this.$emit("save", this.form); this.visible = false; },
  },
};
</script>
