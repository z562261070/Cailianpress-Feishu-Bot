#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书Bot配置测试脚本
用于验证飞书Bot配置是否正确
"""

import os
import sys
import json
import requests
from pathlib import Path

def test_feishu_bot_config():
    """测试飞书Bot配置"""
    print("🔍 开始测试飞书Bot配置...")
    
    # 检查环境变量
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")
    chat_id = os.getenv("FEISHU_CHAT_ID", "")
    
    if not app_id:
        print("❌ 错误: 未设置 FEISHU_APP_ID 环境变量")
        return False
    
    if not app_secret:
        print("❌ 错误: 未设置 FEISHU_APP_SECRET 环境变量")
        return False
    
    if not chat_id:
        print("❌ 错误: 未设置 FEISHU_CHAT_ID 环境变量")
        return False
    
    print(f"✅ 环境变量检查通过")
    print(f"   App ID: {app_id[:10]}...")
    print(f"   Chat ID: {chat_id[:10]}...")
    
    # 测试获取访问令牌
    print("\n🔑 测试获取访问令牌...")
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    payload = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    
    try:
        response = requests.post(token_url, json=payload, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        if data.get("code") == 0:
            access_token = data.get("tenant_access_token")
            print("✅ 访问令牌获取成功")
            print(f"   Token: {access_token[:20]}...")
        else:
            print(f"❌ 获取访问令牌失败: {data.get('msg', '未知错误')}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 获取访问令牌出错: {e}")
        return False
    
    # 测试发送文本消息
    print("\n💬 测试发送文本消息...")
    message_url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    content = {
        "text": "🤖 飞书Bot配置测试消息\n\n这是一条测试消息，用于验证Bot配置是否正确。\n\n如果您看到这条消息，说明配置成功！"
    }
    
    payload = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps(content)
    }
    
    try:
        response = requests.post(
            f"{message_url}?receive_id_type=chat_id",
            headers=headers,
            json=payload,
            timeout=15
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get("code") == 0:
            print("✅ 测试消息发送成功")
            print("   请检查飞书群聊是否收到测试消息")
        else:
            print(f"❌ 发送测试消息失败: {data.get('msg', '未知错误')}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 发送消息网络请求失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 发送消息出错: {e}")
        return False
    
    # 测试文件上传（创建一个临时测试文件）
    print("\n📁 测试文件上传...")
    test_file_path = Path("test_upload.md")
    test_content = """# 飞书Bot测试文件

这是一个测试文件，用于验证飞书Bot的文件上传功能。

## 测试信息
- 测试时间: 刚刚
- 文件类型: Markdown
- 功能: 文件上传测试

如果您在飞书群聊中看到这个文件，说明文件上传功能正常工作！
"""
    
    try:
        # 创建测试文件
        test_file_path.write_text(test_content, encoding="utf-8")
        
        upload_url = "https://open.feishu.cn/open-apis/im/v1/files"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        with open(test_file_path, 'rb') as f:
            files = {
                'file': (test_file_path.name, f, 'text/markdown'),
                'file_type': (None, 'stream'),
                'file_name': (None, test_file_path.name)
            }
            
            response = requests.post(upload_url, headers=headers, files=files, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") == 0:
                file_key = data.get("data", {}).get("file_key")
                print("✅ 文件上传成功")
                print(f"   File Key: {file_key}")
                
                # 发送文件消息
                print("\n📤 测试发送文件消息...")
                content = {"file_key": file_key}
                payload = {
                    "receive_id": chat_id,
                    "msg_type": "file",
                    "content": json.dumps(content)
                }
                
                response = requests.post(
                    f"{message_url}?receive_id_type=chat_id",
                    headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=15
                )
                response.raise_for_status()
                
                data = response.json()
                if data.get("code") == 0:
                    print("✅ 文件消息发送成功")
                    print("   请检查飞书群聊是否收到测试文件")
                else:
                    print(f"❌ 发送文件消息失败: {data.get('msg', '未知错误')}")
                    return False
            else:
                print(f"❌ 文件上传失败: {data.get('msg', '未知错误')}")
                return False
                
    except Exception as e:
        print(f"❌ 文件上传测试出错: {e}")
        return False
    finally:
        # 清理测试文件
        if test_file_path.exists():
            test_file_path.unlink()
    
    print("\n🎉 所有测试通过！飞书Bot配置正确。")
    return True

def main():
    """主函数"""
    print("=" * 50)
    print("飞书Bot配置测试工具")
    print("=" * 50)
    
    success = test_feishu_bot_config()
    
    if success:
        print("\n✅ 测试结果: 配置正确，可以正常使用飞书Bot功能")
        print("\n💡 提示:")
        print("   1. 请确认在飞书群聊中收到了测试消息和测试文件")
        print("   2. 现在可以运行主程序启用飞书Bot推送功能")
        print("   3. 设置环境变量 ENABLE_FEISHU_BOT=true 启用功能")
    else:
        print("\n❌ 测试结果: 配置有问题，请检查以下内容:")
        print("   1. 飞书应用的App ID和App Secret是否正确")
        print("   2. 机器人是否已添加到目标群聊中")
        print("   3. 应用是否有足够的权限（消息发送、文件上传）")
        print("   4. 群聊ID是否正确")
        print("   5. 网络连接是否正常")
        print("\n📖 详细配置说明请参考: 飞书Bot配置说明.md")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()