/**
 * download.js 单元测试
 *
 * 覆盖三个bug修复场景:
 * 1. RFC 5987 UTF-8 文件名解析
 * 2. 流式下载流程
 * 3. 网络错误与超时处理
 */

import { jest, describe, test, expect, beforeEach, afterEach } from '@jest/globals';
import { parseContentDispositionFilename, downloadReport } from '../src/utils/download.js';

// ============ parseContentDispositionFilename 测试 ============

describe('parseContentDispositionFilename - RFC 5987 UTF-8文件名解析', () => {

  // --- Bug 1: 中文文件名乱码 ---

  test('解析 filename*=UTF-8 编码的中文文件名', () => {
    // "哈尔滨风电场_检测报告.pdf" 的 percent-encoded 形式
    const header = "attachment; filename*=UTF-8''%E5%93%88%E5%B0%94%E6%BB%A8%E9%A3%8E%E7%94%B5%E5%9C%BA_%E6%A3%80%E6%B5%8B%E6%8A%A5%E5%91%8A.pdf";
    expect(parseContentDispositionFilename(header)).toBe('哈尔滨风电场_检测报告.pdf');
  });

  test('解析 filename*=utf-8 小写编码格式', () => {
    const header = "attachment; filename*=utf-8''%E6%8A%A5%E5%91%8A.pdf";
    expect(parseContentDispositionFilename(header)).toBe('报告.pdf');
  });

  test('filename* 优先于 filename', () => {
    const header = "attachment; filename=\"report.pdf\"; filename*=UTF-8''%E5%93%88%E5%B0%94%E6%BB%A8.pdf";
    expect(parseContentDispositionFilename(header)).toBe('哈尔滨.pdf');
  });

  test('解析普通带引号的 filename', () => {
    const header = 'attachment; filename="report.pdf"';
    expect(parseContentDispositionFilename(header)).toBe('report.pdf');
  });

  test('解析不带引号的 filename', () => {
    const header = 'attachment; filename=report.pdf';
    expect(parseContentDispositionFilename(header)).toBe('report.pdf');
  });

  test('header为空时返回默认文件名', () => {
    expect(parseContentDispositionFilename(null)).toBe('download.pdf');
    expect(parseContentDispositionFilename('')).toBe('download.pdf');
  });

  test('无法匹配时使用自定义回退名', () => {
    expect(parseContentDispositionFilename('invalid-header', 'custom.pdf')).toBe('custom.pdf');
  });

  test('filename* percent-decode失败时回退到filename', () => {
    const header = 'attachment; filename="fallback.pdf"; filename*=UTF-8\'\'%ZZ%YY';
    expect(parseContentDispositionFilename(header)).toBe('fallback.pdf');
  });

  test('filename*=后有多余分号截断', () => {
    const header = "attachment; filename*=UTF-8''%E6%8A%A5%E5%91%8A.pdf; size=12345";
    expect(parseContentDispositionFilename(header)).toBe('报告.pdf');
  });

  test('filename带空格和特殊字符', () => {
    const header = "attachment; filename*=UTF-8''2024%E5%B9%B4_%E6%A3%80%E6%B5%8B%20%E6%8A%A5%E5%91%8A%20(final).pdf";
    expect(parseContentDispositionFilename(header)).toBe('2024年_检测 报告 (final).pdf');
  });
});

// ============ downloadReport 测试 ============

// 辅助: 创建mock ReadableStream
function createMockStream(chunks) {
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(chunks[index]);
        index++;
      } else {
        controller.close();
      }
    },
  });
}

// 辅助: 创建mock fetch Response
function createMockResponse({ status = 200, headers = {}, body = null }) {
  const responseHeaders = new Map();
  Object.entries(headers).forEach(([k, v]) => responseHeaders.set(k.toLowerCase(), v));

  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: (name) => responseHeaders.get(name.toLowerCase()) || null,
    },
    body,
    blob: jest.fn().mockResolvedValue(new Blob(['mock-data'], { type: 'application/pdf' })),
  };
}

describe('downloadReport - 流式下载', () => {

  let originalFetch;
  let originalCreateObjectURL;
  let originalRevokeObjectURL;

  beforeEach(() => {
    originalFetch = global.fetch;
    originalCreateObjectURL = global.URL.createObjectURL;
    originalRevokeObjectURL = global.URL.revokeObjectURL;

    global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = jest.fn();

    // mock DOM: document.createElement / document.body
    global.document = {
      createElement: jest.fn(() => ({
        href: '',
        download: '',
        style: {},
        click: jest.fn(),
      })),
      body: {
        appendChild: jest.fn(),
        removeChild: jest.fn(),
      },
    };
  });

  afterEach(() => {
    global.fetch = originalFetch;
    global.URL.createObjectURL = originalCreateObjectURL;
    global.URL.revokeObjectURL = originalRevokeObjectURL;
    jest.restoreAllMocks();
  });

  test('正常下载: 流式读取并触发浏览器下载', async () => {
    const chunks = [
      new Uint8Array([1, 2, 3]),
      new Uint8Array([4, 5, 6]),
      new Uint8Array([7, 8, 9]),
    ];

    global.fetch = jest.fn().mockResolvedValue(createMockResponse({
      headers: {
        'content-disposition': "attachment; filename*=UTF-8''%E6%8A%A5%E5%91%8A.pdf",
        'content-length': '9',
      },
      body: createMockStream(chunks),
    }));

    const progressCalls = [];
    const result = await downloadReport({
      url: 'https://api.example.com/download/report/123',
      onProgress: (pct, loaded, total) => progressCalls.push({ pct, loaded, total }),
    });

    expect(result.success).toBe(true);
    expect(result.filename).toBe('报告.pdf');
    expect(progressCalls.length).toBe(3);
    expect(progressCalls[2].pct).toBe(100);
    expect(progressCalls[2].loaded).toBe(9);
  });

  test('HTTP错误: 返回错误信息并调用onError', async () => {
    global.fetch = jest.fn().mockResolvedValue(createMockResponse({
      status: 404,
    }));

    const errors = [];
    const result = await downloadReport({
      url: 'https://api.example.com/download/report/123',
      onError: (err) => errors.push(err),
    });

    expect(result.success).toBe(false);
    expect(result.error.code).toBe('HTTP_ERROR');
    expect(result.error.status).toBe(404);
    expect(errors.length).toBe(1);
  });

  test('网络中断: fetch抛出TypeError', async () => {
    const networkErr = new TypeError('Failed to fetch');
    global.fetch = jest.fn().mockRejectedValue(networkErr);

    const errors = [];
    const result = await downloadReport({
      url: 'https://api.example.com/download/report/123',
      onError: (err) => errors.push(err),
    });

    expect(result.success).toBe(false);
    expect(result.error.code).toBe('NETWORK_ERROR');
    expect(errors[0].message).toContain('网络连接失败');
  });

  test('URL为空: 直接返回错误', async () => {
    const errors = [];
    const result = await downloadReport({
      url: '',
      onError: (err) => errors.push(err),
    });

    expect(result.success).toBe(false);
    expect(result.error.code).toBe('INVALID_PARAMS');
    expect(errors.length).toBe(1);
  });

  test('外部AbortSignal 取消下载', async () => {
    const controller = new AbortController();

    const abortErr = new Error('The operation was aborted.');
    abortErr.name = 'AbortError';
    global.fetch = jest.fn().mockRejectedValue(abortErr);

    const errors = [];
    const result = await downloadReport({
      url: 'https://api.example.com/download/report/123',
      externalSignal: controller.signal,
      onError: (err) => errors.push(err),
    });

    expect(result.success).toBe(false);
    expect(result.error.code).toBe('CANCELLED');
  });

  test('超时检测: 长时间无数据返回超时错误', async () => {
    // 创建一个永不返回数据的stream
    const neverStream = new ReadableStream({
      pull() {
        return new Promise(() => {}); // 永远不resolve
      },
    });

    global.fetch = jest.fn().mockResolvedValue(createMockResponse({
      headers: { 'content-length': '1000' },
      body: neverStream,
    }));

    const errors = [];
    const result = await downloadReport({
      url: 'https://api.example.com/download/report/123',
      chunkTimeoutMs: 50, // 50ms超时(测试用)
      onError: (err) => errors.push(err),
    });

    expect(result.success).toBe(false);
    expect(result.error.code).toBe('TIMEOUT');
    expect(errors[0].message).toContain('下载超时');
  }, 5000);

  test('不支持流式时回退到blob()', async () => {
    global.fetch = jest.fn().mockResolvedValue(createMockResponse({
      headers: {
        'content-disposition': 'attachment; filename="report.pdf"',
      },
      body: null, // 不支持流式
    }));

    const result = await downloadReport({
      url: 'https://api.example.com/download/report/123',
    });

    expect(result.success).toBe(true);
    expect(result.filename).toBe('report.pdf');
  });

  test('onComplete回调在下载成功后被调用', async () => {
    global.fetch = jest.fn().mockResolvedValue(createMockResponse({
      headers: {
        'content-disposition': "attachment; filename*=UTF-8''%E6%A3%80%E6%B5%8B%E6%8A%A5%E5%91%8A.pdf",
      },
      body: null,
    }));

    const completions = [];
    await downloadReport({
      url: 'https://api.example.com/download/report/123',
      onComplete: (name) => completions.push(name),
    });

    expect(completions).toEqual(['检测报告.pdf']);
  });
});
