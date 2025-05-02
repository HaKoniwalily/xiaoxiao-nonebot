import json
import re
import asyncio
from nonebot.log import logger
from nonebot.rule import Rule
from nonebot.log import logger
from nonebot import on_regex, on_message
from pathlib import Path
from nonebot.permission import SUPERUSER
from nonebot.params import RegexGroup
from nonebot.adapters.onebot.v11 import Bot, Event,MessageSegment,GroupMessageEvent
from nonebot.matcher import Matcher
from typing import Optional, Tuple

config_path = Path("config/danyao.json")
id_path = Path("config/config.json")
config_path.parent.mkdir(parents=True, exist_ok=True)
xx_id = "3889001741"
self_id = None
nickname = None
flag = False

default_lianjin = {
    "炼金": [
        "回元丹",
        "培元丹",
        "养元丹",
        "培元丹",
        "回春丹",
        "黄龙丹",
        "生骨丹",
        "化瘀丹",
        "太元真丹",
        "九阳真丹",
        "归藏灵丹",
        "冰心丹"      
    ]
}
if not config_path.exists():
    CONFIG = default_lianjin
    with open(config_path, "w", encoding="utf-8-sig") as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=4)

if id_path.exists():
    with open(id_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)

# 添加和删除丹药炼金，使用#分隔
danyao = on_regex(r"^(添加|删除)丹药炼金\s*(.+)$", priority=1, block=True, permission=SUPERUSER)

@danyao.handle()
async def handle_danyao(bot: Bot, event: Event, matcher: Matcher, args: Tuple[Optional[str], ...] = RegexGroup()):
    action = args[0]  
    danyao_content = args[1].strip()  
    danyao_list = [item.strip() for item in danyao_content.split('#')]
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            danyao_data = json.load(f)
    except Exception as e:
        logger.error(f"加载丹药文件时发生错误: {e}")
        return
    alchemy_list = danyao_data.get("炼金", [])
    if action == "添加":
        added = []
        for danyao in danyao_list:
            if danyao and danyao not in alchemy_list:
                alchemy_list.append(danyao)
                added.append(danyao)
        if added:
            danyao_data["炼金"] = alchemy_list
            with open(config_path, "w", encoding="utf-8-sig") as f:
                json.dump(danyao_data, f, ensure_ascii=False, indent=4)
            current_list = '#'.join(alchemy_list)
            await matcher.finish(f"成功添加丹药:\n{'#'.join(added)}\n当前炼金丹药:\n{current_list}")
        else:
            await matcher.finish("别加了")
    elif action == "删除":
        deleted = []
        for danyao in danyao_list:
            if danyao and danyao in alchemy_list:
                alchemy_list.remove(danyao)
                deleted.append(danyao)
        
        if deleted:
            danyao_data["炼金"] = alchemy_list  
            with open(config_path, "w", encoding="utf-8-sig") as f:
                json.dump(danyao_data, f, ensure_ascii=False, indent=4)
            current_list = '#'.join(alchemy_list)
            await matcher.finish(f"成功删除丹药:\n{'#'.join(deleted)}\n当前炼金丹药:\n{current_list}")
        else:
            await matcher.finish("删什么")


lianjin = on_regex(r"^一键丹药炼金$", priority=1, block=True, permission=SUPERUSER)
@lianjin.handle()
async def handle_lianjin(bot: Bot, event: Event, matcher: Matcher, args: Tuple[Optional[str], ...] = RegexGroup()):
    global flag
    flag = True
    await on_start(bot)
    await bot.send_group_msg(group_id=config["group_id"], message=MessageSegment.at(xx_id) + " 丹药背包")
    
    
async def on_start(bot: Bot):
    global self_id,nickname
    self_id = (await bot.get_login_info())["user_id"]
    group_member_info = await bot.get_group_member_info(group_id=config["group_id"], user_id=self_id)
    nickname = group_member_info.get("card") or group_member_info["nickname"]   # 机器人在该群的昵称
async def contains_at_me(bot: Bot, event: GroupMessageEvent) -> bool:
    global self_id,nickname
    if self_id is None or nickname is None:
        self_id = (await bot.get_login_info())["user_id"]
        group_member_info = await bot.get_group_member_info(group_id=config["group_id"], user_id=self_id)
        nickname = group_member_info.get("card") or group_member_info["nickname"]
    return (str(self_id) in str(event.message)  or f"@{nickname}" in str(event.message)) and str(event.group_id) in str(config["group_id"])

lianjin_rule =  Rule(contains_at_me)
lianjin_matcher = on_message(rule=lianjin_rule, block=False)
@lianjin_matcher.handle()
async def get_mijing_minute(bot: Bot, event: GroupMessageEvent):
    global flag
    if not flag: 
        return
    item_pattern = re.compile(r"名字：([^.\n]+)\s*物品功效拥有数量:(\d+)")
    message_text = str(event.message)  

    # 背包中的丹药
    items = item_pattern.findall(message_text)
    if not items:
        return
    danyao_data = load_lianjin()
    alchemy_list = danyao_data.get("炼金", [])
    found_danyao = []
    for item in items:
        name, quantity = item
        logger.warning(f"{name} (数量:{quantity})")
        if name in alchemy_list:
            found_danyao.append(f"{name} {quantity}")
    if found_danyao:     
            for info in found_danyao:
                await bot.send_group_msg(group_id=config["group_id"], message=MessageSegment.at(xx_id)+f" 炼金{info}")
                await asyncio.sleep(3)      
    else:
        await bot.send_group_msg(group_id=config["group_id"],message="炼啥")
    flag = False

#  获取需要炼金的丹药
def load_lianjin():
    try:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)  
        else:
            return {}
    except Exception as e:
        print(f"获取失败: {e}")
        return {}
    
    



