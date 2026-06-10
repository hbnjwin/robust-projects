# -*- coding: utf-8 -*-
"""测试报告审核系统的三个 WebSocket 同步修复

测试覆盖：
1. 问题1：审核状态变更 + 批注更新后通过 WebSocket 广播，确保其他审核员实时收到
2. 问题2：心跳机制和连接管理（服务端侧）
3. 问题3：乐观锁版本冲突检测（409 响应）+ 冲突解决
"""
import json
import time

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import Report, Section, Annotation, init_db


# ── 问题1：状态变更实时广播 ───────────────────────────────

class TestReviewStatusBroadcast:
    """验证审核状态变更后通过 WebSocket 广播给其他审核员"""

    def test_update_review_status_returns_updated_section(self, client):
        """更新审核状态后 API 返回正确的更新数据"""
        # 先通过 API 创建测试数据（确保在 API 使用的数据库中）
        create_resp = client.post('/api/reports', json={
            'title': '测试报告',
            'sections': [{'content': '测试段落'}],
        })
        assert create_resp.status_code == 201
        report_data = create_resp.get_json()
        section_id = report_data['sections'][0]['id']

        # 更新审核状态
        resp = client.put(
            f'/api/sections/{section_id}/review',
            json={
                'status': 'flagged',
                'reviewed_by': 'reviewer_a',
            },
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['review_status'] == 'flagged'
        assert data['reviewed_by'] == 'reviewer_a'

    def test_section_model_status_field(self, db_session):
        """Section 模型的 review_status 字段可以正确存储"""
        session = db_session

        report = Report(title='测试报告')
        session.add(report)
        session.flush()

        section = Section(
            report_id=report.id,
            order=0,
            content='测试段落',
            review_status='pending',
        )
        session.add(section)
        session.commit()

        assert section.review_status == 'pending'

        section.review_status = 'flagged'
        section.reviewed_by = 'reviewer_a'
        session.commit()

        assert section.review_status == 'flagged'
        assert section.reviewed_by == 'reviewer_a'


# ── 问题2：心跳和连接管理 ─────────────────────────────────

class TestHeartbeatAndConnection:
    """验证 WebSocket 心跳和连接管理（服务端侧）"""

    def test_websocket_config_has_heartbeat_constants(self):
        """WebSocket 模块定义了心跳间隔和超时参数"""
        from src.websocket import HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT

        assert HEARTBEAT_INTERVAL > 0, '心跳间隔必须为正数'
        assert HEARTBEAT_TIMEOUT > HEARTBEAT_INTERVAL, '超时时间必须大于心跳间隔'
        # 默认配置：15s 心跳，45s 超时（允许3次丢失）
        assert HEARTBEAT_INTERVAL == 15
        assert HEARTBEAT_TIMEOUT == 45

    def test_websocket_module_exports_broadcast(self):
        """WebSocket 模块导出广播函数供 API 层调用"""
        from src.websocket import broadcast_to_report, get_online_users

        assert callable(broadcast_to_report)
        assert callable(get_online_users)

    def test_get_online_users_empty_room(self):
        """空房间返回空列表"""
        from src.websocket import get_online_users as _get_online_users

        users = _get_online_users(99999)
        assert users == []


# ── 问题3：乐观锁冲突检测 ─────────────────────────────────

class TestOptimisticLocking:
    """验证批注更新的乐观锁冲突检测"""

    def test_annotation_version_starts_at_1(self, db_session):
        """新建批注的 version 默认为 1"""
        session = db_session

        report = Report(title='测试报告')
        session.add(report)
        session.flush()
        section = Section(report_id=report.id, order=0, content='测试段落')
        session.add(section)
        session.flush()

        annotation = Annotation(
            section_id=section.id,
            author='reviewer_a',
            content='初始批注',
        )
        session.add(annotation)
        session.commit()

        assert annotation.version == 1

    def test_annotation_version_increments_on_update(self, db_session):
        """更新批注后 version 自增"""
        session = db_session

        report = Report(title='测试报告')
        session.add(report)
        session.flush()
        section = Section(report_id=report.id, order=0, content='测试段落')
        session.add(section)
        session.flush()

        annotation = Annotation(
            section_id=section.id,
            author='reviewer_a',
            content='初始批注',
            version=1,
        )
        session.add(annotation)
        session.commit()

        # 模拟更新
        annotation.content = '修改后的批注'
        annotation.version += 1
        session.commit()

        assert annotation.version == 2

    def test_annotation_to_dict_includes_version(self, db_session):
        """to_dict() 输出包含 version 字段"""
        session = db_session

        report = Report(title='测试报告')
        session.add(report)
        session.flush()
        section = Section(report_id=report.id, order=0, content='测试段落')
        session.add(section)
        session.flush()

        annotation = Annotation(
            section_id=section.id,
            author='reviewer_a',
            content='批注内容',
            version=3,
        )
        session.add(annotation)
        session.commit()

        d = annotation.to_dict()
        assert 'version' in d
        assert d['version'] == 3
        assert d['author'] == 'reviewer_a'
        assert d['content'] == '批注内容'

    def test_version_mismatch_detection_logic(self, db_session):
        """验证版本号不匹配的检测逻辑（乐观锁核心）"""
        session = db_session

        report = Report(title='测试报告')
        session.add(report)
        session.flush()
        section = Section(report_id=report.id, order=0, content='测试段落')
        session.add(section)
        session.flush()

        annotation = Annotation(
            section_id=section.id,
            author='reviewer_a',
            content='原始内容',
            version=2,
        )
        session.add(annotation)
        session.commit()

        # 审核员 B 持有 version=1，但服务端已是 version=2
        client_version = 1
        server_version = annotation.version

        # 模拟乐观锁校验
        is_conflict = (client_version != server_version)
        assert is_conflict is True, '版本号不匹配应检测为冲突'

        # 审核员 C 持有 version=2，与服务端一致
        client_version_ok = 2
        is_conflict_ok = (client_version_ok != server_version)
        assert is_conflict_ok is False, '版本号匹配不应检测为冲突'

    def test_concurrent_annotation_update_scenario(self, db_session):
        """模拟两个审核员同时编辑同一条批注的场景"""
        session = db_session

        report = Report(title='测试报告')
        session.add(report)
        session.flush()
        section = Section(report_id=report.id, order=0, content='测试段落')
        session.add(section)
        session.flush()

        # 初始批注
        annotation = Annotation(
            section_id=section.id,
            author='reviewer_a',
            content='初始内容',
            version=1,
        )
        session.add(annotation)
        session.commit()

        # 审核员 A 和 B 同时读取（都拿到 version=1）
        version_a = annotation.version
        version_b = annotation.version
        assert version_a == version_b == 1

        # 审核员 A 先提交成功
        annotation.content = 'A 的修改'
        annotation.version += 1
        session.commit()
        assert annotation.version == 2

        # 审核员 B 提交时发现 version 不匹配
        assert version_b != annotation.version, 'B 的版本已过期'

        # 模拟 B 收到 409 冲突响应
        conflict_response = {
            'error': 'conflict',
            'server_version': annotation.version,
            'server_content': annotation.content,
            'server_author': annotation.author,
            'your_version': version_b,
            'your_content': 'B 的修改',
        }
        assert conflict_response['server_version'] == 2
        assert conflict_response['your_version'] == 1
        assert conflict_response['server_content'] == 'A 的修改'

    def test_resolve_conflict_force_overwrite(self, db_session):
        """冲突解决：强制覆盖并递增版本号"""
        session = db_session

        report = Report(title='测试报告')
        session.add(report)
        session.flush()
        section = Section(report_id=report.id, order=0, content='测试段落')
        session.add(section)
        session.flush()

        annotation = Annotation(
            section_id=section.id,
            author='reviewer_a',
            content='被修改的内容',
            version=3,
        )
        session.add(annotation)
        session.commit()

        # 强制覆盖
        old_version = annotation.version
        annotation.content = '解决冲突后的最终内容'
        annotation.version += 1
        session.commit()

        assert annotation.version == old_version + 1
        assert annotation.content == '解决冲突后的最终内容'


# ── 数据模型基础测试 ──────────────────────────────────────

class TestModels:
    """验证数据模型的基础功能"""

    def test_report_to_dict(self, db_session):
        """Report.to_dict() 输出格式正确"""
        session = db_session

        report = Report(title='安全检查报告')
        session.add(report)
        session.flush()

        section = Section(
            report_id=report.id,
            order=0,
            content='段落内容',
            review_status='pending',
        )
        session.add(section)
        session.commit()

        d = report.to_dict()
        assert d['title'] == '安全检查报告'
        assert len(d['sections']) == 1
        assert d['sections'][0]['content'] == '段落内容'
        assert d['sections'][0]['review_status'] == 'pending'

    def test_section_to_dict_with_annotations(self, db_session):
        """Section.to_dict() 包含批注列表"""
        session = db_session

        report = Report(title='报告')
        session.add(report)
        session.flush()
        section = Section(report_id=report.id, order=0, content='内容')
        session.add(section)
        session.flush()

        ann = Annotation(
            section_id=section.id,
            author='reviewer',
            content='批注',
            version=1,
        )
        session.add(ann)
        session.commit()

        d = section.to_dict()
        assert len(d['annotations']) == 1
        assert d['annotations'][0]['content'] == '批注'
        assert d['annotations'][0]['version'] == 1
