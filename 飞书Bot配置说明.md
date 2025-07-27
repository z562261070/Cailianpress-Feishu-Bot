# 飞书Bot配置说明

## 功能概述

新增的飞书Bot功能可以将财联社电报文件自动上传到飞书群聊，解决GitHub访问限制的问题。

**流程**: 抓取脚本 → GitHub生成md文件 → 上传飞书Bot → 群聊推送附件 → 下游获取

## 配置步骤

### 1. 创建飞书自建应用

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 进入"开发者后台" → "应用管理" → "创建应用"
3. 选择"自建应用"，填写应用信息
4. 记录应用的 **App ID** 和 **App Secret**

### 2. 配置应用权限

在应用管理页面，进入"权限管理"，添加以下权限：

**机器人权限**:
- `im:message` - 获取与发送单聊、群组消息
- `im:message:send_as_bot` - 以应用的身份发送消息
- `im:file` - 上传文件

**API权限**:
- `im:chat` - 获取群组信息

### 3. 获取群聊ID

#### 方法一：通过飞书客户端
1. 在飞书群聊中，点击群名称进入群设置
2. 在群设置中找到"群ID"或"Chat ID"
3. 复制群ID（格式通常为 `oc_xxxxxxxxxxxxxx`）

#### 方法二：通过API获取
```bash
# 使用应用token获取群列表
curl -X GET \
  'https://open.feishu.cn/open-apis/im/v1/chats' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

### 4. 将机器人添加到群聊

1. 在飞书群聊中，点击"+"添加成员
2. 搜索你创建的应用名称
3. 将机器人添加到群聊中

## 环境变量配置

### 本地运行配置

在运行脚本前设置以下环境变量：

```bash
# Windows (PowerShell)
$env:FEISHU_APP_ID="cli_xxxxxxxxxxxxxxxx"
$env:FEISHU_APP_SECRET="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:FEISHU_CHAT_ID="oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:ENABLE_FEISHU_BOT="true"

# Linux/Mac
export FEISHU_APP_ID="cli_xxxxxxxxxxxxxxxx"
export FEISHU_APP_SECRET="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export FEISHU_CHAT_ID="oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export ENABLE_FEISHU_BOT="true"
```

### GitHub Actions配置

在GitHub仓库中设置以下Secrets：

1. 进入GitHub仓库 → Settings → Secrets and variables → Actions
2. 点击"New repository secret"，添加以下secrets：

| Secret名称 | 说明 | 示例值 |
|-----------|------|--------|
| `FEISHU_APP_ID` | 飞书应用ID | `cli_xxxxxxxxxxxxxxxx` |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `FEISHU_CHAT_ID` | 飞书群聊ID | `oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `ENABLE_FEISHU_BOT` | 是否启用飞书Bot | `true` |

## 使用说明

### 启用飞书Bot功能

设置环境变量 `ENABLE_FEISHU_BOT=true` 即可启用飞书Bot功能。

### 推送内容

当有新的财联社电报时，飞书Bot会自动推送：

1. **今日电报文件** - 包含当天所有电报的markdown文件
2. **5天整合文件** - 包含最近5天电报的整合文件
3. **汇总通知消息** - 包含更新时间、新增电报数量等信息

### 文件格式

推送的文件为markdown格式，包含：
- 🔴 重要电报（包含关键词的电报）
- 📰 一般电报
- 时间戳和链接信息

## 故障排除

### 常见错误

1. **获取访问令牌失败**
   - 检查App ID和App Secret是否正确
   - 确认应用状态为"已启用"

2. **文件上传失败**
   - 检查应用是否有文件上传权限
   - 确认文件大小不超过20MB

3. **发送消息失败**
   - 检查机器人是否已添加到群聊
   - 确认Chat ID是否正确
   - 检查应用是否有发送消息权限

### 调试方法

1. 查看控制台日志输出
2. 检查飞书开放平台的应用日志
3. 验证环境变量是否正确设置

## 安全注意事项

1. **保护密钥安全**：不要在代码中硬编码App Secret
2. **权限最小化**：只授予必要的API权限
3. **定期轮换**：定期更新App Secret
4. **监控使用**：关注API调用频率和异常

## 技术细节

- **Token缓存**：访问令牌会自动缓存，有效期2小时
- **文件限制**：单个文件最大20MB
- **重试机制**：网络请求失败会自动重试
- **错误处理**：完善的错误处理和日志记录

## 联系支持

如果遇到问题，可以：
1. 查看飞书开放平台文档
2. 检查应用权限配置
3. 查看详细的错误日志
