# -*- coding: utf-8 -*-
"""报告PDF下载API。

流式传输文件，避免大文件内存问题。
正确设置Content-Disposition header支持中文文件名。
"""
import os

from flask import Blueprint, Response, abort, request

from src.utils.filename_encoding import encode_content_disposition

download_bp = Blueprint('download', __name__)

CHUNK_SIZE = 64 * 1024  # 64KB


def _stream_file(file_path: str):
    """生成器：按chunk读取文件，避免一次性加载到内存。"""
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            yield chunk


@download_bp.route('/api/reports/<int:report_id>/download', methods=['GET', 'HEAD'])
def download_report(report_id: int):
    """下载报告PDF文件。

    支持GET（下载文件）和HEAD（获取文件元信息，供前端判断文件大小）。

    URL参数:
        report_id: 报告ID

    响应头:
        Content-Disposition: RFC 5987编码的文件名
        Content-Length: 文件大小
        Content-Type: application/pdf
    """
    # 实际项目中应从数据库查询报告信息
    # 这里用配置的报告目录 + report_id 作为示例
    report_dir = os.environ.get('REPORT_DIR', os.path.join(os.path.dirname(__file__), '..', 'reports'))
    report_dir = os.path.abspath(report_dir)

    # 查找报告文件（实际项目中应从数据库获取文件名）
    report_file = _find_report_file(report_dir, report_id)
    if report_file is None:
        abort(404, description='报告不存在')

    file_path = os.path.join(report_dir, report_file)

    # 安全检查：防止路径遍历
    real_path = os.path.realpath(file_path)
    if not real_path.startswith(os.path.realpath(report_dir)):
        abort(403, description='禁止访问')

    if not os.path.isfile(real_path):
        abort(404, description='报告文件不存在')

    file_size = os.path.getsize(real_path)
    content_disposition = encode_content_disposition(report_file)

    headers = {
        'Content-Disposition': content_disposition,
        'Content-Length': str(file_size),
        'Content-Type': 'application/pdf',
        'Accept-Ranges': 'none',
    }

    # HEAD请求只返回header，不传输文件体
    if request.method == 'HEAD':
        return Response('', status=200, headers=headers)

    # GET请求：流式传输文件
    response = Response(
        _stream_file(real_path),
        status=200,
        headers=headers,
        mimetype='application/pdf',
        direct_passthrough=True,
    )
    return response


def _find_report_file(report_dir: str, report_id: int) -> str | None:
    """根据report_id查找报告文件。

    实际项目中应从数据库查询。这里简单地查找以report_id开头的PDF文件。
    """
    if not os.path.isdir(report_dir):
        return None

    for f in os.listdir(report_dir):
        if f.endswith('.pdf'):
            # 匹配格式: {report_id}_xxx.pdf 或 {report_id}.pdf
            name_part = f.split('_')[0] if '_' in f else f.rsplit('.', 1)[0]
            try:
                if int(name_part) == report_id:
                    return f
            except ValueError:
                continue

    return None
