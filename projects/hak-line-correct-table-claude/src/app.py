# -*- coding: utf-8 -*-
"""Flask应用入口。"""
import os

from flask import Flask


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder='static',
        template_folder='templates',
    )

    report_dir = os.environ.get('REPORT_DIR', os.path.join(os.path.dirname(__file__), 'reports'))
    os.makedirs(report_dir, exist_ok=True)

    from src.api.download import download_bp
    app.register_blueprint(download_bp)

    @app.route('/')
    def index():
        from flask import render_template
        return render_template('download_demo.html')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
