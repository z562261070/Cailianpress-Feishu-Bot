# cailianpress_to_feishu_rewritten.py

import json
import time
import random
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
import re
import hashlib
import urllib.parse
from typing import Optional, List

import requests
import pytz

# --- 1. 配置常量 ---
CONFIG = {
    "OUTPUT_DIR": "./output/cls",  # 输出目录
    "FEISHU_WEBHOOK_URL": os.getenv("FEISHU_WEBHOOK_URL", ""),  # 飞书自动化 Webhook URL
    "MAX_TELEGRAMS_FETCH": 100,  # 每次API请求最大获取电报数量 (根据财联社API实际能力调整)
    "RED_KEYWORDS": ["利好", "利空", "重要", "突发", "紧急", "关注", "提醒", "涨停", "大跌", "突破"],  # 标红关键词，可扩展
    "FILE_SEPARATOR": "━━━━━━━━━━━━━━━━━━━",  # 文件内容分割线
    "USE_PROXY": os.getenv("USE_PROXY", "False").lower() == "true",
    "DEFAULT_PROXY": os.getenv("DEFAULT_PROXY", "http://127.0.0.1:10086"),
    "REQUEST_TIMEOUT": 15, # 请求超时时间
    "RETRY_ATTEMPTS": 3, # 请求重试次数
    "RETRY_DELAY": 5, # 重试间隔秒数
    "KEEP_FILES_COUNT": 7, # 保留的文件数量，超过此数量的旧文件将被自动删除
}

# --- 2. 时间处理工具类 ---
class TimeHelper:
    """提供时间相关的辅助方法"""
    BEIJING_TZ = pytz.timezone("Asia/Shanghai")
    @staticmethod
    def get_beijing_time() -> datetime: return datetime.now(TimeHelper.BEIJING_TZ)
    @staticmethod
    def format_date(dt: datetime = None) -> str: return (dt or TimeHelper.get_beijing_time()).strftime("%Y年%m月%d日")
    @staticmethod
    def format_time(dt: datetime = None) -> str: return (dt or TimeHelper.get_beijing_time()).strftime("%H:%M:%S")
    @staticmethod
    def format_datetime(dt: datetime = None) -> str: return (dt or TimeHelper.get_beijing_time()).strftime("%Y-%m-%d %H:%M:%S")
    @staticmethod
    def timestamp_to_beijing_datetime(timestamp: int) -> datetime: return datetime.fromtimestamp(timestamp, TimeHelper.BEIJING_TZ)
    @staticmethod
    def timestamp_to_hhmm(timestamp: int) -> str:
        try: return TimeHelper.timestamp_to_beijing_datetime(timestamp).strftime("%H:%M")
        except (ValueError, TypeError): return ""

# --- 3. 财联社 API 交互类 ---
class CailianpressAPI:
    """处理财联社电报数据的获取和解析"""
    BASE_URL = "https://www.cls.cn/nodeapi/updateTelegraphList"
    APP_PARAMS = {"app_name": "CailianpressWeb", "os": "web", "sv": "7.7.5"}
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    @staticmethod
    def _generate_signature(params: dict) -> str:
        sorted_keys = sorted(params.keys())
        params_string = "&".join([f"{key}={params[key]}" for key in sorted_keys])
        sha1_hash = hashlib.sha1(params_string.encode('utf-8')).hexdigest()
        return hashlib.md5(sha1_hash.encode('utf-8')).hexdigest()
    @staticmethod
    def _get_request_params() -> dict:
        all_params = {**CailianpressAPI.APP_PARAMS}
        all_params["sign"] = CailianpressAPI._generate_signature(all_params)
        return all_params
    @staticmethod
    def fetch_telegrams() -> list[dict]:
        params = CailianpressAPI._get_request_params()
        full_url = f"{CailianpressAPI.BASE_URL}?{urllib.parse.urlencode(params)}"
        proxies = {"http": CONFIG["DEFAULT_PROXY"], "https": CONFIG["DEFAULT_PROXY"]} if CONFIG["USE_PROXY"] else None
        print(f"[{TimeHelper.format_datetime()}] 正在请求财联社API...")
        for attempt in range(CONFIG["RETRY_ATTEMPTS"]):
            try:
                response = requests.get(full_url, proxies=proxies, headers=CailianpressAPI.HEADERS, timeout=CONFIG["REQUEST_TIMEOUT"])
                response.raise_for_status()
                data = response.json()
                if data.get("error") == 0 and data.get("data") and data["data"].get("roll_data"):
                    raw_telegrams = data["data"]["roll_data"]
                    print(f"[{TimeHelper.format_datetime()}] 成功获取 {len(raw_telegrams)} 条原始财联社电报。")
                    processed = []
                    for item in raw_telegrams:
                        if item.get("is_ad"): continue
                        item_id = str(item.get("id"))
                        title = item.get("title", "")
                        content = item.get("brief", "") or title
                        timestamp = item.get("ctime")
                        item_time_str, ts_int = "", None
                        if timestamp:
                            try:
                                ts_int = int(timestamp)
                                item_time_str = TimeHelper.timestamp_to_hhmm(ts_int)
                            except (ValueError, TypeError): pass
                        processed.append({
                            "id": item_id, "content": content, "time": item_time_str,
                            "url": f"https://www.cls.cn/detail/{item_id}" if item_id else "",
                            "is_red": any(k in (title + content) for k in CONFIG["RED_KEYWORDS"]),
                            "timestamp_raw": ts_int
                        })
                    return processed
            except requests.exceptions.RequestException as e: print(f"[{TimeHelper.format_datetime()}] 请求API失败 (尝试 {attempt + 1}): {e}")
            except json.JSONDecodeError as e: print(f"[{TimeHelper.format_datetime()}] JSON解析失败 (尝试 {attempt + 1}): {e}")
            if attempt < CONFIG["RETRY_ATTEMPTS"] - 1: time.sleep(CONFIG["RETRY_DELAY"])
        return []

# --- 4. 文件写入与读取类 (已重构为仅追加模式) ---
class TelegramFileManager:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, date_str: str) -> Path:
        return self.output_dir / f"cls_{date_str}.md"

    def get_existing_ids_for_date(self, date_str: str) -> set:
        """仅用于获取文件中已存在的ID集合，用于去重。"""
        file_path = self._get_file_path(date_str)
        if not file_path.exists():
            return set()
        
        ids = set()
        content = file_path.read_text(encoding="utf-8")
        # 正则表达式从URL中提取ID
        found_ids = re.findall(r'\(https://www.cls.cn/detail/(\d+)\)', content)
        ids.update(found_ids)
        return ids

    def _format_telegram_lines_for_insertion(self, telegram: dict) -> List[str]:
        """将单条电报格式化为要插入文件的文本行列表。"""
        title = telegram.get("content", "")
        time_str = telegram.get("time", "")
        url = telegram.get("url", "")
        is_red = telegram.get("is_red", False)
        
        line = ""
        if url:
            if is_red: line = f"  - [{time_str}] **[{title}]({url})**"
            else: line = f"  - [{time_str}] [{title}]({url})"
        else: # Fallback
            if is_red: line = f"  - [{time_str}] **{title}**"
            else: line = f"  - [{time_str}] {title}"
        
        return [line, ""] # 返回内容行和紧随其后的一个空行

    def append_new_telegrams(self, new_telegrams: List[dict]) -> bool:
        """
        核心方法：将新电报追加到对应的日期文件中，不改动旧内容。
        """
        if not new_telegrams:
            print(f"[{TimeHelper.format_datetime()}] 没有新电报需要保存到文件。")
            return False

        # 按时间倒序排列新电报，确保最新的在最前面
        new_telegrams.sort(key=lambda x: x.get("timestamp_raw", 0), reverse=True)
        
        # 按日期对新电报进行分组
        telegrams_by_date = {}
        for t in new_telegrams:
            if not t.get("timestamp_raw"): continue
            dt = TimeHelper.timestamp_to_beijing_datetime(t["timestamp_raw"])
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in telegrams_by_date: telegrams_by_date[date_str] = []
            telegrams_by_date[date_str].append(t)

        saved_any_new = False
        for date_str, items_for_day in telegrams_by_date.items():
            file_path = self._get_file_path(date_str)
            
            new_red = [t for t in items_for_day if t.get("is_red")]
            new_normal = [t for t in items_for_day if not t.get("is_red")]

            # 将新电报格式化为待插入的行
            new_red_lines = [line for t in new_red for line in self._format_telegram_lines_for_insertion(t)]
            new_normal_lines = [line for t in new_normal for line in self._format_telegram_lines_for_insertion(t)]

            # 读取现有文件或创建模板
            if file_path.exists():
                lines = file_path.read_text(encoding="utf-8").split('\n')
            else:
                lines = ["**🔴 重要电报**", "", CONFIG["FILE_SEPARATOR"], "", "**📰 一般电报**", ""]
            
            # 插入“一般电报”
            if new_normal_lines:
                try:
                    idx = lines.index("**📰 一般电报**") + 1
                    # 在标题行和第一条内容间插入一个空行（如果需要）
                    if idx < len(lines) and lines[idx].strip() != "": lines.insert(idx, "")
                    lines[idx+1:idx+1] = new_normal_lines
                    saved_any_new = True
                except ValueError: # 如果标题不存在，则在末尾追加
                    lines.extend(["", CONFIG["FILE_SEPARATOR"], "", "**📰 一般电报**", ""])
                    lines.extend(new_normal_lines)

            # 插入“重要电报”
            if new_red_lines:
                try:
                    idx = lines.index("**🔴 重要电报**") + 1
                    if idx < len(lines) and lines[idx].strip() != "": lines.insert(idx, "")
                    lines[idx+1:idx+1] = new_red_lines
                    saved_any_new = True
                except ValueError: # 如果标题不存在，则在开头追加
                    lines.insert(0, "**🔴 重要电报**")
                    lines.insert(1, "")
                    lines[2:2] = new_red_lines

            # 将更新后的内容写回文件
            try:
                file_path.write_text("\n".join(lines), encoding="utf-8")
                print(f"[{TimeHelper.format_datetime()}] 已将 {len(items_for_day)} 条新电报追加到文件: {file_path}")
            except Exception as e:
                print(f"[{TimeHelper.format_datetime()}] 写入文件失败: {e}")

        return saved_any_new

    def cleanup_old_files(self, keep_count: int = 7) -> None:
        """
        自动清理旧文件，只保留最近创建的指定数量的文件。
        
        Args:
            keep_count: 要保留的文件数量，默认为7个
        """
        try:
            # 获取输出目录中所有的cls_*.md文件
            pattern = "cls_*.md"
            files = list(self.output_dir.glob(pattern))
            
            if len(files) <= keep_count:
                print(f"[{TimeHelper.format_datetime()}] 当前文件数量 {len(files)} 未超过保留限制 {keep_count}，无需清理。")
                return
            
            # 按文件的修改时间排序，最新的在前
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # 保留最新的keep_count个文件，删除其余的
            files_to_keep = files[:keep_count]
            files_to_delete = files[keep_count:]
            
            if files_to_delete:
                print(f"[{TimeHelper.format_datetime()}] 发现 {len(files)} 个文件，将保留最新的 {keep_count} 个，删除 {len(files_to_delete)} 个旧文件。")
                
                for file_path in files_to_delete:
                    try:
                        file_path.unlink()  # 删除文件
                        print(f"[{TimeHelper.format_datetime()}] 已删除旧文件: {file_path.name}")
                    except Exception as e:
                        print(f"[{TimeHelper.format_datetime()}] 删除文件失败 {file_path.name}: {e}")
                
                print(f"[{TimeHelper.format_datetime()}] 文件清理完成，当前保留文件: {[f.name for f in files_to_keep]}")
            
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 文件清理过程中出错: {e}")

# --- 5. 五天整合文件管理类 ---
class FiveDaysSummaryManager:
    """负责生成最近5天的整合文件"""
    def __init__(self, output_dir: str):
        self.base_output_dir = Path(output_dir)
        self.summary_dir = self.base_output_dir / "5days"
        self.summary_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_five_days_summary(self) -> None:
        """生成最近5天的整合文件"""
        print(f"[{TimeHelper.format_datetime()}] 开始生成最近5天的整合文件...")
        
        current_time = TimeHelper.get_beijing_time()
        summary_lines = []
        summary_lines.append(f"# 财联社电报 - 最近5天整合")
        summary_lines.append(f"")
        summary_lines.append(f"**生成时间**: {TimeHelper.format_datetime()}")
        summary_lines.append(f"**数据范围**: {(current_time - timedelta(days=4)).strftime('%Y-%m-%d')} 至 {current_time.strftime('%Y-%m-%d')}")
        summary_lines.append(f"")
        summary_lines.append(CONFIG["FILE_SEPARATOR"])
        summary_lines.append(f"")
        
        total_telegrams = 0
        
        # 遍历最近5天
        for day_offset in range(5):
            target_date = current_time - timedelta(days=day_offset)
            date_str = target_date.strftime("%Y-%m-%d")
            file_path = self.base_output_dir / f"cls_{date_str}.md"
            
            summary_lines.append(f"## {target_date.strftime('%Y年%m月%d日')} ({target_date.strftime('%A')})")
            summary_lines.append(f"")
            
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    
                    # 提取重要电报部分
                    red_section = self._extract_section(content, "**🔴 重要电报**")
                    if red_section:
                        summary_lines.append("### 🔴 重要电报")
                        summary_lines.append("")
                        summary_lines.extend(red_section)
                        summary_lines.append("")
                        total_telegrams += len([line for line in red_section if line.strip().startswith("- ")])
                    
                    # 提取一般电报部分
                    normal_section = self._extract_section(content, "**📰 一般电报**")
                    if normal_section:
                        summary_lines.append("### 📰 一般电报")
                        summary_lines.append("")
                        summary_lines.extend(normal_section)
                        summary_lines.append("")
                        total_telegrams += len([line for line in normal_section if line.strip().startswith("- ")])
                    
                    if not red_section and not normal_section:
                        summary_lines.append("*该日期暂无电报数据*")
                        summary_lines.append("")
                        
                except Exception as e:
                    print(f"[{TimeHelper.format_datetime()}] 读取文件 {file_path} 失败: {e}")
                    summary_lines.append("*读取该日期数据时出错*")
                    summary_lines.append("")
            else:
                summary_lines.append("*该日期文件不存在*")
                summary_lines.append("")
            
            summary_lines.append(CONFIG["FILE_SEPARATOR"])
            summary_lines.append("")
        
        # 添加统计信息
        summary_lines.append(f"## 📊 统计信息")
        summary_lines.append(f"")
        summary_lines.append(f"- **总电报数量**: {total_telegrams} 条")
        summary_lines.append(f"- **数据来源**: 财联社")
        summary_lines.append(f"- **整合范围**: 最近5天")
        summary_lines.append(f"")
        
        # 保存整合文件
        summary_filename = f"财联社电报_最近5天_{current_time.strftime('%Y%m%d_%H%M%S')}.md"
        summary_file_path = self.summary_dir / summary_filename
        
        try:
            summary_file_path.write_text("\n".join(summary_lines), encoding="utf-8")
            print(f"[{TimeHelper.format_datetime()}] 5天整合文件已生成: {summary_file_path}")
            print(f"[{TimeHelper.format_datetime()}] 整合了 {total_telegrams} 条电报数据")
            
            # 清理旧的整合文件，只保留最新的1个
            self._cleanup_old_summary_files()
            
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 生成整合文件失败: {e}")
    
    def _extract_section(self, content: str, section_title: str) -> List[str]:
        """从文件内容中提取指定章节的内容"""
        lines = content.split('\n')
        section_lines = []
        in_section = False
        
        for line in lines:
            if line.strip() == section_title:
                in_section = True
                continue
            elif in_section and line.strip().startswith("**") and "电报" in line:
                # 遇到下一个章节标题，停止提取
                break
            elif in_section and line.strip() == CONFIG["FILE_SEPARATOR"]:
                # 遇到分隔符，停止提取
                break
            elif in_section:
                section_lines.append(line)
        
        # 移除末尾的空行
        while section_lines and not section_lines[-1].strip():
            section_lines.pop()
        
        return section_lines
    
    def _cleanup_old_summary_files(self, keep_count: int = 1) -> None:
        """清理旧的整合文件，只保留最新的1个"""
        try:
            pattern = "财联社电报_最近5天_*.md"
            files = list(self.summary_dir.glob(pattern))
            
            if len(files) <= keep_count:
                return
            
            # 按文件的修改时间排序，最新的在前
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # 删除多余的文件
            files_to_delete = files[keep_count:]
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    print(f"[{TimeHelper.format_datetime()}] 已删除旧的整合文件: {file_path.name}")
                except Exception as e:
                    print(f"[{TimeHelper.format_datetime()}] 删除整合文件失败 {file_path.name}: {e}")
                    
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 清理整合文件时出错: {e}")

# --- 6. 飞书通知类 ---
class FeishuNotifier:
    """负责向飞书自动化发送通知"""
    def __init__(self, webhook_url: str): self.webhook_url = webhook_url
    def send_notification(self, new_telegrams: list[dict]) -> None:
        if not self.webhook_url: return
        if not new_telegrams:
            print(f"[{TimeHelper.format_datetime()}] 没有新的电报内容可供飞书推送。")
            return
        
        # 按时间升序发送通知，方便阅读
        new_telegrams.sort(key=lambda x: x.get("timestamp_raw", 0))
        content = "\n\n".join([f"[{t.get('time')}] {t.get('content')} - {t.get('url')}" for t in new_telegrams])
        payload = {"content": {"text": content, "total_titles": len(new_telegrams), "timestamp": TimeHelper.format_datetime(), "report_type": "财联社电报"}}
        
        print(f"[{TimeHelper.format_datetime()}] 正在发送 {len(new_telegrams)} 条新电报到飞书自动化。")
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=CONFIG["REQUEST_TIMEOUT"])
            if response.status_code != 200:
                print(f"[{TimeHelper.format_datetime()}] 发送飞书通知失败，状态码：{response.status_code}，响应：{response.text}")
        except requests.exceptions.RequestException as e:
            print(f"[{TimeHelper.format_datetime()}] 发送飞书通知出错：{e}")

# --- 6. 主程序逻辑 ---
def main():
    """主函数，编排整个爬取、保存和通知流程"""
    print(f"\n--- 财联社电报抓取与通知程序启动 --- [{TimeHelper.format_datetime()}]")

    file_manager = TelegramFileManager(CONFIG["OUTPUT_DIR"])
    feishu_notifier = FeishuNotifier(CONFIG["FEISHU_WEBHOOK_URL"])
    summary_manager = FiveDaysSummaryManager(CONFIG["OUTPUT_DIR"])

    # 1. 获取财联社电报
    fetched_telegrams = CailianpressAPI.fetch_telegrams()
    if not fetched_telegrams:
        print(f"[{TimeHelper.format_datetime()}] 未获取到任何财联社电报，程序退出。")
        return

    # 2. 识别真正的新电报 (用于文件追加和飞书通知)
    today_date_str = TimeHelper.get_beijing_time().strftime("%Y-%m-%d")
    existing_ids = file_manager.get_existing_ids_for_date(today_date_str)
    
    new_telegrams = [t for t in fetched_telegrams if t.get("id") and t["id"] not in existing_ids and t.get("timestamp_raw")]

    if not new_telegrams:
        print(f"[{TimeHelper.format_datetime()}] 本次运行没有发现需要记录的新电报。")
    else:
        print(f"[{TimeHelper.format_datetime()}] 发现 {len(new_telegrams)} 条新电报需要处理。")

    # 3. 将新电报追加到文件
    file_manager.append_new_telegrams(new_telegrams)

    # 4. 发送飞书通知
    feishu_notifier.send_notification(new_telegrams)

    # 5. 生成最近5天的整合文件
    summary_manager.generate_five_days_summary()

    # 6. 清理旧文件，保留最近指定数量的文件
    file_manager.cleanup_old_files(keep_count=CONFIG["KEEP_FILES_COUNT"])

    print(f"--- 财联社电报抓取与通知程序完成 --- [{TimeHelper.format_datetime()}]\n")

def generate_five_days_summary_only():
    """独立运行：仅生成最近5天的整合文件"""
    print(f"\n--- 财联社电报5天整合程序启动 --- [{TimeHelper.format_datetime()}]")
    
    summary_manager = FiveDaysSummaryManager(CONFIG["OUTPUT_DIR"])
    summary_manager.generate_five_days_summary()
    
    print(f"--- 财联社电报5天整合程序完成 --- [{TimeHelper.format_datetime()}]\n")

if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--summary":
        generate_five_days_summary_only()
    else:
        main()