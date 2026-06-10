/**
 * PDF报告下载工具
 *
 * 解决三个核心问题：
 * 1. 中文文件名乱码 - 正确解析RFC 5987 Content-Disposition header
 * 2. 大文件内存崩溃 - 流式下载，超大文件降级为原生浏览器下载
 * 3. 网络中断无提示 - 停滞检测、超时控制、错误回调
 */

/**
 * 从Content-Disposition header解析文件名。
 * 优先使用filename*=UTF-8''编码格式，回退到普通filename。
 *
 * @param {string} header - Content-Disposition header值
 * @returns {string} 解码后的文件名
 */
function parseContentDisposition(header) {
    if (!header) return 'download.pdf';

    // 优先匹配 filename*=UTF-8''encoded_name (RFC 5987)
    const rfc5987Match = header.match(/filename\*=UTF-8''([^;]+)/i);
    if (rfc5987Match) {
        try {
            return decodeURIComponent(rfc5987Match[1].trim());
        } catch (e) {
            // 解码失败，继续尝试普通filename
        }
    }

    // 回退到 filename="name" 或 filename=name
    const plainMatch = header.match(/filename="?([^";]+)"?/);
    if (plainMatch) {
        return plainMatch[1].trim();
    }

    return 'download.pdf';
}

/**
 * 创建结构化错误对象
 *
 * @param {string} type - 错误类型
 * @param {string} message - 用户友好的错误消息
 * @param {boolean} retryable - 是否可重试
 * @returns {Object} 错误对象
 */
function createDownloadError(type, message, retryable) {
    return { type: type, message: message, retryable: retryable };
}

// 预定义的错误消息
var ERROR_MESSAGES = {
    network_error: '网络连接中断，请检查网络后重试',
    timeout: '下载超时，请检查网络连接后重试',
    stall: '下载停滞超过15秒，可能网络不稳定，请重试',
    server_error: '服务器错误，请联系管理员',
    abort: '下载已取消'
};

/**
 * 大文件阈值（字节），超过此大小使用原生浏览器下载
 * 避免JS内存中积累过多数据
 */
var LARGE_FILE_THRESHOLD = 200 * 1024 * 1024; // 200MB

/**
 * 停滞检测超时时间（毫秒）
 */
var STALL_TIMEOUT = 15000; // 15秒

/**
 * 下载报告PDF文件
 *
 * @param {string} url - 下载URL
 * @param {Object} options - 配置选项
 * @param {function} options.onProgress - 进度回调 function(percent, loaded, total)
 * @param {function} options.onError - 错误回调 function({type, message, retryable})
 * @param {function} options.onComplete - 完成回调 function(filename)
 * @param {number} options.timeout - 总超时时间(ms)，默认30分钟
 * @returns {Object} 包含abort()方法的控制器对象
 */
function downloadReport(url, options) {
    options = options || {};
    var onProgress = options.onProgress || function () {};
    var onError = options.onError || function () {};
    var onComplete = options.onComplete || function () {};
    var totalTimeout = options.timeout || 30 * 60 * 1000; // 30分钟

    var abortController = new AbortController();
    var stallTimer = null;
    var overallTimer = null;
    var aborted = false;

    function cleanup() {
        if (stallTimer) clearTimeout(stallTimer);
        if (overallTimer) clearTimeout(overallTimer);
    }

    function resetStallTimer() {
        if (stallTimer) clearTimeout(stallTimer);
        stallTimer = setTimeout(function () {
            if (!aborted) {
                aborted = true;
                abortController.abort();
                cleanup();
                onError(createDownloadError('stall', ERROR_MESSAGES.stall, true));
            }
        }, STALL_TIMEOUT);
    }

    // 总超时计时器
    overallTimer = setTimeout(function () {
        if (!aborted) {
            aborted = true;
            abortController.abort();
            cleanup();
            onError(createDownloadError('timeout', ERROR_MESSAGES.timeout, true));
        }
    }, totalTimeout);

    // 先发HEAD请求获取文件大小，决定下载策略
    fetch(url, { method: 'HEAD' })
        .then(function (headResp) {
            var contentLength = parseInt(headResp.headers.get('content-length') || '0', 10);

            // 超大文件：降级为原生浏览器下载，避免JS内存问题
            if (contentLength > LARGE_FILE_THRESHOLD) {
                cleanup();
                var a = document.createElement('a');
                a.href = url;
                a.download = '';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                onComplete('(浏览器原生下载)');
                return;
            }

            // 正常流式下载
            return _streamDownload(url, abortController, {
                onProgress: onProgress,
                onError: onError,
                onComplete: onComplete,
                resetStallTimer: resetStallTimer,
                cleanup: cleanup,
                abortedRef: function () { return aborted; },
                setAborted: function () { aborted = true; }
            });
        })
        .catch(function (err) {
            if (aborted) return;
            cleanup();
            if (err.name === 'AbortError') return;
            onError(createDownloadError('network_error', ERROR_MESSAGES.network_error, true));
        });

    return {
        abort: function () {
            if (!aborted) {
                aborted = true;
                abortController.abort();
                cleanup();
                onError(createDownloadError('abort', ERROR_MESSAGES.abort, false));
            }
        }
    };
}

/**
 * 流式下载实现（内部函数）
 */
function _streamDownload(url, abortController, ctx) {
    ctx.resetStallTimer();

    return fetch(url, { signal: abortController.signal })
        .then(function (response) {
            if (!response.ok) {
                ctx.cleanup();
                var errType = response.status >= 500 ? 'server_error' : 'network_error';
                var retryable = response.status < 500;
                ctx.onError(createDownloadError(
                    errType,
                    response.status >= 500 ? ERROR_MESSAGES.server_error : '下载失败 (HTTP ' + response.status + ')',
                    retryable
                ));
                return;
            }

            var contentDisposition = response.headers.get('content-disposition') || '';
            var filename = parseContentDisposition(contentDisposition);
            var totalBytes = parseInt(response.headers.get('content-length') || '0', 10);
            var loadedBytes = 0;

            var reader = response.body.getReader();
            var chunks = [];

            function readChunk() {
                return reader.read().then(function (result) {
                    if (ctx.abortedRef()) return;

                    if (result.done) {
                        // 下载完成，组装文件
                        ctx.cleanup();
                        var blob = new Blob(chunks, { type: 'application/pdf' });
                        chunks = []; // 释放chunk引用

                        var downloadUrl = URL.createObjectURL(blob);
                        var a = document.createElement('a');
                        a.href = downloadUrl;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);

                        // 延迟释放blob URL
                        setTimeout(function () {
                            URL.revokeObjectURL(downloadUrl);
                        }, 1000);

                        ctx.onProgress(100, totalBytes, totalBytes);
                        ctx.onComplete(filename);
                        return;
                    }

                    // 收到新chunk，重置停滞计时器
                    ctx.resetStallTimer();
                    chunks.push(result.value);
                    loadedBytes += result.value.length;

                    if (totalBytes > 0) {
                        var percent = Math.round((loadedBytes / totalBytes) * 100);
                        ctx.onProgress(percent, loadedBytes, totalBytes);
                    } else {
                        ctx.onProgress(-1, loadedBytes, 0); // 未知总大小
                    }

                    return readChunk();
                });
            }

            return readChunk();
        })
        .catch(function (err) {
            if (ctx.abortedRef()) return;
            ctx.setAborted();
            ctx.cleanup();

            if (err.name === 'AbortError') {
                // AbortError由停滞/超时检测触发，已经发过错误通知
                return;
            }

            // TypeError通常表示网络中断
            ctx.onError(createDownloadError('network_error', ERROR_MESSAGES.network_error, true));
        });
}

// 导出供外部使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { downloadReport: downloadReport, parseContentDisposition: parseContentDisposition };
}
