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
    
    # 飞书Bot相关配置
    "FEISHU_APP_ID": os.getenv("FEISHU_APP_ID", ""),  # 飞书应用ID
    "FEISHU_APP_SECRET": os.getenv("FEISHU_APP_SECRET", ""),  # 飞书应用密钥
    "FEISHU_CHAT_ID": os.getenv("FEISHU_CHAT_ID", ""),  # 飞书群聊ID
    "ENABLE_FEISHU_BOT": os.getenv("ENABLE_FEISHU_BOT", "False").lower() == "true",  # 是否启用飞书Bot推送
    "FEISHU_MAX_FILE_SIZE": 20 * 1024 * 1024,  # 飞书文件上传最大限制 20MB
    
    # Gitee Token分发配置
    "ENABLE_GITEE_TOKEN_SHARE": os.getenv("ENABLE_GITEE_TOKEN_SHARE", "False").lower() == "true",  # 默认关闭Gitee
    "GITEE_ACCESS_TOKEN": os.getenv("GITEE_ACCESS_TOKEN", ""),  # Gitee个人访问令牌 - 请设置你的真实token
    "GITEE_OWNER": os.getenv("GITEE_OWNER", "zhanweifu"),  # Gitee用户名或组织名
    "GITEE_REPO": os.getenv("GITEE_REPO", "cailianshewenjian"),  # Gitee仓库名
    "GITEE_FILE_PATH": os.getenv("GITEE_FILE_PATH", "new.json"),  # 存储token的文件路径
    
    # 腾讯云函数 Token分发配置
    "ENABLE_TENCENT_CLOUD_TOKEN_SHARE": True,  # !!!注意：已强制开启腾讯云函数功能!!!
     "TENCENT_CLOUD_API_URL": "https://1371601812-k9mik95whg.ap-shanghai.tencentscf.com",  # !!!注意：请将这里替换成您的真实URL!!!
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

# --- 7. 飞书Bot管理类 ---
class FeishuBotManager:
    """负责飞书Bot文件上传和群聊推送"""
    
    def __init__(self, app_id: str, app_secret: str, chat_id: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.chat_id = chat_id
        self.access_token = None
        self.token_expires_at = 0
        
        # 飞书API端点
        self.token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        self.upload_url = "https://open.feishu.cn/open-apis/im/v1/files"
        self.message_url = "https://open.feishu.cn/open-apis/im/v1/messages"
        self.download_url = "https://open.feishu.cn/open-apis/drive/v1/medias/{}/download"
        
        # 用于客户端的app_access_token端点
        self.app_token_url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
    
    def _is_token_valid(self) -> bool:
        """检查当前token是否有效"""
        return self.access_token and time.time() < self.token_expires_at
    
    def get_tenant_access_token(self) -> Optional[str]:
        """获取飞书租户访问令牌"""

        
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            print(f"[{TimeHelper.format_datetime()}] 正在获取飞书访问令牌...")
            response = requests.post(self.token_url, json=payload, timeout=CONFIG["REQUEST_TIMEOUT"])
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") == 0:
                self.access_token = data.get("tenant_access_token")
                # 飞书token有效期为2小时，我们提前5分钟刷新
                self.token_expires_at = time.time() + data.get("expire", 7200) - 300
                print(f"[{TimeHelper.format_datetime()}] 飞书访问令牌获取成功")
                return self.access_token
            else:
                print(f"[{TimeHelper.format_datetime()}] 获取飞书访问令牌失败: {data.get('msg', '未知错误')}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"[{TimeHelper.format_datetime()}] 获取飞书访问令牌请求失败: {e}")
            return None
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 获取飞书访问令牌出错: {e}")
            return None
    
    def upload_file(self, file_path: Path) -> Optional[str]:
        """上传文件到飞书，返回file_key"""
        if not file_path.exists():
            print(f"[{TimeHelper.format_datetime()}] 文件不存在: {file_path}")
            return None
        
        # 检查文件大小
        file_size = file_path.stat().st_size
        if file_size > CONFIG["FEISHU_MAX_FILE_SIZE"]:
            print(f"[{TimeHelper.format_datetime()}] 文件过大，无法上传到飞书: {file_path.name} ({file_size / 1024 / 1024:.2f}MB)")
            return None
        
        token = self.get_tenant_access_token()
        if not token:
            return None
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            print(f"[{TimeHelper.format_datetime()}] 正在上传文件到飞书: {file_path.name}")
            
            with open(file_path, 'rb') as f:
                files = {
                    'file': (file_path.name, f, 'text/markdown'),
                    'file_type': (None, 'stream'),
                    'file_name': (None, file_path.name)
                }
                
                response = requests.post(self.upload_url, headers=headers, files=files, timeout=CONFIG["REQUEST_TIMEOUT"])
                response.raise_for_status()
                
                data = response.json()
                if data.get("code") == 0:
                    file_key = data.get("data", {}).get("file_key")
                    print(f"[{TimeHelper.format_datetime()}] 文件上传成功: {file_path.name}, file_key: {file_key}")
                    return file_key
                else:
                    print(f"[{TimeHelper.format_datetime()}] 文件上传失败: {data.get('msg', '未知错误')}")
                    return None
                    
        except requests.exceptions.RequestException as e:
            print(f"[{TimeHelper.format_datetime()}] 文件上传请求失败: {e}")
            return None
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 文件上传出错: {e}")
            return None
    
    def send_file_message(self, file_key: str, file_name: str) -> bool:
        """发送文件消息到群聊"""
        token = self.get_tenant_access_token()
        if not token:
            return False
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 构建消息内容
        content = {
            "file_key": file_key
        }
        
        payload = {
            "receive_id": self.chat_id,
            "msg_type": "file",
            "content": json.dumps(content)
        }
        
        try:
            print(f"[{TimeHelper.format_datetime()}] 正在发送文件消息到飞书群聊: {file_name}")
            
            response = requests.post(
                f"{self.message_url}?receive_id_type=chat_id",
                headers=headers,
                json=payload,
                timeout=CONFIG["REQUEST_TIMEOUT"]
            )
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") == 0:
                print(f"[{TimeHelper.format_datetime()}] 文件消息发送成功: {file_name}")
                return True
            else:
                print(f"[{TimeHelper.format_datetime()}] 文件消息发送失败: {data.get('msg', '未知错误')}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"[{TimeHelper.format_datetime()}] 发送文件消息请求失败: {e}")
            return False
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 发送文件消息出错: {e}")
            return False
    
    def upload_and_send_file(self, file_path: Path) -> bool:
        """上传文件并发送到群聊的组合方法"""
        if not file_path.exists():
            print(f"[{TimeHelper.format_datetime()}] 文件不存在，无法发送: {file_path}")
            return False
        
        # 上传文件
        file_key = self.upload_file(file_path)
        if not file_key:
            return False
        
        # 发送文件消息
        return self.send_file_message(file_key, file_path.name)
    
    def send_text_message(self, text: str) -> bool:
        """发送文本消息到群聊"""
        token = self.get_tenant_access_token()
        if not token:
            return False
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "receive_id": self.chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text})
        }

        try:
            print(f"[{TimeHelper.format_datetime()}] 正在发送文本消息到飞书群聊...")
            response = requests.post(
                f"{self.message_url}?receive_id_type=chat_id",
                headers=headers,
                json=payload,
                timeout=CONFIG["REQUEST_TIMEOUT"]
            )
            response.raise_for_status()

            data = response.json()
            if data.get("code") == 0:
                print(f"[{TimeHelper.format_datetime()}] 文本消息发送成功")
                return True
            else:
                print(f"[{TimeHelper.format_datetime()}] 文本消息发送失败: {data.get('msg', '未知错误')}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"[{TimeHelper.format_datetime()}] 发送文本消息请求失败: {e}")
            return False
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 发送文本消息出错: {e}")
            return False

    def send_access_token_message(self) -> bool:
        """发送 access_token 到群聊"""
        token = self.get_tenant_access_token()
        if not token:
            print(f"[{TimeHelper.format_datetime()}] 无法获取 access_token，无法发送消息。")
            return False
        
        message_content = f"[系统消息] 新的飞书 access_token 已更新：{token}"
        return self.send_text_message(message_content)

        
        payload = {
            "receive_id": self.chat_id,
            "msg_type": "text",
            "content": json.dumps(content)
        }
        
        try:
            response = requests.post(
                f"{self.message_url}?receive_id_type=chat_id",
                headers=headers,
                json=payload,
                timeout=CONFIG["REQUEST_TIMEOUT"]
            )
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") == 0:
                print(f"[{TimeHelper.format_datetime()}] 文本消息发送成功")
                return True
            else:
                print(f"[{TimeHelper.format_datetime()}] 文本消息发送失败: {data.get('msg', '未知错误')}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"[{TimeHelper.format_datetime()}] 发送文本消息请求失败: {e}")
            return False
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 发送文本消息出错: {e}")
            return False
    
    def get_and_send_app_access_token(self, gitee_distributor: Optional['GiteeTokenDistributor'] = None, tencent_cloud_distributor: Optional['TencentCloudTokenDistributor'] = None) -> bool:
        """获取app_access_token并发送到飞书群，同时可选择分发到Gitee和腾讯云函数"""
        try:
            print(f"[{TimeHelper.format_datetime()}] 正在获取客户端用的app_access_token...")
            
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }
            
            response = requests.post(self.app_token_url, json=payload, timeout=CONFIG["REQUEST_TIMEOUT"])
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") == 0:
                app_access_token = data.get("app_access_token")
                expire_time = data.get("expire", 7200)  # 默认2小时
                
                # 计算过期时间
                expire_datetime = TimeHelper.get_beijing_time() + timedelta(seconds=expire_time)
                
                # 构建token消息
                token_message = f"🔑 ACCESS_TOKEN_UPDATE\n" \
                              f"Token: {app_access_token}\n" \
                              f"过期时间: {expire_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                              f"有效期: {expire_time}秒\n" \
                              f"生成时间: {TimeHelper.format_datetime()}\n" \
                              f"⚠️ 此token供客户端应用使用，请勿泄露"
                
                # 发送token到群聊
                feishu_success = self.send_text_message(token_message)
                
                # 分发token到Gitee（如果启用）
                gitee_success = True
                if gitee_distributor:
                    print(f"[{TimeHelper.format_datetime()}] 开始分发token到Gitee...")
                    gitee_success = gitee_distributor.distribute_token(app_access_token, expire_time)
                
                # 分发token到腾讯云函数（如果启用）
                tencent_cloud_success = True
                if tencent_cloud_distributor:
                    print(f"[{TimeHelper.format_datetime()}] 开始分发token到腾讯云函数...")
                    tencent_cloud_success = tencent_cloud_distributor.distribute_token(app_access_token, expire_time)
                
                if feishu_success:
                    print(f"[{TimeHelper.format_datetime()}] app_access_token已成功发送到飞书群")
                else:
                    print(f"[{TimeHelper.format_datetime()}] app_access_token发送到飞书群失败")
                
                if gitee_distributor:
                    if gitee_success:
                        print(f"[{TimeHelper.format_datetime()}] app_access_token已成功分发到Gitee")
                    else:
                        print(f"[{TimeHelper.format_datetime()}] app_access_token分发到Gitee失败")
                
                if tencent_cloud_distributor:
                    if tencent_cloud_success:
                        print(f"[{TimeHelper.format_datetime()}] app_access_token已成功分发到腾讯云函数")
                    else:
                        print(f"[{TimeHelper.format_datetime()}] app_access_token分发到腾讯云函数失败")
                
                # 只要有一个成功就返回True
                return feishu_success or gitee_success or tencent_cloud_success
            else:
                print(f"[{TimeHelper.format_datetime()}] 获取app_access_token失败: {data.get('msg', '未知错误')}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"[{TimeHelper.format_datetime()}] 获取app_access_token请求失败: {e}")
            return False
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 获取app_access_token出错: {e}")
            return False

# --- 8. Gitee Token分发类 ---
class GiteeTokenDistributor:
    """负责将access_token分发到Gitee仓库，供客户端获取"""
    
    def __init__(self, access_token: str, owner: str, repo: str, file_path: str):
        self.access_token = access_token
        self.owner = owner
        self.repo = repo
        self.file_path = file_path
        
        # Gitee API端点
        self.api_base = "https://gitee.com/api/v5"
        self.file_url = f"{self.api_base}/repos/{owner}/{repo}/contents/{file_path}"
    
    def get_file_info(self) -> Optional[dict]:
        """获取文件信息，包括SHA值（用于更新文件）"""
        try:
            params = {"access_token": self.access_token}
            response = requests.get(self.file_url, params=params, timeout=CONFIG["REQUEST_TIMEOUT"])
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # 文件不存在
                return None
            else:
                print(f"[{TimeHelper.format_datetime()}] 获取Gitee文件信息失败: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"[{TimeHelper.format_datetime()}] 获取Gitee文件信息请求失败: {e}")
            return None
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 获取Gitee文件信息出错: {e}")
            return None
    
    def upload_token_file(self, token_data: dict) -> bool:
        """上传或更新token文件到Gitee"""
        try:
            # 将token数据转换为JSON字符串
            import base64
            content = json.dumps(token_data, ensure_ascii=False, indent=2)
            content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            # 获取现有文件信息
            file_info = self.get_file_info()
            
            # 构建请求数据
            data = {
                "access_token": self.access_token,
                "content": content_base64,
                "message": f"Update feishu access token - {TimeHelper.format_datetime()}",
                "branch": "master"
            }
            
            # 如果文件已存在，需要提供SHA值
            if file_info:
                data["sha"] = file_info.get("sha")
                print(f"[{TimeHelper.format_datetime()}] 正在更新Gitee中的token文件...")
                method = "PUT"
            else:
                print(f"[{TimeHelper.format_datetime()}] 正在创建Gitee中的token文件...")
                method = "POST"
            
            # 发送请求
            if method == "PUT":
                response = requests.put(self.file_url, json=data, timeout=CONFIG["REQUEST_TIMEOUT"])
            else:
                response = requests.post(self.file_url, json=data, timeout=CONFIG["REQUEST_TIMEOUT"])
            
            if response.status_code in [200, 201]:
                result = response.json()
                download_url = result.get("content", {}).get("download_url", "")
                print(f"[{TimeHelper.format_datetime()}] Token文件已成功上传到Gitee")
                print(f"[{TimeHelper.format_datetime()}] 下载地址: {download_url}")
                return True
            else:
                print(f"[{TimeHelper.format_datetime()}] 上传token文件到Gitee失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 上传token文件到Gitee出错: {e}")
            return False
    
    def distribute_token(self, app_access_token: str, expire_time: int) -> bool:
        """分发token到Gitee"""
        try:
            # 计算过期时间
            expire_datetime = TimeHelper.get_beijing_time() + timedelta(seconds=expire_time)
            
            # 构建token数据
            token_data = {
                "access_token": app_access_token,
                "expire_time": expire_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                "expire_timestamp": int(expire_datetime.timestamp()),
                "valid_duration_seconds": expire_time,
                "generated_time": TimeHelper.format_datetime(),
                "generated_timestamp": int(TimeHelper.get_beijing_time().timestamp()),
                "source": "财联社自动化系统",
                "usage": "用于客户端从飞书群获取财联社电报文件",
                "download_url": f"https://gitee.com/{self.owner}/{self.repo}/raw/master/{self.file_path}"
            }
            
            # 上传到Gitee
            success = self.upload_token_file(token_data)
            if success:
                print(f"[{TimeHelper.format_datetime()}] Token已成功分发到Gitee，客户端可通过以下地址获取:")
                print(f"[{TimeHelper.format_datetime()}] {token_data['download_url']}")
                return True
            else:
                return False
                
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 分发token到Gitee出错: {e}")
            return False

# --- 9. 腾讯云函数 Token分发类 ---
class TencentCloudTokenDistributor:
    """负责将access_token分发到腾讯云函数，供客户端获取"""
    
    def __init__(self):
        self.api_url = CONFIG.get("TENCENT_CLOUD_API_URL", "")
        
    def distribute_token(self, app_access_token: str, expire_time: int) -> bool:
        """分发token到腾讯云函数"""
        try:
            if not self.api_url:
                print(f"[{TimeHelper.format_datetime()}] 腾讯云函数API地址未配置")
                return False
            
            # 计算过期时间
            expire_datetime = TimeHelper.get_beijing_time() + timedelta(seconds=expire_time)
            
            # 构建token数据
            token_data = {
                "access_token": app_access_token,
                "expire_time": expire_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                "expire_timestamp": int(expire_datetime.timestamp()),
                "valid_duration_seconds": expire_time,
                "generated_time": TimeHelper.format_datetime(),
                "generated_timestamp": int(TimeHelper.get_beijing_time().timestamp()),
                "source": "财联社自动化系统",
                "usage": "用于客户端从飞书群获取财联社电报文件",
                "platform": "腾讯云函数"
            }
            
            # 发送到腾讯云函数
            print(f"[{TimeHelper.format_datetime()}] 正在上传token到腾讯云函数...")
            response = requests.post(
                self.api_url,
                json=token_data,
                headers={'Content-Type': 'application/json'},
                timeout=CONFIG["REQUEST_TIMEOUT"]
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success', False):
                    print(f"[{TimeHelper.format_datetime()}] Token已成功分发到腾讯云函数")
                    return True
                else:
                    print(f"[{TimeHelper.format_datetime()}] 腾讯云函数返回错误: {result.get('message', '未知错误')}")
                    return False
            else:
                print(f"[{TimeHelper.format_datetime()}] 腾讯云函数HTTP错误: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[{TimeHelper.format_datetime()}] 分发token到腾讯云函数出错: {e}")
            return False

# --- 10. 主程序逻辑 ---
def main():
    """主函数，编排整个爬取、保存和通知流程"""
    print(f"\n--- 财联社电报抓取与通知程序启动 --- [{TimeHelper.format_datetime()}]")

    file_manager = TelegramFileManager(CONFIG["OUTPUT_DIR"])
    feishu_notifier = FeishuNotifier(CONFIG["FEISHU_WEBHOOK_URL"])
    summary_manager = FiveDaysSummaryManager(CONFIG["OUTPUT_DIR"])
    
    # 初始化飞书Bot管理器
    feishu_bot = None
    if CONFIG["ENABLE_FEISHU_BOT"] and CONFIG["FEISHU_APP_ID"] and CONFIG["FEISHU_APP_SECRET"] and CONFIG["FEISHU_CHAT_ID"]:
        feishu_bot = FeishuBotManager(
            CONFIG["FEISHU_APP_ID"],
            CONFIG["FEISHU_APP_SECRET"],
            CONFIG["FEISHU_CHAT_ID"]
        )
        print(f"[{TimeHelper.format_datetime()}] 飞书Bot功能已启用")
    elif CONFIG["ENABLE_FEISHU_BOT"]:
        print(f"[{TimeHelper.format_datetime()}] 飞书Bot功能已启用，但配置不完整，将跳过飞书推送")

    # 初始化Token分发器
    gitee_distributor = None
    tencent_cloud_distributor = None
    
    # Gitee分发器
    if CONFIG["ENABLE_GITEE_TOKEN_SHARE"] and CONFIG["GITEE_ACCESS_TOKEN"] and CONFIG["GITEE_OWNER"] and CONFIG["GITEE_REPO"]:
        gitee_distributor = GiteeTokenDistributor(
            CONFIG["GITEE_ACCESS_TOKEN"],
            CONFIG["GITEE_OWNER"],
            CONFIG["GITEE_REPO"],
            CONFIG["GITEE_FILE_PATH"]
        )
        print(f"[{TimeHelper.format_datetime()}] Gitee Token分发功能已启用")
        print(f"[{TimeHelper.format_datetime()}] Token将分发到: https://gitee.com/{CONFIG['GITEE_OWNER']}/{CONFIG['GITEE_REPO']}/raw/master/{CONFIG['GITEE_FILE_PATH']}")
    elif CONFIG["ENABLE_GITEE_TOKEN_SHARE"]:
        print(f"[{TimeHelper.format_datetime()}] Gitee Token分发功能已启用，但配置不完整，将跳过Gitee分发")
    
    # 腾讯云函数分发器
    if CONFIG.get("TENCENT_CLOUD_ENABLED", False) and CONFIG.get("TENCENT_CLOUD_API_URL"):
        tencent_cloud_distributor = TencentCloudTokenDistributor()
        print(f"[{TimeHelper.format_datetime()}] 腾讯云函数 Token分发功能已启用")
        print(f"[{TimeHelper.format_datetime()}] API地址: {CONFIG['TENCENT_CLOUD_API_URL']}")
    elif CONFIG.get("TENCENT_CLOUD_ENABLED", False):
        print(f"[{TimeHelper.format_datetime()}] 腾讯云函数 Token分发功能已启用，但API地址未配置，将跳过腾讯云函数分发")

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
    has_new_content = file_manager.append_new_telegrams(new_telegrams)

    # 4. 发送飞书通知
    feishu_notifier.send_notification(new_telegrams)

    # 5. 生成最近5天的整合文件
    summary_manager.generate_five_days_summary()

    # 6. 清理旧文件，保留最近指定数量的文件
    file_manager.cleanup_old_files(keep_count=CONFIG["KEEP_FILES_COUNT"])

    # 7. 飞书Bot文件推送和token管理
    if feishu_bot:
        print(f"[{TimeHelper.format_datetime()}] 开始飞书Bot相关任务...")
        
        # 检查是否需要发送新的access_token（每90分钟发送一次）
        current_time = TimeHelper.get_beijing_time()
        should_send_token = False
        
        # 检查是否是GitHub Actions环境
        is_github_actions = os.getenv("GITHUB_ACTIONS", "false").lower() == "true"
        
        if is_github_actions:
            # 在GitHub Actions中，每次运行都检查是否需要发送token
            # 通过检查当前时间的分钟数来决定（比如每90分钟的倍数时发送）
            minutes_since_midnight = current_time.hour * 60 + current_time.minute
            if minutes_since_midnight % 90 == 0:  # 每90分钟发送一次
                should_send_token = True
                print(f"[{TimeHelper.format_datetime()}] 定时发送access_token（每90分钟）")
        
        # 发送access_token
        # 无论是否是定时发送，都尝试发送一次 access_token
        token_success = feishu_bot.get_and_send_app_access_token(gitee_distributor, tencent_cloud_distributor)
        if token_success:
            print(f"[{TimeHelper.format_datetime()}] 客户端access_token已更新")
        else:
            print(f"[{TimeHelper.format_datetime()}] 客户端access_token更新失败")

        
        # 文件推送（仅在有新内容时）
        if has_new_content:
            print(f"[{TimeHelper.format_datetime()}] 开始文件推送...")
            
            # 发送今日文件
            today_file_path = file_manager._get_file_path(today_date_str)
            if today_file_path.exists():
                success = feishu_bot.upload_and_send_file(today_file_path)
                if success:
                    print(f"[{TimeHelper.format_datetime()}] 今日财联社电报文件已推送到飞书群聊")
                else:
                    print(f"[{TimeHelper.format_datetime()}] 今日财联社电报文件推送失败")
            
            # 发送5天整合文件
            summary_files = list(summary_manager.summary_dir.glob("财联社电报_最近5天_*.md"))
            if summary_files:
                # 获取最新的整合文件
                latest_summary = max(summary_files, key=lambda f: f.stat().st_mtime)
                success = feishu_bot.upload_and_send_file(latest_summary)
                if success:
                    print(f"[{TimeHelper.format_datetime()}] 5天整合文件已推送到飞书群聊")
                else:
                    print(f"[{TimeHelper.format_datetime()}] 5天整合文件推送失败")
            
            # 发送汇总消息
            if new_telegrams:
                summary_text = f"📰 财联社电报更新通知\n\n" \
                              f"🕐 更新时间: {TimeHelper.format_datetime()}\n" \
                              f"📊 新增电报: {len(new_telegrams)} 条\n" \
                              f"🔴 重要电报: {len([t for t in new_telegrams if t.get('is_red')])} 条\n" \
                              f"📁 文件已上传，请查看群聊附件获取完整内容"
                
                feishu_bot.send_text_message(summary_text)

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
