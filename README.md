# 财联社电报到飞书推送工具

这个工具可以自动获取财联社当天的电报信息，并将其发送到飞书群聊中，方便团队成员及时了解财经动态。

## 功能特点

- **自动获取财联社电报**：获取当天的财联社电报信息
- **智能分类展示**：将重要电报（包含关键词的）和一般电报分开展示
- **飞书群聊推送**：将格式化后的电报信息推送到飞书群聊
- **可自定义配置**：支持自定义飞书Webhook URL、最大获取电报数量、标红关键词等

## 使用方法

### 1. 设置飞书机器人

1. 在飞书群聊中添加自定义机器人：
   - 打开飞书群聊 -> 点击群设置 -> 群机器人 -> 添加机器人 -> 自定义机器人
   - 设置机器人名称（如"财联社电报推送"）
   - 获取并保存Webhook URL

### 2. 配置脚本

有两种方式配置Webhook URL：

#### 方式一：直接修改脚本中的配置

打开`cls_to_feishu.py`文件，找到CONFIG部分，修改`FEISHU_WEBHOOK_URL`：

```python
CONFIG = {
    "FEISHU_WEBHOOK_URL": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx",  # 替换为你的Webhook URL
    # 其他配置...
}
```

#### 方式二：使用环境变量（推荐）

设置环境变量`FEISHU_WEBHOOK_URL`：

```bash
# Windows
set FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx

# Linux/Mac
export FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx
```

### 3. 安装依赖

```bash
pip install requests pytz
```

### 4. 运行脚本

```bash
python cls_to_feishu.py
```

## 自定义配置

你可以根据需要修改脚本中的CONFIG配置：

```python
CONFIG = {
    "FEISHU_SEPARATOR": "━━━━━━━━━━━━━━━━━━━",  # 飞书消息分割线
    "FEISHU_WEBHOOK_URL": "",  # 飞书机器人的webhook URL
    "MAX_TELEGRAMS": 50,  # 最大获取电报数量
    "RED_KEYWORDS": ["利好", "利空", "重要", "突发", "紧急", "关注", "提醒"],  # 标红关键词
}
```

## 设置定时任务

### Windows（使用任务计划程序）

1. 打开任务计划程序
2. 创建基本任务 -> 设置名称和描述 -> 每天触发 -> 设置时间 -> 启动程序
3. 程序/脚本：`python`
4. 添加参数：`D:\00kaifa\财联社\cls_to_feishu.py`（替换为你的实际路径）

### Linux/Mac（使用crontab）

```bash
# 编辑crontab
crontab -e

# 添加定时任务（每小时运行一次）
0 * * * * export FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx; /usr/bin/python /path/to/cls_to_feishu.py
```

## 注意事项

1. 脚本默认获取当天（北京时间）的电报信息
2. 包含特定关键词的电报会被标记为重要电报并在飞书消息中标红显示
3. 确保网络环境能够访问财联社API和飞书API
