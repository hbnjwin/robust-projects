# -*- coding: utf-8 -*-
"""RFC 5987 Content-Disposition 文件名编码工具。

解决中文等非ASCII字符文件名在HTTP下载时的乱码问题。
生成同时包含 ASCII fallback 和 UTF-8 编码的 Content-Disposition header。
"""
import re
import unicodedata
from urllib.parse import quote


def _ascii_fallback(filename: str) -> str:
    """将文件名转换为ASCII安全的回退版本。

    非ASCII字符替换为下划线，保留扩展名。
    """
    result = []
    for char in filename:
        if ord(char) < 128:
            result.append(char)
        else:
            result.append('_')
    # 合并连续下划线
    fallback = re.sub(r'_+', '_', ''.join(result))
    return fallback


def _rfc5987_encode(filename: str) -> str:
    """按RFC 5987规范进行UTF-8百分号编码。

    RFC 5987要求：
    - attr-char 不需要编码：ALPHA / DIGIT / "!" / "#" / "$" / "&" / "+" /
      "-" / "." / "^" / "_" / "`" / "|" / "~"
    - 其他字符（包括空格、中文等）需要百分号编码
    """
    return quote(filename, safe='!#$&+-.^_`|~')


def encode_content_disposition(filename: str, disposition: str = 'attachment') -> str:
    """生成符合RFC 5987的Content-Disposition header值。

    同时包含：
    - filename="ascii_fallback" 供不支持RFC 5987的旧浏览器使用
    - filename*=UTF-8''encoded_name 供现代浏览器正确显示中文等字符

    Args:
        filename: 原始文件名（可包含中文等非ASCII字符）
        disposition: 处置类型，默认'attachment'（下载），可设'inline'（预览）

    Returns:
        完整的Content-Disposition header值

    Examples:
        >>> encode_content_disposition('哈尔滨风电场_检测报告.pdf')
        'attachment; filename="_________.pdf"; filename*=UTF-8\'\'%E5%93%88%E5%B0%94%E6%BB%A8%E9%A3%8E%E7%94%B5%E5%9C%BA_%E6%A3%80%E6%B5%8B%E6%8A%A5%E5%91%8A.pdf'
    """
    if not filename:
        filename = 'download'

    # 规范化Unicode（NFC形式）
    filename = unicodedata.normalize('NFC', filename)

    ascii_name = _ascii_fallback(filename)
    utf8_encoded = _rfc5987_encode(filename)

    return f'{disposition}; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_encoded}'


def parse_content_disposition(header: str) -> str:
    """从Content-Disposition header解析文件名。

    优先使用filename*（RFC 5987 UTF-8编码），回退到普通filename。
    此函数主要用于后端测试验证，前端有对应的JS实现。

    Args:
        header: Content-Disposition header值

    Returns:
        解码后的文件名
    """
    # 优先匹配 filename*=UTF-8''encoded_name
    match = re.search(r"filename\*=UTF-8''(.+?)(?:;|$)", header, re.IGNORECASE)
    if match:
        from urllib.parse import unquote
        return unquote(match.group(1).strip())

    # 回退到 filename="name" 或 filename=name
    match = re.search(r'filename="?([^";]+)"?', header)
    if match:
        return match.group(1).strip()

    return 'download'
