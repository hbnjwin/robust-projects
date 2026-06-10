# -*- coding: utf-8 -*-
"""数据库会话管理 - 避免循环引用"""
import os
from .models import init_db

db_url = os.environ.get('DATABASE_URL', 'sqlite:///review.db')
engine, Session = init_db(db_url)
