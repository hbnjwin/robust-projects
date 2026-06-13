#!/usr/bin/env python3
"""
Azure OpenAI 连接诊断工具
帮助排查连接和认证问题
"""

import requests
import json
from urllib.parse import urljoin

# 配置信息
AZURE_ENDPOINT = "https://bluecloud-bca-ai.openai.azure.com/"
API_KEY = "ff954f763ea14b7ea75e864136ee0eae"
API_VERSION = "2024-02-15-preview"
MODEL_NAME = "text-embedding-ada-002"

def test_basic_connectivity():
    """测试基本网络连接"""
    print("🌐 测试基本网络连接...")
    
    try:
        response = requests.get(AZURE_ENDPOINT, timeout=10)
        print(f"✅ 基本连接成功 (HTTP {response.status_code})")
        return True
    except requests.exceptions.Timeout:
        print("❌ 连接超时")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 连接错误 - 请检查URL是否正确")
        return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def test_azure_openai_api():
    """测试Azure OpenAI API端点"""
    print("\n🔍 测试Azure OpenAI API端点...")
    
    # 测试部署列表
    deployments_url = f"{AZURE_ENDPOINT}/openai/deployments?api-version={API_VERSION}"
    headers = {
        "api-key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        print(f"📡 请求URL: {deployments_url}")
        print(f"🔑 API密钥: {'*' * 20}{API_KEY[-4:]}")
        
        response = requests.get(deployments_url, headers=headers, timeout=10)
        print(f"📊 响应状态: HTTP {response.status_code}")
        
        if response.status_code == 200:
            deployments = response.json()
            print("✅ API认证成功!")
            print(f"📋 可用部署: {json.dumps(deployments, indent=2, ensure_ascii=False)}")
            
            # 检查目标模型是否存在
            if 'deployments' in deployments:
                model_found = False
                for deployment in deployments['deployments']:
                    if deployment.get('model') == MODEL_NAME:
                        model_found = True
                        print(f"✅ 找到目标模型: {MODEL_NAME}")
                        break
                
                if not model_found:
                    print(f"⚠️  未找到目标模型: {MODEL_NAME}")
                    print("📋 可用模型:")
                    for deployment in deployments['deployments']:
                        print(f"  - {deployment.get('model', 'Unknown')}")
            
            return True
        else:
            print(f"❌ API请求失败")
            print(f"📄 响应内容: {response.text}")
            
            # 根据状态码提供具体建议
            if response.status_code == 401:
                print("\n🔧 401错误解决方案:")
                print("1. 检查API密钥是否正确")
                print("2. 确认Azure OpenAI资源是否已创建")
                print("3. 检查密钥是否已过期")
            elif response.status_code == 404:
                print("\n🔧 404错误解决方案:")
                print("1. 检查端点URL是否正确")
                print("2. 确认API版本是否正确")
                print("3. 检查资源名称是否正确")
            elif response.status_code == 403:
                print("\n🔧 403错误解决方案:")
                print("1. 检查防火墙设置")
                print("2. 确认网络访问权限")
            
            return False
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_embedding_endpoint():
    """测试具体的embedding端点"""
    print(f"\n🧪 测试embedding端点...")
    
    embedding_url = f"{AZURE_ENDPOINT}/openai/deployments/{MODEL_NAME}/embeddings?api-version={API_VERSION}"
    headers = {
        "api-key": API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "input": "Hello, world!"
    }
    
    try:
        print(f"📡 请求URL: {embedding_url}")
        response = requests.post(embedding_url, headers=headers, json=data, timeout=10)
        print(f"📊 响应状态: HTTP {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Embedding端点测试成功!")
            print(f"📐 向量维度: {len(result['data'][0]['embedding'])}")
            return True
        else:
            print(f"❌ Embedding端点测试失败")
            print(f"📄 响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Embedding测试失败: {e}")
        return False

def check_common_issues():
    """检查常见问题"""
    print("\n🔍 常见问题检查:")
    
    # 检查端点格式
    if not AZURE_ENDPOINT.endswith('/'):
        print("⚠️  端点URL应该以'/'结尾")
    
    # 检查API密钥格式
    if len(API_KEY) != 32:
        print(f"⚠️  API密钥长度异常: {len(API_KEY)} (期望32)")
    
    # 检查模型名称
    valid_models = [
        "text-embedding-ada-002",
        "text-embedding-3-small", 
        "text-embedding-3-large"
    ]
    
    if MODEL_NAME not in valid_models:
        print(f"⚠️  模型名称可能不正确: {MODEL_NAME}")
        print(f"📋 常见模型: {', '.join(valid_models)}")

def provide_solutions():
    """提供解决方案建议"""
    print("\n🔧 解决方案建议:")
    print("1. 确认Azure OpenAI资源已正确创建")
    print("2. 检查API密钥是否从Azure门户正确复制")
    print("3. 确认端点URL格式正确: https://your-resource.openai.azure.com/")
    print("4. 检查模型部署名称是否正确")
    print("5. 确认API版本兼容性")
    print("6. 检查网络连接和防火墙设置")

if __name__ == "__main__":
    print("=" * 60)
    print("🔬 Azure OpenAI 连接诊断工具")
    print("=" * 60)
    
    # 显示配置
    print("📋 当前配置:")
    print(f"  端点: {AZURE_ENDPOINT}")
    print(f"  模型: {MODEL_NAME}")
    print(f"  API版本: {API_VERSION}")
    print(f"  API密钥: {'*' * 20}{API_KEY[-4:]}")
    print()
    
    # 执行诊断
    success_count = 0
    total_tests = 3
    
    if test_basic_connectivity():
        success_count += 1
    
    if test_azure_openai_api():
        success_count += 1
    
    if test_embedding_endpoint():
        success_count += 1
    
    # 检查常见问题
    check_common_issues()
    
    # 提供解决方案
    provide_solutions()
    
    # 总结
    print("\n" + "=" * 60)
    print(f"📊 诊断结果: {success_count}/{total_tests} 项测试通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过! 连接正常")
    else:
        print("💥 存在连接问题，请查看上述错误信息")
        print("\n📞 建议联系Azure管理员检查:")
        print("  - OpenAI资源状态")
        print("  - API密钥有效性") 
        print("  - 模型部署状态")
    
    print("=" * 60)
