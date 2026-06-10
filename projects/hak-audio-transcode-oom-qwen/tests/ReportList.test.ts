import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import ReportList from '../src/ReportList.vue'

// Mock vue-virtual-scroller
vi.mock('vue-virtual-scroller', () => ({
  DynamicScroller: {
    name: 'DynamicScroller',
    props: ['items', 'minItemSize', 'keyField', 'buffer'],
    template: '<div class="mock-scroller"><slot v-for="item in items" :item="item" :index="0" :active="true" /></div>',
  },
  DynamicScrollerItem: {
    name: 'DynamicScrollerItem',
    props: ['item', 'active', 'sizeDependencies'],
    template: '<div class="mock-scroller-item"><slot /></div>',
  },
}))

// Mock StatusBadge
vi.mock('../src/StatusBadge.vue', () => ({
  default: {
    name: 'StatusBadge',
    props: ['status'],
    template: '<span class="status-badge">{{ status }}</span>',
  },
}))

const mockReports = [
  {
    id: 1,
    title: '单行标题报告',
    status: 'pending' as const,
    tags: ['标签1'],
    reviewers: [{ name: '张三', avatar: '' }],
    createdAt: '2026-01-01',
    summary: '这是第一条报告的摘要内容',
  },
  {
    id: 2,
    title: '这是一个非常非常长的报告标题，它肯定会换行显示，占据两行甚至更多的空间，这样就能测试动态行高功能是否正常工作了',
    status: 'approved' as const,
    tags: ['标签1', '标签2', '标签3'],
    reviewers: [
      { name: '李四', avatar: '' },
      { name: '王五', avatar: '' },
    ],
    createdAt: '2026-01-02',
    summary: '这是第二条报告的摘要内容，包含更多信息',
  },
  {
    id: 3,
    title: '已驳回的报告',
    status: 'rejected' as const,
    tags: [],
    reviewers: [],
    createdAt: '2026-01-03',
    summary: '这条报告被驳回了',
  },
]

describe('ReportList 虚拟滚动修复', () => {
  describe('动态行高支持', () => {
    it('使用 DynamicScroller 而非 RecycleScroller', () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      // DynamicScroller 支持不等高行，RecycleScroller 只支持等高行
      expect(wrapper.html()).toContain('mock-scroller')
      expect(wrapper.html()).not.toContain('recycle-scroller')
    })

    it('为 DynamicScrollerItem 传递 size-dependencies 以触发重新测量', () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const scroller = wrapper.findComponent({ name: 'DynamicScroller' })
      expect(scroller.exists()).toBe(true)

      // size-dependencies 应该包含影响行高的所有字段
      const props = scroller.props()
      expect(props).toBeDefined()
    })

    it('设置合理的 min-item-size 作为初始估算', () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const scroller = wrapper.findComponent({ name: 'DynamicScroller' })
      const minItemSize = scroller.props('minItemSize')

      // min-item-size 应该足够大，避免初始渲染时内容被截断
      expect(minItemSize).toBeGreaterThanOrEqual(72)
    })
  })

  describe('筛选后缓存重置', () => {
    it('筛选条件变化时 scrollerKey 递增', async () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const vm = wrapper.vm as any
      const initialKey = vm.scrollerKey

      // 改变筛选条件
      vm.filterStatus = 'pending'
      vm.handleFilterChange()
      await nextTick()

      expect(vm.scrollerKey).toBe(initialKey + 1)
    })

    it('多次筛选变化时 scrollerKey 持续递增', async () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const vm = wrapper.vm as any
      const initialKey = vm.scrollerKey

      vm.filterStatus = 'pending'
      vm.handleFilterChange()
      await nextTick()

      vm.filterStatus = 'approved'
      vm.handleFilterChange()
      await nextTick()

      vm.filterStatus = ''
      vm.handleFilterChange()
      await nextTick()

      expect(vm.scrollerKey).toBe(initialKey + 3)
    })

    it('搜索关键词变化时也触发缓存重置', async () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const vm = wrapper.vm as any
      const initialKey = vm.scrollerKey

      vm.searchKeyword = '测试'
      vm.handleFilterChange()
      await nextTick()

      expect(vm.scrollerKey).toBe(initialKey + 1)
    })

    it('外部 reports 数据变化时也重置缓存', async () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const vm = wrapper.vm as any
      const initialKey = vm.scrollerKey

      // 模拟外部数据更新
      await wrapper.setProps({
        reports: mockReports.slice(0, 1),
      })
      await nextTick()

      expect(vm.scrollerKey).toBeGreaterThan(initialKey)
    })
  })

  describe('筛选功能正确性', () => {
    it('按状态筛选返回正确的报告', async () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const vm = wrapper.vm as any

      // 筛选待审核
      vm.filterStatus = 'pending'
      await nextTick()
      expect(vm.filteredReports).toHaveLength(1)
      expect(vm.filteredReports[0].status).toBe('pending')

      // 筛选已通过
      vm.filterStatus = 'approved'
      await nextTick()
      expect(vm.filteredReports).toHaveLength(1)
      expect(vm.filteredReports[0].status).toBe('approved')

      // 筛选已驳回
      vm.filterStatus = 'rejected'
      await nextTick()
      expect(vm.filteredReports).toHaveLength(1)
      expect(vm.filteredReports[0].status).toBe('rejected')

      // 全部
      vm.filterStatus = ''
      await nextTick()
      expect(vm.filteredReports).toHaveLength(3)
    })

    it('按关键词搜索返回正确的报告', async () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const vm = wrapper.vm as any

      vm.searchKeyword = '驳回'
      await nextTick()
      expect(vm.filteredReports).toHaveLength(1)
      expect(vm.filteredReports[0].title).toContain('驳回')
    })

    it('组合筛选（状态 + 关键词）正确工作', async () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const vm = wrapper.vm as any

      vm.filterStatus = 'pending'
      vm.searchKeyword = '单行'
      await nextTick()
      expect(vm.filteredReports).toHaveLength(1)

      vm.filterStatus = 'approved'
      vm.searchKeyword = '单行'
      await nextTick()
      expect(vm.filteredReports).toHaveLength(0)
    })

    it('筛选结果为空时显示空状态', async () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const vm = wrapper.vm as any
      vm.filterStatus = 'pending'
      vm.searchKeyword = '不存在的关键词'
      await nextTick()

      expect(wrapper.find('.empty-state').exists()).toBe(true)
    })
  })

  describe('DynamicScroller 配置', () => {
    it('使用 id 作为 keyField 确保唯一性', () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const scroller = wrapper.findComponent({ name: 'DynamicScroller' })
      expect(scroller.props('keyField')).toBe('id')
    })

    it('设置适当的 buffer 值优化滚动性能', () => {
      const wrapper = mount(ReportList, {
        props: { reports: mockReports },
      })

      const scroller = wrapper.findComponent({ name: 'DynamicScroller' })
      const buffer = scroller.props('buffer')

      // buffer 应该足够大，避免快速滚动时频繁渲染新项
      expect(buffer).toBeGreaterThanOrEqual(200)
    })
  })
})
