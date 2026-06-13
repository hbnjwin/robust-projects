#!/usr/bin/env python3
"""
测试Azure OpenAI Text Embedding模型连接
测试text-embedding-ada-002模型是否可以正常工作
"""

import os
import sys
from typing import List
import time

try:
    import openai
    from openai import AzureOpenAI
except ImportError:
    print("❌ 错误: 需要安装openai库")
    print("请运行: pip install openai")
    sys.exit(1)

# Azure OpenAI 配置
AZURE_ENDPOINT = "https://bluecloud-bca-ai.openai.azure.com/"
API_KEY = "ff954f763ea14b7ea75e864136ee0eae"
API_VERSION = "2024-02-15-preview"
MODEL_NAME = "text-embedding-ada-002"

def test_azure_embedding():
    """测试Azure OpenAI Embedding模型"""
    print("🔍 开始测试Azure OpenAI Embedding模型...")
    print(f"📍 端点: {AZURE_ENDPOINT}")
    print(f"🤖 模型: {MODEL_NAME}")
    print(f"🌐 区域: East US")
    print("-" * 50)
    
    try:
        # 创建Azure OpenAI客户端
        client = AzureOpenAI(
            azure_endpoint=AZURE_ENDPOINT,
            api_key=API_KEY,
            api_version=API_VERSION
        )
        
        # 测试文本
        test_texts = [
            "Hello, this is a test message.",
            "这是一个中文测试消息。",
            "The quick brown fox jumps over the lazy dog."
        ]
        
        print(f"📝 测试文本数量: {len(test_texts)}")
        
        # 记录开始时间
        start_time = time.time()
        
        # 调用embedding API
        print("🚀 正在调用embedding API...")
        response = client.embeddings.create(
            model=MODEL_NAME,
            input=test_texts
        )
        
        # 计算耗时
        end_time = time.time()
        duration = end_time - start_time
        
        # 验证响应
        if response and response.data:
            print("✅ API调用成功!")
            print(f"⏱️  响应时间: {duration:.2f}秒")
            print(f"📊 返回向量数量: {len(response.data)}")
            
            # 检查每个向量的维度
            for i, embedding in enumerate(response.data):
                vector = embedding.embedding
                print(f"  📐 文本 {i+1} 向量维度: {len(vector)}")
                
                # 验证向量维度是否正确 (ada-002应该是1536维)
                if len(vector) != 1536:
                    print(f"  ⚠️  警告: 期望维度1536，实际维度{len(vector)}")
                else:
                    print(f"  ✅ 向量维度正确")
                
                # 显示向量前几个值作为示例
                print(f"  📈 向量前5个值: {vector[:5]}")
            
            # 测试单个文本embedding
            print("\n🔍 测试单个文本embedding...")
            single_response = client.embeddings.create(
                model=MODEL_NAME,
                input="Single test text"
            )
            
            if single_response and single_response.data:
                single_vector = single_response.data[0].embedding
                print(f"✅ 单文本测试成功，向量维度: {len(single_vector)}")
                
                # 计算向量相似度（测试一致性）
                print("\n🔄 测试向量一致性...")
                same_text_response = client.embeddings.create(
                    model=MODEL_NAME,
                    input="Hello, this is a test message."
                )
                
                if same_text_response and same_text_response.data:
                    same_vector = same_text_response.data[0].embedding
                    # 简单的余弦相似度计算
                    dot_product = sum(a * b for a, b in zip(vector, same_vector))
                    norm_a = sum(a * a for a in vector) ** 0.5
                    norm_b = sum(b * b for b in same_vector) ** 0.5
                    similarity = dot_product / (norm_a * norm_b)
                    
                    print(f"📏 相同文本的余弦相似度: {similarity:.6f}")
                    if similarity > 0.999:
                        print("✅ 向量一致性测试通过")
                    else:
                        print("⚠️  向量一致性可能有问题")
            
            print("\n🎉 所有测试通过! Azure OpenAI Embedding模型工作正常")
            return True
            
        else:
            print("❌ 错误: API响应为空")
            return False
            
    except openai.APIError as e:
        print(f"❌ OpenAI API错误: {e}")
        return False
    except openai.RateLimitError as e:
        print(f"❌ 速率限制错误: {e}")
        return False
    except openai.AuthenticationError as e:
        print(f"❌ 认证错误: {e}")
        print("请检查API密钥是否正确")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False

def test_connection_info():
    """测试连接信息"""
    print("🌐 连接信息测试:")
    print(f"端点: {AZURE_ENDPOINT}")
    print(f"API版本: {API_VERSION}")
    print(f"模型: {MODEL_NAME}")
    
    # 测试网络连通性
    try:
        import requests
        response = requests.get(f"{AZURE_ENDPOINT}/openai/deployments?api-version={API_VERSION}", 
                              headers={"api-key": API_KEY}, timeout=10)
        if response.status_code == 200:
            print("✅ 网络连接正常")
        else:
            print(f"⚠️  网络连接异常: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ 网络连接测试失败: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Azure OpenAI Text Embedding 连接测试")
    print("=" * 60)
    
    # 显示配置信息
    print("📋 配置信息:")
    print(f"  Azure Endpoint: {AZURE_ENDPOINT}")
    print(f"  Model: {MODEL_NAME}")
    print(f"  Region: East US")
    print(f"  API Key: {'*' * 20}{API_KEY[-4:]}")  # 只显示最后4位
    print()
    
    # 测试连接信息
    test_connection_info()
    print()
    
    # 执行主要测试
    success = test_azure_embedding()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 测试结果: 成功 ✅")
        print("Azure OpenAI Embedding模型可以正常使用")
    else:
        print("💥 测试结果: 失败 ❌")
        print("请检查配置和网络连接")
    print("=" * 60)
