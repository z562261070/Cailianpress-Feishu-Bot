# 腾讯云函数 Token 分发配置说明

## 📋 概述

腾讯云函数（Serverless Cloud Function）是腾讯云提供的无服务器计算服务，我们使用腾讯云函数作为 `app_access_token` 的分发平台，具有以下优势：

### 🌟 腾讯云函数优势

1. **高可用性** - 腾讯云基础设施保障，99.9%+ 可用性
2. **自动扩缩容** - 根据请求量自动调整资源
3. **按量付费** - 只为实际使用的计算资源付费
4. **API网关集成** - 提供HTTP API接口，便于客户端调用
5. **安全可靠** - 支持HTTPS、访问控制等安全特性
6. **免运维** - 无需管理服务器，专注业务逻辑

## ⚙️ 配置方法

### Python 脚本配置

腾讯云函数功能默认已启用，需要配置API网关地址：

```python
# 腾讯云函数 Token分发配置
CONFIG = {
    "TENCENT_CLOUD_ENABLED": True,  # 启用腾讯云函数
    "TENCENT_CLOUD_API_URL": "https://your-api-gateway-url.tencentcloudapi.com/release/get-token"
}
```

### Node.js 客户端配置

在 `news.js` 中已默认配置：

```javascript
// 腾讯云函数 Token分发配置
const TENCENT_CLOUD_CONFIG = {
    ENABLED: true,  // 默认启用腾讯云函数
    API_URL: "https://your-api-gateway-url.tencentcloudapi.com/release/get-token"
};
```

## 🔄 工作流程

### 服务端（Python脚本）

1. 获取飞书 `app_access_token`
2. 构建包含过期时间等信息的 JSON 数据
3. 通过 HTTP POST 请求发送到腾讯云函数
4. 腾讯云函数存储 token 数据

### 客户端（Node.js）

1. 通过 HTTP GET 请求从腾讯云函数获取 token
2. 验证 token 是否过期
3. 使用有效的 token 调用飞书 API

## 📊 Token 数据格式

```json
{
  "access_token": "t-g1044ghEGNOJ5OSQF5OYATETPB",
  "expire_time": "2024-01-15 16:30:00",
  "expire_timestamp": 1705308600,
  "valid_duration_seconds": 7200,
  "generated_time": "2024-01-15 14:30:00",
  "generated_timestamp": 1705301400,
  "source": "财联社自动化系统",
  "usage": "用于客户端从飞书群获取财联社电报文件",
  "platform": "腾讯云函数"
}
```

## 🧪 测试方法

### 1. 测试腾讯云函数连接

```bash
curl -X GET "https://your-api-gateway-url.tencentcloudapi.com/release/get-token"
```

### 2. 运行完整测试

```bash
cd 财联社自动
python cls_to_feishu.py
```

预期输出：
```
🚀 腾讯云函数Token分发功能测试

1. 测试腾讯云函数API连接
✅ 腾讯云函数API连接成功

2. 测试腾讯云函数token上传功能
[2024-01-15 14:30:01] 正在上传token到腾讯云函数...
[2024-01-15 14:30:02] Token已成功分发到腾讯云函数
✅ 腾讯云函数token上传测试成功

🎉 所有测试通过！腾讯云函数token分发功能正常
```

## 📝 运行日志示例

### 成功运行日志

```
[2024-01-15 14:30:00] 腾讯云函数 Token分发功能已启用
[2024-01-15 14:30:00] API地址: https://your-api-gateway-url.tencentcloudapi.com/release/get-token

[2024-01-15 14:30:30] 开始分发token到腾讯云函数...
[2024-01-15 14:30:31] 正在上传token到腾讯云函数...
[2024-01-15 14:30:32] Token已成功分发到腾讯云函数
[2024-01-15 14:30:33] app_access_token已成功分发到腾讯云函数
```

程序会在飞书群中发送包含腾讯云函数API地址的消息：

```
🔑 客户端 Access Token 已更新

📅 生成时间: 2024-01-15 14:30:00
⏰ 过期时间: 2024-01-15 16:30:00 (剩余 120 分钟)
🔗 腾讯云函数API: https://your-api-gateway-url.tencentcloudapi.com/release/get-token

请客户端使用此API地址获取最新的access_token
```

## 🔧 故障排除

### 常见问题

#### 问题：腾讯云函数连接失败

```
❌ 腾讯云函数HTTP错误: 404
```

**解决方案：**
- 检查API网关地址是否正确
- 确认腾讯云函数服务状态
- 验证API网关配置

#### 问题：token上传失败

```
❌ 腾讯云函数返回错误: 权限不足
```

**解决方案：**
- 检查腾讯云函数权限配置
- 确认API网关访问策略
- 验证请求格式是否正确

#### 问题：客户端获取token失败

```
❌ 腾讯云函数 token获取失败: HTTP 500: Internal Server Error
```

**解决方案：**
- 检查腾讯云函数运行状态
- 查看函数日志排查错误
- 确认数据库连接是否正常

### 备用方案

如果腾讯云函数不可用，可以切换到Gitee：

```python
CONFIG = {
    "TENCENT_CLOUD_ENABLED": False,  # 禁用腾讯云函数
    "ENABLE_GITEE_TOKEN_SHARE": True,  # 启用Gitee
    "GITEE_ACCESS_TOKEN": "your_gitee_token",
    "GITEE_OWNER": "your_username",
    "GITEE_REPO": "your_repo_name",
    "GITEE_FILE_PATH": "token.json"
}
```

## 🏗️ 腾讯云函数部署

### 1. 创建云函数

```python
import json
import time
from datetime import datetime

def main_handler(event, context):
    """腾讯云函数主处理函数"""
    
    # 处理 GET 请求 - 获取token
    if event.get('httpMethod') == 'GET':
        # 从数据库或缓存中获取最新的token
        # 这里需要根据实际存储方案实现
        token_data = get_latest_token()
        
        if token_data and not is_token_expired(token_data):
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(token_data)
            }
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Token not found or expired'})
            }
    
    # 处理 POST 请求 - 存储token
    elif event.get('httpMethod') == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            # 存储token到数据库或缓存
            success = store_token(body)
            
            if success:
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'success': True, 'message': 'Token stored successfully'})
                }
            else:
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'success': False, 'message': 'Failed to store token'})
                }
        except Exception as e:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'success': False, 'message': str(e)})
            }
    
    return {
        'statusCode': 405,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': 'Method not allowed'})
    }

def get_latest_token():
    """获取最新的token（需要根据实际存储方案实现）"""
    # 实现从数据库或缓存获取token的逻辑
    pass

def store_token(token_data):
    """存储token（需要根据实际存储方案实现）"""
    # 实现存储token到数据库或缓存的逻辑
    pass

def is_token_expired(token_data):
    """检查token是否过期"""
    if 'expire_timestamp' in token_data:
        return time.time() >= token_data['expire_timestamp']
    return True
```

### 2. 配置API网关

1. 在腾讯云控制台创建API网关
2. 配置路径映射到云函数
3. 设置CORS策略
4. 获取API网关地址

## 💡 最佳实践

1. **监控告警** - 设置云函数监控和告警
2. **日志记录** - 启用详细的函数日志
3. **版本管理** - 使用函数版本管理功能
4. **性能优化** - 合理设置内存和超时时间
5. **安全加固** - 配置访问控制和API密钥

## 📚 总结

腾讯云函数作为 token 分发平台具有以下特点：

- **企业级可靠性** - 基于腾讯云基础设施
- **弹性扩展** - 自动处理高并发请求
- **成本优化** - 按实际使用量付费
- **易于维护** - 无服务器架构，减少运维负担
- **安全合规** - 符合企业安全要求

总的来说，腾讯云函数是一个稳定、可靠的 token 分发解决方案，特别适合对可用性和性能有较高要求的生产环境使用。
