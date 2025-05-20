import re
import os
import asyncio
from nonebot.log import logger
from nonebot.rule import Rule
from nonebot import on_regex, on_message
from nonebot.permission import SUPERUSER
from nonebot.params import RegexGroup
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment, GroupMessageEvent
from nonebot.matcher import Matcher
from typing import Optional, Tuple


flag = False
xx_id = "3889001741"
bot_root_parent_dir = os.path.abspath(os.path.join(os.getcwd(), ".."))
fangshi_path = os.path.join(bot_root_parent_dir, "fangshi.ini")

# 一键药材上架命令
shangjia = on_regex(r"^一键药材上架", priority=1, block=True, permission=SUPERUSER)

@shangjia.handle()
async def handle_lianjin(bot: Bot, event: GroupMessageEvent, matcher: Matcher, args: Tuple[Optional[str], ...] = RegexGroup()):
    global flag
    flag = True
    await bot.send_group_msg(group_id=event.group_id, message=MessageSegment.at(xx_id) + " 药材背包")

# 判断消息
async def contains_at_me(bot: Bot, event: GroupMessageEvent) -> bool:
    self_id = str((await bot.get_login_info())["user_id"])
    group_member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=self_id)
    nickname = group_member_info.get("card") or group_member_info["nickname"]
    return (self_id in str(event.message) or f"@{nickname}" in str(event.message))

shangjia_rule = Rule(contains_at_me)
shangjia_matcher = on_message(rule=shangjia_rule, block=False)

@shangjia_matcher.handle()
async def shangjia(bot: Bot, event: GroupMessageEvent):
    global flag
    if not flag:
        return
    
    message = event.get_plaintext()
    pattern = r"名字：([^.\n]+)\s*拥有数量:(\d+)"
    matches = re.findall(pattern, message)
    shangjia_list = []

    # 加载坊市数据
    fangshi_data = load_from_ini(fangshi_path)

    fangshi_dict = {}
    for line in fangshi_data:
        name, price_date_history = line.split('=', 1)
        price_list = [price_date.split('_')[0] for price_date in price_date_history.split('/')]
        fangshi_dict[name] = price_list

    if matches:
        for name, quantity in matches:
            if name not in fangshi_dict:
                # await bot.send_group_msg(group_id=event.group_id, message=f"{name}未记录")
                continue
            
            # 选取最左边的四个价格
            prices = [int(price) for price in fangshi_dict[name][:4]]  # 选取最左边的四个价格
            
            # 筛选出成交价格
            valid_prices = []
            for i in range(1, len(prices)):
                if prices[i] < prices[i - 1]:
                    valid_prices.append(prices[i])

            if not valid_prices:
                chosen_price = prices[0]
            else:
                # 计算四个价格的平均值
                average_price = sum(prices) / len(prices)
                
                # 计算差值
                price_diffs = [(price, abs(price - average_price)) for price in valid_prices]
                
                # 这里选取与均价更近的价格, 若有其他需求可自行更改
                min_diff = min(diff for _, diff in price_diffs)
                candidates = [price for price, diff in price_diffs if diff == min_diff]
                chosen_price = min(candidates)
            
            shangjia_list.append((name, chosen_price, int(quantity)))
    
    if shangjia_list:
        for name, price, quantity in shangjia_list:
            await bot.send_group_msg(group_id=event.group_id, message=MessageSegment.at(xx_id) + f" 确认坊市上架{name} {price} {quantity}")
            await asyncio.sleep(5)  # 可以根据需要调整间隔
    flag = False

def load_from_ini(file_path=fangshi_path):
    """加载坊市数据"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = [line.strip() for line in file.readlines() if line.strip()]
        return data
    except FileNotFoundError:
        return []