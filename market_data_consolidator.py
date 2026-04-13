# market_data_consolidator.py
import json
import os
import csv
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict, Counter

class MarketDataConsolidator:
    def __init__(self, base_dir="."):
        root_path = Path(base_dir)
        # 💡 数据源指向缓存目录，产出指向 date 目录
        self.base_dir = root_path / "output" / "json_cache"
        self.output_base = root_path / "output"
        self.date_dir = self.output_base / "date"
        self.history_dir = self.date_dir / "history"
        
        root_path.mkdir(parents=True, exist_ok=True) 
        self.base_dir.mkdir(parents=True, exist_ok=True) 
        self.date_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_market_suffix(self, code):
        if not code: return ""
        code = str(code)
        if code.startswith('6'):
            return f"{code}.SH"
        elif code.startswith('0') or code.startswith('3'):
            return f"{code}.SZ"
        elif code.startswith('8') or code.startswith('4'):
            return f"{code}.BJ"
        return code

    def _format_timestamp(self, ts):
        if not ts or str(ts) in ["-60", "0", "None", "null"]:
            return ""
        try:
            # 💡 强行锁定北京时间
            tz_beijing = timezone(timedelta(hours=8))
            dt = datetime.fromtimestamp(int(float(ts)), tz=tz_beijing)
            return dt.strftime("%H:%M:%S")
        except:
            return ""

    def process(self, business_date=None):
        """核心处理逻辑：读取JSON -> 整理表格 -> 生成研报"""
        try:
            # 1. 确定业务日期
            if not business_date:
                tz_beijing = timezone(timedelta(hours=8))
                business_date = datetime.now(tz=tz_beijing).strftime("%Y-%m-%d")
            else:
                if len(business_date) == 8:
                    business_date = f"{business_date[:4]}-{business_date[4:6]}-{business_date[6:]}"
            
            # 💡 核心变动：根据日期定位 JSON 缓存目录
            root_path = self.output_base.parent # 假设 output_base 是 root/output
            self.base_dir = root_path / "output" / "json_cache" / business_date
            
            print(f"正在从 {self.base_dir} 读取原始数据...")
            
            # 归档老旧文件
            self._archive_old_files(business_date)
            
            print(f"正在整合业务日期: {business_date} 的量化数据...")
            
            # 文件池定义
            files = {
                "涨停池": "涨停池.json",
                "炸板池": "炸板池.json",
                "跌停池": "跌停池.json"
            }
            
            final_rows = []
            sector_mapping = defaultdict(list)
            
            for pool_name, filename in files.items():
                file_path = self.base_dir / filename
                if not file_path.exists():
                    continue
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    info = data.get("data", {}).get("info", [])
                    for item in info:
                        # 核心清洗字段
                        row = {
                            "日期": business_date,
                            "池类型": pool_name,
                            "股票代码": self._get_market_suffix(item.get("code")),
                            "股票名称": item.get("name"),
                            "现价": item.get("latest"),
                            "涨跌幅%": item.get("range"),
                            "换手率%": item.get("turnover_rate"),
                            "连板天数": item.get("limit_up_days", 1),
                            "最后封板时间": self._format_timestamp(item.get("last_limit_up_time")),
                            "首次封板时间": self._format_timestamp(item.get("first_limit_up_time")),
                            "首次开板时间": self._format_timestamp(item.get("first_open_limit_time")),
                            "最后开板时间": self._format_timestamp(item.get("last_open_limit_time")),
                            "开板次数": item.get("open_limit_num", 0),
                            "封单额": item.get("order_amount", 0),
                            "流通市值": item.get("currency_value", 0),
                            "涨停原因": item.get("reason_type", "未知"),
                            "所属行业": item.get("order_field", "未知")
                        }
                        final_rows.append(row)
                        # 记录题材
                        if pool_name == "涨停池":
                            concepts = str(row["涨停原因"]).split('+')
                            for c in concepts:
                                if c.strip(): sector_mapping[c.strip()].append(row["股票名称"])

            if not final_rows:
                print("⚠️ 未发现可处理的数据行，请检查 JSON 数据源。")
                return

            # 保存为 CSV (UTF-8-SIG 兼容 Excel)
            output_file = self.date_dir / f"{business_date}_market_pool.csv"
            keys = final_rows[0].keys()
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(final_rows)
            print(f"成功生成增强型表格: {output_file} (总计 {len(final_rows)} 条数据)")
            
            # 生成深度研报
            self._generate_market_summary(business_date, sector_mapping, final_rows)
            
            # 合并5日数据
            self._generate_5day_consolidated_csv()
            
        except Exception as e:
            print(f"处理进程出错: {e}")
            import traceback
            traceback.print_exc()

    def _archive_old_files(self, current_date, keep_days=7):
        """将非本日且超过保留期限的文件移入 history，保持主目录清空"""
        try:
            # 1. 获取所有类似 YYYY-MM-DD 的日期前缀文件
            files = list(self.date_dir.glob("????-??-??_*"))
            if not files: return
            
            # 2. 提取并排序日期
            dates = sorted(list(set([f.name[:10] for f in files])), reverse=True)
            if len(dates) <= keep_days: return
            
            # 3. 确定哪些日期属于“历史”
            history_dates = dates[keep_days:]
            
            count = 0
            for d in history_dates:
                for f in self.date_dir.glob(f"{d}_*"):
                    if f.is_file():
                        target_path = self.history_dir / f.name
                        if target_path.exists(): target_path.unlink()
                        f.rename(target_path)
                        count += 1
            if count > 0:
                print(f"成功归档 {len(history_dates)} 个交易日的数据（共 {count} 个文件）至 history 目录。")
        except Exception as e:
            print(f"归档过程出错: {e}")

    def _generate_market_summary(self, business_date, sector_mapping, final_rows):
        overview_file = self.base_dir / "市场大局观.json"
        
        # 💡 容错处理：即使没有大局观数据，也生成部分报告
        ov_data = {}
        if overview_file.exists():
            try:
                with open(overview_file, 'r', encoding='utf-8') as f:
                    ov_data = json.load(f).get("data", {})
            except: pass
        
        turnover = ov_data.get("turnover", {"now": "未知", "pre": "未知"})
        rf = ov_data.get("rise_fall", {})
        dt_count = rf.get('limit_down', 0)
        
        # --- 深度量化计算 ---
        zt_rows = [r for r in final_rows if "涨停池" in r.get("池类型", "")]
        non_st_zt_rows = [r for r in zt_rows if "ST" not in str(r.get("股票名称", "")) and "*" not in str(r.get("股票名称", ""))]
        
        zt_count = rf.get('limit_up', 0) or len(zt_rows)
        zb_count = len([r for r in final_rows if "炸板" in r.get("池类型", "")])
        zb_rate_str = f"{(zb_count / (zt_count + zb_count) * 100):.1f}%" if (zt_count + zb_count) > 0 else "0%"
        
        # 题材统计
        def extract_concepts(rows):
            concepts = []
            for r in rows:
                res = str(r.get("涨停原因", ""))
                concepts.extend([c.strip() for c in res.split('+') if c.strip()])
            return concepts

        today_concepts = extract_concepts(non_st_zt_rows)
        concept_counts = Counter(today_concepts)
        top_mainlines = concept_counts.most_common(5)

        # 昨日比对
        prev_date, prev_df = self._load_previous_data(business_date)
        yesterday_feedback = ""
        sector_persistence = "未知"
        
        if prev_df is not None:
            yest_zt = prev_df[(prev_df['池类型'].str.contains('涨停池', na=False)) & (~prev_df['股票名称'].str.contains('ST', na=False))]
            if len(yest_zt) > 0:
                yest_codes = set(yest_zt['股票代码'].apply(lambda x: str(x).split('.')[0]))
                today_zt_codes = set([r['股票代码'].split('.')[0] for r in non_st_zt_rows])
                promotion = len(yest_codes & today_zt_codes)
                promotion_rate = (promotion / len(yest_codes)) * 100
                status = "🔥 极佳" if promotion_rate > 50 else "良好" if promotion_rate > 30 else "谨慎" if promotion_rate > 15 else "恶劣"
                yesterday_feedback = f"昨日涨停今日晋级: `{promotion}/{len(yest_codes)}` ({promotion_rate:.1f}%) | 赚钱效应: `{status}`"
            
            # 持续性
            def get_df_concepts(df):
                zt = df[(df['池类型'].str.contains('涨停池', na=False)) & (~df['股票名称'].str.contains('ST', na=False))]
                concepts = []
                for res in zt['涨停原因'].fillna(""):
                    concepts.extend([c.strip() for c in str(res).split('+') if c.strip()])
                return Counter(concepts)

            yest_concept_counts = get_df_concepts(prev_df)
            top_yest_concepts = [item[0] for item in yest_concept_counts.most_common(5)]
            persistent = [c for c, _ in top_mainlines if c in top_yest_concepts]
            sector_persistence = f"持续题材: `{', '.join(persistent) if persistent else '无 (主流换血)'}`"

        # 情绪 Bar
        total_stocks = (rf.get('rise') or 0) + (rf.get('fall') or 0) + (rf.get('deuce') or 0)
        rise_ratio = int((rf.get('rise') or 0) / total_stocks * 10) if total_stocks > 0 else 0
        bar = "🔴" * rise_ratio + "🟢" * (10 - rise_ratio)
        sentiment = "极好" if rise_ratio >= 8 else "良好" if rise_ratio >= 6 else "平淡" if rise_ratio >= 4 else "低迷"
        
        summary_content = [
            f"# 📅 {business_date} | 深度量化·主流复盘报告",
            f"",
            f"**核心情绪定性：{sentiment} {bar}**",
            f"",
            f"---",
            f"### 🕰️ 因果反馈 (主流博弈)",
            f"- **昨日(非ST)表现**: {yesterday_feedback or '缺少比对数据'}",
            f"- **题材持续性**: {sector_persistence}",
            f"- **炸板率监控**: `{zb_rate_str}`",
            f"- **亏钱效应监控**: 🟢 跌停 {dt_count} 家 ({'风险可控' if dt_count < 5 else '风险扩散' if dt_count < 15 else '大面横行'})",
            f"",
            f"### 🌡️ 市场温度计 (量能维度)",
            f"- **成交额**: 💰 {turnover.get('now')} (前值 {turnover.get('pre')})",
            f"- **涨跌分布**: ⬆️ {rf.get('rise', '未知')} : ⬇️ {rf.get('fall', '未知')} (胜率: {(rf.get('rise',0)/total_stocks*100 if total_stocks>0 else 0):.1f}%)",
            f"",
            f"### 🎯 实战核心主线 (题材共振 · 已剔除ST)",
        ]
        
        for concept, count in top_mainlines:
            avg_t = 0; s_c = 0
            for r in non_st_zt_rows:
                if concept in str(r.get("涨停原因", "")):
                    try:
                        avg_t += float(r.get("换手率%") or 0); s_c += 1
                    except: pass
            avg_t = avg_t / s_c if s_c > 0 else 0
            summary_content.append(f"- **{concept}** ({count} 股涨停) | 平均换手 `{avg_t:.1f}%`")

        summary_content.append(f"")
        summary_content.append(f"### 🪜 连板梯队 (身位逻辑 · 已剔除ST)")
        heights = defaultdict(list)
        for r in non_st_zt_rows:
            h = int(r.get("连板天数", 1))
            if h > 1:
                reason = str(r.get("涨停原因", "")).split('+')[0]
                heights[h].append(f"{r['股票名称']}({reason})")
        
        for h in sorted(heights.keys(), reverse=True):
            summary_content.append(f"- **{h}板** : {'、'.join(heights[h])}")
        
        summary_content.append(f"")
        summary_content.append(f"---")
        summary_content.append(f"**禅师研报总结**：")
        summary_content.append(f"> “{self._get_zen_quote(rise_ratio)}”")
        
        summary_md = self.date_dir / f"{business_date}_market_summary.md"
        with open(summary_md, 'w', encoding='utf-8') as f:
            f.write("\n".join(summary_content))
        print(f"成功生成去噪版深度报告: {summary_md}")

    def _load_previous_data(self, current_date):
        import pandas as pd
        csv_files = list(self.date_dir.glob("????-??-??_market_pool.csv")) + \
                    list(self.history_dir.glob("????-??-??_market_pool.csv"))
        date_map = {f.name[:10]: f for f in csv_files}
        sorted_dates = sorted(date_map.keys())
        cur_iso = current_date if '-' in current_date else f"{current_date[:4]}-{current_date[4:6]}-{current_date[6:]}"
        if cur_iso in sorted_dates:
            idx = sorted_dates.index(cur_iso)
            if idx > 0:
                prev_date = sorted_dates[idx-1]
                try:
                    return prev_date, pd.read_csv(date_map[prev_date], encoding='utf-8-sig')
                except: pass
        return None, None

    def _get_zen_quote(self, ratio):
        if ratio >= 8: return "大音希声，由于亢龙有悔，切莫盲目追高。"
        if ratio >= 6: return "上善若水，顺势而为，关注主线轮动。"
        if ratio >= 4: return "持而盈之，不如其已。震荡市宜减冗余，守本心。"
        return "否极泰来。处于众之所恶，故几于道，静待修复。"

    def _generate_5day_consolidated_csv(self):
        try:
            fiveday_dir = self.date_dir / "5day"
            fiveday_dir.mkdir(parents=True, exist_ok=True)
            csv_files = sorted(list(self.date_dir.glob("????-??-??_market_pool.csv")), key=lambda x: x.name)
            if not csv_files: return
            all_rows = []
            headers = None
            for file_path in csv_files:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    if headers is None: headers = reader.fieldnames
                    for row in reader: all_rows.append(row)
            if all_rows and headers:
                out_file = fiveday_dir / "recent_5days_market_pool.csv"
                with open(out_file, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(all_rows)
                print(f"成功合并最近 {len(csv_files)} 日数据至 5day 文件夹.")
        except: pass

if __name__ == "__main__":
    consolidator = MarketDataConsolidator()
    consolidator.process()
