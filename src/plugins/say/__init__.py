import json
import re
from nonebot.matcher import Matcher
from pathlib import Path
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.params import RegexGroup
from typing import Optional, Tuple

config_path = Path("config/config.json")
config_path.parent.mkdir(parents=True, exist_ok=True)

if config_path.exists():
        with open(config_path, "r", encoding="utf-8-sig") as f:
            CONFIG = json.load(f)
OWNER_IDS = [int(id) for id in CONFIG.get("owner_id", [])]  
name = CONFIG.get("name", " ")  

command_pattern = rf"^{re.escape(name)}?听令(1|2)(.*)"
trun_on_listen = on_regex(command_pattern, priority=1, block=True)

async def send_at_message(bot: Bot, group_id: int, user_id: str, message: str):
    try:
        at_message = MessageSegment.at(user_id) + message
        await bot.send_group_msg(group_id=group_id, message=at_message)
        
    except Exception as e:
        print(f"发送消息失败: {e}")

@trun_on_listen.handle()
async def handle_command(
    bot: Bot, 
    event: GroupMessageEvent, 
    matcher: Matcher,
    args: Tuple[Optional[str], ...] = RegexGroup(), 
):
    user_id = event.user_id
    command_type = args[0].strip()
    command_content = args[1].strip()
    group_id = event.group_id
    if user_id in OWNER_IDS:  
        
        if command_type == "2":
            await matcher.finish()
            await bot.send_group_msg(group_id=group_id, message=command_content)
        elif command_type == "1":
            await matcher.finish()
            target_user_id = "3889001741" 
            await send_at_message(bot, group_id, target_user_id, command_content)
        else:
            await bot.send(event, "命令无效")
    else:
           return
