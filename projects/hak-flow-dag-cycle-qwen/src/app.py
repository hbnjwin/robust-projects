# -*- coding: utf-8 -*-
"""Flask 应用入口 - 报告审核协作系统"""
import os

from flask import Flask

from .websocket import init_websocket


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

    from .api import api_bp
    app.register_blueprint(api_bp)

    init_websocket(app)

    return app
