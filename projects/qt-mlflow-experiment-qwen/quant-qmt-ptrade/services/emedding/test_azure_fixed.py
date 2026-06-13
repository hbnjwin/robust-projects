#!/usr/bin/env python3
"""
修复版Azure OpenAI测试脚本
解决了URL格式和常见配置问题
"""

import os
import sys
import time
from typing import List

try:
    import openai
    from openai import AzureOpenAI
except ImportError:
    print("❌ 错误: 需要安装openai库")
    print("请运行: pip install openai")
    sys.exit(1)

# Azure OpenAI 配置 (修复版)
AZURE_ENDPOINT = "https://bluecloud-bca-ai.openai.azure.com"  # 移除末尾斜杠
API_KEY = "ff954f763ea14b7ea75e864136ee0eae"
API_VERSION = "2024-02-15-preview"
MODEL_NAME = "text-embedding-ada-002"

def test_with_openai_sdk():
    """使用OpenAI SDK测试"""
    print("🚀 使用OpenAI SDK测试...")
    
    try:
        # 创建客户端
        client = AzureOpenAI(
            azure_endpoint=AZURE_ENDPOINT,
            api_key=API_KEY,
            api_version=API_VERSION
        )
        
        # 测试文本
        test_text = "Hello, this is a test for Azure OpenAI embedding."
        
        print(f"📝 测试文本: {test_text}")
        print("🔄 正在调用embedding API...")
        
        start_time = time.time()
        
        # 调用API
        response = client.embeddings.create(
            model=MODEL_NAME,
            input=test_text
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if response and response.data:
            embedding = response.data[0].embedding
            print(f"✅ API调用成功!")
            print(f"⏱️  响应时间: {duration:.2f}秒")
            print(f"📐 向量维度: {len(embedding)}")
            print(f"📈 前5个值: {embedding[:5]}")
            
            # 验证维度
            if len(embedding) == 1536:
                print("✅ 向量维度正确 (1536)")
            else:
                print(f"⚠️  向量维度异常: {len(embedding)} (期望1536)")
            
            return True
        else:
            print("❌ 响应为空")
            return False
            
    except openai.AuthenticationError as e:
        print(f"❌ 认证错误: {e}")
        print("\n🔧 解决方案:")
        print("1. 检查API密钥是否正确")
        print("2. 确认Azure OpenAI资源状态")
        print("3. 检查密钥是否已过期")
        return False
        
    except openai.NotFoundError as e:
        print(f"❌ 资源未找到: {e}")
        print("\n🔧 解决方案:")
        print("1. 检查端点URL是否正确")
        print("2. 确认模型部署名称")
        print("3. 检查API版本")
        return False
        
    except openai.RateLimitError as e:
        print(f"❌ 速率限制: {e}")
        return False
        
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False

def test_with_requests():
    """使用requests直接测试API"""
    print("\n🌐 使用requests直接测试API...")
    
    import requests
    
    # 构建正确的URL
    embedding_url = f"{AZURE_ENDPOINT}/openai/deployments/{MODEL_NAME}/embeddings?api-version={API_VERSION}"
    
    headers = {
        "api-key": API_KEY,
        "Content-Type": "application/json"
    }
    
    data = {
        "input": "Hello world"
    }
    
    try:
        print(f"📡 请求URL: {embedding_url}")
        
        response = requests.post(embedding_url, headers=headers, json=data, timeout=10)
        
        print(f"📊 响应状态: HTTP {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            embedding = result['data'][0]['embedding']
            print(f"✅ 直接API调用成功!")
            print(f"📐 向量维度: {len(embedding)}")
            return True
        else:
            print(f"❌ API调用失败")
            print(f"📄 响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def check_configuration():
    """检查配置信息"""
    print("\n🔍 配置检查:")
    
    print(f"📍 端点: {AZURE_ENDPOINT}")
    print(f"🤖 模型: {MODEL_NAME}")
    print(f"🔑 API密钥: {'*' * 20}{API_KEY[-4:]}")
    print(f"📋 API版本: {API_VERSION}")
    
    # 检查常见问题
    issues = []
    
    if AZURE_ENDPOINT.endswith('//'):
        issues.append("端点URL包含双斜杠")
    
    if len(API_KEY) != 32:
        issues.append(f"API密钥长度异常: {len(API_KEY)}")
    
    if issues:
        print("\n⚠️  发现问题:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ 配置检查通过")

def provide_troubleshooting():
    """提供故障排除指南"""
    print("\n🔧 故障排除指南:")
    print("1. 确认Azure OpenAI资源已创建")
    print("2. 检查资源名称: 'bluecloud-bca-ai'")
    print("3. 确认模型已部署: 'text-embedding-ada-002'")
    print("4. 检查API密钥是否有效")
    print("5. 确认区域: East US")
    print("6. 验证网络连接")
    
    print("\n📋 Azure门户检查清单:")
    print("□ Azure OpenAI资源存在")
    print("□ 资源名称正确: bluecloud-bca-ai")
    print("□ API密钥有效且未过期")
    print("□ text-embedding-ada-002模型已部署")
    print("□ 部署名称与MODEL_NAME一致")
    print("□ 网络访问权限正常")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Azure OpenAI Embedding 修复版测试")
    print("=" * 60)
    
    # 检查配置
    check_configuration()
    
    # 执行测试
    success_count = 0
    total_tests = 2
    
    if test_with_openai_sdk():
        success_count += 1
    
    if test_with_requests():
        success_count += 1
    
    # 提供故障排除
    provide_troubleshooting()
    
    # 总结
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {success_count}/{total_tests} 项通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过! Azure OpenAI Embedding工作正常")
    else:
        print("💥 测试失败，请查看上述错误信息")
        print("\n💡 建议:")
        print("1. 检查Azure门户中的资源配置")
        print("2. 验证API密钥和端点URL")
        print("3. 确认模型部署状态")
    
    print("=" * 60)
