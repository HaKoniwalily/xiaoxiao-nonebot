from nonebot.plugin import on_regex
from nonebot.permission import SUPERUSER
from nonebot.params import RegexGroup
from nonebot.matcher import Matcher
from nonebot import require, get_bot, on_message
from nonebot.rule import keyword, Rule
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageSegment,
    GroupMessageEvent,
    Adapter,
)
from nonebot.adapters.onebot.v11.event import Event, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from nonebot.typing import overrides
from typing import Dict, Optional, Tuple, Literal, Type, TypeVar
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
import aiofiles
try:
    import ujson as json
except ModuleNotFoundError:
    import json

id_path = Path("config/config.json")
config_path = Path("config/zongmen.json")
config_path.parent.mkdir(parents=True, exist_ok=True)
self_id = None

# 定义默认配置
default_zongmen_config: Dict[str, object] = {
    "zongmen_task_list": [
        {
            "task_number": 1,
            "message": "传言山外村庄有邪修抢夺灵石，请道友下山为民除害",
            "complete": True
        },
        {
            "task_number": 2,
            "message": "有少量弟子私下消费，私自架设小型窝点，请道友前去查抄",
            "complete": True
        },
        {
            "task_number": 3,
            "message": "山门将开，宗门急缺一批药草熬制九转丹，请道友下山购买",
            "complete": False
        },
        {
            "task_number": 4,
            "message": "在宗门外见到师弟欠了别人灵石被追打催债，请道友帮助其还清",
            "complete": False
        },
        {
            "task_number": 5,
            "message": "山下一月一度的市场又开张了，其中虽凡物较多，但是请道友慷慨解囊，为宗门购买一些蒙尘奇宝",
            "complete": False
        },
    ],
    "zongmen_enabled": False
}

if id_path.exists():
    with open(id_path, "r", encoding="utf-8-sig") as f:
        config: Dict[str, object] = json.load(f)

if config_path.exists():
    with open(config_path, "r", encoding="utf-8-sig") as f:
        CONFIG = json.load(f)
else:
    CONFIG = default_zongmen_config
    with open(config_path, "w", encoding="utf-8-sig") as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=4)

try:
    scheduler = require("nonebot_plugin_apscheduler").scheduler
except Exception:
    scheduler = None

xx_id = "3889001741"
refresh_message =MessageSegment.at(xx_id)+" 宗门任务刷新"
accept_message =MessageSegment.at(xx_id)+" 宗门任务接取"
finish_message = MessageSegment.at(xx_id)+" 宗门任务完成"

trun_on_zongmen = on_regex(r"^(开启|关闭)自动宗门任务$", priority=1, block=True, permission=SUPERUSER)

@trun_on_zongmen.handle()
async def handle_zongmen(
    bot: Bot, 
    event: Event, 
    matcher: Matcher,
    args: Tuple[Optional[str], ...] = RegexGroup(),
):
    await asyncio.sleep(1)  # 避免频繁发送
    await on_start(bot)
    mode = args[0]
    if mode == "开启":
        if CONFIG["zongmen_enabled"]:
            await matcher.finish("自动宗门任务已经开启，无需重复开启")
        else: 
            CONFIG["zongmen_enabled"] = True
            await bot.send_group_msg(group_id=config["group_id"], message=accept_message)           
    else:
        if not CONFIG["zongmen_enabled"]:
            await matcher.finish("自动宗门任务尚未开启，无需关闭")
        else:
            CONFIG["zongmen_enabled"] = False
            if scheduler.get_job("zongmen_job"):
                scheduler.remove_job("zongmen_job")

    async with aiofiles.open(config_path, "w", encoding="utf8") as f:
        await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
    await matcher.finish(f"已成功{mode}自动宗门任务")




# 刷新任务
async def zongmen_job():
    bot: Bot = get_bot()
    try:
        await bot.send_group_msg(group_id=config["group_id"], message=refresh_message)
        return
    except Exception as e:
        logger.warning(f"发送刷新宗门任务消息失败：{e}")
# 完成任务
async def zongmen_fin():
    bot: Bot = get_bot()
    try:
        await bot.send_group_msg(group_id=config["group_id"], message=finish_message)
        return
    except Exception as e:
        logger.warning(f"发送完成宗门任务消息失败：{e}")


async def on_start(bot: Bot):
    global self_id
    self_id = (await bot.get_login_info())["user_id"]
async def is_zongmen_enabled() -> bool:
    return CONFIG["zongmen_enabled"]
async def contains_at_me(bot: Bot, event: GroupMessageEvent) -> bool:
    """
    检查消息是否为小小所@
    """
    is_at_me = any(seg.type == "at" and seg.data["qq"] == str(self_id) for seg in event.message)
    return is_at_me and str(event.user_id) == xx_id

zongmen_rule = Rule(is_zongmen_enabled, contains_at_me)

zongmen_matcher = on_message(rule=zongmen_rule, block=False)
@zongmen_matcher.handle()
async def handle_zongmen_matcher(bot: Bot, event: GroupMessageEvent):
    args = str(event.get_message()).strip()
    for task in CONFIG["zongmen_task_list"]:
        if task["message"] in args:
            if task["complete"]:
                # logger.warning("可完成任务")
                if scheduler.get_job("zongmen_job"):
                    scheduler.remove_job("zongmen_job")
                await bot.send_group_msg(group_id=config["group_id"], message=finish_message)
                return
            else:
                if not scheduler.get_job("zongmen_job"):
                    await bot.send_group_msg(group_id=config["group_id"], message=refresh_message)
                    scheduler.add_job(zongmen_job, "date", run_date=datetime.now() + timedelta(seconds=70), id="zongmen_job") #设置刷新间隔
                    return                 
            
zongmen_finish = on_regex(r".*无法再获取宗门.*", block=True, rule=zongmen_rule)
@zongmen_finish.handle()
async def handle_zongmen_finish(bot: Bot):
    if scheduler.get_job("zongmen_job"):
        scheduler.remove_job("zongmen_job")
    CONFIG["zongmen_enabled"] = False
    await bot.send_group_msg(group_id=config["group_id"], message="已完成宗门任务")
    async with aiofiles.open(config_path, "w", encoding="utf8") as f:
        await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))
        
zongmen_failure = on_regex(r".*扣你任务次数.*", block=True, rule=zongmen_rule)
@zongmen_failure.handle()
async def handle_zongmen_failure(bot: Bot):
    if scheduler.get_job("zongmen_job"):
        scheduler.remove_job("zongmen_job")
    scheduler.add_job(zongmen_fin, "date", run_date=datetime.now() + timedelta(seconds=270), id="zongmen_job")
    logger.warning("完成失败，等待恢复")

zongmen_complete = on_regex(r".*宗门建设度增加.*", block=True, rule=zongmen_rule)
@zongmen_complete.handle()
async def handle_zongmen_complete(bot: Bot):
    await bot.send_group_msg(group_id=config["group_id"], message=accept_message)
 

#识别自身发送信息
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
    