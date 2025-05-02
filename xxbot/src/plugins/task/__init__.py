import json
import re
import asyncio
from nonebot.matcher import Matcher
from pathlib import Path
from nonebot import on_regex, require, get_bot
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.params import RegexGroup
from typing import Optional, Tuple

try:
    scheduler = require("nonebot_plugin_apscheduler").scheduler
except Exception:
    scheduler = None

config_path = Path("config/config.json")
config_path.parent.mkdir(parents=True, exist_ok=True)

if config_path.exists():
    with open(config_path, "r", encoding="utf-8-sig") as f:
        CONFIG = json.load(f)
target_user_id = str(CONFIG.get("target_user_id", "3889001741"))
name = CONFIG.get("name", " ")

command_pattern = rf"^{re.escape(name)}?(?:添加任务([12])\s+(.+)\s+(\d+)|清除任务([12]?))$"

trun_on_listen = on_regex(command_pattern, priority=1, block=True)

async def send_task(group_id: int, message: str, task_type: int):
    bot = get_bot()
    if task_type == 1:
        message = MessageSegment.at(target_user_id) + message
    await bot.send_group_msg(group_id=group_id, message=message)

@trun_on_listen.handle()
async def handle_command(
    bot: Bot,
    event: GroupMessageEvent,
    matcher: Matcher,
    args: Tuple[Optional[str], ...] = RegexGroup(),
):
    # 权限验证
    if str(event.user_id) not in bot.config.superusers:
        await bot.send(event, "你想干啥", at_sender=True)
        return

    if args[0]:  # 添加任务
        task_id = args[0]
        message = args[1]
        interval_str = args[2]
        action = '添加'
    else:  # 清除任务
        action = '清除'
        task_id = args[3] if args[3] else None  # 空表示清除所有任务

    if action == '添加':
        try:
            task_id = int(task_id)
            interval = int(interval_str)
        except ValueError:
            await bot.send(event, "参数格式错误：任务号和间隔必须为数字")
            return

        if interval <= 0:
            await bot.send(event, "间隔必须大于0秒")
            return

        job_id = f"task_{task_id}"
        existing_job = scheduler.get_job(job_id)
        if existing_job:
            existing_job.remove()

        new_job = scheduler.add_job(
            send_task,
            'interval',
            seconds=interval,
            args=(event.group_id, message, task_id),
            id=job_id,
            replace_existing=True,
        )

        if new_job:
            await bot.send(event, f"任务{task_id}已添加")
        else:
            await bot.send(event, "添加任务失败，请检查参数")

    elif action == '清除':
        if task_id is None or task_id == "":  # 清除所有任务
            for job in scheduler.get_jobs():
                if job.id.startswith("task_"):
                    job.remove()
            await bot.send(event, "所有任务已清除")
        else:
            try:
                task_id = int(task_id)
                if task_id not in [1,2]:
                    await bot.send(event, "任务编号必须为1或2")
                    return
            except ValueError:
                await bot.send(event, "任务编号必须为数字1或2")
                return

            job_id = f"task_{task_id}"
            existing_job = scheduler.get_job(job_id)
            if existing_job:
                existing_job.remove()
                await bot.send(event, f"任务{task_id}已清除")
            else:
                await bot.send(event, f"任务{task_id}不存在或未运行")
    else:
        await bot.send(event, "无效的命令类型，只能是添加或清除")