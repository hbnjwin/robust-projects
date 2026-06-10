<template>
  <div class="settings-view">
    <el-tabs v-model="activeTab">
      <!-- 基本设置 -->
      <el-tab-pane :label="$t('settings.basicSettings')" name="basic">
        <el-card shadow="hover">
          <el-form :model="basicForm" label-width="140px">
            <el-form-item :label="$t('settings.siteName')">
              <el-input v-model="basicForm.siteName" />
            </el-form-item>
            <el-form-item :label="$t('settings.siteDescription')">
              <el-input v-model="basicForm.siteDescription" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item :label="$t('settings.logo')">
              <el-upload action="#" :auto-upload="false" accept="image/*">
                <el-button>{{ $t('settings.logo') }}</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item :label="$t('settings.copyright')">
              <el-input v-model="basicForm.copyright" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSave">{{ $t('system.common.save') }}</el-button>
              <el-button @click="handleReset">{{ $t('system.common.reset') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 安全设置 -->
      <el-tab-pane :label="$t('settings.securitySettings')" name="security">
        <el-card shadow="hover">
          <el-form :model="securityForm" label-width="180px">
            <el-form-item :label="$t('settings.maxLoginAttempts')">
              <el-input-number v-model="securityForm.maxAttempts" :min="1" :max="10" />
            </el-form-item>
            <el-form-item :label="$t('settings.lockDuration')">
              <el-input-number v-model="securityForm.lockDuration" :min="1" :max="1440" />
            </el-form-item>
            <el-form-item :label="$t('settings.sessionTimeout')">
              <el-input-number v-model="securityForm.sessionTimeout" :min="5" :max="480" />
            </el-form-item>
            <el-form-item :label="$t('settings.passwordPolicy')">
              <el-checkbox v-model="securityForm.requireUppercase">
                {{ $t('user.passwordRule') }}
              </el-checkbox>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSave">{{ $t('system.common.save') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 通知设置 -->
      <el-tab-pane :label="$t('settings.notificationSettings')" name="notification">
        <el-card shadow="hover">
          <el-form :model="notificationForm" label-width="140px">
            <el-form-item :label="$t('settings.emailNotification')">
              <el-switch v-model="notificationForm.emailEnabled" />
            </el-form-item>
            <el-form-item v-if="notificationForm.emailEnabled" :label="$t('settings.smtpServer')">
              <el-input v-model="notificationForm.smtpServer" placeholder="smtp.example.com" />
            </el-form-item>
            <el-form-item v-if="notificationForm.emailEnabled" :label="$t('settings.smtpPort')">
              <el-input-number v-model="notificationForm.smtpPort" :min="1" :max="65535" />
            </el-form-item>
            <el-form-item :label="$t('settings.smsNotification')">
              <el-switch v-model="notificationForm.smsEnabled" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSave">{{ $t('system.common.save') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const { t } = useI18n()

const activeTab = ref('basic')

const basicForm = reactive({
  siteName: 'Admin System',
  siteDescription: '企业后台管理系统',
  copyright: 'Copyright 2026'
})

const securityForm = reactive({
  maxAttempts: 5,
  lockDuration: 30,
  sessionTimeout: 30,
  requireUppercase: true
})

const notificationForm = reactive({
  emailEnabled: true,
  smtpServer: 'smtp.example.com',
  smtpPort: 465,
  smsEnabled: false
})

function handleSave() {
  ElMessage.success(t('system.common.operationSuccess'))
}

function handleReset() {
  ElMessage.success(t('system.common.operationSuccess'))
}
</script>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
