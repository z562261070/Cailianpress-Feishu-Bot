# Cloudflare Workers Token分发配置说明

## 概述

本系统使用Cloudflare Workers作为飞书群`app_access_token`的中转站，实现Python脚本与utools应用之间的token共享。

## 工作流程

1. **Python脚本** → 获取飞书token → 上传到Cloudflare Workers
2. **utools应用** → 从Cloudflare Workers获取token → 下载财联社文件

## Cloudflare Workers配置

### 1. 创建Worker

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入 `Workers & Pages` 页面
3. 点击 `Create application` → `Create Worker`
4. 输入Worker名称，如：`feishu-token-distributor`

### 2. Worker代码示例

```javascript
export default {
  async fetch(request, env, ctx) {
    // 处理CORS
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // 处理OPTIONS请求
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      if (request.method === 'POST') {
        // 接收并存储token
        const tokenData = await request.json();
        
        // 验证数据格式
        if (!tokenData.access_token || !tokenData.expire_timestamp) {
          return new Response(JSON.stringify({ error: 'Invalid token data' }), {
            status: 400,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
          });
        }

        // 存储到KV存储（需要绑定KV命名空间）
        await env.TOKEN_STORE.put('feishu_token', JSON.stringify(tokenData));
        
        return new Response(JSON.stringify({ 
          success: true, 
          message: 'Token stored successfully',
          expire_time: tokenData.expire_time
        }), {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });

      } else if (request.method === 'GET') {
        // 获取token
        const tokenDataStr = await env.TOKEN_STORE.get('feishu_token');
        
        if (!tokenDataStr) {
          return new Response(JSON.stringify({ error: 'No token found' }), {
            status: 404,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
          });
        }

        const tokenData = JSON.parse(tokenDataStr);
        
        // 检查token是否过期
        const currentTimestamp = Math.floor(Date.now() / 1000);
        if (currentTimestamp >= tokenData.expire_timestamp) {
          return new Response(JSON.stringify({ error: 'Token expired' }), {
            status: 410,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
          });
        }

        return new Response(JSON.stringify(tokenData), {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });

      } else {
        return new Response('Method not allowed', { 
          status: 405,
          headers: corsHeaders
        });
      }

    } catch (error) {
      return new Response(JSON.stringify({ error: 'Internal server error' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  },
};
```

### 3. 绑定KV存储

1. 在Worker设置页面，找到 `Variables and Secrets`
2. 在 `KV Namespace Bindings` 部分点击 `Add binding`
3. 设置：
   - Variable name: `TOKEN_STORE`
   - KV namespace: 创建或选择一个KV命名空间

### 4. 部署Worker

1. 点击 `Save and Deploy`
2. 获取Worker URL，格式如：`https://feishu-token-distributor.your-subdomain.workers.dev`

## Python脚本配置

在 `cls_to_feishu.py` 中配置：

```python
# Cloudflare Workers配置
CLOUDFLARE_CONFIG = {
    "ENABLED": True,
    "WORKER_URL": "https://feishu-token-distributor.your-subdomain.workers.dev"
}
```

## utools应用配置

在 `news.js` 中配置：

```javascript
const CLOUDFLARE_CONFIG = {
    ENABLED: true,
    TOKEN_URL: "https://feishu-token-distributor.your-subdomain.workers.dev"
};
```

## 优势

1. **免费额度充足**：Cloudflare Workers每天有100,000次免费请求
2. **全球CDN**：访问速度快，延迟低
3. **高可用性**：Cloudflare的基础设施保证高可用
4. **简单配置**：只需要一个Worker URL即可
5. **安全性**：支持HTTPS，数据传输加密

## 注意事项

1. **KV存储限制**：免费版每天有1,000次写入限制，但读取无限制
2. **数据持久性**：KV存储的数据会持久保存，直到被覆盖
3. **访问控制**：可以通过Worker代码添加访问控制逻辑
4. **监控**：可以在Cloudflare Dashboard中查看Worker的使用情况和日志

## 故障排除

### 常见问题

1. **Worker无法访问**
   - 检查Worker是否已部署
   - 确认URL是否正确
   - 检查域名解析

2. **KV存储错误**
   - 确认KV命名空间已创建并绑定
   - 检查变量名是否为 `TOKEN_STORE`

3. **CORS错误**
   - 确认Worker代码中包含CORS头部设置
   - 检查请求方法是否被允许

### 调试方法

1. 在Cloudflare Dashboard中查看Worker日志
2. 使用浏览器开发者工具检查网络请求
3. 在Worker代码中添加console.log进行调试

## 更新记录

- 2024-01-XX：初始版本，替换文叔叔方案
- 支持token的存储和获取
- 包含完整的错误处理和CORS支持
