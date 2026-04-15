#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日A股量化分析 - 图表生成脚本
生成8张图表
"""
import pandas as pd
import matplotlib
matplotlib.use('Agg') # 设置为非交互式后端，适用于服务器/GitHub Actions
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import re
import os
from pathlib import Path

# ========== 路径配置 ==========
BASE_DIR = Path(__file__).parent
out_dir = BASE_DIR / "output" / "date" / "5day" / "trend_charts"
out_dir.mkdir(parents=True, exist_ok=True)
csv_path = BASE_DIR / "output" / "date" / "5day" / "recent_5days_market_pool.csv"

# ========== 加载中文字体 ==========
# 尝试多个常见中文字体路径
FONT_PATHS = [
    Path("C:/Windows/Fonts/msyh.ttc"),    # Windows: 微软雅黑
    Path("C:/Windows/Fonts/simhei.ttf"),  # Windows: 黑体
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"), # Linux: 文泉驿微米黑
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), # Linux: Noto Sans
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"), # Linux: Noto Sans
]
FONT_PATH = None
for fp in FONT_PATHS:
    if fp.exists():
        FONT_PATH = fp
        break

if FONT_PATH:
    fm.fontManager.addfont(str(FONT_PATH))
    font_name = fm.FontProperties(fname=FONT_PATH).get_name()
    matplotlib.rcParams['font.family'] = font_name
    print(f"Using font: {font_name}")
else:
    print("Warning: Chinese font not found, Chinese may display incorrectly")
    matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['axes.unicode_minus'] = False

# 统一配色方案
COLOR_PEAK = '#E63946'   # 峰值红色（涨停池）
COLOR_OTHER = '#4A90D9'  # 其他蓝色
COLOR_ZHABAN = '#FF8C42'  # 炸板池橙色
COLOR_DIE_TING = '#9B59B6'  # 跌停池紫色

# ========== 获取数据 ==========
df = pd.read_csv(csv_path)

# ========== 图1: 每日涨停家数统计 ==========
fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

daily_zt = df[df['池类型'] == '涨停池'].groupby('日期').size().reset_index(name='涨停家数')
daily_zt['日期'] = pd.to_datetime(daily_zt['日期']).dt.strftime('%m-%d')

dates = daily_zt['日期'].tolist()
counts = daily_zt['涨停家数'].tolist()
colors = [COLOR_PEAK if c == max(counts) else COLOR_OTHER for c in counts]

bars = ax.bar(dates, counts, color=colors, width=0.5, edgecolor='white', linewidth=0.8)
for bar, val in zip(bars, counts):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5, str(val),
            ha='center', va='bottom', fontsize=13, fontweight='bold')

ax.set_xlabel('日期', fontsize=12)
ax.set_ylabel('涨停家数', fontsize=12)
ax.set_title('每日涨停家数统计（近5日）', fontsize=15, fontweight='bold', pad=15)
ax.set_ylim(0, max(counts) * 1.15)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='y', alpha=0.3, linestyle='--')
ax.tick_params(axis='both', labelsize=11)

avg = np.mean(counts)
ax.axhline(y=avg, color='red', linestyle='--', linewidth=1.2, alpha=0.7, label=f'均值: {avg:.0f}')
ax.legend(fontsize=10)

plt.tight_layout()
plt.savefig(f'{out_dir}/chart_01_daily_count.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("[OK] chart_01_daily_count.png 已保存")

# ========== 图2: 行业板块分布 (基于涨停原因) ==========
fig, ax = plt.subplots(figsize=(11, 7), dpi=150)

def extract_primary_tag(reason):
    if pd.isna(reason):
        return '其他'
    reason = str(reason)
    tags = re.split(r'[,+，+]', reason)
    tags = [t.strip() for t in tags if t.strip()]
    return tags[0] if tags else '其他'

# 只统计涨停池，排除ST和未知原因
df_zt = df[df['池类型'] == '涨停池'].copy()
# 排除ST股票
df_zt = df_zt[~(df_zt['股票名称'].str.contains('ST', na=False) | df_zt['股票名称'].str.contains(r'\*', na=False, regex=True))]
df_zt['主要概念'] = df_zt['涨停原因'].apply(extract_primary_tag)
# 过滤掉"其他"和"未知"
df_zt = df_zt[~df_zt['主要概念'].isin(['其他', '未知'])]
sector_counts = df_zt['主要概念'].value_counts()
top_sectors = sector_counts.head(12)

palette = plt.cm.Blues(np.linspace(0.3, 0.9, len(top_sectors)))[::-1]
bars2 = ax.barh(list(top_sectors.index)[::-1], list(top_sectors.values)[::-1],
                color=palette[::-1], height=0.6, edgecolor='white')
for bar, val in zip(bars2, list(top_sectors.values)[::-1]):
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
            str(val), va='center', fontsize=10, fontweight='bold')

ax.set_xlabel('股票数量', fontsize=12)
ax.set_title('涨停概念板块分布（Top12）', fontsize=15, fontweight='bold', pad=15)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='x', alpha=0.3, linestyle='--')
ax.tick_params(axis='both', labelsize=10)
ax.set_xlim(0, top_sectors.max() * 1.2)

plt.tight_layout()
plt.savefig(f'{out_dir}/chart_02_sector_dist.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("[OK] chart_02_sector_dist.png 已保存")

# ========== 图3: 封板时间分布 ==========
fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

df_seal = df[df['池类型'] == '涨停池'].copy()
df_seal = df_seal[df_seal['首次封板时间'].notna()].copy()

def parse_hour(t):
    try:
        h = int(str(t).split(':')[0])
        return h
    except:
        return None

df_seal['小时'] = df_seal['首次封板时间'].apply(parse_hour)
df_seal = df_seal[df_seal['小时'].notna()]

labels = ['9:00-10:00', '10:00-11:00', '11:00-13:00', '13:00-14:00', '14:00-15:00']

time_bins = {
    (9, 10): '9:00-10:00',
    (10, 11): '10:00-11:00',
    (11, 13): '11:00-13:00',
    (13, 14): '13:00-14:00',
    (14, 16): '14:00-15:00'
}

def assign_bin(h):
    for (low, high), label in time_bins.items():
        if low <= h < high:
            return label
    return None

df_seal['时段'] = df_seal['小时'].apply(assign_bin)
df_seal = df_seal[df_seal['时段'].notna()]

time_counts = df_seal['时段'].value_counts().reindex(labels, fill_value=0)

bar_colors = [COLOR_PEAK if v == time_counts.max() else COLOR_OTHER for v in time_counts.values]
bars3 = ax.bar(labels, time_counts.values, color=bar_colors, width=0.5, edgecolor='white')

for bar, val in zip(bars3, time_counts.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, str(val),
            ha='center', va='bottom', fontsize=12, fontweight='bold')

ax.set_xlabel('封板时间', fontsize=12)
ax.set_ylabel('涨停家数', fontsize=12)
ax.set_title('首次封板时间分布（近5日）', fontsize=15, fontweight='bold', pad=15)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='y', alpha=0.3, linestyle='--')
ax.tick_params(axis='both', labelsize=10)
ax.set_ylim(0, time_counts.max() * 1.15)

plt.tight_layout()
plt.savefig(f'{out_dir}/chart_03_seal_time.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("[OK] chart_03_seal_time.png 已保存")

# ========== 图4: 每日池类型结构堆叠柱状图 ==========
fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

daily_total = df.groupby('日期').size()
daily_zt = df[df['池类型'] == '涨停池'].groupby('日期').size()
daily_zq = df[df['池类型'] == '炸板池'].groupby('日期').size()
daily_dt = df[df['池类型'] == '跌停池'].groupby('日期').size()

all_dates = sorted(set(daily_total.index))
bar_width = 0.5
x = np.arange(len(all_dates))

zt_vals = [daily_zt.get(d, 0) for d in all_dates]
zq_vals = [daily_zq.get(d, 0) for d in all_dates]
dt_vals = [daily_dt.get(d, 0) for d in all_dates]

p1 = ax.bar(x, zt_vals, bar_width, label='涨停池', color=COLOR_OTHER, edgecolor='white')
p2 = ax.bar(x, zq_vals, bar_width, bottom=zt_vals, label='炸板池', color=COLOR_ZHABAN, edgecolor='white')
p3 = ax.bar(x, dt_vals, bar_width, bottom=[z+q for z,q in zip(zt_vals, zq_vals)], label='跌停池', color=COLOR_DIE_TING, edgecolor='white')

ax.set_xticks(x)
ax.set_xticklabels([pd.to_datetime(d).strftime('%m-%d') for d in all_dates])
ax.set_xlabel('日期', fontsize=12)
ax.set_ylabel('股票数量', fontsize=12)
ax.set_title('每日市场情绪结构（近5日）', fontsize=15, fontweight='bold', pad=15)
ax.legend(fontsize=11)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='y', alpha=0.3, linestyle='--')
ax.tick_params(axis='both', labelsize=11)

for i, (zt, zq, dt) in enumerate(zip(zt_vals, zq_vals, dt_vals)):
    ax.annotate(str(zt), xy=(i, zt/2), ha='center', va='center', fontsize=9, fontweight='bold', color='white')

plt.tight_layout()
plt.savefig(f'{out_dir}/chart_04_pool_daily.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("[OK] chart_04_pool_daily.png 已保存")

# ========== 图5: 涨停概念板块5日热力图 ==========
import seaborn as sns

top_concepts = df_zt['主要概念'].value_counts().head(15).index.tolist()
dates_wp = sorted(df_zt['日期'].unique())

heatmap_data = []
for concept in top_concepts:
    row = []
    for d in dates_wp:
        count = len(df_zt[(df_zt['日期'] == d) & (df_zt['主要概念'] == concept)])
        row.append(count)
    heatmap_data.append(row)

heatmap_df = pd.DataFrame(heatmap_data, index=top_concepts, columns=dates_wp)

fig, ax = plt.subplots(figsize=(12, 10), dpi=150)
sns.heatmap(heatmap_df, annot=True, fmt='d', cmap='YlOrRd', ax=ax,
            linewidths=0.5, cbar_kws={'label': '涨停家数'})
ax.set_title('热点概念轮动热力图（近5日）', fontsize=15, fontweight='bold', pad=15)
ax.set_xlabel('日期', fontsize=12)
ax.set_ylabel('概念', fontsize=12)
plt.xticks(rotation=45, ha='right')
plt.yticks(rotation=0)
plt.tight_layout()
plt.savefig(f'{out_dir}/chart_05_theme_heatmap.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("[OK] chart_05_theme_heatmap.png 已保存")

# ========== 图6: 流通市值 vs 换手率 散点图 ==========
fig, ax = plt.subplots(figsize=(12, 8), dpi=150)

df['流通市值亿'] = df['流通市值'].astype(float) / 1e8
df_filtered = df[df['流通市值亿'] < 500].copy()

colors_scatter = {
    '涨停池': COLOR_OTHER,
    '炸板池': COLOR_ZHABAN,
    '跌停池': COLOR_DIE_TING
}

for pool_type, color in colors_scatter.items():
    subset = df_filtered[df_filtered['池类型'] == pool_type]
    ax.scatter(subset['流通市值亿'], subset['换手率%'].astype(float),
               c=color, label=pool_type, alpha=0.6, s=50, edgecolors='white', linewidth=0.5)

ax.set_xlabel('流通市值（亿元）', fontsize=12)
ax.set_ylabel('换手率（%）', fontsize=12)
ax.set_title('流通市值 vs 换手率分布', fontsize=15, fontweight='bold', pad=15)
ax.legend(fontsize=11)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(alpha=0.3, linestyle='--')
ax.tick_params(axis='both', labelsize=11)

plt.tight_layout()
plt.savefig(f'{out_dir}/chart_06_marketcap_hs.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("[OK] chart_06_marketcap_hs.png 已保存")

# ========== 图7: 尾盘封板比例趋势图 ==========
fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

daily_zt_df = df[df['池类型'] == '涨停池'].copy()
daily_zt_df['小时'] = daily_zt_df['首次封板时间'].apply(parse_hour)
daily_zt_df = daily_zt_df[daily_zt_df['小时'].notna()]
daily_zt_df['尾盘'] = daily_zt_df['小时'] >= 14

wb_dates = sorted(daily_zt_df['日期'].unique())
wb_ratios = []
for d in wb_dates:
    day_df = daily_zt_df[daily_zt_df['日期'] == d]
    total = len(day_df)
    wb = len(day_df[day_df['尾盘']])
    wb_ratios.append(wb / total * 100 if total > 0 else 0)

wb_dates_fmt = [pd.to_datetime(d).strftime('%m-%d') for d in wb_dates]
ax.plot(wb_dates_fmt, wb_ratios, marker='o', linewidth=2.5, color=COLOR_PEAK, markersize=10)

for i, (d, r) in enumerate(zip(wb_dates_fmt, wb_ratios)):
    ax.annotate(f'{r:.1f}%', xy=(i, r), xytext=(0, 10),
                textcoords='offset points', ha='center', va='bottom',
                fontsize=11, fontweight='bold', color=COLOR_PEAK)

ax.set_xlabel('日期', fontsize=12)
ax.set_ylabel('尾盘封板占比（%）', fontsize=12)
ax.set_title('尾盘封板比例趋势（近5日）', fontsize=15, fontweight='bold', pad=15)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(alpha=0.3, linestyle='--')
ax.tick_params(axis='both', labelsize=11)
ax.set_ylim(0, max(wb_ratios) * 1.3 if wb_ratios else 10)

plt.tight_layout()
plt.savefig(f'{out_dir}/chart_07_seal_timing_trend.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("[OK] chart_07_seal_timing_trend.png 已保存")

# ========== 图8: 炸板率与跌停率趋势 ==========
fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

daily_total = df.groupby('日期').size()
daily_zt = df[df['池类型'] == '涨停池'].groupby('日期').size()
daily_zq = df[df['池类型'] == '炸板池'].groupby('日期').size()
daily_dt = df[df['池类型'] == '跌停池'].groupby('日期').size()

zhaban_rate = (daily_zq / daily_total * 100).dropna()
dieting_rate = (daily_dt / daily_total * 100).dropna()
zt_rate = (daily_zt / daily_total * 100).dropna()

all_dates_rate = sorted(set(zhaban_rate.index) & set(dieting_rate.index))
zq_rates = [zhaban_rate.get(d, 0) for d in all_dates_rate]
dt_rates = [dieting_rate.get(d, 0) for d in all_dates_rate]
zt_rates = [zt_rate.get(d, 0) for d in all_dates_rate]

all_dates_fmt = [pd.to_datetime(d).strftime('%m-%d') for d in all_dates_rate]
ax.plot(all_dates_fmt, zt_rates, marker='o', linewidth=2.5, color=COLOR_PEAK,
        label='涨停率', markersize=8)
ax.plot(all_dates_fmt, zq_rates, marker='s', linewidth=2, color=COLOR_ZHABAN,
        label='炸板率', markersize=7)
ax.plot(all_dates_fmt, dt_rates, marker='^', linewidth=2, color=COLOR_DIE_TING,
        label='跌停率', markersize=7)

for i, (zt, zq, dt) in enumerate(zip(zt_rates, zq_rates, dt_rates)):
    ax.annotate(f'{zt:.1f}%', xy=(i, zt), xytext=(0, 8),
                textcoords='offset points', ha='center', va='bottom',
                fontsize=9, color=COLOR_PEAK, fontweight='bold')
    ax.annotate(f'{zq:.1f}%', xy=(i, zq), xytext=(0, 4),
                textcoords='offset points', ha='center', va='bottom',
                fontsize=9, color=COLOR_ZHABAN)
    ax.annotate(f'{dt:.1f}%', xy=(i, dt), xytext=(0, -12),
                textcoords='offset points', ha='center', va='top',
                fontsize=9, color=COLOR_DIE_TING)

ax.set_xlabel('日期', fontsize=12)
ax.set_ylabel('比例（%）', fontsize=12)
ax.set_title('市场情绪节奏（近5日）', fontsize=15, fontweight='bold', pad=15)
ax.legend(fontsize=11)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(alpha=0.3, linestyle='--')
ax.tick_params(axis='both', labelsize=11)

plt.tight_layout()
plt.savefig(f'{out_dir}/chart_08_rates_trend.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("[OK] chart_08_rates_trend.png 已保存")

print("\nAll charts generated!")
