# -*- coding: utf-8 -*-
"""文件名编码工具测试。"""
import pytest

from src.utils.filename_encoding import (
    _ascii_fallback,
    _rfc5987_encode,
    encode_content_disposition,
    parse_content_disposition,
)


class TestAsciiFallback:
    def test_pure_ascii(self):
        assert _ascii_fallback('report.pdf') == 'report.pdf'

    def test_chinese_characters(self):
        result = _ascii_fallback('哈尔滨风电场_检测报告.pdf')
        # 中文全部替换为下划线，连续下划线合并
        assert result == '_.pdf'
        assert all(ord(c) < 128 for c in result)

    def test_mixed_ascii_and_chinese(self):
        result = _ascii_fallback('2024_哈尔滨_report.pdf')
        # 中文→下划线，连续下划线合并：2024_____report.pdf → 2024_report.pdf
        assert result == '2024_report.pdf'

    def test_empty_string(self):
        assert _ascii_fallback('') == ''


class TestRfc5987Encode:
    def test_pure_ascii(self):
        assert _rfc5987_encode('report.pdf') == 'report.pdf'

    def test_chinese_encoding(self):
        encoded = _rfc5987_encode('哈尔滨风电场_检测报告.pdf')
        assert '%E5%93%88' in encoded  # 哈
        assert '%E5%B0%94' in encoded  # 尔
        assert '%E6%BB%A8' in encoded  # 滨
        assert '_' in encoded  # 下划线不编码
        assert encoded.endswith('.pdf')

    def test_spaces_are_encoded(self):
        encoded = _rfc5987_encode('my report.pdf')
        assert '%20' in encoded or '+' not in encoded

    def test_safe_chars_preserved(self):
        encoded = _rfc5987_encode('report-v2.0_final.pdf')
        assert encoded == 'report-v2.0_final.pdf'


class TestEncodeContentDisposition:
    def test_chinese_filename(self):
        result = encode_content_disposition('哈尔滨风电场_检测报告.pdf')
        assert result.startswith('attachment; ')
        assert 'filename="' in result
        assert "filename*=UTF-8''" in result
        # UTF-8编码部分应该包含中文的百分号编码
        assert '%E5%93%88' in result

    def test_ascii_filename(self):
        result = encode_content_disposition('report.pdf')
        assert 'filename="report.pdf"' in result
        assert "filename*=UTF-8''report.pdf" in result

    def test_inline_disposition(self):
        result = encode_content_disposition('test.pdf', disposition='inline')
        assert result.startswith('inline; ')

    def test_empty_filename(self):
        result = encode_content_disposition('')
        assert 'filename="download"' in result

    def test_japanese_filename(self):
        result = encode_content_disposition('テスト報告書.pdf')
        assert "filename*=UTF-8''" in result
        assert '%' in result  # 应该有百分号编码

    def test_roundtrip_chinese(self):
        """编码后应能正确解码回原始文件名。"""
        original = '哈尔滨风电场_检测报告.pdf'
        header = encode_content_disposition(original)
        decoded = parse_content_disposition(header)
        assert decoded == original

    def test_roundtrip_mixed(self):
        original = '2024年_风电场A区_检测报告_v2.pdf'
        header = encode_content_disposition(original)
        decoded = parse_content_disposition(header)
        assert decoded == original


class TestParseContentDisposition:
    def test_rfc5987_utf8(self):
        header = "attachment; filename=\"_.pdf\"; filename*=UTF-8''%E5%93%88%E5%B0%94%E6%BB%A8.pdf"
        assert parse_content_disposition(header) == '哈尔滨.pdf'

    def test_plain_filename_quoted(self):
        header = 'attachment; filename="report.pdf"'
        assert parse_content_disposition(header) == 'report.pdf'

    def test_plain_filename_unquoted(self):
        header = 'attachment; filename=report.pdf'
        assert parse_content_disposition(header) == 'report.pdf'

    def test_prefers_filename_star(self):
        """filename*优先于filename。"""
        header = "attachment; filename=\"fallback.pdf\"; filename*=UTF-8''%E6%8A%A5%E5%91%8A.pdf"
        assert parse_content_disposition(header) == '报告.pdf'

    def test_empty_header(self):
        assert parse_content_disposition('') == 'download'

    def test_no_filename(self):
        assert parse_content_disposition('attachment') == 'download'
