import { describe, it, expect } from 'vitest'
import {
  sanitizeHtml,
  sanitizeSvg,
  sanitizeMarkdownHtml,
  sanitizeDocxHtml,
  sanitizeByType,
  detectXssVectors,
} from '@/utils/sanitizer'

// ============================================================
// 漏洞1: HTML报告文件中的script标签直接执行
// ============================================================
describe('XSS漏洞1: HTML script标签注入', () => {
  it('应移除<script>标签及其内容', () => {
    const dirty = '<div>正常内容</div><script>alert("xss")</script>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('<script')
    expect(clean).not.toContain('alert')
    expect(clean).toContain('正常内容')
  })

  it('应移除大小写混合的script标签', () => {
    const dirty = '<ScRiPt>alert(1)</ScRiPt>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('<script')
    expect(clean).not.toContain('<ScRiPt')
    expect(clean).not.toContain('alert')
  })

  it('应移除带属性的script标签', () => {
    const dirty = '<script src="https://evil.com/xss.js"></script>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('<script')
    expect(clean).not.toContain('evil.com')
  })

  it('应移除嵌套在其他标签中的script', () => {
    const dirty = '<div><p>文字</p><script>document.cookie</script></div>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('<script')
    expect(clean).toContain('文字')
  })
})

// ============================================================
// 漏洞2: DOCX转HTML后onerror事件属性未过滤
// ============================================================
describe('XSS漏洞2: DOCX转HTML事件属性注入', () => {
  it('应移除img标签的onerror属性', () => {
    const dirty = '<img src="x" onerror="alert(\'xss\')" alt="图片">'
    const clean = sanitizeDocxHtml(dirty)
    expect(clean).not.toContain('onerror')
    expect(clean).not.toContain('alert')
    expect(clean).toContain('alt="图片"')
  })

  it('应移除所有on*事件处理器属性', () => {
    const dirty = '<div onclick="alert(1)" onmouseover="alert(2)">内容</div>'
    const clean = sanitizeDocxHtml(dirty)
    expect(clean).not.toContain('onclick')
    expect(clean).not.toContain('onmouseover')
    expect(clean).toContain('内容')
  })

  it('应移除body/svg的onload属性', () => {
    const dirty = '<body onload="alert(1)"><p>内容</p></body>'
    const clean = sanitizeDocxHtml(dirty)
    expect(clean).not.toContain('onload')
    expect(clean).toContain('内容')
  })

  it('应保留DOCX转换的内联样式', () => {
    const dirty = '<p style="font-size: 14px; color: #333; text-indent: 2em;">正文段落</p>'
    const clean = sanitizeDocxHtml(dirty)
    expect(clean).toContain('style=')
    expect(clean).toContain('正文段落')
  })

  it('应保留DOCX表格结构和样式', () => {
    const dirty = `
      <table style="border-collapse: collapse; width: 100%;">
        <thead>
          <tr><th style="border: 1px solid #000;">标题1</th><th>标题2</th></tr>
        </thead>
        <tbody>
          <tr><td colspan="2">合并单元格</td></tr>
          <tr><td>数据1</td><td>数据2</td></tr>
        </tbody>
      </table>`
    const clean = sanitizeDocxHtml(dirty)
    expect(clean).toContain('<table')
    expect(clean).toContain('<thead')
    expect(clean).toContain('<tbody')
    expect(clean).toContain('<th')
    expect(clean).toContain('<td')
    expect(clean).toContain('colspan')
    expect(clean).toContain('标题1')
    expect(clean).toContain('合并单元格')
  })
})

// ============================================================
// 漏洞3: Markdown代码块中iframe执行javascript
// ============================================================
describe('XSS漏洞3: Markdown预览iframe注入', () => {
  it('应移除代码块外的iframe标签', () => {
    const dirty = '<p>文字</p><iframe src="javascript:alert(1)"></iframe>'
    const clean = sanitizeMarkdownHtml(dirty)
    expect(clean).not.toContain('<iframe')
    expect(clean).not.toContain('javascript:')
    expect(clean).toContain('文字')
  })

  it('应移除带javascript协议的iframe', () => {
    const dirty = '<iframe src="javascript:alert(document.cookie)"></iframe>'
    const clean = sanitizeMarkdownHtml(dirty)
    expect(clean).not.toContain('<iframe')
    expect(clean).not.toContain('javascript:')
  })

  it('应移除伪装的iframe标签', () => {
    const dirty = '<iframe/src="javascript:alert(1)">'
    const clean = sanitizeMarkdownHtml(dirty)
    expect(clean).not.toContain('<iframe')
  })

  it('应保留Markdown渲染的代码块结构', () => {
    const dirty = '<pre><code class="language-js">const x = 1;\nconsole.log(x);</code></pre>'
    const clean = sanitizeMarkdownHtml(dirty)
    expect(clean).toContain('<pre>')
    expect(clean).toContain('<code')
    expect(clean).toContain('const x = 1')
  })

  it('应保留Markdown表格', () => {
    const dirty = `
      <table>
        <thead><tr><th>名称</th><th>值</th></tr></thead>
        <tbody><tr><td>A</td><td>1</td></tr></tbody>
      </table>`
    const clean = sanitizeMarkdownHtml(dirty)
    expect(clean).toContain('<table')
    expect(clean).toContain('<th')
    expect(clean).toContain('<td')
    expect(clean).toContain('名称')
  })

  it('应保留Markdown列表结构', () => {
    const dirty = '<ul><li>项目1</li><li>项目2</li></ul><ol><li>有序1</li></ol>'
    const clean = sanitizeMarkdownHtml(dirty)
    expect(clean).toContain('<ul>')
    expect(clean).toContain('<ol>')
    expect(clean).toContain('<li>')
    expect(clean).toContain('项目1')
  })
})

// ============================================================
// 漏洞4: SVG中foreignObject嵌入脚本
// ============================================================
describe('XSS漏洞4: SVG foreignObject脚本注入', () => {
  it('应移除SVG中的foreignObject及其脚本', () => {
    const dirty = `
      <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <circle cx="50" cy="50" r="40" fill="blue"/>
        <foreignObject width="100" height="100">
          <body xmlns="http://www.w3.org/1999/xhtml">
            <script>alert('xss')</script>
          </body>
        </foreignObject>
      </svg>`
    const clean = sanitizeSvg(dirty)
    expect(clean).not.toContain('foreignObject')
    expect(clean).not.toContain('foreignobject')
    expect(clean).not.toContain('<script')
    expect(clean).not.toContain('alert')
    // 正常的SVG内容应保留
    expect(clean).toContain('<circle')
    expect(clean).toContain('fill="blue"')
  })

  it('应移除SVG中的script标签', () => {
    const dirty = `
      <svg xmlns="http://www.w3.org/2000/svg">
        <script>alert('xss')</script>
        <rect width="100" height="100" fill="red"/>
      </svg>`
    const clean = sanitizeSvg(dirty)
    expect(clean).not.toContain('<script')
    expect(clean).toContain('<rect')
  })

  it('应移除SVG元素上的事件处理器', () => {
    const dirty = `
      <svg xmlns="http://www.w3.org/2000/svg">
        <rect width="100" height="100" fill="green" onclick="alert(1)"/>
      </svg>`
    const clean = sanitizeSvg(dirty)
    expect(clean).not.toContain('onclick')
    expect(clean).toContain('fill="green"')
  })

  it('应保留正常SVG图形元素和属性', () => {
    const dirty = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
        <defs>
          <linearGradient id="grad1">
            <stop offset="0%" stop-color="red"/>
            <stop offset="100%" stop-color="blue"/>
          </linearGradient>
        </defs>
        <circle cx="100" cy="100" r="80" fill="url(#grad1)" stroke="black" stroke-width="2"/>
        <text x="100" y="105" text-anchor="middle" font-size="16">示例</text>
        <path d="M10 80 Q 95 10 180 80" stroke="black" fill="transparent"/>
      </svg>`
    const clean = sanitizeSvg(dirty)
    expect(clean).toContain('<svg')
    expect(clean).toContain('viewBox')
    expect(clean).toContain('<circle')
    expect(clean).toContain('<text')
    expect(clean).toContain('<path')
    expect(clean).toContain('<linearGradient') // 保留渐变定义
    expect(clean).toContain('示例')
  })
})

// ============================================================
// 格式保留测试: 确保消毒不破坏正常排版
// ============================================================
describe('格式保留: CSS样式、表格、列表不被破坏', () => {
  it('应保留内联CSS样式', () => {
    const dirty = '<div style="color: red; font-size: 16px; margin: 10px;">样式内容</div>'
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('style=')
    expect(clean).toContain('样式内容')
  })

  it('应保留style标签中的CSS', () => {
    const dirty = '<style>.title { color: blue; font-weight: bold; }</style><div class="title">标题</div>'
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('<style>')
    expect(clean).toContain('.title')
    expect(clean).toContain('标题')
  })

  it('应保留完整的复杂表格结构', () => {
    const dirty = `
      <table>
        <caption>报告数据表</caption>
        <colgroup><col style="width: 50%"><col style="width: 50%"></colgroup>
        <thead><tr><th scope="col">指标</th><th scope="col">数值</th></tr></thead>
        <tbody>
          <tr><td>风速</td><td>12.5 m/s</td></tr>
          <tr><td rowspan="2">温度</td><td>25°C (白天)</td></tr>
          <tr><td>18°C (夜间)</td></tr>
        </tbody>
        <tfoot><tr><td colspan="2">数据截止2024年</td></tr></tfoot>
      </table>`
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('<table')
    expect(clean).toContain('<caption')
    expect(clean).toContain('<colgroup')
    expect(clean).toContain('<thead')
    expect(clean).toContain('<tbody')
    expect(clean).toContain('<tfoot')
    expect(clean).toContain('rowspan')
    expect(clean).toContain('colspan')
    expect(clean).toContain('scope')
    expect(clean).toContain('报告数据表')
    expect(clean).toContain('风速')
  })

  it('应保留嵌套列表结构', () => {
    const dirty = `
      <ul>
        <li>一级项目
          <ul>
            <li>二级项目A</li>
            <li>二级项目B</li>
          </ul>
        </li>
        <li>另一个一级</li>
      </ul>`
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('<ul>')
    expect(clean).toContain('<li>')
    expect(clean).toContain('一级项目')
    expect(clean).toContain('二级项目A')
  })

  it('应保留有序列表的属性', () => {
    const dirty = '<ol type="a" start="3"><li value="5">项目</li></ol>'
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('<ol')
    expect(clean).toContain('type="a"')
    expect(clean).toContain('start="3"')
  })

  it('应保留定义列表', () => {
    const dirty = '<dl><dt>术语</dt><dd>术语的定义说明</dd></dl>'
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('<dl>')
    expect(clean).toContain('<dt>')
    expect(clean).toContain('<dd>')
    expect(clean).toContain('术语的定义说明')
  })

  it('应保留文本格式标签', () => {
    const dirty = '<p><strong>粗体</strong> <em>斜体</em> <u>下划线</u> <s>删除线</s> <mark>高亮</mark> <sub>下标</sub> <sup>上标</sup></p>'
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('<strong>')
    expect(clean).toContain('<em>')
    expect(clean).toContain('<u>')
    expect(clean).toContain('<s>')
    expect(clean).toContain('<mark>')
    expect(clean).toContain('<sub>')
    expect(clean).toContain('<sup>')
  })

  it('应保留带安全href的链接', () => {
    const dirty = '<a href="https://example.com" target="_blank">链接</a>'
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('<a')
    expect(clean).toContain('href="https://example.com"')
    expect(clean).toContain('链接')
  })

  it('应阻止javascript:协议的链接', () => {
    const dirty = '<a href="javascript:alert(1)">恶意链接</a>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('javascript:')
  })

  it('应保留图片标签和安全属性', () => {
    const dirty = '<img src="https://example.com/img.png" alt="图片说明" width="200">'
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('<img')
    expect(clean).toContain('src="https://example.com/img.png"')
    expect(clean).toContain('alt="图片说明"')
  })
})

// ============================================================
// sanitizeByType统一入口测试
// ============================================================
describe('sanitizeByType统一消毒入口', () => {
  it('html类型应移除script', () => {
    const result = sanitizeByType('<script>alert(1)</script><p>ok</p>', 'html')
    expect(result).not.toContain('<script')
    expect(result).toContain('ok')
  })

  it('docx类型应移除onerror', () => {
    const result = sanitizeByType('<img onerror="alert(1)" src="x">', 'docx')
    expect(result).not.toContain('onerror')
  })

  it('markdown类型应移除iframe', () => {
    const result = sanitizeByType('<iframe src="javascript:alert(1)"></iframe><p>text</p>', 'markdown')
    expect(result).not.toContain('<iframe')
    expect(result).toContain('text')
  })

  it('svg类型应移除foreignObject', () => {
    const result = sanitizeByType('<svg><foreignObject><script>alert(1)</script></foreignObject><rect fill="red"/></svg>', 'svg')
    expect(result).not.toContain('foreignObject')
    expect(result).not.toContain('<script')
  })
})

// ============================================================
// 安全审计检测测试
// ============================================================
describe('detectXssVectors安全审计', () => {
  it('应检测出script标签', () => {
    const report = detectXssVectors('<script>alert(1)</script>')
    expect(report.removedTags).toContain('script')
  })

  it('应检测出事件处理器属性', () => {
    const report = detectXssVectors('<img onerror="alert(1)" src="x">')
    expect(report.removedAttributes).toContain('onerror')
  })

  it('应检测出javascript URI', () => {
    const report = detectXssVectors('<a href="javascript:alert(1)">link</a>')
    expect(report.blockedUris).toBeGreaterThan(0)
  })

  it('应检测出foreignObject', () => {
    const report = detectXssVectors('<svg><foreignObject><script>x</script></foreignObject></svg>')
    expect(report.removedTags).toContain('foreignobject')
    expect(report.removedTags).toContain('script')
  })

  it('安全内容应无检测结果', () => {
    const report = detectXssVectors('<p>这是安全的<strong>内容</strong></p>')
    expect(report.removedTags).toHaveLength(0)
    expect(report.removedAttributes).toHaveLength(0)
    expect(report.blockedUris).toBe(0)
  })
})

// ============================================================
// 边界攻击向量测试
// ============================================================
describe('高级攻击向量防御', () => {
  it('应阻止data URI中的脚本', () => {
    const dirty = '<a href="data:text/html,<script>alert(1)</script>">click</a>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('data:text/html')
  })

  it('应阻止CSS表达式注入', () => {
    const dirty = '<div style="width: expression(alert(1))">text</div>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toMatch(/expression\s*\(\s*alert/)
  })

  it('应阻止vbscript协议', () => {
    const dirty = '<a href="vbscript:alert(1)">link</a>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('vbscript:')
  })

  it('应移除embed标签', () => {
    const dirty = '<embed src="evil.swf" type="application/x-shockwave-flash">'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('<embed')
  })

  it('应移除object标签', () => {
    const dirty = '<object data="evil.swf"><param name="movie" value="evil.swf"></object>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('<object')
  })

  it('应移除form和input标签防止表单劫持', () => {
    const dirty = '<form action="https://evil.com"><input type="password" name="pass"><button>Submit</button></form>'
    const clean = sanitizeHtml(dirty)
    expect(clean).not.toContain('<form')
    expect(clean).not.toContain('<input')
    expect(clean).not.toContain('<button')
  })

  it('应给链接添加noopener noreferrer安全属性', () => {
    const dirty = '<a href="https://example.com" target="_blank">链接</a>'
    const clean = sanitizeHtml(dirty)
    expect(clean).toContain('rel="noopener noreferrer"')
  })
})
