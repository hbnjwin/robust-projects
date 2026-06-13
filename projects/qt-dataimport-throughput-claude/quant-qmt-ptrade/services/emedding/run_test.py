#!/usr/bin/env python3
"""
快速运行Azure OpenAI Embedding测试
"""

import subprocess
import sys
import os

def install_requirements():
    """安装依赖"""
    print("📦 正在安装依赖...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ 依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False

def run_test():
    """运行测试"""
    print("🚀 开始运行测试...")
    try:
        subprocess.check_call([sys.executable, "test_azure_embedding.py"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 测试运行失败: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Azure OpenAI Embedding 测试启动器")
    print("=" * 50)
    
    # 检查是否存在requirements.txt
    if os.path.exists("requirements.txt"):
        if not install_requirements():
            sys.exit(1)
    
    # 运行测试
    if run_test():
        print("\n🎉 测试完成!")
    else:
        print("\n💥 测试失败!")
        sys.exit(1)
