import json
import re
from nonebot.log import logger
from nonebot import on_regex, on_message, get_bot
from pathlib import Path
from nonebot.adapters.onebot.v11 import Message, MessageSegment, GroupMessageEvent, Bot
from nonebot_plugin_apscheduler import scheduler
from datetime import datetime, timedelta
from typing import Dict, Optional
from nonebot.rule import Rule

path = Path("config/config.json")
config_path = Path("config/lingtian.json")
path.parent.mkdir(parents=True, exist_ok=True)
xx_id = "3889001741"
harvest_message = MessageSegment.at(xx_id) + " 灵田收取"
if path.exists():
    with open(path, "r", encoding="utf-8-sig") as f:
        config: Dict[str, object] = json.load(f)

if config_path.exists():
    with open(config_path, "r", encoding="utf-8-sig") as f:
        CONFIG: Dict[str, bool] = json.load(f)
else:
    logger.warning("未找到灵田收取配置")

# 定时灵田收获
async def lingtian_job():
    bot: Bot = get_bot()
    try:
        await bot.send_group_msg(group_id=config.get("group_id"), message=harvest_message)
        logger.info("已成功发送灵田收取消息")
    except Exception as e:
        logger.warning(f"发送灵田收取信息失败：{e}")

# 保存收取时间
def save_harvest_time(harvest_time: datetime):
    data = {
        "harvest_time": harvest_time.strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(config_path, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.warning(f"收取时间已保存：{data['harvest_time']}")
    except Exception as e:
        logger.error(f"保存收取时间失败：{e}")

# 读取收取时间
def load_harvest_time() -> Optional[datetime]:
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            harvest_time_str = data.get("harvest_time")
            if harvest_time_str:
                return datetime.strptime(harvest_time_str, "%Y-%m-%d %H:%M:%S")
    return None

async def contains_at_me(bot: Bot, event: GroupMessageEvent) -> bool:
    self_id = (await bot.get_login_info())["user_id"]
    is_at_me = any(seg.type == "at" and seg.data["qq"] == str(self_id) for seg in event.message)
    allowed_qq = "3889001741"
    return is_at_me and str(event.user_id) == allowed_qq

lingtian_rule = Rule(contains_at_me)

lingtian_matcher = on_message(rule=lingtian_rule, block=False)
# 获取收获时间
@lingtian_matcher.handle()
async def get_lingtian_date(event: GroupMessageEvent):
    lingtian_date = str(event.message)
    pattern = r".*收取时间为：(\d+)\.(\d+)小时.*" 
    match = re.search(pattern, lingtian_date, re.DOTALL)
    if match:
        hours = int(match.group(1))
        minutes = float(match.group(2)) * 0.6
        total_minutes = hours * 60 + minutes
        harvest_time = datetime.now() + timedelta(minutes=total_minutes)
        save_harvest_time(harvest_time)
        if not scheduler.get_job("lingtian_job"):
            scheduler.add_job(lingtian_job, "date", run_date=harvest_time, id="lingtian_job")
            logger.warning(f"下次灵田收取时间为{harvest_time}")

finish_harvest = on_regex(r".*成功收获药材.*", block=True, rule=lingtian_rule)
@finish_harvest.handle()
async def handle_finish_harvest(bot: Bot):
    harvest_time = datetime.now() + timedelta(hours=47,minutes=1)
    save_harvest_time(harvest_time)
    if not scheduler.get_job("lingtian_job"):
        scheduler.add_job(lingtian_job, "date", run_date=harvest_time, id="lingtian_job")
        logger.warning(f"下次灵田收取时间为{harvest_time}")

    

