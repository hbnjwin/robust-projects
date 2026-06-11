import type { App, Directive, DirectiveBinding } from 'vue'
import { usePermissionStoreWithOut } from '@/store/modules/permission'

function checkPermi(el: HTMLElement, binding: DirectiveBinding) {
  const { value } = binding
  const permissionStore = usePermissionStoreWithOut()
  const allPermission = '*:*:*'
  const permissions = permissionStore.getPermissions

  if (value && value instanceof Array && value.length > 0) {
    const hasPermission = permissions.some((p: string) => {
      return allPermission === p || value.includes(p)
    })

    if (!hasPermission) {
      // BUG: 在 mounted 钩子中通过 removeChild 移除元素
      // 但在 v-for 场景下，Vue 会复用 DOM 元素（通过 key diff）
      // 当列表更新时，已被移除的元素不会被重新创建
      // 而且 removeChild 后如果列表重新渲染，Vue 找不到这个 DOM 节点会报错
      el.parentNode?.removeChild(el)
    }
  }
}

export const hasPermi: Directive = {
  // BUG: 只在 mounted 时检查权限
  // v-for 中如果列表数据更新，Vue 可能复用 DOM 元素但绑定不同的数据
  // mounted 不会再次触发，导致权限检查不会重新执行
  // 应该同时在 updated 钩子中重新检查
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    checkPermi(el, binding)
  }
  // BUG: 缺少 updated 钩子
  // updated(el, binding) { checkPermi(el, binding) }
}

export function setupPermissionDirective(app: App) {
  app.directive('hasPermi', hasPermi)
}
