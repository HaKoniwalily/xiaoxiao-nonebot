import json
from pathlib import Path
import re
import os
from configparser import ConfigParser
from typing import Dict
from nonebot.log import logger
from nonebot import on_regex, on_message
from nonebot.permission import SUPERUSER
from nonebot.params import RegexGroup
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment, GroupMessageEvent

xx_id = "3889001741"
id_path = Path("config/config.json")

if id_path.exists():
    with open(id_path, "r", encoding="utf-8-sig") as f:
        config: Dict[str, object] = json.load(f)
# 启用群
allowed_group_ids = config.get("炼丹与行情辅助")
bot_root_parent_dir = Path(os.path.abspath(os.path.join(os.getcwd(), "..")))
fangshi_path = bot_root_parent_dir / "fangshi.ini"
pill_path = bot_root_parent_dir / "pill.ini"

# 丹方
CACHED_PILL_RECIPES: Dict[str, list] = {}
# 加载丹方数据
def load_pill_recipes() -> Dict[str, list]:
    """加载丹方"""
    global CACHED_PILL_RECIPES
    if not CACHED_PILL_RECIPES and pill_path.exists():
        config = ConfigParser(allow_no_value=True)
        config.read(pill_path, encoding="utf-8-sig")
        CACHED_PILL_RECIPES = {section: list(config.options(section)) for section in config.sections()}
    return CACHED_PILL_RECIPES

# 炼丹用户信息
alchemy_users = {}

def load_fangshi_data():
    """加载坊市价格数据"""
    fangshi_data = {}
    if fangshi_path.exists():
        with open(fangshi_path, "r", encoding="utf-8-sig") as f:
            for line in f.readlines():
                if '=' in line:
                    material, prices = line.strip().split('=')
                    first_price_date = prices.split('/')[0]
                    try:
                        price = int(first_price_date.split('_')[0])  # 提取价格部分
                        fangshi_data[material] = price
                    except (IndexError, ValueError):
                        logger.warning(f"解析价格数据失败: {first_price_date}")
    return fangshi_data

# 计算税收
def calculate_tax(price):
    tax_rate = 0.30
    if price <= 5000000:
        tax_rate = 0.05
    elif price <= 10000000:
        tax_rate = 0.10
    elif price <= 15000000:
        tax_rate = 0.15
    elif price <= 20000000:
        tax_rate = 0.20
    return int(price * tax_rate)

# 炼丹指令
liandan = on_regex(r"^炼丹$", priority=5, block=True)

@liandan.handle()
async def handle_liandan(bot: Bot, event: GroupMessageEvent):
    if event.group_id in allowed_group_ids:
        group_id = event.group_id
        group_member_info = await bot.get_group_member_info(group_id=group_id, user_id=event.user_id)
        nickname = group_member_info.get("card") or group_member_info["nickname"]
        alchemy_users[(group_id, nickname)] = event.user_id
        await bot.send_group_msg(
            group_id=group_id,
            message=MessageSegment.at(event.user_id) + " 请打开你的药材背包"
        )

# 处理药材背包
def is_bag(event: Event) -> bool:
    return event.get_user_id() == xx_id and "药材" in event.get_plaintext() and event.group_id in allowed_group_ids

liandan_matcher = on_message(rule=is_bag, priority=5, block=True)

# 每个用户的药材信息
user_medicine_info = {}

@liandan_matcher.handle()
async def yaocai(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    message = event.get_plaintext()

    # 正在处理的用户
    target_user_id = None
    for (g_id, nickname), user_id in alchemy_users.items():
        if g_id == group_id and nickname in message:
            target_user_id = user_id
            current_nickname = nickname
            break
    if not target_user_id:
        return

    pattern = r"名字：([^.\n]+)\s*拥有数量:\s*(\d+)"
    matches = re.findall(pattern, message)

    if matches:
        if current_nickname not in user_medicine_info:
            user_medicine_info[current_nickname] = {}
        for medicine_name, count in matches:
            # 累加药材数量
            if medicine_name in user_medicine_info[current_nickname]:
                user_medicine_info[current_nickname][medicine_name] += int(count)
            else:
                user_medicine_info[current_nickname][medicine_name] = int(count)

    if "下一页" in message:
        pass
    else:
        fangshi_data = load_fangshi_data()
        herb_bag = user_medicine_info.get(current_nickname, {})

        # 打印背包药材信息
        print(f"{current_nickname} 的背包药材:")
        for name, count in herb_bag.items():
            print(f"{name}: {count}")

        if herb_bag:
            all_potion_recipes = {}
            pill_recipes = load_pill_recipes()
            shared_herb_bag = herb_bag.copy()  # 用于所有丹药匹配的共享背包

            # 遍历丹方
            for potion_name, recipes in pill_recipes.items():
                all_potion_recipes[potion_name] = []
                while True:
                    found_recipe = False
                    for recipe in recipes:
                        # 解析丹方中的药材和数量
                        recipe_herbs = re.findall(r'(主药|药引|辅药)([\u4e00-\u9fa5]+)(\d+)', recipe)
                        herb_usage = {}
                        can_use = True
                        for position, herb_name, herb_num in recipe_herbs:
                            herb_num = int(herb_num)
                            if herb_name not in shared_herb_bag or shared_herb_bag[herb_name] < herb_num:
                                can_use = False
                                break
                            if herb_name not in herb_usage:
                                herb_usage[herb_name] = herb_num
                            else:
                                herb_usage[herb_name] += herb_num
                            if herb_usage[herb_name] > shared_herb_bag[herb_name]:
                                can_use = False
                                break
                        if can_use:
                            found_recipe = True
                            # 计算炼丹收益
                            herb_cost = 0
                            for position, herb_name, herb_num in recipe_herbs:
                                herb_num = int(herb_num)
                                herb_price = fangshi_data.get(herb_name)
                                if herb_price is None:
                                    logger.warning(f"未找到药材 {herb_name} 的价格将其价格视为 0")
                                    herb_price = 0
                                herb_tax = calculate_tax(herb_price)
                                herb_cost += (herb_price - herb_tax) * herb_num

                            danyao_price = fangshi_data.get(potion_name)
                            if danyao_price is None:
                                logger.warning(f"未找到丹药 {potion_name} 的价格将其价格视为 0")
                                danyao_price = 0
                            danyao_tax = calculate_tax(danyao_price)
                            profit = (danyao_price - danyao_tax) * 6 - herb_cost

                            all_potion_recipes[potion_name].append((recipe, profit))

                            # 更新共享背包
                            for position, herb_name, herb_num in recipe_herbs:
                                herb_num = int(herb_num)
                                if herb_name in shared_herb_bag and shared_herb_bag[herb_name] >= herb_num:
                                    shared_herb_bag[herb_name] -= herb_num
                                    if shared_herb_bag[herb_name] == 0:
                                        del shared_herb_bag[herb_name]
                    if not found_recipe:
                        break

            msg = ""
            for potion_name, recipes in all_potion_recipes.items():
                if recipes:
                    msg += f'\n{potion_name}:\n'
                    for recipe, profit in recipes:
                        msg += f'配方{recipe}丹炉寒铁铸心炉\n理想收益:{profit / 10000}w\n'
                    msg += "-" * 31 + "\n"
            if msg:
                await bot.send_group_msg(group_id=group_id, message=MessageSegment.at(target_user_id) + msg)
            else:
                await bot.send_group_msg(group_id=group_id, message=MessageSegment.at(target_user_id) + " 无药可炼")

        # 清除用户：最后一页处理完毕后删除记录
        user_medicine_info.pop(current_nickname, None)
        alchemy_users.pop((group_id, current_nickname), None)
    