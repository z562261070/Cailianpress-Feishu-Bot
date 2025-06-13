# cailianpress_to_feishu_rewritten.py

import json
import time
import random
from datetime import datetime
import os
import sys
from pathlib import Path
import re
import hashlib
import urllib.parse
from typing import Optional

import requests
import pytz

# --- 1. 配置常量 ---
CONFIG = {
    "OUTPUT_DIR": "./output/财联社电报",  # 输出目录
    "FEISHU_WEBHOOK_URL": os.getenv("FEISHU_WEBHOOK_URL", ""),  # 飞书自动化 Webhook URL
    "MAX_TELEGRAMS_FETCH": 100,  # 每次API请求最大获取电报数量 (根据财联社API实际能力调整)
    "RED_KEYWORDS": ["利好", "利空", "重要", "突发", "紧急", "关注", "提醒", "涨停", "大跌", "突破"],  # 标红关键词，可扩展
    "FILE_SEPARATOR": "━━━━━━━━━━━━━━━━━━━",  # 文件内容分割线
    "USE_PROXY": os.getenv("USE_PROXY", "False").lower() == "true",
    "DEFAULT_PROXY": os.getenv("DEFAULT_PROXY", "http://127.0.0.1:10086"),
    "REQUEST_TIMEOUT": 15, # 请求超时时间
    "RETRY_ATTEMPTS": 3, # 请求重试次数
    "RETRY_DELAY": 5, # 重试间隔秒数
}

# --- 2. 时间处理工具类 ---
class TimeHelper:
    """提供时间相关的辅助方法"""

    BEIJING_TZ = pytz.timezone("Asia/Shanghai")

    @staticmethod
    def get_beijing_time() -> datetime:
        """获取当前北京时间"""
        return datetime.now(TimeHelper.BEIJING_TZ)

    @staticmethod
    def format_date(dt: datetime = None) -> str:
        """格式化日期，默认为当前北京时间"""
        if dt is None:
            dt = TimeHelper.get_beijing_time()
        return dt.strftime("%Y年%m月%d日")

    @staticmethod
    def format_time(dt: datetime = None) -> str:
        """格式化时间，默认为当前北京时间"""
        if dt is None:
            dt = TimeHelper.get_beijing_time()
        return dt.strftime("%H:%M:%S")

    @staticmethod
    def format_datetime(dt: datetime = None) -> str:
        """格式化日期时间，默认为当前北京时间"""
        if dt is None:
            dt = TimeHelper.get_beijing_time()
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def timestamp_to_beijing_datetime(timestamp: int) -> datetime:
        """将Unix时间戳转换为北京时间datetime对象"""
        return datetime.fromtimestamp(timestamp, TimeHelper.BEIJING_TZ)

    @staticmethod
    def timestamp_to_hhmm(timestamp: int) -> str:
        """将Unix时间戳转换为 HH:MM 格式的字符串"""
        try:
            return TimeHelper.timestamp_to_beijing_datetime(timestamp).strftime("%H:%M")
        except (ValueError, TypeError):
            return ""

# --- 3. 财联社 API 交互类 ---
class CailianpressAPI:
    """处理财联社电报数据的获取和解析"""

    BASE_URL = "https://www.cls.cn/nodeapi/updateTelegraphList"
    APP_PARAMS = {
        "app_name": "CailianpressWeb",
        "os": "web",
        "sv": "7.7.5",
    }
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    @staticmethod
    def _generate_signature(params: dict) -> str:
        """生成财联社API请求所需的签名"""
        sorted_keys = sorted(params.keys())
        params_list = [f"{key}={params[key]}" for key in sorted_keys]
        params_string = "&".join(params_list)
        
        md5_hash = hashlib.md5(params_string.encode('utf-8')).hexdigest()
        sha1_hash = hashlib.sha1(params_string.encode('utf-8')).hexdigest()
        
        return hashlib.md5(sha1_hash.encode('utf-8')).hexdigest()

    @staticmethod
    def _get_request_params() -> dict:
        """获取带签名的完整请求参数"""
        all_params = {**CailianpressAPI.APP_PARAMS}
        all_params["sign"] = CailianpressAPI._generate_signature(all_params)
        return all_params

    @staticmethod
    def fetch_telegrams() -> list[dict]:
        """
        获取财联社电报数据。
        返回一个字典列表，每个字典代表一条电报。
        """
        params = CailianpressAPI._get_request_params()
        full_url = f"{CailianpressAPI.BASE_URL}?{urllib.parse.urlencode(params)}"
        
        proxies = {"http": CONFIG["DEFAULT_PROXY"], "https": CONFIG["DEFAULT_PROXY"]} if CONFIG["USE_PROXY"] else None

        print(f"[{TimeHelper.format_datetime()}] 正在请求财联社API: {full_url}")

        for attempt in range(CONFIG["RETRY_ATTEMPTS"]):
            try:
                response = requests.get(
                    full_url, 
                    proxies=proxies, 
                    headers=CailianpressAPI.HEADERS, 
                    timeout=CONFIG["REQUEST_TIMEOUT"]
                )
                response.raise_for_status()  # 检查HTTP错误
                data = response.json()

                if data.get("error") == 0 and data.get("data") and data["data"].get("roll_data"):
                    raw_telegrams = data["data"]["roll_data"]
                    print(f"[{TimeHelper.format_datetime()}] 成功获取 {len(raw_telegrams)} 条原始财联社电报。")
                    
                    processed_telegrams = []
                    for item in raw_telegrams:
                        if item.get("is_ad"): # 过滤广告
                            continue
                        
                        item_id = str(item.get("id")) # 确保ID是字符串
                        title = item.get("title", "")
                        content = item.get("brief", "") or title # 优先使用brief

                        timestamp = item.get("ctime")
                        if timestamp is not None:
                            try:
                                timestamp = int(timestamp)
                                item_time_str = TimeHelper.timestamp_to_hhmm(timestamp)
                            except (ValueError, TypeError):
                                print(f"[{TimeHelper.format_datetime()}] 警告: 电报ID {item_id} 时间戳 {timestamp} 无效，跳过解析时间。")
                                timestamp = None # 标记为无效时间戳
                                item_time_str = ""
                        else:
                            item_time_str = ""

                        is_red = any(keyword in (title + content) for keyword in CONFIG["RED_KEYWORDS"])

                        processed_telegrams.append({
                            "id": item_id,
                            "title": title,
                            "content": content,
                            "time": item_time_str, # HH:MM 格式
                            "url": f"https://www.cls.cn/detail/{item_id}" if item_id else "",
                            "is_red": is_red,
                            "timestamp_raw": timestamp # 原始时间戳 (int或None)
                        })
                    
                    print(f"[{TimeHelper.format_datetime()}] 已处理 {len(processed_telegrams)} 条有效电报。")
                    return processed_telegrams
                else:
                    print(f"[{TimeHelper.format_datetime()}] API返回格式错误或无数据 (尝试 {attempt + 1}/{CONFIG['RETRY_ATTEMPTS']}): {data}")
            except requests.exceptions.RequestException as e:
                print(f"[{TimeHelper.format_datetime()}] 请求财联社API失败 (尝试 {attempt + 1}/{CONFIG['RETRY_ATTEMPTS']}): {e}")
            except json.JSONDecodeError as e:
                print(f"[{TimeHelper.format_datetime()}] JSON解析失败 (尝试 {attempt + 1}/{CONFIG['RETRY_ATTEMPTS']}): {e}")
            
            if attempt < CONFIG["RETRY_ATTEMPTS"] - 1:
                time.sleep(CONFIG["RETRY_DELAY"] + random.uniform(0, 2)) # 随机延迟
        
        print(f"[{TimeHelper.format_datetime()}] 达到最大重试次数，获取财联社电报失败。")
        return []

# --- 4. 文件写入与读取类 ---
class TelegramFileManager:
    """处理电报数据的文件读写和归档"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, date_str: str) -> Path:
        """获取特定日期的文件路径"""
        return self.output_dir / f"财联社电报_{date_str}.md"

    def _parse_telegram_from_line(self, line: str, is_red_category: bool) -> Optional[dict]:
        """
        从文件行中解析单个电报的数据。
        由于Markdown格式不存储原始时间戳，这里会将其设为None。
        """
        line = line.strip()

        # 【关键修改2】: 正则表达式现在匹配以 "-" 开头的项目符号列表，而不是数字列表
        # 模式解释:
        # ^\s*-\s* - 匹配行首的 " - "
        # ...其余部分与之前类似
        pattern_url = re.compile(
            r'^\s*-\s*'  # <--- 修改点: 匹配项目符号 "-"
            r'\[(\d{2}:\d{2})\]\s*'
            r'(\*\*?)'
            r'\[(.*?)\]'
            r'\(https://www.cls.cn/detail/(\d+)\)'
            r'\2'
            r'$'
        )

        match = pattern_url.match(line)
        if match:
            item_time, _, item_content, item_id = match.groups()
            is_red_from_markdown = line.count('**') >= 2

            return {
                "id": item_id,
                "content": item_content,
                "time": item_time,
                "url": f"https://www.cls.cn/detail/{item_id}",
                "is_red": is_red_from_markdown,
                "timestamp_raw": None
            }
        
        if line:
            print(f"[{TimeHelper.format_datetime()}] 警告: 无法解析文件中的行: '{line}'")
            
        return None

    def load_existing_telegrams(self, date_str: str) -> list[dict]:
        """
        从文件中加载指定日期的所有已保存电报。
        返回一个字典列表。
        """
        file_path = self._get_file_path(date_str)
        existing_telegrams = []
        if not file_path.exists():
            return existing_telegrams

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.split('\n')
            is_red_category = False
            for line in lines:
                if line.startswith('**🔴 重要电报**'):
                    is_red_category = True
                    continue
                elif line.startswith('**📰 一般电报**'):
                    is_red_category = False
                    continue
                elif line.startswith(CONFIG["FILE_SEPARATOR"]):
                    continue
                elif line.strip() == "": # 跳过空行
                    continue

                telegram = self._parse_telegram_from_line(line, is_red_category)
                if telegram:
                    existing_telegrams.append(telegram)
            
            print(f"[{TimeHelper.format_datetime()}] 从文件 '{file_path}' 加载了 {len(existing_telegrams)} 条现有电报。")
            return existing_telegrams

        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 错误: 读取并解析文件 '{file_path}' 失败: {e}")
            return []

    def save_telegrams(self, telegrams_to_save: list[dict]) -> bool:
        """
        将电报内容保存到文件，并按日期归档、合并、去重和排序。
        返回 True 如果有新电报被保存，否则返回 False。
        """
        telegrams_by_date_new = {}
        for t in telegrams_to_save:
            if t.get("timestamp_raw") is None:
                print(f"[{TimeHelper.format_datetime()}] 警告: 电报ID {t.get('id')} 缺少原始时间戳，跳过文件保存。")
                continue
            
            item_datetime = TimeHelper.timestamp_to_beijing_datetime(int(t["timestamp_raw"]))
            item_date_str = item_datetime.strftime("%Y-%m-%d")
            
            if item_date_str not in telegrams_by_date_new:
                telegrams_by_date_new[item_date_str] = []
            telegrams_by_date_new[item_date_str].append(t)

        saved_any_new = False
        for date_str, current_batch_telegrams in telegrams_by_date_new.items():
            file_path = self._get_file_path(date_str)
            
            existing_telegrams = self.load_existing_telegrams(date_str)
            existing_ids = {t['id'] for t in existing_telegrams if t.get('id')}

            truly_new_telegrams_for_day = [
                t for t in current_batch_telegrams 
                if t.get("id") and t["id"] not in existing_ids
            ]

            if not truly_new_telegrams_for_day:
                print(f"[{TimeHelper.format_datetime()}] 日期 {date_str} 没有真正新的财联社电报需要保存。")

            all_telegrams_for_day = existing_telegrams + truly_new_telegrams_for_day
            
            unique_telegrams_map = {t['id']: t for t in all_telegrams_for_day if t.get('id')}
            all_telegrams_for_day_unique = list(unique_telegrams_map.values())

            all_telegrams_for_day_unique.sort(
                key=lambda x: int(x["timestamp_raw"]) if x.get("timestamp_raw") is not None else 0,
                reverse=True
            )

            content_to_write = self._build_file_content(date_str, all_telegrams_for_day_unique)
            if not content_to_write:
                print(f"[{TimeHelper.format_datetime()}] 警告: 日期 {date_str} 构建文件内容为空。")
                continue
            
            try:
                # 检查文件内容是否有变化，避免无意义的写入操作
                current_content = ""
                if file_path.exists():
                    current_content = file_path.read_text(encoding="utf-8")
                
                if content_to_write != current_content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content_to_write)
                                
                    print(f"[{TimeHelper.format_datetime()}] 日期 {date_str} 的财联社电报已更新并保存到: {file_path}")
                else:
                    print(f"[{TimeHelper.format_datetime()}] 日期 {date_str} 的内容无变化，无需写入文件。")
                
                if truly_new_telegrams_for_day:
                    saved_any_new = True
            except Exception as e:
                print(f"[{TimeHelper.format_datetime()}] 错误: 保存日期 {date_str} 的电报到文件失败: {e}")
        
        return saved_any_new

    def _build_file_content(self, date_str: str, telegrams: list[dict]) -> str:
        """构建Markdown格式的文件内容"""
        if not telegrams:
            return ""

        red_telegrams = [t for t in telegrams if t.get("is_red")]
        normal_telegrams = [t for t in telegrams if not t.get("is_red")]

        text_content = ""

        if red_telegrams:
            text_content += "**🔴 重要电报**\n\n"
            # 【关键修改1】: 不再使用 enumerate 生成数字，而是使用固定的 "-"
            for telegram in red_telegrams:
                title = telegram.get("content", "")
                time_str = telegram.get("time", "")
                url = telegram.get("url", "")

                if url:
                    # <--- 修改点: "  {i}. " 变为 "  - "
                    text_content += f"  - [{time_str}] **[{title}]({url})**\n\n"
                else:
                    text_content += f"  - [{time_str}] **{title}**\n\n"

            if normal_telegrams:
                text_content += f"{CONFIG['FILE_SEPARATOR']}\n\n"

        if normal_telegrams:
            text_content += "**📰 一般电报**\n\n"
            # 【关键修改1】: 不再使用 enumerate 生成数字，而是使用固定的 "-"
            for telegram in normal_telegrams:
                title = telegram.get("content", "")
                time_str = telegram.get("time", "")
                url = telegram.get("url", "")

                if url:
                    # <--- 修改点: "  {i}. " 变为 "  - "
                    text_content += f"  - [{time_str}] [{title}]({url})\n\n"
                else:
                    text_content += f"  - [{time_str}] {title}\n\n"

        return text_content

# --- 5. 飞书通知类 ---
class FeishuNotifier:
    """负责向飞书自动化发送通知"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_notification(self, new_telegrams: list[dict]) -> None:
        """
        向飞书自动化发送新电报的通知。
        只发送本次运行中真正新增的电报。
        """
        if not self.webhook_url:
            print(f"[{TimeHelper.format_datetime()}] 警告: FEISHU_WEBHOOK_URL未设置，跳过飞书自动化 Webhook 发送。")
            return

        if not new_telegrams:
            print(f"[{TimeHelper.format_datetime()}] 没有新的电报内容可供飞书推送。")
            return

        combined_telegram_content = "\n\n".join([
            f"[{t.get('time', '未知时间')}] {t.get('content', '无内容')} - {t.get('url', '无链接')}"
            for t in new_telegrams
        ])

        payload = {
            "content": {
                "text": combined_telegram_content,
                "total_titles": len(new_telegrams),
                "timestamp": TimeHelper.format_datetime(),
                "report_type": "财联社电报"
            }
        }
        
        print(f"[{TimeHelper.format_datetime()}] 正在发送 {len(new_telegrams)} 条新电报到飞书自动化。")
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=CONFIG["REQUEST_TIMEOUT"])
            if response.status_code == 200:
                print(f"[{TimeHelper.format_datetime()}] 成功发送 Webhook 到飞书自动化。")
            else:
                print(f"[{TimeHelper.format_datetime()}] 发送 Webhook 到飞书自动化失败，状态码：{response.status_code}，响应：{response.text}")
        except requests.exceptions.RequestException as e:
            print(f"[{TimeHelper.format_datetime()}] 发送 Webhook 到飞书自动化时出错：{e}")

# --- 6. 主程序逻辑 ---
def main():
    """主函数，编排整个爬取、保存和通知流程"""
    print(f"\n--- 财联社电报抓取与通知程序启动 ---")
    print(f"[{TimeHelper.format_datetime()}]")

    file_manager = TelegramFileManager(CONFIG["OUTPUT_DIR"])
    feishu_notifier = FeishuNotifier(CONFIG["FEISHU_WEBHOOK_URL"])

    fetched_telegrams = CailianpressAPI.fetch_telegrams()
    if not fetched_telegrams:
        print(f"[{TimeHelper.format_datetime()}] 未获取到任何财联社电报，程序退出。")
        return

    # 在保存文件前，确定哪些是用于通知的新电报
    today_date_str = TimeHelper.get_beijing_time().strftime("%Y-%m-%d")
    # 这里加载一次，仅用于判断哪些是新条目，避免重复加载
    existing_ids_today = {t['id'] for t in file_manager.load_existing_telegrams(today_date_str) if t.get('id')}

    new_telegrams_for_notification = []
    for t in fetched_telegrams:
        if t.get("id") and t["id"] not in existing_ids_today:
            new_telegrams_for_notification.append(t)
    
    new_telegrams_for_notification.sort(
        key=lambda x: int(x["timestamp_raw"]) if x.get("timestamp_raw") is not None else 0,
        reverse=True
    )

    if new_telegrams_for_notification:
        print(f"[{TimeHelper.format_datetime()}] 发现 {len(new_telegrams_for_notification)} 条新的电报用于通知。")

    # 保存文件（方法内部会处理加载、合并、去重、排序和写入的完整逻辑）
    file_manager.save_telegrams(fetched_telegrams)

    # 发送通知
    feishu_notifier.send_notification(new_telegrams_for_notification)

    print(f"\n--- 财联社电报抓取与通知程序完成 ---")
    print(f"[{TimeHelper.format_datetime()}]")


if __name__ == "__main__":
    main()
