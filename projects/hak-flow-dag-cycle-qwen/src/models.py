# -*- coding: utf-8 -*-
"""数据模型 - 报告审核系统

包含报告、段落、审核状态和批注模型。
批注模型使用 version 字段实现乐观锁，用于并发冲突检测。

修复说明（问题3 - 冲突检测）：
    Annotation.version 字段是乐观锁的核心。每次更新批注时 version + 1，
    客户端提交更新时必须携带当前持有的 version，服务端校验：
    - 匹配 → 更新成功，version 自增
    - 不匹配 → 返回 409 Conflict，附带服务端最新内容供客户端合并
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Report(Base):
    """审核报告"""
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True)
    title = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sections = relationship('Section', back_populates='report', order_by='Section.order')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'sections': [s.to_dict() for s in self.sections],
        }


class Section(Base):
    """报告段落"""
    __tablename__ = 'sections'

    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)
    order = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False, default='')
    review_status = Column(
        Enum('pending', 'approved', 'flagged', name='review_status_enum'),
        nullable=False,
        default='pending',
    )
    reviewed_by = Column(String(128), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    report = relationship('Report', back_populates='sections')
    annotations = relationship('Annotation', back_populates='section', order_by='Annotation.created_at')

    def to_dict(self):
        return {
            'id': self.id,
            'report_id': self.report_id,
            'order': self.order,
            'content': self.content,
            'review_status': self.review_status,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'annotations': [a.to_dict() for a in self.annotations],
        }


class Annotation(Base):
    """段落批注 - version 字段用于乐观锁冲突检测

    并发控制流程：
    1. 客户端获取批注时记录 version
    2. 提交更新时携带 version
    3. 服务端比较 version：匹配则更新并 +1，不匹配则返回 409
    4. 客户端收到 409 后展示冲突解决界面
    """
    __tablename__ = 'annotations'

    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey('sections.id'), nullable=False)
    author = Column(String(128), nullable=False)
    content = Column(Text, nullable=False, default='')
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    section = relationship('Section', back_populates='annotations')

    def to_dict(self):
        return {
            'id': self.id,
            'section_id': self.section_id,
            'author': self.author,
            'content': self.content,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


def init_db(db_url='sqlite:///review.db'):
    """初始化数据库，返回 (engine, Session)"""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
