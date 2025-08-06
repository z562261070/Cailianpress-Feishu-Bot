# json_data_generator.py
# 为utools应用生成JSON格式的数据

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict, Counter

class JSONDataGenerator:
    """为utools应用生成JSON格式的财联社数据"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.json_output_dir = self.output_dir / "json"
        self.json_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 关键词配置
        self.keywords = ["机器人", "无人机", "军工", "算力", "芯片", "新能源", "人工智能", "半导体"]
        self.stock_list = ["华为", "腾讯", "药明康德", "理想汽车", "京东", "宁德时代", "山河智能", 
                          "小米", "长城军工", "胜通能源", "东杰智能", "中际旭创", "中马传动", 
                          "上纬新材", "阿里巴巴", "福元医药", "利德曼", "航天电子", "思特奇", 
                          "网易", "比亚迪", "TCL", "英伟达", "谷歌"]
    
    def generate_all_json_data(self) -> None:
        """生成所有JSON数据文件"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始生成JSON数据...")
        
        # 获取最近5天的数据
        news_data = self._extract_news_data()
        hotspot_data = self._generate_hotspot_data(news_data)
        stock_data = self._generate_stock_data(news_data)
        
        # 生成主数据文件
        main_data = {
            "lastUpdate": datetime.now().isoformat(),
            "newsData": news_data,
            "hotspotData": hotspot_data,
            "stockData": stock_data,
            "dateRange": self._get_date_range()
        }
        
        # 保存主数据文件
        main_file = self.json_output_dir / "cailianpress_data.json"
        try:
            with open(main_file, 'w', encoding='utf-8') as f:
                json.dump(main_data, f, ensure_ascii=False, indent=2)
            
            # 验证生成的JSON文件
            with open(main_file, 'r', encoding='utf-8') as f:
                json.load(f)  # 尝试解析以验证JSON有效性
            print(f"主数据文件验证成功: {main_file}")
        except Exception as e:
            print(f"主数据文件生成或验证失败: {e}")
            raise
        
        # 生成简化版本（用于快速加载）
        summary_data = {
            "lastUpdate": main_data["lastUpdate"],
            "newsCount": len(news_data),
            "dateRange": main_data["dateRange"],
            "topKeywords": hotspot_data[:10],  # 只保留前10个热点
            "topStocks": stock_data[:15]       # 只保留前15个股票
        }
        
        summary_file = self.json_output_dir / "cailianpress_summary.json"
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
            
            # 验证生成的JSON文件
            with open(summary_file, 'r', encoding='utf-8') as f:
                json.load(f)  # 尝试解析以验证JSON有效性
            print(f"摘要数据文件验证成功: {summary_file}")
        except Exception as e:
            print(f"摘要数据文件生成或验证失败: {e}")
            raise
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] JSON数据生成完成")
        print(f"  - 新闻数据: {len(news_data)} 条")
        print(f"  - 热点数据: {len(hotspot_data)} 个")
        print(f"  - 股票数据: {len(stock_data)} 个")
    
    def _extract_news_data(self) -> List[Dict[str, Any]]:
        """从markdown文件中提取新闻数据"""
        news_data = []
        current_time = datetime.now()
        
        # 获取最近5天的文件
        for day_offset in range(5):
            target_date = current_time - timedelta(days=day_offset)
            date_str = target_date.strftime("%Y-%m-%d")
            file_path = self.output_dir / f"cls_{date_str}.md"
            
            if not file_path.exists():
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8")
                daily_news = self._parse_markdown_content(content, date_str)
                news_data.extend(daily_news)
            except Exception as e:
                print(f"解析文件 {file_path} 失败: {e}")
        
        # 按时间倒序排列
        news_data.sort(key=lambda x: f"{x['date']} {x['time']}", reverse=True)
        return news_data
    
    def _parse_markdown_content(self, content: str, date_str: str) -> List[Dict[str, Any]]:
        """解析markdown内容，提取新闻条目"""
        news_items = []
        lines = content.split('\n')
        current_type = "general"
        
        for line in lines:
            line = line.strip()
            
            # 识别章节类型
            if "🔴 重要电报" in line:
                current_type = "important"
                continue
            elif "📰 一般电报" in line:
                current_type = "general"
                continue
            
            # 解析新闻条目
            if line.startswith("- [") and "]" in line:
                news_item = self._parse_news_line(line, date_str, current_type)
                if news_item:
                    news_items.append(news_item)
        
        return news_items
    
    def _parse_news_line(self, line: str, date_str: str, news_type: str) -> Dict[str, Any]:
        """解析单条新闻行"""
        try:
            # 提取时间
            time_match = re.search(r'\[(\d{2}:\d{2})\]', line)
            time_str = time_match.group(1) if time_match else "00:00"
            
            # 提取内容和链接
            content_match = re.search(r'\] (.+?)(?:\(https://www\.cls\.cn/detail/(\d+)\))?$', line)
            if not content_match:
                return None
            
            content = content_match.group(1)
            # 移除markdown格式
            content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)  # 移除粗体
            content = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', content)  # 移除链接格式，保留文本
            
            # 清理可能导致JSON错误的字符
            content = content.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            content = re.sub(r'\s+', ' ', content)  # 合并多个空格
            content = content.strip()
            
            # 确保内容不为空
            if not content:
                return None
            
            return {
                "date": date_str,
                "time": time_str,
                "type": news_type,
                "content": content
            }
        except Exception as e:
            print(f"解析新闻行失败: {line}, 错误: {e}")
            return None
    
    def _generate_hotspot_data(self, news_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成热点数据"""
        # 按日期和关键词统计
        daily_keyword_stats = defaultdict(lambda: defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0}))
        
        for news in news_data:
            date = news.get("date", "")
            content = news.get("content", "")
            news_type = news.get("type", "general")
            
            # 验证数据有效性
            if not date or not content or not isinstance(content, str):
                continue
                
            for keyword in self.keywords:
                if keyword in content:
                    # 简单的情感分析
                    if news_type == "important":
                        if any(word in content for word in ["利好", "上涨", "突破", "增长", "涨停"]):
                            daily_keyword_stats[date][keyword]["positive"] += 1
                        elif any(word in content for word in ["利空", "下跌", "暴跌", "风险", "警告"]):
                            daily_keyword_stats[date][keyword]["negative"] += 1
                        else:
                            daily_keyword_stats[date][keyword]["neutral"] += 1
                    else:
                        daily_keyword_stats[date][keyword]["neutral"] += 1
        
        # 转换为列表格式，确保数据类型正确
        hotspot_data = []
        for date, keywords in daily_keyword_stats.items():
            if not isinstance(date, str) or not date.strip():
                continue
            for keyword, stats in keywords.items():
                if not isinstance(keyword, str) or not keyword.strip():
                    continue
                hotspot_data.append({
                    "date": date.strip(),
                    "keyword": keyword.strip(),
                    "positive": int(stats["positive"]),
                    "negative": int(stats["negative"]),
                    "neutral": int(stats["neutral"])
                })
        
        return hotspot_data
    
    def _generate_stock_data(self, news_data: List[Dict[str, Any]]) -> List[List]:
        """生成股票提及数据"""
        stock_counts = Counter()
        
        for news in news_data:
            content = news.get("content", "")
            if not content or not isinstance(content, str):
                continue
                
            for stock in self.stock_list:
                if isinstance(stock, str) and stock.strip() and stock in content:
                    stock_counts[stock] += 1
        
        # 转换为列表格式，按提及次数排序，确保数据类型正确
        stock_data = []
        for stock, count in stock_counts.most_common():
            if isinstance(stock, str) and stock.strip() and isinstance(count, int):
                stock_data.append([stock.strip(), count])
        
        return stock_data
    
    def _get_date_range(self) -> Dict[str, str]:
        """获取数据日期范围"""
        current_time = datetime.now()
        start_date = current_time - timedelta(days=4)
        return {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": current_time.strftime("%Y-%m-%d")
        }

if __name__ == "__main__":
    generator = JSONDataGenerator("./output/cls")
    generator.generate_all_json_data()
