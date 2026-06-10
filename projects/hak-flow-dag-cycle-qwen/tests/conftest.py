# -*- coding: utf-8 -*-
"""pytest 配置和共享 fixtures"""
import sys
import os

# 确保 src 包可以被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from src.app import create_app
from src.models import init_db


@pytest.fixture
def app():
    """创建测试用 Flask app"""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()


@pytest.fixture
def db_session():
    """独立的数据库会话（每个测试使用内存数据库）"""
    engine, Session = init_db('sqlite://')
    session = Session()
    yield session
    session.close()
