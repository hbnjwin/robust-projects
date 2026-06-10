# -*- coding: utf-8 -*-
"""REST API 测试 - 重点测试三个核心场景的后端逻辑"""
import json
import pytest


class TestReviewStatusBroadcast:
    """问题1：审核状态变更应能正确更新并广播"""

    def test_update_review_status(self, seeded_client):
        """审核员标记段落为 'flagged' 后，GET 返回最新状态"""
        # 获取初始报告
        res = seeded_client.get('/api/reports/1')
        assert res.status_code == 200
        report = res.get_json()
        section_id = report['sections'][0]['id']

        # 初始状态应为 pending
        assert report['sections'][0]['review_status'] == 'pending'

        # 审核员A标记为有问题
        res = seeded_client.put(f'/api/sections/{section_id}/review', json={
            'status': 'flagged',
            'reviewed_by': '审核员A',
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data['review_status'] == 'flagged'
        assert data['reviewed_by'] == '审核员A'

        # 重新获取报告，验证状态已持久化
        res = seeded_client.get('/api/reports/1')
        report = res.get_json()
        assert report['sections'][0]['review_status'] == 'flagged'

    def test_update_to_approved(self, seeded_client):
        """审核员可以将段落标记为通过"""
        res = seeded_client.get('/api/reports/1')
        section_id = res.get_json()['sections'][1]['id']

        res = seeded_client.put(f'/api/sections/{section_id}/review', json={
            'status': 'approved',
            'reviewed_by': '审核员B',
        })
        assert res.status_code == 200
        assert res.get_json()['review_status'] == 'approved'

    def test_update_nonexistent_section(self, seeded_client):
        """更新不存在的段落应返回 404"""
        res = seeded_client.put('/api/sections/9999/review', json={
            'status': 'flagged',
            'reviewed_by': '审核员A',
        })
        assert res.status_code == 404


class TestConflictDetection:
    """问题3：并发修改批注时的乐观锁冲突检测"""

    def _create_annotation(self, client, section_id):
        """辅助：创建一个批注并返回"""
        res = client.post(f'/api/sections/{section_id}/annotations', json={
            'author': '审核员A',
            'content': '初始批注内容',
        })
        assert res.status_code == 201
        return res.get_json()

    def test_normal_update_with_correct_version(self, seeded_client):
        """版本号匹配时正常更新"""
        res = seeded_client.get('/api/reports/1')
        section_id = res.get_json()['sections'][0]['id']
        ann = self._create_annotation(seeded_client, section_id)

        assert ann['version'] == 1

        # 用正确的 version 更新
        res = seeded_client.put(f'/api/annotations/{ann["id"]}', json={
            'content': '更新后的批注',
            'author': '审核员A',
            'version': 1,
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data['content'] == '更新后的批注'
        assert data['version'] == 2  # 版本号自增

    def test_conflict_returns_409(self, seeded_client):
        """两个审核员同时编辑 — 后提交者收到 409 冲突"""
        res = seeded_client.get('/api/reports/1')
        section_id = res.get_json()['sections'][0]['id']
        ann = self._create_annotation(seeded_client, section_id)

        # 审核员A和B同时拿到 version=1
        # 审核员A先提交 → 成功，version 变为 2
        res = seeded_client.put(f'/api/annotations/{ann["id"]}', json={
            'content': 'A的修改',
            'author': '审核员A',
            'version': 1,
        })
        assert res.status_code == 200
        assert res.get_json()['version'] == 2

        # 审核员B后提交，仍持有 version=1 → 应返回 409
        res = seeded_client.put(f'/api/annotations/{ann["id"]}', json={
            'content': 'B的修改',
            'author': '审核员B',
            'version': 1,  # 过期的版本号！
        })
        assert res.status_code == 409
        conflict_data = res.get_json()
        assert conflict_data['error'] == 'conflict'
        assert conflict_data['server_version'] == 2
        assert conflict_data['server_content'] == 'A的修改'
        assert conflict_data['your_content'] == 'B的修改'

    def test_conflict_after_multiple_updates(self, seeded_client):
        """经过多次更新后，过期版本依然被正确检测"""
        res = seeded_client.get('/api/reports/1')
        section_id = res.get_json()['sections'][0]['id']
        ann = self._create_annotation(seeded_client, section_id)

        # 连续更新 3 次
        for i in range(3):
            res = seeded_client.put(f'/api/annotations/{ann["id"]}', json={
                'content': f'第{i+1}次修改',
                'author': '审核员A',
                'version': i + 1,
            })
            assert res.status_code == 200

        # 现在 version=4，用 version=2 提交应冲突
        res = seeded_client.put(f'/api/annotations/{ann["id"]}', json={
            'content': '过期的修改',
            'author': '审核员B',
            'version': 2,
        })
        assert res.status_code == 409
        assert res.get_json()['server_version'] == 4

    def test_resolve_conflict(self, seeded_client):
        """冲突解决 — 使用 force 覆盖"""
        res = seeded_client.get('/api/reports/1')
        section_id = res.get_json()['sections'][0]['id']
        ann = self._create_annotation(seeded_client, section_id)

        # 制造冲突
        seeded_client.put(f'/api/annotations/{ann["id"]}', json={
            'content': 'A的修改', 'author': '审核员A', 'version': 1,
        })

        # 强制解决冲突
        res = seeded_client.put(f'/api/annotations/{ann["id"]}/resolve-conflict', json={
            'content': 'B选择保留的最终内容',
            'author': '审核员B',
            'force': True,
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data['content'] == 'B选择保留的最终内容'
        assert data['version'] == 3  # 又递增了

    def test_resolve_without_force_fails(self, seeded_client):
        """不带 force 标志无法解决冲突"""
        res = seeded_client.get('/api/reports/1')
        section_id = res.get_json()['sections'][0]['id']
        ann = self._create_annotation(seeded_client, section_id)

        res = seeded_client.put(f'/api/annotations/{ann["id"]}/resolve-conflict', json={
            'content': '尝试覆盖',
            'author': '审核员B',
        })
        assert res.status_code == 400

    def test_version_required(self, seeded_client):
        """更新批注时必须提供 version 字段"""
        res = seeded_client.get('/api/reports/1')
        section_id = res.get_json()['sections'][0]['id']
        ann = self._create_annotation(seeded_client, section_id)

        res = seeded_client.put(f'/api/annotations/{ann["id"]}', json={
            'content': '没有version的更新',
            'author': '审核员A',
            # 缺少 version!
        })
        assert res.status_code == 400


class TestAnnotationCRUD:
    """批注基本操作"""

    def test_create_annotation(self, seeded_client):
        res = seeded_client.get('/api/reports/1')
        section_id = res.get_json()['sections'][0]['id']

        res = seeded_client.post(f'/api/sections/{section_id}/annotations', json={
            'author': '审核员A',
            'content': '这里需要补充数据来源',
        })
        assert res.status_code == 201
        data = res.get_json()
        assert data['author'] == '审核员A'
        assert data['version'] == 1
        assert data['section_id'] == section_id

    def test_annotation_in_report(self, seeded_client):
        """创建的批注应出现在报告数据中"""
        res = seeded_client.get('/api/reports/1')
        section_id = res.get_json()['sections'][0]['id']

        seeded_client.post(f'/api/sections/{section_id}/annotations', json={
            'author': '审核员A',
            'content': '测试批注_unique_marker',
        })

        res = seeded_client.get('/api/reports/1')
        section = res.get_json()['sections'][0]
        contents = [a['content'] for a in section['annotations']]
        assert '测试批注_unique_marker' in contents


class TestSeedData:
    """种子数据"""

    def test_seed_creates_report(self, client):
        res = client.post('/api/seed')
        assert res.status_code == 201
        data = res.get_json()
        assert '风电场' in data['title']
        assert len(data['sections']) == 4

    def test_get_nonexistent_report(self, client):
        res = client.get('/api/reports/999')
        assert res.status_code == 404
