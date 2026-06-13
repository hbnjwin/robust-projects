"""绘制量化系统架构流程图"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager

# 加载中文字体
_zh_font = font_manager.FontProperties(fname='/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf')
matplotlib.rcParams['font.family'] = _zh_font.get_name()
font_manager.fontManager.addfont('/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf')
matplotlib.rcParams['font.sans-serif'] = [_zh_font.get_name()] + matplotlib.rcParams['font.sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(1, 1, figsize=(22, 28))
ax.set_xlim(0, 22)
ax.set_ylim(0, 28)
ax.axis('off')
fig.patch.set_facecolor('#FAFBFC')

# 颜色定义
C_SCHED = '#E3F2FD'    # 调度层 - 浅蓝
C_STRAT = '#E8F5E9'    # 策略层 - 浅绿
C_VNPY  = '#FFF3E0'    # vnpy 引擎 - 浅橙
C_GW    = '#F3E5F5'    # Gateway - 浅紫
C_DB    = '#FFEBEE'    # 数据库 - 浅红
C_NOTIFY= '#E0F7FA'   # 通知层 - 浅青
C_RISK  = '#FCE4EC'    # 风控 - 浅粉
C_BORDER= '#455A64'
C_ARROW = '#37474F'
C_TEXT  = '#212121'
C_TITLE = '#FFFFFF'
C_TITLE_BG = '#1565C0'

def draw_box(x, y, w, h, color, label, fontsize=10, bold=False, border_color=C_BORDER, alpha=0.9):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                          facecolor=color, edgecolor=border_color, linewidth=1.5, alpha=alpha)
    ax.add_patch(box)
    weight = 'bold' if bold else 'normal'
    ax.text(x + w/2, y + h/2, label, ha='center', va='center',
            fontsize=fontsize, color=C_TEXT, fontweight=weight, wrap=True,
            fontfamily='sans-serif')

def draw_title_box(x, y, w, h, color, label, fontsize=12):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                          facecolor=color, edgecolor=color, linewidth=2)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, label, ha='center', va='center',
            fontsize=fontsize, color=C_TITLE, fontweight='bold', fontfamily='sans-serif')

def draw_arrow(x1, y1, x2, y2, color=C_ARROW, style='->', lw=1.5):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw))

def draw_dashed_arrow(x1, y1, x2, y2, color='#9E9E9E'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=1.2, linestyle='dashed'))

def draw_label(x, y, text, fontsize=8, color='#616161'):
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize, color=color,
            fontstyle='italic', fontfamily='sans-serif')

# ═══════════════════════════════════════════
# 标题
# ═══════════════════════════════════════════
draw_title_box(1, 26.8, 20, 0.8, C_TITLE_BG, '量化交易系统架构全景图 — Multi-Strategy v1.0 + vnpy 4.3.0', 14)

# ═══════════════════════════════════════════
# 第一层：OpenClaw Cron 调度层
# ═══════════════════════════════════════════
draw_title_box(1, 26.0, 20, 0.5, '#1976D2', '① 调度层 — OpenClaw Cron Gateway 原生调度器', 11)

# 交易时段任务链
draw_box(1.2, 24.6, 3.0, 1.2, C_SCHED,
         '12:00 midday_sync\n数据同步(午间)', 9, True)
draw_box(4.5, 24.6, 3.0, 1.2, C_SCHED,
         '15:10 afternoon_sync\n数据同步(收盘)', 9, True)
draw_box(7.8, 24.6, 3.0, 1.2, C_SCHED,
         '15:15 build_factor\n因子构建', 9, True)
draw_box(11.1, 24.6, 3.0, 1.2, C_SCHED,
         '15:20 signal_generate\n信号生成', 9, True)
draw_box(14.4, 24.6, 3.2, 1.2, C_SCHED,
         '15:25 paper_trading\nvnpy 模拟盘执行', 9, True)
draw_box(17.9, 24.6, 2.8, 1.2, C_SCHED,
         '22:05 daily_report\n每日报告生成', 9, True)

# 箭头：依赖链
draw_arrow(4.2, 25.2, 4.5, 25.2)
draw_arrow(7.5, 25.2, 7.8, 25.2)
draw_arrow(10.8, 25.2, 11.1, 25.2)
draw_arrow(14.1, 25.2, 14.4, 25.2)

# 独立任务
draw_box(1.2, 23.5, 3.5, 0.8, '#BBDEFB',
         '21:00 daily_stability | 22:00 stability_monitor', 8)
draw_box(5.0, 23.5, 3.0, 0.8, '#BBDEFB',
         '23:30 event_batch\n场景回测', 8)

draw_label(11, 23.85, '每个任务执行后 → 飞书 DM + AgentMail 双通道通知', 9, '#1565C0')

# ═══════════════════════════════════════════
# 第二层：策略信号层
# ═══════════════════════════════════════════
draw_title_box(1, 22.5, 20, 0.5, '#2E7D32', '② 策略信号层 — signal_generator_v1.py', 11)

draw_box(1.5, 20.8, 4.0, 1.4, C_STRAT,
         'TrendStrategyV2\n趋势动量策略\nMA20/MA60 交叉确认\n动量排序选股', 9, True)
draw_box(6.0, 20.8, 4.0, 1.4, C_STRAT,
         'LowVolStrategy\n低波动策略\n自适应止损\n波动率排序选股', 9, True)
draw_box(10.5, 20.8, 3.5, 1.4, C_STRAT,
         'RegimeDetectorV2\n市场状态检测\nBULL/NEUTRAL/CRISIS\n危机时过滤买入信号', 9, True)
draw_box(14.5, 20.8, 6.0, 1.4, '#C8E6C9',
         'JSON 信号输出\n{\n  "trend_signals": [{action,ts_code,weight}],\n  "lowvol_signals": [{action,ts_code}],\n  "regime": "NEUTRAL"\n}', 8)

draw_arrow(5.5, 21.5, 6.0, 21.5)
draw_arrow(10.0, 21.5, 10.5, 21.5)
draw_arrow(14.0, 21.5, 14.5, 21.5)

# ═══════════════════════════════════════════
# 第三层：vnpy 信号桥接
# ═══════════════════════════════════════════
draw_title_box(1, 20.0, 20, 0.5, '#E65100', '③ 信号桥接层 — signal_bridge.py', 11)

draw_box(3, 18.6, 5.5, 1.1, '#FFE0B2',
         'SignalBridge\n信号格式转换\n{action,ts_code,weight} → OrderRequest\nweight → 手数计算(向下取整到100股)', 9, True)
draw_box(9.5, 18.6, 5.0, 1.1, '#FFE0B2',
         'ts_code 转换\n000001.SZ → symbol=000001\nexchange=Exchange.SZSE\n买卖分离(先卖后买)', 9, True)
draw_box(15.5, 18.6, 5.0, 1.1, '#FFE0B2',
         '下单前风控检查\ncheck_order_allowed()\n单股权重 ≤ 15%\n冷却期检查', 9, True)

draw_arrow(8.5, 19.15, 9.5, 19.15)
draw_arrow(14.5, 19.15, 15.5, 19.15)

# ═══════════════════════════════════════════
# 第四层：vnpy 核心引擎
# ═══════════════════════════════════════════
draw_title_box(1, 17.8, 20, 0.5, '#BF360C', '④ vnpy 核心引擎 — MainEngine + EventEngine', 11)

# Gateway 区域
draw_box(1.2, 15.2, 6.0, 2.3, C_GW,
         '', 9, border_color='#7B1FA2')
draw_title_box(1.4, 17.0, 5.6, 0.35, '#7B1FA2', 'Gateway 行情层（可插拔替换）', 9)

draw_box(1.5, 15.4, 5.4, 0.7, '#E1BEE7',
         '🟢 PgDailyGateway\nPostgreSQL 日线 → TickData | 2900+ 合约', 8, True)
draw_box(1.5, 16.2, 5.4, 0.7, '#E1BEE7',
         '🟢 TxRealtimeGateway\n腾讯HTTP实时行情 | 五档盘口 | 3s轮询', 8, True)

# PaperEngine
draw_box(7.8, 15.4, 5.5, 2.0, C_VNPY,
         'PaperEngine\n(vnpy_paperaccount)\n\n• 模拟撮合引擎\n• 限价单触价成交\n• 即时撮合模式\n• 持仓自动维护\n• 冻结/解冻管理', 9, True, border_color='#E65100')

# RiskMonitor
draw_box(13.8, 15.4, 6.8, 2.0, C_RISK,
         'RiskMonitor\n(风控引擎 + PG 持久化)\n\n• 最大回撤 25% → 暂停交易\n• 单日亏损 5% → 告警\n• 持仓上限 30 只 → 告警\n• 手续费 0.03% 自动计算\n• 实时写入 PostgreSQL', 9, True, border_color='#C62828')

# 事件流箭头
draw_arrow(6.0, 16.0, 7.8, 16.0, '#7B1FA2', '->', 2)
draw_label(7.0, 16.3, 'TickData', 8, '#7B1FA2')

draw_arrow(13.3, 16.0, 13.8, 16.0, '#E65100', '->', 2)
draw_label(13.5, 16.3, 'Trade/Position\nEvent', 8, '#E65100')

# QMT 未来
draw_dashed_arrow(3.5, 15.2, 3.5, 14.6)
draw_box(1.5, 14.0, 5.4, 0.5, '#F5F5F5',
         '⏳ QMT Gateway（未来实盘 — 招商证券）', 8, border_color='#BDBDBD')

# ═══════════════════════════════════════════
# 第五层：数据持久化层
# ═══════════════════════════════════════════
draw_title_box(1, 13.0, 20, 0.5, '#B71C1C', '⑤ 数据持久化层 — PostgreSQL', 11)

draw_box(1.2, 11.2, 4.0, 1.5, C_DB,
         'daily_price\n日线行情数据\n\n588万行 | 2900+股票\n2015-2026 全市场', 9, True, border_color='#C62828')
draw_box(5.5, 11.2, 3.8, 1.5, C_DB,
         'vnpy_positions\n实时持仓\n\nts_code | direction\nvolume | price | pnl', 9, True, border_color='#C62828')
draw_box(9.6, 11.2, 3.8, 1.5, C_DB,
         'vnpy_trades\n交易流水\n\ntradeid | ts_code\nprice | volume | commission', 9, True, border_color='#C62828')
draw_box(13.7, 11.2, 3.5, 1.5, C_DB,
         'vnpy_snapshots\n每日快照\n\ntotal_equity | cash\nmax_drawdown | regime', 9, True, border_color='#C62828')
draw_box(17.5, 11.2, 3.0, 1.5, C_DB,
         'watchlist\n自选池\n\n27只 | in_position\ncategory | note', 9, True, border_color='#C62828')

# 箭头：RiskMonitor → PG
draw_arrow(16, 15.4, 16, 13.0, '#C62828', '->', 2)
draw_arrow(10, 15.4, 10, 13.0, '#C62828', '->', 2)

# ═══════════════════════════════════════════
# 第六层：通知层
# ═══════════════════════════════════════════
draw_title_box(1, 10.2, 20, 0.5, '#00695C', '⑥ 通知与告警层', 11)

draw_box(2, 8.8, 5.5, 1.1, C_NOTIFY,
         '飞书 DM\nOpenClaw Cron announce\n每个任务执行结果自动推送\n风控告警即时通知', 9, True, border_color='#00695C')
draw_box(8.5, 8.8, 5.5, 1.1, C_NOTIFY,
         'AgentMail\n58625255@qq.com\n每日执行摘要邮件\n每日报告全文推送', 9, True, border_color='#00695C')
draw_box(15, 8.8, 5.5, 1.1, C_NOTIFY,
         '风控告警\nRiskMonitor.on_alert()\n回撤/亏损触发 → 飞书+邮件\n暂停交易 + 人工介入', 9, True, border_color='#C62828')

# ═══════════════════════════════════════════
# 第七层：数据流说明
# ═══════════════════════════════════════════
draw_title_box(1, 7.8, 20, 0.5, '#37474F', '⑦ 核心数据流', 11)

# T+1 日线模拟盘流程
draw_box(1.2, 5.8, 19.3, 1.7, '#ECEFF1', '', 9, border_color='#607D8B')
ax.text(2, 7.2, 'T+1 日线模拟盘（每日 15:25 自动运行）', fontsize=10, fontweight='bold', color='#37474F')

flow_y = 6.3
boxes_t1 = [
    (1.5, 'Cron\n触发', '#BBDEFB'),
    (4.0, 'signal_gen\n生成信号', '#C8E6C9'),
    (6.5, 'SignalBridge\n格式转换', '#FFE0B2'),
    (9.0, 'PgDaily\n推送行情', '#E1BEE7'),
    (11.5, 'PaperEngine\n模拟撮合', '#FFE0B2'),
    (14.0, 'RiskMonitor\n风控+持久化', '#FCE4EC'),
    (16.5, 'PG写入\n快照+流水', '#FFCDD2'),
    (19.0, '通知\n飞书+邮件', '#B2EBF2'),
]
for i, (x, label, color) in enumerate(boxes_t1):
    draw_box(x, flow_y, 2.2, 0.8, color, label, 8, True)
    if i < len(boxes_t1) - 1:
        draw_arrow(x + 2.2, flow_y + 0.4, boxes_t1[i+1][0], flow_y + 0.4, '#455A64', '->', 1.5)

# 盘中实时模拟流程
draw_box(1.2, 3.8, 19.3, 1.7, '#ECEFF1', '', 9, border_color='#607D8B')
ax.text(2, 5.2, '盘中实时模拟（交易时段 9:30-15:00）', fontsize=10, fontweight='bold', color='#37474F')

flow_y2 = 4.3
boxes_rt = [
    (1.5, 'Cron\n9:25启动', '#BBDEFB'),
    (4.0, 'TxRealtime\n订阅行情', '#E1BEE7'),
    (6.5, '3s轮询\n腾讯HTTP', '#E1BEE7'),
    (9.0, 'TickData\n五档盘口', '#E1BEE7'),
    (11.5, 'PaperEngine\n即时撮合', '#FFE0B2'),
    (14.0, 'RiskMonitor\n实时风控', '#FCE4EC'),
    (16.5, 'PG写入\n实时同步', '#FFCDD2'),
    (19.0, '告警\n触发通知', '#B2EBF2'),
]
for i, (x, label, color) in enumerate(boxes_rt):
    draw_box(x, flow_y2, 2.2, 0.8, color, label, 8, True)
    if i < len(boxes_rt) - 1:
        draw_arrow(x + 2.2, flow_y2 + 0.4, boxes_rt[i+1][0], flow_y2 + 0.4, '#455A64', '->', 1.5)

# ═══════════════════════════════════════════
# 底部：技术栈和版本信息
# ═══════════════════════════════════════════
draw_box(1, 1.5, 20, 2.0, '#ECEFF1', '', 9, border_color='#90A4AE')
ax.text(11, 3.2, '技术栈与版本信息', fontsize=11, fontweight='bold', color='#37474F', ha='center')

tech_info = (
    'Python 3.11.2  |  vnpy 4.3.0  |  vnpy_paperaccount 1.0.6  |  vnpy_ctastrategy 1.4.1\n'
    'PostgreSQL (daily_price 588万行)  |  AKShare (数据源)  |  腾讯HTTP行情 (实时)\n'
    'OpenClaw Gateway (调度+通知)  |  AgentMail (邮件)  |  飞书 (IM通知)\n'
    '系统成熟度: ≈ 90%  |  Phase 3 (QMT Gateway) 待招商证券接口'
)
ax.text(11, 2.2, tech_info, fontsize=9, color='#546E7A', ha='center', va='center',
        fontfamily='sans-serif', linespacing=1.6)

# 保存
plt.tight_layout()
plt.savefig('/home/tulin/docs/quant_system_architecture_2026-03-15.png',
            dpi=150, bbox_inches='tight', facecolor='#FAFBFC')
plt.close()
print('Done')
