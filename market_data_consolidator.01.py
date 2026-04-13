# market_data_consolidator.py
import json
import os
import csv
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict, Counter

class MarketDataConsolidator:
    def __init__(self, base_dir="."):
        self.base_dir = Path(base_dir)
        self.output_base = self.base_dir / "output"
        self.date_dir = self.output_base / "date"
        self.history_dir = self.date_dir / "history"
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
            return datetime.fromtimestamp(int(float(ts))).strftime("%H:%M:%S")
        except:
            return ""

    def _get_market_label(self, item):
        name = item.get("name", "")
        code = str(item.get("code", ""))
        if "ST" in name.upper():
            return "ST"
        if code.startswith('688'):
            return "STAR"
        if code.startswith('30'):
            return "GEM"
        return "HS"

    def _parse_high_days(self, text):
        if not text: return 0
        if isinstance(text, int): return text
        if "首板" in text: return 1
        match = re.search(r'(\d+)', str(text))
        if match:
            return int(match.group(1))
        return 0

    def process(self, business_date=None):
        # 1. 自动从 JSON 中提取日期
        zt_file = self.base_dir / "涨停池.json"
        if not business_date and zt_file.exists():
            try:
                with open(zt_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    business_date = data.get("data", {}).get("business_date")
            except: pass
        
        if not business_date:
            business_date = datetime.now().strftime("%Y-%m-%d")
        else:
            if len(business_date) == 8:
                business_date = f"{business_date[:4]}-{business_date[4:6]}-{business_date[6:]}"

        # 2. 核心数据仓库：以 code 为 key，合并所有信息
        master_data = {}

        # 3. 优先处理三个核心池
        files_config = [
            ("涨停池.json", "涨停池"),
            ("炸板池.json", "炸板池"),
            ("跌停池.json", "跌停池")
        ]

        for filename, pool_type in files_config:
            file_path = self.base_dir / filename
            if not file_path.exists(): continue
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    stocks = content.get("data", {}).get("info", [])
                    for s in stocks:
                        code = str(s.get("code"))
                        if code not in master_data:
                            master_data[code] = s
                            master_data[code]["pool_type"] = pool_type
                        else:
                            # 如果已存在，更新池类型（可能一个股既在风口又在涨停池）
                            master_data[code]["pool_type"] = f"{master_data[code].get('pool_type')}/{pool_type}"
            except Exception as e:
                print(f"解析 {filename} 失败: {e}")

        # 4. 合并最强风口数据（包含不在三池中的领涨股）
        sector_file = self.base_dir / "最强风口.json"
        sector_mapping = {}
        if sector_file.exists():
            try:
                with open(sector_file, 'r', encoding='utf-8') as f:
                    sector_data = json.load(f)
                    for sector in sector_data.get("data", []):
                        sector_name = sector.get("name", "")
                        for s in sector.get("stock_list", []):
                            code = str(s.get("code"))
                            sector_mapping[code] = sector_name
                            if code not in master_data:
                                # 这是仅在风口中出现的强势股
                                master_data[code] = s
                                master_data[code]["pool_type"] = "风口领涨"
            except: pass

        # 5. 生成最终行数据
        final_rows = []
        for code, s in master_data.items():
            row = {
                "交易日期": business_date,
                "股票代码": self._get_market_suffix(code),
                "股票名称": s.get("name", ""),
                "池类型": s.get("pool_type", ""),
                "市场类型": self._get_market_label(s),
                "当前价": s.get("latest"),
                "涨跌幅%": s.get("change_rate"),
                "连板天数": self._parse_high_days(s.get("high_days") or s.get("continue_num")),
                "涨停标签": s.get("high_days") or s.get("high") or "",
                "涨停状态": s.get("limit_up_type", ""),
                "首次涨停时间": self._format_timestamp(s.get("first_limit_up_time")),
                "最后涨停时间": self._format_timestamp(s.get("last_limit_up_time")),
                "炸板时间": self._format_timestamp(s.get("last_limit_up_time")) if "炸板" in s.get("pool_type", "") else "",
                "炸板次数": s.get("open_num", 0) if s.get("open_num") is not None else 0,
                "封单金额": s.get("order_amount", 0),
                "封单量": s.get("order_volume", 0),
                "换手率%": s.get("turnover_rate"),
                "成交额": s.get("turnover", 0),
                "流通市值": s.get("currency_value", 0),
                "涨停原因": s.get("reason_type", ""),
                "所属行业": sector_mapping.get(code, "")
            }
            final_rows.append(row)

        if final_rows:
            output_file = self.date_dir / f"{business_date}_market_pool.csv"
            keys = final_rows[0].keys()
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(final_rows)
            print(f"成功生成增强型表格: {output_file} (总计 {len(final_rows)} 条数据)")
        else:
            print("未能整合出数据。")

        # 6. 生成“大局观”市场概览 (Markdown 格式)
        self._generate_market_summary(business_date, sector_mapping, final_rows)

        # 7. 归档旧数据，保持目录整洁
        self._archive_old_files()

        # 8. 聚合最近5日数据到 5day 文件夹
        self._generate_5day_consolidated_csv()

    def _archive_old_files(self, keep_days=5):
        """归档超过指定天数的文件到 history 文件夹"""
        try:
            # 1. 获取所有以日期开头的文件 (YYYY-MM-DD_...)
            all_files = list(self.date_dir.glob("????-??-??_*"))
            
            # 2. 提取并去重所有日期后缀
            dates = sorted(list(set([f.name[:10] for f in all_files])), reverse=True)
            
            if len(dates) <= keep_days:
                return
            
            # 3. 确定哪些日期属于“历史”
            history_dates = dates[keep_days:]
            
            count = 0
            for d in history_dates:
                # 找出该日期的所有相关文件
                for f in self.date_dir.glob(f"{d}_*"):
                    if f.is_file():
                        target_path = self.history_dir / f.name
                        # 如果目标文件已存在（比如之前移过又重新生成了），先删除
                        if target_path.exists(): target_path.unlink()
                        f.rename(target_path)
                        count += 1
            
            if count > 0:
                print(f"成功归档 {len(history_dates)} 个交易日的数据（共 {count} 个文件）至 history 目录。")
        except Exception as e:
            print(f"归档过程出错: {e}")

    def _generate_market_summary(self, business_date, sector_mapping, final_rows):
        overview_file = self.base_dir / "市场大局观.json"
        if not overview_file.exists(): return
        
        try:
            with open(overview_file, 'r', encoding='utf-8') as f:
                ov_data = json.load(f).get("data", {})
            
            turnover = ov_data.get("turnover", {})
            rf = ov_data.get("rise_fall", {})
            dt_count = rf.get('limit_down', 0)
            
            # --- 深度量化计算 ---
            zt_rows = [r for r in final_rows if "涨停池" in r.get("池类型", "")]
            # 💡 核心优化：只筛选非 ST 个股用于题材和连板梯队分析
            non_st_zt_rows = [r for r in zt_rows if "ST" not in r.get("股票名称", "") and "*" not in r.get("股票名称", "")]
            
            zt_count = rf.get('limit_up', 0)
            zb_count = len([r for r in final_rows if "炸板" in r.get("池类型", "")])
            breaking_rate = (zb_count / (zt_count + zb_count) * 100) if (zt_count + zb_count) > 0 else 0
            
            # 提取今日核心题材基因 (剔除 ST)
            def extract_concepts(rows):
                concepts = []
                for r in rows:
                    res = str(r.get("涨停原因", ""))
                    concepts.extend([c.strip() for c in res.split('+') if c.strip()])
                return concepts

            today_concepts = extract_concepts(non_st_zt_rows)
            concept_counts = Counter(today_concepts)
            top_mainlines = concept_counts.most_common(5)

            # --- 跨时空因果分析 (Yesterday Feedback) ---
            prev_date, prev_df = self._load_previous_data(business_date)
            yesterday_feedback = ""
            sector_persistence = "未知"
            
            if prev_df is not None:
                # 1. 昨日非 ST 涨停表现
                yest_zt = prev_df[(prev_df['池类型'].str.contains('涨停池', na=False)) & (~prev_df['股票名称'].str.contains('ST', na=False))]
                if len(yest_zt) > 0:
                    yest_codes = set(yest_zt['股票代码'].apply(lambda x: str(x).split('.')[0]))
                    today_zt_codes = set([r['股票代码'].split('.')[0] for r in non_st_zt_rows if "涨停池" in r['池类型']])
                    
                    promotion = len(yest_codes & today_zt_codes)
                    promotion_rate = (promotion / len(yest_codes)) * 100
                    status = "🔥 极佳" if promotion_rate > 50 else "良好" if promotion_rate > 30 else "谨慎" if promotion_rate > 15 else "恶劣"
                    yesterday_feedback = f"昨日涨停今日晋级: `{promotion}/{len(yest_codes)}` ({promotion_rate:.1f}%) | 赚钱效应: `{status}`"
                
                # 2. 题材持续性分析 (基于非 ST 基因)
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

            # 3. 基础情绪计算
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
                f"- **亏钱效应监控**: 🟢 跌停 {dt_count} 家 ({'风险可控' if dt_count < 5 else '风险扩散' if dt_count < 15 else '大面横行'})",
                f"",
                f"### 🌡️ 市场温度计 (量能维度)",
                f"- **成交额**: 💰 {turnover.get('now')} (前值 {turnover.get('pre')})",
                f"- **涨跌分布**: ⬆️ {rf.get('rise')} : ⬇️ {rf.get('fall')} (胜率: {(rf.get('rise',0)/total_stocks*100 if total_stocks>0 else 0):.1f}%)",
                f"",
                f"### 🎯 实战核心主线 (题材共振 · 已剔除ST)",
            ]
            
            for concept, count in top_mainlines:
                avg_t = 0; s_c = 0
                for r in non_st_zt_rows:
                    if concept in str(r.get("涨停原因", "")):
                        avg_t += float(r.get("换手率%") or 0); s_c += 1
                avg_t = avg_t / s_c if s_c > 0 else 0
                summary_content.append(f"- **{concept}** ({count} 股涨停) | 平均换手 `{avg_t:.1f}%`")

            summary_content.append(f"")
            summary_content.append(f"### 🪜 连板梯队 (身位逻辑 · 已剔除ST)")
            heights = defaultdict(list)
            for r in non_st_zt_rows:
                h = r.get("连板天数", 0)
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
            
        except Exception as e:
            print(f"生成简报失败: {e}")


    def _load_previous_data(self, current_date):
        """寻找并加载上一个交易日的 CSV 数据"""
        import pandas as pd
        # 1. 获取所有可用的 CSV
        csv_files = list(self.date_dir.glob("????-??-??_market_pool.csv")) + \
                    list(self.history_dir.glob("????-??-??_market_pool.csv"))
        
        # 2. 提取并排序日期
        date_map = {f.name[:10]: f for f in csv_files}
        sorted_dates = sorted(date_map.keys())
        
        # 3. 找到 current_date 的前一个索引
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
        """将 date 文件夹下最近保留的5日CSV合并输出到 5day 文件夹中"""
        try:
            fiveday_dir = self.date_dir / "5day"
            fiveday_dir.mkdir(parents=True, exist_ok=True)
            
            # 由于 _archive_old_files 已将老数据移走，此处只需取 date_dir 下所有的当日起止 CSV 即可
            csv_files = list(self.date_dir.glob("????-??-??_market_pool.csv"))
            csv_files.sort(key=lambda x: x.name)  # 按日期升序，旧的在前，新的在后
            
            if not csv_files:
                return
            
            all_rows = []
            headers = None
            
            for file_path in csv_files:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    if headers is None:
                        headers = reader.fieldnames
                    for row in reader:
                        all_rows.append(row)
            
            if all_rows and headers:
                out_file = fiveday_dir / "recent_5days_market_pool.csv"
                with open(out_file, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(all_rows)
                print(f"成功合并最近 {len(csv_files)} 日数据至 5day 文件夹 (共 {len(all_rows)} 条)")
        except Exception as e:
            print(f"合并5日数据出错: {e}")

if __name__ == "__main__":
    consolidator = MarketDataConsolidator()
    consolidator.process()
