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
    "FEISHU_WEBHOOK_URL": os.getenv("FEISHU_WEBHOOK_URL", ""),  # 飞书自动化 Webhook URL
    "MAX_TELEGRAMS": 50,  # 最大获取电报数量
    "RED_KEYWORDS": ["利好", "利空", "重要", "突发", "紧急", "关注", "提醒"],  # 标红关键词
    "FILE_SEPARATOR": "━━━━━━━━━━━━━━━━━━━",  # 文件内容分割线
    # 从环境变量读取 USE_PROXY，如果未设置，默认为 False
    "USE_PROXY": os.getenv("USE_PROXY", "False").lower() == "true",
    # 从环境变量读取 DEFAULT_PROXY，如果未设置，使用默认值
    "DEFAULT_PROXY": os.getenv("DEFAULT_PROXY", "http://127.0.0.1:10086"),
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




import hashlib
import urllib.parse

class CailianpressAPI:
    """财联社API"""

    @staticmethod
    def _md5(text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    @staticmethod
    def _sha1(text):
        return hashlib.sha1(text.encode('utf-8')).hexdigest()

    @staticmethod
    def _get_cls_params(more_params=None):
        if more_params is None:
            more_params = {}
        static_params = {
            "app_name": "CailianpressWeb",
            "os": "web",
            "sv": "7.7.5",
        }
        all_params = {**static_params, **more_params}
        
        # 参数排序对于签名很重要
        sorted_keys = sorted(all_params.keys())
        params_list = []
        for key in sorted_keys:
            params_list.append(f"{key}={all_params[key]}")
        params_string = "&".join(params_list)
        
        signature = CailianpressAPI._md5(CailianpressAPI._sha1(params_string))
        all_params["sign"] = signature
        return all_params

    @staticmethod
    def fetch_telegrams(max_count=CONFIG["MAX_TELEGRAMS"]):
        """获取财联社电报"""
        try:
            api_url = "https://www.cls.cn/nodeapi/updateTelegraphList"
            
            params = CailianpressAPI._get_cls_params()
            full_url = f"{api_url}?{urllib.parse.urlencode(params)}"
            
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

            print(f"请求财联社API: {full_url}")
            response = requests.get(full_url, proxies=proxies, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("error") == 0 and data.get("data") and data["data"].get("roll_data"):
                telegrams = data["data"]["roll_data"]
                print(f"成功获取 {len(telegrams)} 条财联社电报")
                
                processed_telegrams = []
                for item in telegrams:
                    if item.get("is_ad"): # 过滤广告
                        continue
                    
                    title = item.get("title", "")
                    content = item.get("brief", "") or title # 优先使用brief，没有则用title
                    item_id = item.get("id")
                    url = f"https://www.cls.cn/detail/{item_id}" if item_id else ""
                    
                    timestamp = item.get("ctime")
                    if timestamp:
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
                        "is_red": is_red,
                        "timestamp_raw": timestamp # 添加原始时间戳
                    })
                
                print(f"处理后的电报数量: {len(processed_telegrams)}")
                return processed_telegrams
            else:
                print(f"API返回格式错误或无数据: {data}")
                return []
        except Exception as e:
            print(f"获取财联社电报失败: {e}")
            return []


class FileWriter:
    """文件写入工具"""

    @staticmethod
    def save_telegrams_to_file(telegrams):
        """将电报内容保存到文件，并按日期归档和排序"""
        output_dir = Path(CONFIG["OUTPUT_DIR"])
        output_dir.mkdir(parents=True, exist_ok=True)

        # 按日期分组电报
        telegrams_by_date = {}
        for t in telegrams:
            if "timestamp_raw" in t and t["timestamp_raw"]:
                try:
                    # 将时间戳转换为日期
                    item_datetime = datetime.fromtimestamp(int(t["timestamp_raw"]), pytz.timezone("Asia/Shanghai"))
                    item_date_str = item_datetime.strftime("%Y-%m-%d")
                    if item_date_str not in telegrams_by_date:
                        telegrams_by_date[item_date_str] = []
                    telegrams_by_date[item_date_str].append(t)
                except (ValueError, TypeError):
                    print(f"警告: 无法解析电报时间戳 {t.get('timestamp_raw')}，跳过此电报的日期归档。")
                    continue
            else:
                print(f"警告: 电报缺少原始时间戳，跳过此电报的日期归档。电报ID: {t.get('id')}")
                continue

        saved_any_new = False
        for date_str, daily_telegrams in telegrams_by_date.items():
            file_path = output_dir / f"财联社电报_{date_str}.md"
            existing_ids = FileWriter._get_existing_telegram_ids(file_path)

            # 过滤掉已存在的电报
            new_telegrams_for_day = [t for t in daily_telegrams if str(t.get("id")) not in existing_ids]

            if not new_telegrams_for_day:
                print(f"日期 {date_str} 没有新的财联社电报需要保存。")
                continue

            # 对新电报按原始时间戳倒序排序
            new_telegrams_for_day.sort(key=lambda x: int(x.get("timestamp_raw", 0)), reverse=True)

            # 合并新电报和旧电报，并去重
            all_telegrams_for_day = new_telegrams_for_day
            if file_path.exists():
                existing_telegrams = FileWriter._parse_existing_telegrams(file_path)
                all_telegrams_for_day.extend(existing_telegrams)
                # 根据ID去重
                seen_ids = set()
                unique_telegrams = []
                for t in all_telegrams_for_day:
                    if str(t.get("id")) not in seen_ids:
                        unique_telegrams.append(t)
                        seen_ids.add(str(t.get("id")))
                all_telegrams_for_day = unique_telegrams

            # 对所有电报按原始时间戳倒序排序
            all_telegrams_for_day.sort(key=lambda x: int(x.get("timestamp_raw", 0)), reverse=True)

            # 构建文件内容
            content = FileWriter._build_file_content(date_str, all_telegrams_for_day)
            if not content:
                continue
            
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"日期 {date_str} 的财联社电报已保存到: {file_path}")
                saved_any_new = True
            except Exception as e:
                print(f"保存日期 {date_str} 的电报到文件失败: {e}")
        
        return saved_any_new

    @staticmethod
    def _get_existing_telegram_ids(file_path):
        """从文件中读取已存在的电报ID"""
        existing_ids = set()
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                import re
                # 匹配两种URL格式，确保能提取ID
                ids = re.findall(r'https://www.cls.cn/detail/(\d+)', content)
                existing_ids.update(ids)
            except Exception as e:
                print(f"读取文件 {file_path} 失败: {e}")
        return existing_ids

    @staticmethod
    def _parse_existing_telegrams(file_path):
        """从文件中解析已存在的电报内容，返回电报列表"""
        telegrams = []
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 使用正则表达式匹配电报条目
                # 匹配格式：  1. [00:56] [【台风黄色预警生效 广东湛江全市停课】财联社6月13日电，...](https://www.cls.cn/detail/2056133)
                # 或者：      1. [00:56] 【台风黄色预警生效 广东湛江全市停课】财联社6月13日电，...
                # 注意：这里假设URL是可选的，并且内容可能包含方括号
                # 匹配时间、内容和可选的URL及ID
                # 改进的正则表达式，更健壮地匹配时间、内容和URL
                # 匹配模式：数字. [时间] [内容](URL) 或 数字. [时间] 内容
                # 考虑到内容中可能包含方括号，使用非贪婪匹配
                # 匹配重要电报和一般电报两种格式
                matches = re.findall(r'\d+\.\s*\[(\d{2}:\d{2})\]\s*(?:\*?\[([^\]]+)\]\((https://www\.cls\.cn/detail/(\d+))\)\*?|\*?([^*]+)\*?)\n\n', content)

                for match in matches:
                    item_time = match[0] # 时间
                    # 根据匹配组判断是带URL的还是不带URL的
                    if match[1] and match[2] and match[3]: # 带URL的格式
                        item_content = match[1]
                        item_url = match[2]
                        item_id = match[3]
                    else: # 不带URL的格式
                        item_content = match[4]
                        item_url = ""
                        item_id = ""
                    
                    # 尝试从URL中提取timestamp_raw，如果URL不存在则跳过
                    timestamp_raw = None
                    if item_id:
                        try:
                            # 假设ID就是timestamp_raw的一部分或者可以用来生成一个唯一的timestamp_raw
                            # 这里我们简单地用ID作为timestamp_raw，或者可以根据实际情况进行更复杂的转换
                            # 为了避免重复，我们使用一个简单的哈希值或者直接使用ID
                            timestamp_raw = int(item_id) # 假设ID可以直接作为时间戳
                        except ValueError:
                            pass # 如果ID不是数字，则跳过

                    telegrams.append({
                        "id": item_id,
                        "content": item_content,
                        "time": item_time,
                        "url": item_url,
                        "timestamp_raw": timestamp_raw # 确保有这个字段
                    })
            except Exception as e:
                print(f"解析文件 {file_path} 失败: {e}")
        return telegrams

    @staticmethod
    def _build_file_content(date_str, telegrams):
        """构建文件内容"""
        if not telegrams:
            return "" # 如果没有电报，不返回任何内容

        # 先显示标红的电报
        red_telegrams = [t for t in telegrams if t.get("is_red")]
        normal_telegrams = [t for t in telegrams if not t.get("is_red")]

        text_content = ""

        if red_telegrams:
            text_content += "**🔴 重要电报**\n\n"
            for i, t in enumerate(red_telegrams):
                # 格式化时间，例如：[07:00]
                formatted_time = f"[{t.get('time', '')}]"
                # 构建电报内容，如果is_red为True，则加粗
                telegram_content = f"【{t.get('title', '')}】{t.get('content', '')}"
                # 构建URL部分，如果存在
                url_part = f"({t.get('url', '')})" if t.get('url') else ""
                text_content += f"{i+1}. {formatted_time} **[{telegram_content}]{url_part}**\n\n"

        if normal_telegrams:
            if red_telegrams:
                text_content += "\n" # 如果有重要电报，加一个空行分隔
            text_content += "**📰 一般电报**\n\n"
            for i, t in enumerate(normal_telegrams):
                # 格式化时间，例如：[07:00]
                formatted_time = f"[{t.get('time', '')}]"
                # 构建电报内容
                telegram_content = f"【{t.get('title', '')}】{t.get('content', '')}"
                # 构建URL部分，如果存在
                url_part = f"({t.get('url', '')})" if t.get('url') else ""
                text_content += f"{i+1}. {formatted_time} [{telegram_content}]{url_part}\n\n"

        return text_content


def main():
    telegrams = CailianpressAPI.fetch_telegrams()
    if not telegrams:
        print("未获取到财联社电报或获取失败。")
        return

    # 获取当天已保存的电报ID，用于去重
    output_dir = Path(CONFIG["OUTPUT_DIR"])
    today_date = TimeHelper.get_beijing_time().strftime("%Y-%m-%d")
    file_path = output_dir / f"财联社电报_{today_date}.md"
    existing_ids = FileWriter._get_existing_telegram_ids(file_path)

    # 过滤掉已存在的电报，得到真正需要处理的新电报
    new_telegrams_to_process = [t for t in telegrams if str(t.get("id")) not in existing_ids]

    if not new_telegrams_to_process:
        print("没有新的财联社电报需要保存或发送。")
        return

    # 对需要处理的新电报按原始时间戳倒序排序，确保飞书接收到的也是按时间倒序的
    new_telegrams_to_process.sort(key=lambda x: int(x.get("timestamp_raw", 0)), reverse=True)

    # 保存新的电报到文件 (FileWriter.save_telegrams_to_file 内部会按日期归档和去重)
    FileWriter.save_telegrams_to_file(new_telegrams_to_process)

    # 尝试发送 Webhook 到飞书自动化 (只发送当天新获取并已排序的电报)
    webhook_url = CONFIG["FEISHU_WEBHOOK_URL"]
    if webhook_url:
        try:
            # 构建发送到飞书 Webhook 的内容
            combined_telegram_content = "\n\n".join([
                f"[{t.get('time', '')}] {t.get('content', '')} - {t.get('url', '')}"
                for t in new_telegrams_to_process
            ])

            payload = {
                "content": {
                    "text": combined_telegram_content,
                    "total_titles": len(new_telegrams_to_process),
                    "timestamp": TimeHelper.format_datetime(),
                    "report_type": "财联社电报"
                }
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


if __name__ == "__main__":
    main()
