# market_data_fetcher.py
import requests
import json
import time
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

class MarketDataFetcher:
    def __init__(self, base_dir="."):
        self.base_dir = Path(base_dir)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://data.10jqka.com.cn/datacenter/limitup/",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest"
        }
        
    def _get_business_date(self):
        # 💡 强制使用北京时间
        tz_beijing = timezone(timedelta(hours=8))
        return datetime.now(tz=tz_beijing).strftime("%Y%m%d")

    def fetch_pool_all_pages(self, base_url_pattern, filename, date_str):
        """循环抓取所有页面，确保数据完整"""
        all_info = []
        page = 1
        limit = 50 # 尝试增大 limit，若服务器不支持则依赖多页循环
        
        while True:
            # 替换 url 中的 page 和 limit，并保持其它参数
            url = base_url_pattern.replace("page=1", f"page={page}").replace("limit=15", f"limit={limit}")
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在请求 {filename} 第 {page} 页...")
            
            # 禅定延迟
            time.sleep(random.uniform(2.5, 4.5))
            
            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status_code") == 0:
                    info_list = data.get("data", {}).get("info", [])
                    if not info_list:
                        break
                        
                    all_info.extend(info_list)
                    
                    page_info = data.get("data", {}).get("page", {})
                    total = page_info.get("total", 0)
                    
                    print(f"  - 已获取 {len(all_info)} / 总计 {total} 条数据")
                    
                    # 如果已经抓完所有数据，或者已抓取条数大于等于总数，停止
                    if len(all_info) >= total or not info_list:
                        break
                    
                    page += 1
                else:
                    print(f"接口报错: {data.get('status_msg')}")
                    break
            except Exception as e:
                print(f"抓取失败: {e}")
                break
        
        # 保存完整数据
        if all_info:
            output_data = {
                "status_code": 0,
                "data": {
                    "info": all_info,
                    "business_date": date_str
                }
            }
            with open(self.output_dir / filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            print(f"成功保存 {len(all_info)} 条数据到 {filename}")
            return True
        return False

    def fetch_block_top(self, url, filename):
        """风口数据通常一页返回，带有重试机制"""
        for attempt in range(3):
            try:
                time.sleep(random.uniform(1, 2))
                res = requests.get(url, headers=self.headers, timeout=20)
                res.raise_for_status()
                data = res.json()
                if data.get("status_code") == 0:
                    with open(self.output_dir / filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    print(f"成功同步最强风口数据")
                    return True
            except Exception as e:
                print(f"抓取风口失败 (尝试 {attempt+1}): {e}")
        return False

    def fetch_market_overview(self, url, filename):
        """抓取市场大局观数据，带有更强的重试机制"""
        for attempt in range(3):
            try:
                time.sleep(random.uniform(1, 2))
                # 💡 增加超时时间到 25 秒
                res = requests.get(url, headers=self.headers, timeout=25)
                res.raise_for_status()
                data = res.json()
                if data.get("status_code") == 0:
                    with open(self.output_dir / filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    print(f"成功同步市场大局观数据")
                    return True
            except Exception as e:
                print(f"抓取大盘数据失败 (尝试 {attempt+1}): {e}")
        return False

    def run(self, date_target=None):
        if not date_target:
            date_target = self._get_business_date()
            
        # 💡 创建日期子目录，如 output/json_cache/2026-04-13
        # 统一格式为 YYYY-MM-DD
        dir_name = date_target if '-' in date_target else f"{date_target[:4]}-{date_target[4:6]}-{date_target[6:]}"
        self.output_dir = self.base_dir / "output" / "json_cache" / dir_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
            
        print(f"--- 开启同花顺数据同步法阵 [日期: {date_target}] ---")
        
        # 涨停池 (增加 461252 行业字段)
        url_zt = f"https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool?page=1&limit=15&field=10,19,48,9001,9002,9003,9004,133970,133971,199112,330323,330324,330325,330329,330333,330334,1968584,3475914,3541450,461252&filter=HS,GEM2STAR,ST,NEW&order_field=330324&order_type=0&date={date_target}"
        self.fetch_pool_all_pages(url_zt, f"{dir_name}_涨停池.json", date_target)
        
        # 炸板池 (增加 461252 行业字段)
        url_zb = f"https://data.10jqka.com.cn/dataapi/limit_up/open_limit_pool?page=1&limit=15&field=10,19,48,9001,9002,9003,9004,133970,133971,199112,330323,330324,330325,330329,330333,330334,1968584,3475914,3541450,461252&filter=HS,GEM2STAR,ST,NEW&order_field=199112&order_type=0&date={date_target}"
        self.fetch_pool_all_pages(url_zb, f"{dir_name}_炸板池.json", date_target)
        
        # 跌停池 (增加 461252 行业字段)
        url_dt = f"https://data.10jqka.com.cn/dataapi/limit_up/lower_limit_pool?page=1&limit=15&field=10,19,48,9001,9002,9003,9004,133970,133971,199112,330323,330324,330325,330329,330333,330334,1968584,3475914,3541450,461252&filter=HS,GEM2STAR,ST,NEW&date={date_target}&order_field=330334&order_type=0"
        self.fetch_pool_all_pages(url_dt, f"{dir_name}_跌停池.json", date_target)
        
        # 最强风口
        url_fk = f"https://data.10jqka.com.cn/dataapi/limit_up/block_top?filter=HS,GEM2STAR,ST,NEW&date={date_target}"
        self.fetch_block_top(url_fk, f"{dir_name}_最强风口.json")
        
        # 市场大局观
        url_ov = f"https://data.10jqka.com.cn/mobileapi/hotspot_focus/market_state/v1/overview?date={date_target}"
        self.fetch_market_overview(url_ov, f"{dir_name}_市场大局观.json")
        
        print(f"--- 同步完成 ---")

if __name__ == "__main__":
    fetcher = MarketDataFetcher()
    # 💡 移除硬编码，默认同步当天数据
    fetcher.run()
