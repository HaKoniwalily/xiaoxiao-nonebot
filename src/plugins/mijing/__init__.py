import json
from nonebot.log import logger
from nonebot import on_regex, get_bot, on_message
from pathlib import Path
from nonebot_plugin_apscheduler import scheduler
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from nonebot.permission import SUPERUSER
from nonebot.rule import Rule
from nonebot.params import RegexGroup
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment, Event
import aiofiles
import asyncio
import re

id_path = Path("config/config.json")
config_path = Path("config/mijing.json")
config_path.parent.mkdir(parents=True, exist_ok=True)

if id_path.exists():
    with open(id_path, "r", encoding="utf-8-sig") as f:
        config: Dict[str, object] = json.load(f)

if config_path.exists():
    with open(config_path, "r", encoding="utf-8-sig") as f:
        CONFIG = json.load(f)
else:
    CONFIG: Dict[str, bool] = {"mijing_enabled": False, "finish_time": None}
    with open(config_path, "w", encoding="utf-8-sig") as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=4)

xx_id = "3889001741"
start_message = MessageSegment.at(xx_id) + " 探索秘境"
finish_message = MessageSegment.at(xx_id) + " 秘境结算"

trun_on_mijing = on_regex(r"^(开启|关闭)自动秘境$", priority=1, block=True, permission=SUPERUSER)
@trun_on_mijing.handle()
async def handle_mijing(bot: Bot, event: GroupMessageEvent, matcher: Matcher, args: Tuple[Optional[str], ...] = RegexGroup()):
    await asyncio.sleep(1)  # 避免频繁发送
    mode = args[0]
    if mode == "开启":
        if CONFIG["mijing_enabled"]:
            await matcher.finish("自动秘境已经开启，无需重复开启")
        else:
            CONFIG["mijing_enabled"] = True
            if scheduler.get_job("xiulian_job"):
                try:
                    scheduler.pause_job("xiulian_job")
                    await bot.send_group_msg(group_id=config["group_id"], message="60秒后启动")
                    logger.warning("已暂停修炼任务")
                    await asyncio.sleep(60)
                except Exception as e:
                    logger.warning(f"暂停修炼任务失败: {e}")
            await bot.send_group_msg(group_id=event.group_id, message=start_message)

    else:
        if not CONFIG["mijing_enabled"]:
            await matcher.finish("自动秘境尚未开启，无需关闭")
        else:
            CONFIG["mijing_enabled"] = False
            try:
                scheduler.remove_job("mijing_job")
            except Exception as e:
                logger.warning(f"尝试移除不存在秘境任务: {e}")
    async with aiofiles.open(config_path, "w", encoding="utf8") as f:
        await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))

# 保存结算时间
def save_mijing_finish_time(finish_time: datetime):
    data = {
        "mijing_enabled": CONFIG["mijing_enabled"],
        "finish_time": finish_time.strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(config_path, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.warning(f"结算时间已保存：{data['finish_time']}")
    except Exception as e:
        logger.error(f"保存结算时间失败：{e}")

async def mijing_job(group_id: int):
    bot: Bot = get_bot()
    try:
        await bot.send_group_msg(group_id=group_id, message=finish_message)
        await asyncio.sleep(5)
        await bot.send_group_msg(group_id=group_id, message=start_message)
    except Exception as e:
        logger.warning(f"发送秘境结算消息失败：{e}")

async def is_mijing_enabled() -> bool:
    return CONFIG["mijing_enabled"]

async def contains_at_me(bot: Bot, event: GroupMessageEvent) -> bool:
    self_id = (await bot.get_login_info())["user_id"]
    is_at_me = any(seg.type == "at" and seg.data["qq"] == str(self_id) for seg in event.message)
    allowed_qq = "3889001741"  
    return is_at_me and str(event.user_id) == allowed_qq

mijing_rule = Rule(is_mijing_enabled, contains_at_me)

mijing_matcher = on_message(rule=mijing_rule, block=False)
# 获取秘境所需时间并创建任务
@mijing_matcher.handle()
async def get_mijing_minute(event: GroupMessageEvent):
    mijing_minute = str(event.message)
    pattern = r"(花费时间：|预计)(\d+(\.\d+)?)(?:\(原\d+(\.\d+)?\))?分钟"
    match = re.search(pattern, mijing_minute, re.DOTALL)  
    if match:
        mijing_minute = float(match.group(2))
        finish_time = datetime.now() + timedelta(minutes=mijing_minute, seconds=10)
        # 保存结算时间
        save_mijing_finish_time(finish_time)     
        scheduler.add_job(mijing_job, "date", run_date=finish_time, id="mijing_job",args=[event.group_id])
        logger.warning(f"当前进行中的秘境预计{mijing_minute}分钟后完成")

# 读取结算时间
def load_mijing_finish_time() -> Optional[datetime]:
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            finish_time_str = data.get("finish_time")
            if finish_time_str:
                return datetime.strptime(finish_time_str, "%Y-%m-%d %H:%M:%S")
    return None

is_mijing = on_regex(r".*现在正在秘境.*", block=True, rule=mijing_rule)
@is_mijing.handle()
async def handle_is_mijing(bot: Bot,event: GroupMessageEvent):
    finish_time = load_mijing_finish_time()
    if finish_time and not scheduler.get_job("mijing_job"):
        scheduler.add_job(mijing_job, "date", run_date=finish_time, id="mijing_job",args=[event.group_id])
        logger.warning(f"恢复任务：秘境将在 {finish_time} 结算")
    else:
        logger.warning("已存在秘境探索任务或没有结算时间")

finish_mijing = on_regex(r".*已经参加过本次秘境.*", block=True, rule=mijing_rule)
@finish_mijing.handle()
async def handle_finish_mijing(bot: Bot, event: GroupMessageEvent):
    try:
        CONFIG["mijing_enabled"] = False
        job = scheduler.get_job("xiulian_job")
        if job:
            scheduler.resume_job("xiulian_job")
            logger.warning("已恢复修炼任务")
        else:
            logger.warning("无需恢复")
    except Exception as e:
        logger.warning(f"恢复修炼失败: {e}")
    
    async with aiofiles.open(config_path, "w", encoding="utf8") as f:
        await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
    
    await bot.send_group_msg(group_id=event.group_id, message=MessageSegment.at(xx_id) + " 宗门闭关")
''' 
# 恶搞用
import random
async def jiesuan(bot: Bot, event: GroupMessageEvent) -> bool:
    return xx_id in str(event.message)  and "秘境结算" in str(event.message) and event.group_id==761433933
mj_jiesuan = on_message(rule=Rule(jiesuan), priority=5, block=True)
messages = [
    "道友进入秘境后闯过了重重试炼，拿到了无上仙器：射曰弓!",
    "在秘境最深处与神秘势力大战，底牌尽出总算是抢到了极品仙器：厚罪（残缺）!",
    "在秘境最深处与神秘势力大战，底牌尽出总算是抢到了极品仙器：旡罪（残缺）!",
    "道友在秘境里探索险境，突然感觉一阵天旋地转，清醒过来时已被踢出秘境！但手里多了一件法器，竟然是失传已久的无上仙器：天罪!回过神定睛一看，居然是一场梦！ ",
]
@mj_jiesuan.handle()
async def handle_mj_jiesuan(bot: Bot, event: GroupMessageEvent):
    random_message = random.choice(messages)
    await bot.send_group_msg(group_id=761433933, message=random_message)
'''