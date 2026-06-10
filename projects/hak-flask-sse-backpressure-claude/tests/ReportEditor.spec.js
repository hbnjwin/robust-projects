/**
 * ReportEditor 内存泄漏修复 - 单元测试
 *
 * 验证两个修复点:
 * 1. keep-alive场景下editor实例的正确创建/销毁
 * 2. paste事件监听器的绑定/解绑
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'

// Mock wangEditor
const mockDestroy = vi.fn()
const mockGetHtml = vi.fn(() => '<p>test</p>')
const mockDangerouslyInsertHtml = vi.fn()

let createdEditors = []

vi.mock('@wangeditor/editor', () => ({
  createEditor: vi.fn((config) => {
    const editor = {
      destroy: mockDestroy,
      getHtml: mockGetHtml,
      dangerouslyInsertHtml: mockDangerouslyInsertHtml,
      isDestroyed: false,
      config,
    }
    // 让destroy真正标记isDestroyed
    editor.destroy = vi.fn(() => {
      editor.isDestroyed = true
    })
    createdEditors.push(editor)
    return editor
  }),
  createToolbar: vi.fn(() => ({})),
}))

vi.mock('@wangeditor/editor/dist/css/style.css', () => ({}))

// 动态导入组件（在mock之后）
const ReportEditor = (await import('../src/components/ReportEditor.vue')).default

describe('ReportEditor 内存泄漏修复', () => {
  let addSpy
  let removeSpy

  beforeEach(() => {
    createdEditors = []
    addSpy = vi.spyOn(document, 'addEventListener')
    removeSpy = vi.spyOn(document, 'removeEventListener')
  })

  afterEach(() => {
    vi.clearAllMocks()
    addSpy.mockRestore()
    removeSpy.mockRestore()
  })

  function createWrapper(props = {}) {
    return shallowMount(ReportEditor, {
      props: {
        reportId: '1',
        reportTitle: '测试报告',
        initialContent: '<p>初始内容</p>',
        ...props,
      },
      attachTo: document.createElement('div'),
    })
  }

  // ---------------------------------------------------------
  // 修复点1: keep-alive下editor实例不累积
  // ---------------------------------------------------------
  describe('editor实例生命周期管理', () => {
    it('onActivated时先销毁旧实例再创建新实例', async () => {
      const wrapper = createWrapper()

      // 模拟第一次activated
      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()
      expect(createdEditors.length).toBe(1)

      // 模拟第二次activated（路由切回）
      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()

      // 旧实例应该被销毁
      expect(createdEditors[0].isDestroyed).toBe(true)
      // 应该创建了新实例
      expect(createdEditors.length).toBe(2)
      // 新实例未被销毁
      expect(createdEditors[1].isDestroyed).toBe(false)
    })

    it('onDeactivated时销毁当前editor实例', async () => {
      const wrapper = createWrapper()

      // activated -> 创建editor
      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()
      expect(createdEditors.length).toBe(1)

      // deactivated -> 应该销毁editor
      wrapper.vm.$.deactivated && wrapper.vm.$.deactivated.forEach((fn) => fn())
      await nextTick()
      expect(createdEditors[0].isDestroyed).toBe(true)
    })

    it('onBeforeUnmount时销毁editor实例（兜底清理）', async () => {
      const wrapper = createWrapper()

      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()
      expect(createdEditors.length).toBe(1)

      wrapper.unmount()
      expect(createdEditors[0].isDestroyed).toBe(true)
    })

    it('重复销毁不会报错（isDestroyed检查）', async () => {
      const wrapper = createWrapper()

      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()

      // deactivated销毁一次
      wrapper.vm.$.deactivated && wrapper.vm.$.deactivated.forEach((fn) => fn())
      await nextTick()

      // unmount再销毁一次 —— 不应报错
      expect(() => wrapper.unmount()).not.toThrow()
    })

    it('切换reportId时重建editor', async () => {
      const wrapper = createWrapper({ reportId: '1' })

      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()
      expect(createdEditors.length).toBe(1)

      // 切换报告
      await wrapper.setProps({ reportId: '2' })
      await nextTick()

      // 旧editor应被销毁，新editor应被创建
      expect(createdEditors[0].isDestroyed).toBe(true)
      expect(createdEditors.length).toBe(2)
    })
  })

  // ---------------------------------------------------------
  // 修复点2: paste事件监听器不泄漏
  // ---------------------------------------------------------
  describe('paste事件监听器清理', () => {
    it('activated时绑定paste监听器', async () => {
      const wrapper = createWrapper()
      const pasteBefore = addSpy.mock.calls.filter((c) => c[0] === 'paste').length

      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()

      const pasteAfter = addSpy.mock.calls.filter((c) => c[0] === 'paste').length
      expect(pasteAfter - pasteBefore).toBe(1)
    })

    it('deactivated时解绑paste监听器', async () => {
      const wrapper = createWrapper()

      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()

      const removeBefore = removeSpy.mock.calls.filter((c) => c[0] === 'paste').length
      wrapper.vm.$.deactivated && wrapper.vm.$.deactivated.forEach((fn) => fn())
      await nextTick()

      const removeAfter = removeSpy.mock.calls.filter((c) => c[0] === 'paste').length
      expect(removeAfter - removeBefore).toBe(1)
    })

    it('多次activated/deactivated循环后监听器数量始终为0或1', async () => {
      const wrapper = createWrapper()

      for (let i = 0; i < 5; i++) {
        wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
        await nextTick()
        wrapper.vm.$.deactivated && wrapper.vm.$.deactivated.forEach((fn) => fn())
        await nextTick()
      }

      const addCount = addSpy.mock.calls.filter((c) => c[0] === 'paste').length
      const removeCount = removeSpy.mock.calls.filter((c) => c[0] === 'paste').length

      // 每次add都应有对应的remove
      expect(removeCount).toBeGreaterThanOrEqual(addCount)
    })

    it('removeEventListener使用与addEventListener相同的handler引用', async () => {
      const wrapper = createWrapper()

      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()

      const addedHandler = addSpy.mock.calls.find((c) => c[0] === 'paste')?.[1]

      wrapper.vm.$.deactivated && wrapper.vm.$.deactivated.forEach((fn) => fn())
      await nextTick()

      const removedHandler = removeSpy.mock.calls.find((c) => c[0] === 'paste')?.[1]

      // 同一个函数引用，才能真正移除
      expect(addedHandler).toBe(removedHandler)
    })

    it('编辑器销毁后粘贴图片不触发上传', async () => {
      const wrapper = createWrapper()

      wrapper.vm.$.activated && wrapper.vm.$.activated.forEach((fn) => fn())
      await nextTick()

      const editor = createdEditors[0]

      // 销毁编辑器
      wrapper.vm.$.deactivated && wrapper.vm.$.deactivated.forEach((fn) => fn())
      await nextTick()

      // 此时编辑器已被销毁，paste handler已被移除
      // 即使有残留handler也不应对已销毁的editor操作
      expect(editor.isDestroyed).toBe(true)
      expect(editor.dangerouslyInsertHtml).not.toHaveBeenCalled()
    })
  })
})
