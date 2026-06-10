# -*- coding: utf-8 -*-
"""WebSocket 处理模块

解决三个核心同步问题:
1. 状态变更实时广播给所有连接的审核员
2. 心跳检测 + 断线感知
3. 版本号冲突检测与通知
"""
import json
import threading
import time

from flask import Blueprint
from flask_sock import Sock

ws_bp = Blueprint('ws', __name__)
sock = Sock()

# ── 连接管理 ──────────────────────────────────────────────
# 按 report_id 分组管理连接，每个连接存储 { ws, user_id, last_pong }
_rooms: dict[int, dict[str, dict]] = {}
_lock = threading.Lock()

HEARTBEAT_INTERVAL = 15  # 秒
HEARTBEAT_TIMEOUT = 45   # 超过此时间没有 pong 视为断开


def _add_client(report_id: int, user_id: str, ws):
    with _lock:
        if report_id not in _rooms:
            _rooms[report_id] = {}
        _rooms[report_id][user_id] = {
            'ws': ws,
            'last_pong': time.time(),
        }
    # 通知房间内其他人有新用户加入
    _broadcast(report_id, {
        'type': 'user_joined',
        'user_id': user_id,
        'online_users': list(_rooms.get(report_id, {}).keys()),
    }, exclude=None)


def _remove_client(report_id: int, user_id: str):
    with _lock:
        room = _rooms.get(report_id, {})
        room.pop(user_id, None)
        if not room:
            _rooms.pop(report_id, None)
    _broadcast(report_id, {
        'type': 'user_left',
        'user_id': user_id,
        'online_users': list(_rooms.get(report_id, {}).keys()),
    }, exclude=None)


def _broadcast(report_id: int, message: dict, exclude: str | None = None):
    """向房间内所有连接广播消息（可排除某个用户）"""
    with _lock:
        room = _rooms.get(report_id, {})
        clients = list(room.items())

    payload = json.dumps(message, ensure_ascii=False)
    dead = []
    for uid, client in clients:
        if uid == exclude:
            continue
        try:
            client['ws'].send(payload)
        except Exception:
            dead.append(uid)

    # 清理已断开的连接
    if dead:
        with _lock:
            room = _rooms.get(report_id, {})
            for uid in dead:
                room.pop(uid, None)


def broadcast_to_report(report_id: int, message: dict, exclude: str | None = None):
    """供 API 层调用的广播入口"""
    _broadcast(report_id, message, exclude)


# ── WebSocket 端点 ────────────────────────────────────────

def init_websocket(app):
    """初始化 WebSocket，绑定到 Flask app"""
    sock.init_app(app)


@sock.route('/ws/review/<int:report_id>')
def review_ws(ws, report_id):
    """审核协作 WebSocket 端点

    客户端连接时发送: {"type": "join", "user_id": "reviewer_a"}
    服务端周期性发送: {"type": "ping"}
    客户端须回复:     {"type": "pong"}
    """
    user_id = None
    try:
        # 等待客户端发送 join 消息
        raw = ws.receive(timeout=10)
        if not raw:
            return
        msg = json.loads(raw)
        if msg.get('type') != 'join' or not msg.get('user_id'):
            ws.send(json.dumps({'type': 'error', 'message': 'First message must be join with user_id'}))
            return

        user_id = msg['user_id']
        _add_client(report_id, user_id, ws)

        # 发送连接确认
        ws.send(json.dumps({
            'type': 'connected',
            'user_id': user_id,
            'report_id': report_id,
            'heartbeat_interval': HEARTBEAT_INTERVAL,
            'online_users': list(_rooms.get(report_id, {}).keys()),
        }))

        # 消息循环
        last_ping = time.time()
        while True:
            # 定期发送心跳
            now = time.time()
            if now - last_ping >= HEARTBEAT_INTERVAL:
                try:
                    ws.send(json.dumps({'type': 'ping', 'timestamp': now}))
                    last_ping = now
                except Exception:
                    break

            # 检查心跳超时
            with _lock:
                client = _rooms.get(report_id, {}).get(user_id)
                if client and now - client['last_pong'] > HEARTBEAT_TIMEOUT:
                    break

            # 接收客户端消息（短超时以允许心跳循环继续）
            try:
                raw = ws.receive(timeout=5)
            except Exception:
                # 超时继续循环，连接断开则退出
                continue

            if raw is None:
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            _handle_message(ws, report_id, user_id, msg)

    except Exception:
        pass
    finally:
        if user_id:
            _remove_client(report_id, user_id)


def _handle_message(ws, report_id: int, user_id: str, msg: dict):
    """处理客户端发来的 WebSocket 消息"""
    msg_type = msg.get('type')

    if msg_type == 'pong':
        # 更新心跳时间戳
        with _lock:
            client = _rooms.get(report_id, {}).get(user_id)
            if client:
                client['last_pong'] = time.time()

    elif msg_type == 'review_status':
        # 审核状态变更 — 广播给其他审核员
        # 实际的数据持久化由 REST API 处理，这里只负责广播
        _broadcast(report_id, {
            'type': 'review_status_changed',
            'section_id': msg.get('section_id'),
            'status': msg.get('status'),
            'reviewed_by': user_id,
            'timestamp': time.time(),
        }, exclude=user_id)

    elif msg_type == 'annotation_update':
        # 批注更新 — 广播给其他审核员（含 version 信息用于冲突检测）
        _broadcast(report_id, {
            'type': 'annotation_changed',
            'section_id': msg.get('section_id'),
            'annotation_id': msg.get('annotation_id'),
            'content': msg.get('content'),
            'author': user_id,
            'version': msg.get('version'),
            'timestamp': time.time(),
        }, exclude=user_id)

    elif msg_type == 'conflict_resolved':
        # 冲突解决通知
        _broadcast(report_id, {
            'type': 'conflict_resolved',
            'section_id': msg.get('section_id'),
            'annotation_id': msg.get('annotation_id'),
            'resolved_by': user_id,
            'chosen_version': msg.get('chosen_version'),
            'timestamp': time.time(),
        }, exclude=user_id)

    elif msg_type == 'cursor_position':
        # 光标位置同步（可选）
        _broadcast(report_id, {
            'type': 'cursor_position',
            'user_id': user_id,
            'section_id': msg.get('section_id'),
            'position': msg.get('position'),
        }, exclude=user_id)
