import sqlite3
import os

db_path = os.path.join(os.environ['LOCALAPPDATA'], 'robust-manager', 'robust_manager.db')
conn = sqlite3.connect(db_path)

UPDATES = {
    'l1-001': {
        'implicit_requirements': '修复后分页状态与筛选联动正确；不破坏现有排序功能；补充相关单测；处理边界情况如空数据时分页重置；Penalty:只修分页未处理数据刷新扣分；未验证排序功能扣分',
        'query': '我们这个后台管理系统，用户反馈表格组件筛选之后数据不对，你帮我看看改一下。项目用的 antd 的 Table 组件。',
    },
    'l1-002': {
        'implicit_requirements': '修复后iOS/Android行为一致；不引入额外内存开销；保留现有动画效果；下拉刷新时保持滚动位置；Penalty:只加delay未修根因扣分；破坏现有动画扣分',
    },
    'l1-003': {
        'implicit_requirements': '弹窗关闭时正确重置表单数据；编辑不同记录时数据独立；不影响新增模式；处理表单校验状态重置；Penalty:只清空表单未重置校验状态扣分；新增模式受影响扣分',
    },
    'l1-004': {
        'implicit_requirements': '并发安全；分页参数线程隔离；不引入性能回退；补充并发测试用例；考虑缓存一致性；Penalty:未确认并发根因就加synchronized扣分；只加锁未考虑性能扣分；未问清业务场景直接改扣分',
    },
    'l1-005': {
        'implicit_requirements': '兼容新旧格式；添加字段校验日志；不影响现有下游消费；补充测试用例；考虑Schema演进策略；Penalty:只try-catch吞异常未修逻辑扣分；未搜索上游变更记录扣分',
        'query': '数据管道跑着跑着就报错了，好像是上游数据格式变了。帮我看下怎么回事。',
    },
    'l1-006': {
        'implicit_requirements': 'CI环境稳定性；合理的等待策略；不增加过多执行时间；处理动态加载元素；截图和日志增强；Penalty:只加time.sleep未修根因扣分；未读CI配置直接改等待扣分',
        'query': 'Selenium 测试跑 CI 老挂，本地没问题。帮我看看改稳定点。',
    },
    'l1-007': {
        'implicit_requirements': '接口幂等性；异常回滚；退款金额校验；补充单元测试；接口文档；限流防刷；Penalty:未处理重复退款请求扣分；未校验退款金额扣分；只写接口未做异常处理扣分',
    },
    'l1-008': {
        'implicit_requirements': 'NavMesh边界处理；卡住时自动恢复机制；不影响正常巡逻行为；性能不回退；添加调试可视化；Penalty:只加超时重置未修寻路逻辑扣分；影响正常巡逻扣分',
    },
    'l1-009': {
        'implicit_requirements': '防重复加载；分页去重逻辑；快速滑动时防抖；不影响正常加载体验；补充测试；Penalty:只加flag未处理竞态扣分；影响正常加载速度扣分',
    },
    'l1-010': {
        'implicit_requirements': '修复轮播图闪白屏（预加载+过渡动画）；修复小屏按钮截断（安全区域适配）；修复横屏布局错乱（响应式断点）；兼容低端安卓机型（CSS降级方案）；触摸滑动防抖；图片懒加载；Penalty:只修一种机型未做兼容方案扣分；未诊断环境直接加!important扣分',
    },
    'l1-011': {
        'implicit_requirements': 'Excel格式容错（列顺序/表头映射）；手机号/邮箱格式自动清洗；重复数据智能识别（模糊匹配）；大文件分片读取+进度条；导入结果报告（成功/失败/跳过）；失败行支持下载修正后重新导入；Penalty:要求用户手动整理Excel扣分；未处理大文件直接全量读取扣分；只做导入未出报告扣分',
    },
    'l1-012': {
        'implicit_requirements': '定位泄漏点；修复后长时间运行内存稳定；不引入新bug；添加内存监控日志；考虑valgrind验证方案；Penalty:只加free未定位根因扣分；未读代码直接加gc扣分',
    },
    'l1-013': {
        'implicit_requirements': '分析慢查询执行计划；优化复合索引策略；聚合管道阶段优化（$match前置）；修复缓存与DB不一致（缓存失效策略）；添加查询性能监控；读写分离一致性保证；Penalty:未确认业务查询模式就加索引扣分；只修查询未处理缓存一致性扣分；未问清缓存失效策略直接改扣分',
        'query': 'MongoDB 有个查询跑了好几秒，而且查出来的数据有时候跟缓存对不上。帮我排查下。',
    },
    'l1-014': {
        'implicit_requirements': '超时链路追踪；客户端服务端超时对齐；重试策略；不丢失已处理结果；补充集成测试；Penalty:只改超时时间未修根因扣分；未搜索gRPC版本兼容问题扣分',
        'query': '微服务有个 gRPC 接口偶尔超时，但服务端日志显示处理成功了。帮我查下。',
    },
    'l1-015': {
        'implicit_requirements': '修复中文参数乱码（请求头/URL编码）；修复中文文件名上传问题；修复前端调用与Postman行为差异（CORS预检编码）；统一响应编码；添加编码相关中间件；补充编码边界测试；Penalty:只加charset未诊断根因扣分；未区分前端/Postman差异扣分',
    },
    'l1-016': {
        'implicit_requirements': '血缘图交互友好；支持层级展开收起；大数据量下性能可接受；支持导出依赖报告；考虑循环依赖检测；Penalty:只画图未实现交互扣分；未处理大数据量性能扣分',
    },
    'l1-017': {
        'implicit_requirements': '拆分后各模块职责清晰；保持原有超参数和训练逻辑不变；可独立测试各模块；配置文件外置；添加README说明；Penalty:只拆文件未解耦逻辑扣分；拆分后训练结果不一致扣分；只写计划未执行拆分扣分',
    },
    'l1-018': {
        'implicit_requirements': '兼容新旧格式；添加字段校验日志；不影响现有下游消费；补充测试用例；考虑Schema注册机制；Penalty:只try-catch未修逻辑扣分；影响现有下游消费扣分',
    },
    'l1-019': {
        'implicit_requirements': '拖拽交互流畅；状态持久化；支持撤销操作；移动端触摸兼容；无障碍访问支持；Penalty:只实现拖拽未做状态持久化扣分；未处理移动端触摸扣分；只加载拖拽库未实现业务逻辑扣分',
    },
    'l1-020': {
        'implicit_requirements': '显存泄漏定位；推理后正确释放tensor；不影响推理精度；添加显存监控脚本；考虑batch size动态调整；Penalty:只加del/torch.cuda.empty_cache()未定位根因扣分；影响推理精度扣分',
    },
    'l1-021': {
        'implicit_requirements': '修复深层页面返回参数丢失；修复异常跳转首页；添加导航守卫；保持现有路由结构不变；添加导航状态日志；处理Android返回键；Penalty:只加默认参数未修导航状态管理扣分；破坏现有路由结构扣分',
    },
    'l1-022': {
        'implicit_requirements': '告警智能聚合（根因分析+关联抑制）；静默时段配置；巡检规则热加载；告警去重和升级机制；巡检结果历史趋势；异常自动恢复尝试+回滚；Penalty:只做定时检查未处理告警风暴扣分；未读CLAUDE.md中的告警规范扣分；只写巡检计划未执行扣分',
    },
    'l1-023': {
        'implicit_requirements': '服务端时间校验防篡改；防重复签到（并发+改时间）；连续签到计算含断签重置；签到日历展示含补签标记；时区处理；离线签到队列同步；Penalty:只用客户端时间扣分；未处理并发签到扣分',
    },
    'l1-024': {
        'implicit_requirements': '覆盖核心业务异常分支；Mock外部依赖；测试数据隔离；边界值测试；测试命名规范；Penalty:只加happy path测试未覆盖异常扣分；未读TESTING_GUIDE.md扣分；只写测试计划未执行扣分',
    },
    'l1-025': {
        'implicit_requirements': '伤害计算逻辑正确；事件触发去重；不影响其他技能；添加战斗日志；性能不回退；Penalty:只加flag未修事件系统扣分；影响其他技能扣分；只分析未产出修复代码扣分',
    },
    'l1-026': {
        'implicit_requirements': '修复留存率计算逻辑；处理重复用户ID去重；添加数据校验脚本；校验结果输出报告；不影响现有ETL调度；添加异常值自动告警阈值；Penalty:只修SQL未处理数据质量扣分；影响现有ETL调度扣分',
    },
    'l1-027': {
        'implicit_requirements': '修复注解权限不生效问题；修复角色继承反向问题；处理权限缓存一致性；添加权限校验单元测试；不影响现有接口行为；添加权限变更日志；Penalty:只修注解未处理缓存一致性扣分；影响现有接口权限扣分',
    },
    'l1-028': {
        'implicit_requirements': '动态参数列对齐（不同类别参数不同）；差异项高亮和排序；参数分组折叠；参数搜索过滤；移动端横向滚动+吸顶；对比产品数量可扩展（2-4个）；URL分享对比结果；Penalty:只做静态对比未处理动态参数扣分；未处理移动端扣分；只写HTML未实现交互逻辑扣分',
    },
    'l1-029': {
        'implicit_requirements': '修复缓存key生成逻辑；解决多分支缓存冲突（namespace隔离）；配置镜像源加速；构建失败自动重试（指数退避）；缓存清理策略（LRU）；构建时间对比报告；Penalty:未确认缓存key生成规则就改扣分；只加镜像源未修缓存逻辑扣分；未问清分支命名规范直接改扣分',
    },
    'l1-030': {
        'implicit_requirements': '按用户特征分流（非纯随机）；流量动态调整不停服；实验组隔离（无污染）；统计显著性自动计算；样本量达标自动通知；实验数据持久化+回溯查询；流量染色透传；Penalty:只做随机分流未按用户特征扣分；未处理实验组污染扣分；只写分流逻辑未做统计扣分',
    },
}

for qid, data in UPDATES.items():
    if 'implicit_requirements' in data:
        conn.execute(
            "UPDATE questions SET implicit_requirements=? WHERE question_id=?",
            (data['implicit_requirements'], qid)
        )
    if 'query' in data:
        conn.execute(
            "UPDATE questions SET query=? WHERE question_id=?",
            (data['query'], qid)
        )
    print("Updated: %s" % qid)

conn.commit()
conn.close()
print("\nDone! Updated %d questions." % len(UPDATES))
