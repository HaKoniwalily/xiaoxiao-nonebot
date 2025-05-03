import re
from nonebot.plugin import on_regex
from nonebot.permission import SUPERUSER
from nonebot.params import RegexGroup
from nonebot.matcher import Matcher
from nonebot_plugin_apscheduler import scheduler
from nonebot import require, get_bot, on_message
from nonebot.rule import Rule
import os
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageSegment,
    GroupMessageEvent,
    Adapter,
)
from nonebot.adapters.onebot.v11.event import Event, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from nonebot.typing import overrides
from typing import Dict, Optional, Tuple, Literal, Type, TypeVar, Match
from pathlib import Path
from datetime import datetime, timedelta
import re
import aiofiles
import asyncio
try:
    import ujson as json
except ModuleNotFoundError:
    import json

id_path = Path("config/config.json")
config_path = Path("config/xuanshang.json")
config_path.parent.mkdir(parents=True, exist_ok=True)
bot_root_parent_dir = os.path.abspath(os.path.join(os.getcwd(), ".."))
fangshi_path = os.path.join(bot_root_parent_dir, "fangshi.ini")
self_id = None
nickname = None

default_xuanshang_config = {
    "xuanshang_enabled": False,
    "xuanshang_mode": "value"
}

if config_path.exists():
    with open(config_path, "r", encoding="utf-8-sig") as f:
        CONFIG = json.load(f)
else:
    CONFIG = default_xuanshang_config
    with open(config_path, "w", encoding="utf-8-sig") as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=4)

if id_path.exists():
    with open(id_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)


xx_id = "3889001741"
refresh_message = MessageSegment.at(xx_id) + " 悬赏令刷新"
finish_message = MessageSegment.at(xx_id) + " 悬赏令结算"
view_message = MessageSegment.at(xx_id) + " 悬赏令"

trun_on_xuanshang = on_regex(r"^(开启|关闭)自动悬赏$", priority=1, block=True, permission=SUPERUSER)


@trun_on_xuanshang.handle()
async def handle_xuanshang(
    bot: Bot,
    event: Event,
    matcher: Matcher,
    args: Tuple[Optional[str], ...] = RegexGroup(),
):
    await asyncio.sleep(1)  # 避免频繁发送
    await on_start(bot)
    mode = args[0]
    if mode == "开启":
        if CONFIG["xuanshang_enabled"]:
            await matcher.finish("自动悬赏已经开启，无需重复开启")
        else:
            CONFIG["xuanshang_enabled"] = True
            if scheduler.get_job("xiulian_job"):
                try:
                    scheduler.pause_job("xiulian_job")
                    await bot.send_group_msg(group_id=config["group_id"], message="60s后启动")
                    logger.warning("已暂停修炼任务")
                    await asyncio.sleep(60)
                except Exception as e:
                    logger.warning(f"暂停修炼任务失败: {e}")
            await bot.send_group_msg(group_id=event.group_id, message=view_message)

    else:
        if not CONFIG["xuanshang_enabled"]:
            await matcher.finish("自动悬赏尚未开启，无需关闭")
        else:
            CONFIG["xuanshang_enabled"] = False
            try:
                scheduler.remove_job("xuanshang_job")
            except Exception as e:
                logger.warning(f"尝试移除不存在悬赏令任务: {e}")
    async with aiofiles.open(config_path, "w", encoding="utf8") as f:
        await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
    await matcher.finish(f"已成功{mode}自动悬赏")


async def xuanshang_job(group_id: int):
    bot: Bot = get_bot()
    try:
        await bot.send_group_msg(group_id=group_id, message=finish_message)
        return
    except Exception as e:
        logger.warning(f"发送悬赏结算信息失败：{e}")


async def is_xuanshang_enabled() -> bool:
    return CONFIG["xuanshang_enabled"]


import re


async def on_start(bot: Bot):
    global self_id, nickname
    self_id = (await bot.get_login_info())["user_id"]
    group_member_info = await bot.get_group_member_info(group_id=config["group_id"], user_id=self_id)
    nickname = group_member_info.get("card") or group_member_info["nickname"]  # 机器人在该群的昵称


async def contains_at_me(bot: Bot, event: GroupMessageEvent) -> bool:
    return (str(self_id) in str(event.message) or f"@{nickname}" in str(event.message)) and str(
        event.group_id) in str(config["group_id"])


xuanshang_rule = Rule(is_xuanshang_enabled) & Rule(contains_at_me)

accept_xuanshang = on_regex(r".*没有查到你的悬赏令|悬赏令结算.*?增加修为.*", block=True, rule=xuanshang_rule)


@accept_xuanshang.handle()
async def handle_accept_xuanshang(bot: Bot, event: GroupMessageEvent):
    await bot.send_group_msg(group_id=config["group_id"], message=refresh_message)


none_xuanshang = on_regex(r".*结算任务信息.*", block=True, rule=xuanshang_rule)


@none_xuanshang.handle()
async def handle_none_xuanshang(bot: Bot, event: GroupMessageEvent):
    await bot.send_group_msg(group_id=config["group_id"], message=finish_message)


finish_xuanshang = on_regex(r".*刷新次数已用尽.*", block=True, rule=xuanshang_rule)


@finish_xuanshang.handle()
async def handle_finish_xuanshang(bot: Bot, event: GroupMessageEvent):
    CONFIG["xuanshang_enabled"] = False
    try:
        job = scheduler.get_job("xiulian_job")
        if job:
            scheduler.resume_job("xiulian_job")
            logger.warning("已恢复修炼任务")
        else:
            logger.warning("无需恢复修炼")
    except Exception as e:
        logger.warning(f"恢复修炼失败: {e}")
    async with aiofiles.open(config_path, "w", encoding="utf8") as f:
        await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
    await bot.send_group_msg(group_id=config["group_id"], message=MessageSegment.at(xx_id) + " 宗门闭关")


accept_xuanshang_success = on_regex(r".*接取任务(.*?)成功.*", block=True, rule=xuanshang_rule)


@accept_xuanshang_success.handle()
async def handle_accept_xuanshang_success(bot: Bot, event: GroupMessageEvent):
    await bot.send_group_msg(group_id=config["group_id"], message=view_message)


xuanshang_matcher = on_message(rule=xuanshang_rule, block=False)


# 获取悬赏令所需时间并创建任务
@xuanshang_matcher.handle()
def get_xuanshang_minute(event: GroupMessageEvent):
    xuanshang_minute = str(event.message)
    pattern = r".*悬赏令(.*?)预计(\d+(\.\d+)?)(?:\(原\d+(\.\d+)?\))?分钟.*"
    match = re.search(pattern, xuanshang_minute, re.DOTALL)
    if match:
        xuanshang_minute = float(match.group(2))
        finish_time = datetime.now() + timedelta(minutes=xuanshang_minute, seconds=10)
        group_id = event.group_id  # 获取群聊ID
        scheduler.add_job(xuanshang_job, "date", run_date=finish_time, id="xuanshang_job", args=[group_id])
        logger.warning(f"当前进行中的悬赏令预计{xuanshang_minute}分钟后完成")


# 悬赏令接取
@xuanshang_matcher.handle()
async def handle_xuanshang_matcher(bot: Bot, event: GroupMessageEvent):
    xuanshang_text = str(event.message)
    xuanshang_list = parse_xuanshang_info(xuanshang_text)  # 解析悬赏令

    if xuanshang_list:
        fangshi_data = load_from_ini(fangshi_path)  # 加载坊市数据
        fangshi_prices = parse_fangshi_data(fangshi_data, xuanshang_list)  # 根据悬赏令物品计算价格
        best_xuanshang_info = select_best_xuanshang(xuanshang_list, fangshi_prices)  # 根据价格选择最佳悬赏令

        if best_xuanshang_info:
            await bot.send_group_msg(group_id=config["group_id"], message=MessageSegment.at(xx_id) + " 悬赏令接取" +
                                                                                      best_xuanshang_info["序号"])
    return


# 解析悬赏令信息
def parse_xuanshang_info(xuanshang_text: str) -> list:
    xuanshang_list = []
    pattern = r"(\d+)、(.*?),完成几率(\d+),基础报酬(\d+)修为,预计需(\d+)分钟，可能额外获得：(.*?):(.*?)!"
    matches = re.finditer(pattern, xuanshang_text, re.DOTALL)
    for match in matches:
        index = match.group(1)
        description = match.group(2)
        chance = int(match.group(3))
        reward = int(match.group(4))
        time_needed = int(match.group(5))
        quality = match.group(6).strip()
        item = match.group(7).strip()
        xuanshang_list.append({
            "序号": index,
            "描述": description,
            "完成几率": chance,
            "基础报酬": reward,
            "预计时间": time_needed,
            "品质": quality,
            "物品": item
        })
    return xuanshang_list


# 计算悬赏令中的物品价格
def parse_fangshi_data(fangshi_data: list, xuanshang_list: list) -> Dict[str, float]:
    """
    计算悬赏令物品的平均价格
    """
    required_items = [xuanshang["物品"] for xuanshang in xuanshang_list]  # 从悬赏令中提取物品名称
    prices = {}

    for line in fangshi_data:
        match = re.match(r"^(.+)=(.+)$", line)
        if match:
            item_name = match.group(1).strip()
            price_date_str = match.group(2).strip()

            # 如果该物品在悬赏令中需要计算，则进行计算
            if item_name in required_items:
                try:
                    price_date_pairs = price_date_str.split("/")
                    prices_list = [int(pair.split("_")[0]) for pair in price_date_pairs if pair]
                    avg_price = sum(prices_list) / len(prices_list)  # 计算平均价格
                    prices[item_name] = avg_price
                    logger.warning(f"{item_name}={avg_price}")
                except ValueError:
                    logger.warning(f"获取价格失败: {line}")
    return prices


# 根据价格选择最佳悬赏令
def select_best_xuanshang(xuanshang_list: list, fangshi_prices: Dict[str, float]) -> Optional[Dict[str, str]]:
    """
    根据物品的平均价格选择最佳悬赏令
    """
    best_xuanshang_info = None
    highest_price = -1

    for xuanshang in xuanshang_list:
        item_name = xuanshang["物品"]

        # 如果物品在坊市数据中，获取其平均价格
        if item_name in fangshi_prices:
            avg_price = fangshi_prices[item_name]

            if avg_price > highest_price:
                highest_price = avg_price
                best_xuanshang_info = xuanshang

    return best_xuanshang_info


# 加载坊市数据
def load_from_ini(file_path=fangshi_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = [line.strip() for line in file.readlines() if line.strip()]
        return data
    except FileNotFoundError:
        return []


# 识别自身发送信息
Event_T = TypeVar("Event_T", bound=Type[Event])


def register_event(event: Event_T) -> Event_T:
    Adapter.add_custom_model(event)
    logger.opt(colors=True).trace(
        f"Custom event <e>{event.__qualname__!r}</e> registered from module <g>{event.__class__.__module__!r}</g>"
    )
    return event


@register_event
class GroupMessageSentEvent(GroupMessageEvent):
    """群聊消息里自己发送的消息"""

    post_type: Literal["message_sent"]
    message_type: Literal["group"]

    @overrides(Event)
    def get_type(self) -> str:
        """伪装成message类型。"""
        return "message"

# @register_event
# class PrivateMessageSentEvent(PrivateMessageEvent):
#     """私聊消息里自己发送的消息"""
#
#     post_type: Literal["message_sent"]
#     message_type: Literal["private"]
#
#     @overrides(Event)
#     def get_type(self) -> str:
#         """伪装成message类型。"""
#         return "message"
    