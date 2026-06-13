#!/usr/bin/env python3
"""测试 Redis 连接是否正常"""

import redis
import sys


def test_redis_connection(host: str, port: int) -> bool:
    """测试 Redis 连接
    
    Args:
        host: Redis 服务器地址
        port: Redis 端口
        
    Returns:
        bool: 连接成功返回 True，失败返回 False
    """
    try:
        # 创建 Redis 客户端，设置短超时
        client = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # 执行 PING 命令测试连接
        response = client.ping()
        
        if response:
            print(f"✓ Redis 连接成功: {host}:{port}")
            print(f"  PING 响应: {response}")
            return True
        else:
            print(f"✗ Redis PING 返回异常: {host}:{port}")
            return False
            
    except redis.ConnectionError as e:
        print(f"✗ Redis 连接失败: {host}:{port}")
        print(f"  错误: {e}")
        return False
    except redis.TimeoutError as e:
        print(f"✗ Redis 连接超时: {host}:{port}")
        print(f"  错误: {e}")
        return False
    except Exception as e:
        print(f"✗ Redis 连接异常: {host}:{port}")
        print(f"  错误: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    # Redis 配置
    REDIS_HOST = "192.168.3.42"
    REDIS_PORT = 6379
    
    print(f"测试 Redis 连接: {REDIS_HOST}:{REDIS_PORT}")
    print("-" * 40)
    
    success = test_redis_connection(REDIS_HOST, REDIS_PORT)
    
    sys.exit(0 if success else 1)
