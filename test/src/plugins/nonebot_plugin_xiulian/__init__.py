from nonebot.plugin import on_regex, PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot.params import RegexGroup
from nonebot.matcher import Matcher
from nonebot import require, get_bot
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    MessageSegment,
    GroupMessageEvent,
    ActionFailed,
    Adapter,
)
from nonebot.adapters.onebot.v11.event import Event, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from nonebot.typing import overrides
from typing import Dict, List, Optional, Tuple, Literal, Type, TypeVar
from pathlib import Path
import asyncio
import aiofiles
try:
    import ujson as json
except ModuleNotFoundError:
    import json

id_path = Path("config/config.json")
config_path = Path("config/xiulian.json")
config_path.parent.mkdir(parents=True, exist_ok=True)

if config_path.exists():
    with open(config_path, "r", encoding="utf-8-sig") as f:
        CONFIG: Dict[str, bool] = json.load(f)
else:
    CONFIG: Dict[str, bool] = {"xiulian_enabled": False}
    with open(config_path, "w", encoding="utf-8-sig") as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=4)

if id_path.exists():
    with open(id_path, "r", encoding="utf-8-sig") as f:
        config: Dict[str, bool] = json.load(f)

try:
    scheduler = require("nonebot_plugin_apscheduler").scheduler
except Exception:
    scheduler = None


trun_on_xiulian = on_regex(r"^(开启|关闭)修炼$", priority=99, block=False, permission=SUPERUSER)

@trun_on_xiulian.handle()
async def handle_xiulian(
    bot: Bot, 
    event: MessageEvent, 
    matcher: Matcher, 
    args: Tuple[Optional[str], ...] = RegexGroup(),
):
    mode = args[0]
    logger.info(f"Current CONFIG before processing: {CONFIG}")
    logger.info(f"Scheduler: {scheduler}")
    if not scheduler:
        await bot.send("未安装软依赖nonebot_plugin_apscheduler，不能使用定时发送功能")
        return

    if mode == "开启":
        logger.info("Processing '开启修炼' command...")
        if CONFIG["xiulian_enabled"]:
            logger.info("修炼已经开启，无需重复开启")
            await matcher.finish("修炼已经开启，无需重复开启")
            return
        else:
            CONFIG["xiulian_enabled"] = True
            logger.info("Starting xiulian job...")
            try:
                scheduler.add_job(xiulian_job, "interval", seconds=62, id="xiulian_job")
                logger.info("定时任务添加成功")
            except ActionFailed as e:
                logger.warning(f"定时任务添加失败，{repr(e)}")
    else:
        # 处理“关闭修炼”逻辑
        logger.info("Processing '关闭修炼' command...")
        if not CONFIG["xiulian_enabled"]:
            logger.info("修炼尚未开启，无需关闭")
            await matcher.finish("修炼尚未开启，无需关闭")
            return
        else:
            CONFIG["xiulian_enabled"] = False
            logger.info("Stopping xiulian job...")
            try:
                scheduler.remove_job("xiulian_job")
                logger.info("定时任务移除成功")
            except Exception as e:
                logger.warning(f"定时任务移除失败，{e}")

    logger.info(f"Current state after change: {CONFIG['xiulian_enabled']}")
    
    async with asyncio.Lock():
        async with aiofiles.open(config_path, "w", encoding="utf8") as f:
            await f.write(json.dumps(CONFIG, ensure_ascii=False, indent=4))

    logger.info("即将返回响应")
    await matcher.finish(f"已成功{mode}修炼")
    return

async def xiulian_job():
    bot: Bot = get_bot()
    user_id = "3889001741"  # 指定的群用户ID
    message = MessageSegment.at(user_id) + " 修炼"
    try:
        await bot.send_group_msg(group_id=config["group_id"], message=message)
        await asyncio.sleep(1)  # 避免频繁发送
    except Exception as e:
        logger.warning(f"发送修炼消息失败：{e}")


if CONFIG["xiulian_enabled"]:
    try:
        scheduler = require("nonebot_plugin_apscheduler").scheduler
        scheduler.add_job(xiulian_job, "interval", seconds=62, id="xiulian_job", replace_existing=True)
        logger.info("定时任务启动成功")
    except Exception as e:
        logger.warning(f"启动定时任务失败：{e}")


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
    
#@register_event
#class PrivateMessageSentEvent(PrivateMessageEvent):
#    """私聊消息里自己发送的消息"""
#
#    post_type: Literal["message_sent"]
#    message_type: Literal["private"]
#
#    @overrides(Event)
#    def get_type(self) -> str:
#        """伪装成message类型。"""
#        return "message"