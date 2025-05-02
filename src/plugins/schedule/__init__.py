import nonebot
import json
import re
from nonebot.log import logger
from nonebot import on_regex,on_message, get_bot
from pathlib import Path
from nonebot.adapters.onebot.v11 import Message, MessageSegment,GroupMessageEvent,Bot
from nonebot_plugin_apscheduler import scheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Dict

path = Path("config/config.json")
path.parent.mkdir(parents=True, exist_ok=True)
user_id = 3889001741

if path.exists():
    with open(path, "r", encoding="utf-8-sig") as f:
        config: Dict[str, object] = json.load(f)


# 定时领取丹药
danyao_date = config.get("丹药领取时间")
hour, minute = map(int, danyao_date.split(":"))
@scheduler.scheduled_job(CronTrigger(hour=hour, minute=minute, second=0))
async def send_danyao_message():   
    message = MessageSegment.at(user_id) + " 宗门丹药领取"
    bot = nonebot.get_bot()
    await bot.send_group_msg(group_id=config.get("group_id"), message=message)

# 定时签到
danyao_date = config.get("签到时间")
hour, minute = map(int, danyao_date.split(":"))
@scheduler.scheduled_job(CronTrigger(hour=hour, minute=minute, second=0))
async def send_qiandao_message():
    message = MessageSegment.at(user_id) + " 修仙签到"
    bot = nonebot.get_bot()
    await bot.send_group_msg(group_id=config.get("group_id"), message=message)


