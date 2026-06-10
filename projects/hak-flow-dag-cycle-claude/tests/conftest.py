# -*- coding: utf-8 -*-
"""测试配置 - 使用内存 SQLite"""
import os
import pytest

# 在导入应用模块之前设置数据库URL为内存SQLite
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from src.models import Base, Report, Section, Annotation, init_db
from src.app import create_app


@pytest.fixture
def db_session():
    """每个测试使用独立的内存数据库"""
    engine, Session = init_db('sqlite:///:memory:')
    session = Session()
    yield session
    session.close()


@pytest.fixture
def app(monkeypatch):
    """Flask 测试应用"""
    engine, Session = init_db('sqlite:///:memory:')

    # 替换 db 模块中的 Session，让 API 使用测试数据库
    import src.db as db_module
    monkeypatch.setattr(db_module, 'Session', Session)

    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_client(client):
    """已有种子数据的测试客户端"""
    client.post('/api/seed')
    return client
