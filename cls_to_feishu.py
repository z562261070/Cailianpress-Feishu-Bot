import json
import time
import random
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
import re # Import re for regular expressions

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
                        "id": str(item_id), # Ensure ID is string for consistent comparison
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
        for date_str, daily_new_telegrams in telegrams_by_date.items():
            file_path = output_dir / f"财联社电报_{date_str}.md"
            
            # 读取所有现有电报
            existing_telegrams = FileWriter._read_existing_telegrams(file_path)
            existing_ids = {t['id'] for t in existing_telegrams}

            # 过滤掉已存在的电报，获取真正的“新”电报
            truly_new_telegrams = [t for t in daily_new_telegrams if t.get("id") not in existing_ids]

            if not truly_new_telegrams:
                print(f"日期 {date_str} 没有新的财联社电报需要保存。")
                continue

            # 合并现有电报和新电报
            all_telegrams_for_day = existing_telegrams + truly_new_telegrams
            
            # 再次去重（以防万一，虽然按ID过滤了，但确保最终列表唯一）
            # 使用字典保持插入顺序或转换为集合再转回列表，这里用字典更方便保持唯一性
            unique_telegrams_map = {t['id']: t for t in all_telegrams_for_day}
            all_telegrams_for_day = list(unique_telegrams_map.values())

            # 对所有电报按原始时间戳倒序排序
            all_telegrams_for_day.sort(key=lambda x: int(x.get("timestamp_raw", 0)), reverse=True)

            # 构建完整的新的文件内容
            content_to_write = FileWriter._build_file_content(date_str, all_telegrams_for_day)
            if not content_to_write:
                continue
            
            try:
                # 始终以写入模式打开，因为我们要写入整个更新后的内容
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content_to_write)
                            
                print(f"日期 {date_str} 的财联社电报已更新并保存到: {file_path}")
                saved_any_new = True
            except Exception as e:
                print(f"保存日期 {date_str} 的电报到文件失败: {e}")
        
        return saved_any_new

    @staticmethod
    def _read_existing_telegrams(file_path):
        """从文件中解析已存在的电报内容，并返回其结构化数据列表"""
        existing_telegrams = []
        if not file_path.exists():
            return existing_telegrams

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 使用正则表达式匹配电报条目
            # 考虑到URL可能不存在，并捕获时间、内容和URL中的ID
            # 格式： 1. [时间] [标题](URL) 或 1. [时间] 标题
            # 改进后的正则，尝试匹配更复杂的markdown链接或纯文本，并提取ID
            # 这里需要更智能的解析，因为Markdown不是结构化数据，直接解析回原有的字典格式比较困难
            # 更实际的做法是，如果文件格式复杂，可以考虑将电报保存为JSONL (JSON Lines) 格式，这样读取和写入更方便
            # 但为了兼容现有Markdown输出，我们尝试从Markdown中解析
            
            # 匹配标题行，跳过重要电报/一般电报的标题
            lines = content.split('\n')
            current_category_is_red = False
            for line in lines:
                line = line.strip()
                if line.startswith('**🔴 重要电报**'):
                    current_category_is_red = True
                    continue
                if line.startswith('**📰 一般电报**'):
                    current_category_is_red = False
                    continue
                if line.startswith(CONFIG["FILE_SEPARATOR"]):
                    continue # Skip separator

                # 匹配电报行： 1. [时间] [内容](URL) 或 1. [时间] 内容
                # 提取时间、内容和ID（如果URL存在）
                match = re.match(r'^\s*\d+\.\s*\[(\d{2}:\d{2})\]\s*(?:\*\*)?\[(.*?)\]\(https://www.cls.cn/detail/(\d+)\)(?:\*\*)?$', line)
                if match:
                    item_time, item_content, item_id = match.groups()
                    existing_telegrams.append({
                        "id": item_id,
                        "content": item_content,
                        "time": item_time,
                        "url": f"https://www.cls.cn/detail/{item_id}",
                        "is_red": current_category_is_red, # 根据当前分类标题判断
                        "timestamp_raw": None # 从Markdown中无法直接获取原始时间戳，需要根据时间推算或标记为未知
                    })
                else: # 尝试匹配没有URL的普通电报
                    match_no_url = re.match(r'^\s*\d+\.\s*\[(\d{2}:\d{2})\]\s*(?:\*\*)?(.*?)(?:\*\*)?$', line)
                    if match_no_url:
                        item_time, item_content = match_no_url.groups()
                        # 对于没有URL的电报，我们无法获取ID，这意味着它们无法被准确去重。
                        # 这是Markdown格式的一个局限性。为简化，这里不添加无ID的电报。
                        # 如果需要处理无ID电报，需要更复杂的文本匹配或使用其他存储格式。
                        pass

            # 为了准确去重和排序，最好能从文件中提取原始时间戳。
            # 由于Markdown中没有原始时间戳，这部分解析会比较困难。
            # 如果能确保每条电报在URL中包含ID，我们可以只通过ID来去重。
            # 但为了在保存时能正确排序，最好能有时间戳。
            # 目前的_read_existing_telegrams只提取ID，不提供完整的电报对象，所以需要调整。
            # 实际上，我们需要一种方式来“反向解析”已保存的Markdown文件，还原出电报的Python字典形式。
            # 鉴于Markdown的灵活性，这会比较复杂。
            # 最好的方式是：在文件中也保存原始数据（比如隐藏的JSON或单独的JSON文件），或者在解析时更鲁棒地提取。
            # 这里我们简化，假设只需要ID来去重，并且新的电报会携带完整信息来重新构建文件。
            # 为了更好的排序和去重，我们直接从文件中提取所有的信息，包括时间戳。
            # 这是一个挑战，因为Markdown是为人类阅读设计的，不是机器解析。
            # 考虑一种妥协：在文件顶部或底部保存一个隐藏的JSON列表，存储所有电报的原始数据。
            # 但为了不改变太多原始代码结构，我们先尝试改进`_get_existing_telegram_ids`和`_read_existing_telegrams`。

        except Exception as e:
            print(f"读取并解析文件 {file_path} 失败: {e}")
        
        return existing_telegrams

    @staticmethod
    def _get_existing_telegram_ids(file_path):
        """从文件中读取已存在的电报ID"""
        existing_ids = set()
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # 匹配URL中的ID，确保能提取数字ID
                ids = re.findall(r'https://www.cls.cn/detail/(\d+)', content)
                existing_ids.update(ids)
            except Exception as e:
                print(f"读取文件 {file_path} 失败: {e}")
        return existing_ids

    @staticmethod
    def _build_file_content(date_str, telegrams):
        """构建文件内容"""
        # 这里的 telegrams 已经是针对特定日期且已排序的所有电报（包括旧的和新的）

        if not telegrams:
            return "" 

        red_telegrams = [t for t in telegrams if t.get("is_red")]
        normal_telegrams = [t for t in telegrams if not t.get("is_red")]

        text_content = ""

        if red_telegrams:
            text_content += "**🔴 重要电报**\n\n"
            for i, telegram in enumerate(red_telegrams, 1):
                title = telegram.get("content", "")
                time = telegram.get("time", "")
                url = telegram.get("url", "")

                if url:
                    text_content += f"  {i}. [{time}] **[{title}]({url})**\n\n"
                else:
                    text_content += f"  {i}. [{time}] **{title}**\n\n"

            if normal_telegrams:
                text_content += f"{CONFIG['FILE_SEPARATOR']}\n\n"

        if normal_telegrams:
            text_content += "**📰 一般电报**\n\n"
            for i, telegram in enumerate(normal_telegrams, 1):
                title = telegram.get("content", "")
                time = telegram.get("time", "")
                url = telegram.get("url", "")

                if url:
                    text_content += f"  {i}. [{time}] [{title}]({url})\n\n"
                else:
                    text_content += f"  {i}. [{time}] {title}\n\n"

        return text_content


def main():
    telegrams = CailianpressAPI.fetch_telegrams()
    if not telegrams:
        print("未获取到财联社电报或获取失败。")
        return

    # 在保存到文件之前，我们将所有的电报（包括新抓取到的和已存在的）合并、去重、排序，然后一次性写入。
    # `FileWriter.save_telegrams_to_file` 现在内部会处理这些逻辑。
    saved_any_new = FileWriter.save_telegrams_to_file(telegrams)

    # 飞书 Webhook 应该只发送本次运行中新获取并保存的电报
    # 为了实现这一点，我们需要在 `save_telegrams_to_file` 中返回实际保存的新电报列表，
    # 或者像现在这样，在 `main` 函数中重新进行过滤。
    # 重新过滤新电报以便发送 Feishu Webhook：
    output_dir = Path(CONFIG["OUTPUT_DIR"])
    today_date = TimeHelper.get_beijing_time().strftime("%Y-%m-%d")
    file_path = output_dir / f"财联社电报_{today_date}.md"
    
    # 获取当前文件中的所有电报ID
    existing_ids_after_save = FileWriter._get_existing_telegram_ids(file_path)

    # 找到本次抓取到的电报中，哪些是真正新加入文件（即之前文件里没有的）
    new_telegrams_for_webhook = [
        t for t in telegrams 
        if t.get("id") in existing_ids_after_save and # 确保它最终被保存了
           not any(ex_t.get("id") == t.get("id") for ex_t in FileWriter._read_existing_telegrams(file_path) if ex_t.get("id") != t.get("id")) # 确保它不是旧的
    ]
    # 更简单的方法是，在save_telegrams_to_file中返回真正的新增电报
    # 但为了保持main的逻辑最小化修改，我们在这里进行筛选。
    # 实际上，`main`函数最开始的 `new_telegrams_to_process` 才是应该发送给 Feishu 的内容。
    # 让我们改回使用那个列表。

    # 重新声明 new_telegrams_to_process，确保它是本次运行中抓取到且之前未保存的
    # 这部分逻辑需要放在 `FileWriter.save_telegrams_to_file` 之前执行，
    # 因为 `save_telegrams_to_file` 已经处理了合并和去重。
    # 所以，我们把最初的过滤逻辑放回这里，然后把它传递给保存和发送。
    
    # 过滤掉已存在的电报，得到真正需要处理的新电报 (用于文件保存和飞书推送)
    # 重新获取一次文件中的 ID，以确保我们只处理最新的增量
    file_path_for_today = output_dir / f"财联社电报_{today_date}.md"
    current_existing_ids = FileWriter._get_existing_telegram_ids(file_path_for_today)
    
    new_telegrams_to_process_for_all = [t for t in telegrams if str(t.get("id")) not in current_existing_ids]

    if not new_telegrams_to_process_for_all:
        print("没有新的财联社电报需要保存或发送。")
        return

    # 再次强调，这里是真正新增的电报，需要排序后保存和推送
    new_telegrams_to_process_for_all.sort(key=lambda x: int(x.get("timestamp_raw", 0)), reverse=True)

    # 保存新的电报到文件 (FileWriter.save_telegrams_to_file 内部会合并、去重、排序并重写文件)
    # 传入所有本次抓取到的电报，让FileWriter内部去重和合并
    FileWriter.save_telegrams_to_file(telegrams) # 这里应该传入原始获取到的所有电报，让FileWriter内部处理

    # 尝试发送 Webhook 到飞书自动化 (只发送本次运行中**新发现**的电报)
    webhook_url = CONFIG["FEISHU_WEBHOOK_URL"]
    if webhook_url:
        try:
            # 构建发送到飞书 Webhook 的内容，这里使用上面过滤出来的 `new_telegrams_to_process_for_all`
            # 这样飞书只会收到本次新增的电报，而不是文件中的所有电报
            combined_telegram_content = "\n\n".join([
                f"[{t.get('time', '')}] {t.get('content', '')} - {t.get('url', '')}"
                for t in new_telegrams_to_process_for_all # 使用真正的新电报列表
            ])

            if not combined_telegram_content:
                print("没有新的电报内容可供飞书推送。")
                return

            payload = {
                "content": {
                    "text": combined_telegram_content,
                    "total_titles": len(new_telegrams_to_process_for_all),
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
