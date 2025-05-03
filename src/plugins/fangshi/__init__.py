import re
from nonebot import on_message
import matplotlib
from pathlib import Path
import datetime
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import json
from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.log import logger
from typing import Dict
import os
from filelock import FileLock

matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
bot_root_parent_dir = os.path.abspath(os.path.join(os.getcwd(), ".."))
fangshi_path = os.path.join(bot_root_parent_dir, "fangshi.ini")
lock_file = fangshi_path + ".lock"

path = Path("config/config.json")
path.parent.mkdir(parents=True, exist_ok=True)
if path.exists():
    with open(path, "r", encoding="utf-8-sig") as f:
        config: Dict[str, object] = json.load(f)
# 启用查行情群号
allowed_group_ids = config.get("炼丹与行情辅助")

# 格式化价格
def format_price(price: int) -> str:
    """格式化价格为万或亿"""
    if price >= 100000000:  # 大于或等于1亿
        return f"{price / 100000000:.1f}亿"
    elif price >= 10000:  # 大于或等于1万
        return f"{price / 10000}万"
    else:  # 小于1万
        return str(price)

# 加载坊市数据
def load_from_ini(file_path=fangshi_path):
    """加载坊市数据"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = [line.strip() for line in file.readlines() if line.strip()]
        result = {}
        for line in data:
            if "=" not in line:
                continue
            name, price_date_history = line.split("=", 1)
            price_date_pairs = price_date_history.split("/")
            prices = []
            dates = []
            for pair in price_date_pairs:
                if pair:
                    price, date_str = pair.split("_")
                    prices.append(price)
                    dates.append(date_str)
            result[name] = (prices, dates)
        return result
    except FileNotFoundError:
        return {}

# 生成价格图
def generate_line_chart(item_name: str, prices: list, dates: list) -> BytesIO:
    prices = [int(price) for price in prices][::-1]  # 因为坊市价格最左边是最新的。。。
    dates = dates[::-1]

    plt.figure(figsize=(8, 6))
    plt.plot(dates, prices, marker='o', color='b', linestyle='-', markersize=6)

    for i, price in enumerate(prices):
        formatted_price = format_price(price)
        plt.text(dates[i], price, formatted_price, fontsize=10, verticalalignment='bottom', horizontalalignment='center')

    plt.title(f"{item_name} 价格")
    plt.xlabel("日期")
    plt.ylabel("价格")
    plt.xticks(rotation=45)
    plt.grid(True)

    img_buf = BytesIO()
    plt.savefig(img_buf, format="png")
    img_buf.seek(0)
    plt.close()

    return img_buf

# 查询物品价格并生成
async def get_item_price(item_name: str, bot: Bot, event: GroupMessageEvent):
    fangshi_data = load_from_ini(fangshi_path)

    # 查询物品的价格历史
    if item_name in fangshi_data:
        prices, dates = fangshi_data[item_name]
        img_buf = generate_line_chart(item_name, prices, dates)
        await bot.send_group_msg(group_id=event.group_id, message=MessageSegment.image(img_buf))
        return

    await bot.send_group_msg(group_id=event.group_id, message=f"没有找到{item_name}")


# 确认消息是坊市信息
async def is_fangshi(bot: Bot, event: GroupMessageEvent) -> bool:
    # logger.warning(event.message)
    return "CQ:markdown" in str(event.message) and "交易行为" in str(event.message)

rule = Rule(is_fangshi)

fangshi_handler = on_message(rule=rule, block=True)

@fangshi_handler.handle()
async def handle_item_price(bot: Bot, event: GroupMessageEvent):
    message = event.get_plaintext()
    pattern = r"价格:(\d+\.?\d*)\s*([万亿])\s+([^\\\n]+?)(?=\s*物品功效|$)"
    matches = re.findall(pattern, message)
    data = []
    if matches:
        for price, unit, raw_name in matches:
            name = re.sub(r'[\s\u200b\u200c\u200d\ufeff]', '', raw_name).strip()
            if not name or '=' in name or '/' in name:
                continue
            converted_price = convert_price(price, unit)
            current_date = datetime.datetime.now().strftime("%m-%d %H:%M")
            data.append((name, converted_price, current_date))

        if data:
            logger.warning(data)
            save_to_ini(data)
        else:
            logger.warning("匹配到数据但清洗后为空")
    else:
        logger.warning("未匹配到物品和价格信息！")

# 将价格转换为整数形式
def convert_price(price: str, unit: str) -> int:
    multiplier = {"万": 10**4, "亿": 10**8}
    return int(float(price) * multiplier.get(unit, 1))

def save_to_ini(data, file_path=fangshi_path):
    """保存坊市数据"""
    with FileLock(lock_file):
        existing_data = load_from_ini(file_path)

        for name, new_price, new_date in data:
            if name in existing_data:
                prices, dates = existing_data[name]
                # 如果新的价格与当前最新价格相同，则不添加
                if prices and prices[0] != str(new_price):
                    prices.insert(0, str(new_price))
                    dates.insert(0, new_date)
                    if len(prices) > 12:  # 设置储存价格数量
                        prices.pop()
                        dates.pop()
            else:
                # 如果是新物品，初始化价格历史记录
                existing_data[name] = ([str(new_price)], [new_date])

        with open(file_path, "w", encoding="utf-8") as file:
            for name, (prices, dates) in existing_data.items():
                price_date_pairs = [f"{price}_{date}" for price, date in zip(prices, dates)]
                file.write(f"{name}={'/'.join(price_date_pairs)}\n")
    print(f"坊市数据已保存")


async def at_me(bot: Bot, event: GroupMessageEvent) -> bool:
    self_id = str((await bot.get_login_info())["user_id"])
    message = str(event.message)
    return "查行情" in message and (self_id in str(event) or event.group_id in allowed_group_ids)

chaxun_rule = Rule(at_me)
chaxun = on_message(rule=chaxun_rule, block=False)

@chaxun.handle()
async def handle_chaxun(bot: Bot, event: GroupMessageEvent):
    message = str(event.message)
    match = re.search(r"^查行情\s*(\S+)", message)
    if match:
        item_name = match.group(1)
        await get_item_price(item_name, bot, event)
    