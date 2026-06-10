# -*- coding: utf-8 -*-
"""下载API集成测试。"""
import os
import tempfile

import pytest

from src.app import create_app


@pytest.fixture
def report_dir(tmp_path):
    """创建临时报告目录并写入测试PDF文件。"""
    # 创建带中文名的PDF文件
    pdf_name = '1_哈尔滨风电场_检测报告.pdf'
    pdf_path = tmp_path / pdf_name
    # 写入一个最小的有效PDF
    pdf_content = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n'
    pdf_path.write_bytes(pdf_content)
    return tmp_path


@pytest.fixture
def large_report_dir(tmp_path):
    """创建包含大文件的报告目录。"""
    pdf_name = '2_大型扫描报告.pdf'
    pdf_path = tmp_path / pdf_name
    # 写入1MB的测试数据（模拟大文件，但不真的创建200MB文件）
    pdf_path.write_bytes(b'%PDF-1.4\n' + b'x' * (1024 * 1024) + b'\n%%EOF\n')
    return tmp_path


@pytest.fixture
def app(report_dir):
    os.environ['REPORT_DIR'] = str(report_dir)
    app = create_app()
    app.config['TESTING'] = True
    yield app
    del os.environ['REPORT_DIR']


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def large_app(large_report_dir):
    os.environ['REPORT_DIR'] = str(large_report_dir)
    app = create_app()
    app.config['TESTING'] = True
    yield app
    del os.environ['REPORT_DIR']


@pytest.fixture
def large_client(large_app):
    return large_app.test_client()


class TestDownloadEndpoint:
    def test_download_returns_200(self, client):
        response = client.get('/api/reports/1/download')
        assert response.status_code == 200

    def test_content_type_is_pdf(self, client):
        response = client.get('/api/reports/1/download')
        assert response.content_type == 'application/pdf'

    def test_content_disposition_has_utf8_filename(self, client):
        """验证Content-Disposition包含RFC 5987 UTF-8编码的文件名。"""
        response = client.get('/api/reports/1/download')
        cd = response.headers.get('Content-Disposition', '')
        assert "filename*=UTF-8''" in cd
        # 解码后应包含中文
        from src.utils.filename_encoding import parse_content_disposition
        filename = parse_content_disposition(cd)
        assert '哈尔滨' in filename
        assert filename.endswith('.pdf')

    def test_content_disposition_has_ascii_fallback(self, client):
        """验证Content-Disposition包含ASCII回退文件名。"""
        response = client.get('/api/reports/1/download')
        cd = response.headers.get('Content-Disposition', '')
        assert 'filename="' in cd

    def test_content_length_header(self, client):
        response = client.get('/api/reports/1/download')
        content_length = response.headers.get('Content-Length')
        assert content_length is not None
        assert int(content_length) > 0

    def test_head_request_no_body(self, client):
        """HEAD请求应返回header但不传输文件体。"""
        response = client.head('/api/reports/1/download')
        assert response.status_code == 200
        assert response.headers.get('Content-Length') is not None
        assert response.headers.get('Content-Disposition') is not None
        assert len(response.data) == 0

    def test_nonexistent_report_returns_404(self, client):
        response = client.get('/api/reports/9999/download')
        assert response.status_code == 404

    def test_response_body_matches_file(self, client, report_dir):
        """验证流式响应的数据完整性。"""
        response = client.get('/api/reports/1/download')
        # 找到原始文件
        for f in os.listdir(report_dir):
            if f.startswith('1_'):
                original = (report_dir / f).read_bytes()
                assert response.data == original
                break


class TestStreamingResponse:
    def test_large_file_streams_correctly(self, large_client, large_report_dir):
        """验证大文件能正确流式传输，数据完整。"""
        response = large_client.get('/api/reports/2/download')
        assert response.status_code == 200
        content_length = int(response.headers.get('Content-Length', 0))
        assert content_length > 1024 * 1024  # 至少1MB
        assert len(response.data) == content_length

    def test_large_file_content_disposition(self, large_client):
        response = large_client.get('/api/reports/2/download')
        cd = response.headers.get('Content-Disposition', '')
        from src.utils.filename_encoding import parse_content_disposition
        filename = parse_content_disposition(cd)
        assert '大型扫描报告' in filename
