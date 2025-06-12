# coding=utf-8

import json
import time
import random
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

import requests
import pytz

# 配置常量
CONFIG = {
    "OUTPUT_DIR": "./output/财联社电报",  # 输出目录
    "FEISHU_WEBHOOK_URL": "",  # 飞书自动化 Webhook URL，用于触发飞书云文档创建
    "MAX_TELEGRAMS": 50,  # 最大获取电报数量
    "RED_KEYWORDS": ["利好", "利空", "重要", "突发", "紧急", "关注", "提醒"],  # 标红关键词
    "FILE_SEPARATOR": "━━━━━━━━━━━━━━━━━━━",  # 文件内容分割线
    "USE_PROXY": False,  # 是否启用代理，默认为 False，如果需要请设置为 True
    "DEFAULT_PROXY": "http://127.0.0.1:10086", # 默认代理地址
}


class TimeHelper:
    """时间处理工具"""

    @staticmethod
    def get_beijing_time() -> datetime:
        """获取北京时间"""
        return datetime.now(pytz.timezone("Asia/Shanghai"))

    @staticmethod
    def format_date() -> str:
        """返回日期格式"""
        return TimeHelper.get_beijing_time().strftime("%Y年%m月%d日")

    @staticmethod
    def format_time() -> str:
        """返回时间格式"""
        return TimeHelper.get_beijing_time().strftime("%H:%M:%S")

    @staticmethod
    def format_datetime() -> str:
        """返回日期时间格式"""
        return TimeHelper.get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")




class CailianpressAPI:
    """财联社API"""

    @staticmethod
    def fetch_telegrams(max_count=CONFIG["MAX_TELEGRAMS"]):
        """获取财联社电报"""
        try:
            # 获取今天的时间戳
            # 构建API URL
            api_url = "https://newsnow.busiyi.world/api/s?id=telegraphList&latest"
            
            proxies = None
            if CONFIG["USE_PROXY"]:
                proxies = {"http": CONFIG["DEFAULT_PROXY"], "https": CONFIG["DEFAULT_PROXY"]}

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
            }

            print(f"请求财联社API: {api_url}")
            response = requests.get(api_url, proxies=proxies, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("status") in ["success", "cache"] and "items" in data:
                telegrams = data["items"]
                print(f"成功获取 {len(telegrams)} 条财联社电报")
                
                processed_telegrams = []
                for item in telegrams:
                    # 提取所需信息
                    title = item.get("title", "")
                    content = item.get("brief", "") or title # 优先使用brief，没有则用title
                    item_id = item.get("id")
                    url = f"https://www.cls.cn/detail/{item_id}" if item_id else ""
                    
                    # 尝试从 ctime 或 pub_time 获取时间，并格式化
                    timestamp = item.get("ctime") or item.get("pub_time")
                    if timestamp:
                        # 确保时间戳是整数或可以转换为整数
                        try:
                            timestamp = int(timestamp)
                            item_time = datetime.fromtimestamp(timestamp, pytz.timezone("Asia/Shanghai")).strftime("%H:%M")
                        except (ValueError, TypeError):
                            item_time = ""
                    else:
                        item_time = ""

                    is_red = any(keyword in (title + content) for keyword in CONFIG["RED_KEYWORDS"])

                    processed_telegrams.append({
                        "id": item_id,
                        "title": title,
                        "content": content,
                        "time": item_time,
                        "url": url,
                        "is_red": is_red
                    })
                
                print(f"处理后的电报数量: {len(processed_telegrams)}")
                return processed_telegrams
            else:
                print(f"API返回格式错误: {data}")
                return []
        except Exception as e:
            print(f"获取财联社电报失败: {e}")
            return []


class FileWriter:
    """文件写入工具"""

    @staticmethod
    def save_telegrams_to_file(telegrams):
        """将电报内容保存到文件"""
        output_dir = Path(CONFIG["OUTPUT_DIR"])
        output_dir.mkdir(parents=True, exist_ok=True)

        today_date = TimeHelper.get_beijing_time().strftime("%Y-%m-%d")
        file_path = output_dir / f"财联社电报_{today_date}.md"

        content = FileWriter._build_file_content(telegrams)

        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content)
            print(f"财联社电报已保存到: {file_path}")
            return True
        except Exception as e:
            print(f"保存电报到文件失败: {e}")
            return False

    @staticmethod
    def _build_file_content(telegrams):
        """构建文件内容"""
        if not telegrams:
            return f"\n\n---\n\n### {TimeHelper.format_datetime()} - 今日暂无财联社电报\n\n" # 添加时间戳和分割线

        text_content = f"\n\n---\n\n### {TimeHelper.format_datetime()} - 财联社电报\n\n"

        # 先显示标红的电报
        red_telegrams = [t for t in telegrams if t.get("is_red")]
        normal_telegrams = [t for t in telegrams if not t.get("is_red")]

        if red_telegrams:
            text_content += "**🔴 重要电报**\n\n"
            for i, telegram in enumerate(red_telegrams, 1):
                title = telegram.get("content", "")
                time = telegram.get("time", "")
                url = telegram.get("url", "")

                if url:
                    text_content += f"  {i}. [{time}] **[{title}]({url})**\n\n"
                else:
                    text_content += f"  {i}. [{time}] **{title}**\n\n"

            # 添加分割线
            if normal_telegrams:
                text_content += f"{CONFIG['FILE_SEPARATOR']}\n\n"

        if normal_telegrams:
            text_content += "**📰 一般电报**\n\n"
            for i, telegram in enumerate(normal_telegrams, 1):
                title = telegram.get("content", "")
                time = telegram.get("time", "")
                url = telegram.get("url", "")

                if url:
                    text_content += f"  {i}. [{time}] [{title}]({url})\n\n"
                else:
                    text_content += f"  {i}. [{time}] {title}\n\n"

        return text_content


def main():
    telegrams = CailianpressAPI.fetch_telegrams()
    if telegrams:
        FileWriter.save_telegrams_to_file(telegrams)

        # 尝试发送 Webhook 到飞书自动化
        webhook_url = CONFIG["FEISHU_WEBHOOK_URL"]
        if webhook_url:
            try:
                # 构建发送到飞书 Webhook 的内容，这里可以根据飞书自动化接收的格式进行调整
                # 假设飞书自动化需要一个包含电报内容的 JSON 字符串
                payload = {
                    "telegrams": telegrams,
                    "date": TimeHelper.format_date()
                }
                response = requests.post(webhook_url, json=payload)
                if response.status_code == 200:
                    print("成功发送 Webhook 到飞书自动化。")
                else:
                    print(f"发送 Webhook 到飞书自动化失败，状态码：{response.status_code}，响应：{response.text}")
            except Exception as e:
                print(f"发送 Webhook 到飞书自动化时出错：{e}")
        else:
            print("警告: FEISHU_WEBHOOK_URL未设置，跳过飞书自动化 Webhook 发送。")
    else:
        print("未获取到财联社电报或获取失败。")


if __name__ == "__main__":
    main()
