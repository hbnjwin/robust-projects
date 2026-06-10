# -*- coding: utf-8 -*-
"""REST API - 报告审核接口

批注更新接口使用乐观锁（version 校验）实现并发冲突检测（问题3）。
状态变更通过 WebSocket 广播给在线审核员（问题1）。
"""
import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, render_template

from .models import Report, Section, Annotation
from .db import Session
from .websocket import broadcast_to_report

api_bp = Blueprint('api', __name__)


# ── 页面路由 ──────────────────────────────────────────────

@api_bp.route('/')
def index():
    return render_template('index.html')


# ── 报告 ──────────────────────────────────────────────────

@api_bp.route('/api/reports', methods=['POST'])
def create_report():
    data = request.get_json()
    session = Session()
    try:
        report = Report(title=data['title'])
        session.add(report)
        session.flush()
        for i, sec in enumerate(data.get('sections', [])):
            section = Section(
                report_id=report.id,
                order=i,
                content=sec.get('content', ''),
            )
            session.add(section)
        session.commit()
        session.refresh(report)
        return jsonify(report.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        session.close()


@api_bp.route('/api/reports/<int:report_id>')
def get_report(report_id):
    session = Session()
    try:
        report = session.get(Report, report_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        return jsonify(report.to_dict())
    finally:
        session.close()


# ── 审核状态更新 ──────────────────────────────────────────

@api_bp.route('/api/sections/<int:section_id>/review', methods=['PUT'])
def update_review_status(section_id):
    """更新段落审核状态，并通过 WebSocket 广播变更

    问题1修复：API 完成持久化后广播 review_status_changed 消息，
    客户端 WebSocket handler 收到后更新响应式状态并触发视图刷新。
    """
    data = request.get_json()
    session = Session()
    try:
        section = session.get(Section, section_id)
        if not section:
            return jsonify({'error': 'Section not found'}), 404

        section.review_status = data['status']
        section.reviewed_by = data.get('reviewed_by', '')
        section.reviewed_at = datetime.now(timezone.utc)
        session.commit()

        # 通过 WebSocket 广播状态变更（问题1）
        broadcast_to_report(section.report_id, {
            'type': 'review_status_changed',
            'section_id': section.id,
            'status': section.review_status,
            'reviewed_by': section.reviewed_by,
            'reviewed_at': section.reviewed_at.isoformat(),
        })

        return jsonify(section.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        session.close()


# ── 批注 CRUD（带冲突检测）────────────────────────────────

@api_bp.route('/api/sections/<int:section_id>/annotations', methods=['POST'])
def create_annotation(section_id):
    """创建新批注"""
    data = request.get_json()
    session = Session()
    try:
        section = session.get(Section, section_id)
        if not section:
            return jsonify({'error': 'Section not found'}), 404

        annotation = Annotation(
            section_id=section_id,
            author=data['author'],
            content=data['content'],
            version=1,
        )
        session.add(annotation)
        session.commit()
        session.refresh(annotation)

        # 广播新批注
        broadcast_to_report(section.report_id, {
            'type': 'annotation_created',
            'section_id': section_id,
            'annotation': annotation.to_dict(),
        })

        return jsonify(annotation.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        session.close()


@api_bp.route('/api/annotations/<int:annotation_id>', methods=['PUT'])
def update_annotation(annotation_id):
    """更新批注内容 - 使用乐观锁检测并发冲突（问题3核心修复）

    客户端须提交当前持有的 version，服务端校验：
    - version 匹配 → 更新成功，version + 1，广播变更
    - version 不匹配 → 返回 409 Conflict，附带当前最新内容供客户端合并

    冲突响应格式（409）：
    {
        "error": "conflict",
        "message": "...",
        "server_version": 3,        # 服务端当前版本
        "server_content": "...",    # 服务端当前内容
        "server_author": "...",     # 最后修改者
        "your_version": 2,          # 客户端持有的版本
        "your_content": "..."       # 客户端提交的内容
    }
    """
    data = request.get_json()
    session = Session()
    try:
        annotation = session.get(Annotation, annotation_id)
        if not annotation:
            return jsonify({'error': 'Annotation not found'}), 404

        client_version = data.get('version')
        if client_version is None:
            return jsonify({'error': 'version is required for optimistic locking'}), 400

        # ── 乐观锁校验（问题3） ──
        if annotation.version != client_version:
            # 版本冲突！返回当前服务端数据供客户端解决冲突
            section = session.get(Section, annotation.section_id)
            broadcast_to_report(section.report_id if section else 0, {
                'type': 'conflict_detected',
                'annotation_id': annotation.id,
                'section_id': annotation.section_id,
                'your_version': client_version,
                'server_version': annotation.version,
                'server_content': annotation.content,
                'server_author': annotation.author,
            })
            return jsonify({
                'error': 'conflict',
                'message': 'This annotation has been modified by another reviewer',
                'server_version': annotation.version,
                'server_content': annotation.content,
                'server_author': annotation.author,
                'your_version': client_version,
                'your_content': data.get('content', ''),
            }), 409

        # 版本匹配，执行更新
        annotation.content = data['content']
        annotation.author = data.get('author', annotation.author)
        annotation.version += 1
        annotation.updated_at = datetime.now(timezone.utc)
        session.commit()

        # 广播更新
        section = session.get(Section, annotation.section_id)
        broadcast_to_report(section.report_id if section else 0, {
            'type': 'annotation_changed',
            'section_id': annotation.section_id,
            'annotation': annotation.to_dict(),
        })

        return jsonify(annotation.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        session.close()


@api_bp.route('/api/annotations/<int:annotation_id>/resolve-conflict', methods=['PUT'])
def resolve_conflict(annotation_id):
    """解决冲突 - 强制使用指定内容覆盖（问题3）

    需要提供 force: true 确认覆盖操作。
    解决后广播 conflict_resolved 通知其他审核员。
    """
    data = request.get_json()
    session = Session()
    try:
        annotation = session.get(Annotation, annotation_id)
        if not annotation:
            return jsonify({'error': 'Annotation not found'}), 404

        if not data.get('force'):
            return jsonify({'error': 'Must set force: true to resolve conflict'}), 400

        annotation.content = data['content']
        annotation.author = data.get('author', annotation.author)
        annotation.version += 1
        annotation.updated_at = datetime.now(timezone.utc)
        session.commit()

        section = session.get(Section, annotation.section_id)
        broadcast_to_report(section.report_id if section else 0, {
            'type': 'conflict_resolved',
            'section_id': annotation.section_id,
            'annotation': annotation.to_dict(),
            'resolved_by': data.get('author', ''),
        })

        return jsonify(annotation.to_dict())
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        session.close()


# ── 种子数据（开发用）─────────────────────────────────────

@api_bp.route('/api/seed', methods=['POST'])
def seed_data():
    """创建示例报告用于测试"""
    session = Session()
    try:
        report = Report(title='风电场安全检查报告 - 2024Q1')
        session.add(report)
        session.flush()

        sections_data = [
            '一、风机基础检查：基础环螺栓扭矩抽检结果显示，3号机组存在2处扭矩不达标。',
            '二、叶片状态评估：全场15台机组叶片目视检查完成，未发现明显裂纹或前缘侵蚀。',
            '三、电气系统：变频器运行参数正常，主变压器油温在允许范围内，绝缘电阻测试合格。',
            '四、安全防护设施：塔筒内部攀爬系统、防坠落装置检查合格，消防设施在有效期内。',
        ]
        for i, content in enumerate(sections_data):
            session.add(Section(report_id=report.id, order=i, content=content))

        session.commit()
        session.refresh(report)
        return jsonify(report.to_dict()), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        session.close()
