import os
import random
import json
from datetime import datetime, timedelta
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot.rule import Rule
from nonebot.params import RegexGroup
from nonebot import on_message, on_regex
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, MessageSegment

# 存储签到信息
SIGN_IN_FILE = "sign_in_data.json"
OWNER_ID = 2396276021

# 功能开启标志
reply_enabled = False

# 上次触发时间
last_reply_time = {}

if not os.path.exists(SIGN_IN_FILE):
    with open(SIGN_IN_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False, indent=4)

# 加载签到数据
def load_sign_in_data():
    with open(SIGN_IN_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# 保存签到数据
def save_sign_in_data(data):
    with open(SIGN_IN_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 清理过期记录
def clean_expired_reply_time():
    global last_reply_time
    current_time = datetime.now()
    # 保留未过期的记录
    last_reply_time = {user_id: timestamp for user_id, timestamp in last_reply_time.items()
                       if current_time - timestamp < timedelta(minutes=1)}

switch_handler = on_regex(r'^(开启|关闭)签到$', block=True, permission=SUPERUSER)

@switch_handler.handle()
async def handle_switch(bot: Bot, event: GroupMessageEvent, groups=RegexGroup()):
    global reply_enabled
    cmd = groups[0].strip()
    
    if cmd == "开启":
        reply_enabled = True
        msg = "回复开启"
    else:
        reply_enabled = False
        msg = "回复关闭"
    
    await bot.send(event, message=msg, reply_message=True)

async def is_qd(bot: Bot, event: GroupMessageEvent) -> bool:
    return event.group_id == 824852529

rule = Rule(is_qd)

qd = on_message(rule=rule, priority=5, block=True)

@qd.handle()
async def reply(bot: Bot, event: GroupMessageEvent):
    global reply_enabled, last_reply_time

    clean_expired_reply_time()

    # 获取用户 ID 和当前时间
    user_id = event.sender.user_id
    current_time = datetime.now()

    # 检查功能是否开启
    if not reply_enabled:
        return

    # 检查用户是否刷屏
    if user_id in last_reply_time:
        time_diff = current_time - last_reply_time[user_id]
        if time_diff < timedelta(minutes=1):
            #await bot.send(event, message=MessageSegment.at(user_id) + " 别刷屏了", reply_message=True)
            return

    # 更新最后触发时间
    last_reply_time[user_id] = current_time

    if isinstance(event, GroupMessageEvent):
     # 获取发送的消息
            message = event.get_message()
            plain_text = message.extract_plain_text()

            if plain_text.startswith("/签到") or plain_text.startswith("/抽奖"):
                sign_in_data = load_sign_in_data()
                current_date = datetime.now().strftime("%Y-%m-%d")

                # 检查该用户是否已经签到
                if str(user_id) in sign_in_data and sign_in_data[str(user_id)]["date"] == current_date:
                    reward = sign_in_data[str(user_id)]["reward"]
                    reply_message = MessageSegment.at(user_id) + f" 你今天已经抽过了，你抽的东西是：{reward}。"
                    await bot.send(event, message=reply_message, reply_message=True)
                else:
                    # 生成幸运数字
                    lucky_number = random.randint(0, 99)

                    # 生成奖励
                    if lucky_number > 5:
                        reward_message = "你抽到了海洋之心，奖励已发放至邮箱"
                        reward = "海洋之心"
                    else:
                        reward_message = "你抽到了潜影盒，奖励已发放至邮箱"
                        reward = "潜影盒"

                    member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=user_id)
                    nickname = member_info['card'] or member_info['nickname']
                    reply_message = MessageSegment.at(user_id) + f" 恭喜你{nickname}，{reward_message}。你的幸运数字是{lucky_number}。"
                    sign_in_data[str(user_id)] = {"date": current_date, "reward": reward}
                    save_sign_in_data(sign_in_data)
                    await bot.send(event, message=reply_message, reply_message=True)   
            
