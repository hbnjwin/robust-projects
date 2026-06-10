# -*- coding: utf-8 -*-
"""WebSocket 连接管理测试"""
import time
import pytest

from src.websocket import (
    _rooms, _lock, _add_client, _remove_client,
    _broadcast, broadcast_to_report,
)


class FakeWebSocket:
    """模拟 WebSocket 连接"""

    def __init__(self):
        self.sent = []
        self.closed = False

    def send(self, data):
        if self.closed:
            raise ConnectionError('WebSocket closed')
        self.sent.append(data)

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def clean_rooms():
    """每个测试前清空房间"""
    with _lock:
        _rooms.clear()
    yield
    with _lock:
        _rooms.clear()


class TestConnectionManagement:
    """WebSocket 连接管理"""

    def test_add_client(self):
        ws = FakeWebSocket()
        _add_client(1, '审核员A', ws)

        assert 1 in _rooms
        assert '审核员A' in _rooms[1]

    def test_remove_client(self):
        ws = FakeWebSocket()
        _add_client(1, '审核员A', ws)
        _remove_client(1, '审核员A')

        # 房间为空时应自动清理
        assert 1 not in _rooms

    def test_multiple_users_in_room(self):
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()
        _add_client(1, '审核员A', ws_a)
        _add_client(1, '审核员B', ws_b)

        assert len(_rooms[1]) == 2

    def test_remove_one_keeps_room(self):
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()
        _add_client(1, '审核员A', ws_a)
        _add_client(1, '审核员B', ws_b)
        _remove_client(1, '审核员A')

        assert 1 in _rooms
        assert '审核员B' in _rooms[1]
        assert '审核员A' not in _rooms[1]

    def test_separate_rooms(self):
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()
        _add_client(1, '审核员A', ws_a)
        _add_client(2, '审核员B', ws_b)

        assert 1 in _rooms
        assert 2 in _rooms
        assert len(_rooms[1]) == 1
        assert len(_rooms[2]) == 1


class TestBroadcast:
    """问题1相关：状态变更广播"""

    def test_broadcast_to_all(self):
        """广播消息应发送给房间内所有用户"""
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()
        _add_client(1, '审核员A', ws_a)
        _add_client(1, '审核员B', ws_b)

        _broadcast(1, {'type': 'review_status_changed', 'section_id': 1, 'status': 'flagged'})

        assert len(ws_a.sent) > 0  # 包含 join 通知 + 广播
        assert len(ws_b.sent) > 0

    def test_broadcast_excludes_sender(self):
        """广播可以排除发送者"""
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()
        _add_client(1, '审核员A', ws_a)
        _add_client(1, '审核员B', ws_b)

        # 清空之前的 join 通知
        ws_a.sent.clear()
        ws_b.sent.clear()

        _broadcast(1, {'type': 'test'}, exclude='审核员A')

        assert len(ws_a.sent) == 0  # 被排除
        assert len(ws_b.sent) == 1  # 收到消息

    def test_broadcast_removes_dead_connections(self):
        """广播时自动清理已断开的连接"""
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()
        _add_client(1, '审核员A', ws_a)
        _add_client(1, '审核员B', ws_b)

        # 模拟 B 断开连接
        ws_b.closed = True

        _broadcast(1, {'type': 'test'}, exclude=None)

        # B 应被清理
        assert '审核员B' not in _rooms.get(1, {})

    def test_broadcast_to_empty_room(self):
        """向空房间广播不应报错"""
        _broadcast(999, {'type': 'test'})  # 不存在的房间

    def test_broadcast_to_report_api(self):
        """broadcast_to_report 供 API 层调用"""
        ws = FakeWebSocket()
        _add_client(1, '审核员A', ws)
        ws.sent.clear()

        broadcast_to_report(1, {
            'type': 'review_status_changed',
            'section_id': 1,
            'status': 'flagged',
            'reviewed_by': '审核员B',
        })

        assert len(ws.sent) == 1
        import json
        msg = json.loads(ws.sent[0])
        assert msg['type'] == 'review_status_changed'
        assert msg['status'] == 'flagged'


class TestHeartbeat:
    """问题2相关：心跳检测"""

    def test_client_has_last_pong(self):
        """新连接应记录 last_pong 时间"""
        ws = FakeWebSocket()
        before = time.time()
        _add_client(1, '审核员A', ws)

        client = _rooms[1]['审核员A']
        assert client['last_pong'] >= before

    def test_join_notifies_others(self):
        """用户加入时应通知房间内其他用户"""
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()
        _add_client(1, '审核员A', ws_a)
        ws_a.sent.clear()

        _add_client(1, '审核员B', ws_b)

        # 审核员A应收到审核员B加入的通知
        import json
        join_msgs = [json.loads(m) for m in ws_a.sent if 'user_joined' in m]
        assert len(join_msgs) == 1
        assert '审核员B' in join_msgs[0]['online_users']

    def test_leave_notifies_others(self):
        """用户离开时应通知房间内其他用户"""
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()
        _add_client(1, '审核员A', ws_a)
        _add_client(1, '审核员B', ws_b)
        ws_a.sent.clear()

        _remove_client(1, '审核员B')

        import json
        leave_msgs = [json.loads(m) for m in ws_a.sent if 'user_left' in m]
        assert len(leave_msgs) == 1
        assert '审核员B' not in leave_msgs[0]['online_users']
