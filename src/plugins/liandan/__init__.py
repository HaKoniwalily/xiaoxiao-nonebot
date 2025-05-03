import json
from pathlib import Path
import re
import os
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
path = Path("config/liandan.json")

try:
    with open(path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
except FileNotFoundError:
    print("找不到文件")
except json.JSONDecodeError:
    print("数据解析错误")

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
            # 分离丹药和药材数据
            medicines = {k: v for k, v in data.items() if "el_co" in v}
            herbs = {k: v for k, v in data.items() if "el_co" not in v}
            current_herb_bag = herb_bag.copy()
            all_potion_recipes = {}

            # 遍历丹药计算配方
            for potion_id, potion_info in medicines.items():
                potion_name = potion_info['name']
                all_potion_recipes[potion_name] = []
                while True:
                    main_herbs = select_main_herbs(potion_id, data, herbs, current_herb_bag)
                    if not main_herbs:
                        break
                    possible = False
                    for main_herb in main_herbs:
                        guiding_herbs = select_guiding_herbs(main_herb, data, herbs, current_herb_bag)
                        if guiding_herbs:
                            secondary_herbs = select_secondary_herbs(potion_id, data, herbs, current_herb_bag)
                            if secondary_herbs:
                                for guiding_herb in guiding_herbs:
                                    for secondary_herb in secondary_herbs:
                                        recipe_herbs = [main_herb, guiding_herb, secondary_herb]
                                        if can_use_recipe(recipe_herbs, current_herb_bag):
                                            possible = True
                                            recipes = calculate_recipes([main_herb], [guiding_herb], [secondary_herb])
                                            for recipe in recipes:
                                                # 计算炼丹收益
                                                herb_cost = 0
                                                for herb in recipe_herbs:
                                                    name = ''.join(filter(str.isalpha, herb))
                                                    num = int(''.join(filter(str.isdigit, herb)))
                                                    herb_price = fangshi_data.get(name)
                                                    if herb_price is None:
                                                        logger.warning(f"未找到药材 {name} 的价格将其价格视为 0")
                                                        herb_price = 0
                                                    herb_tax = calculate_tax(herb_price)
                                                    herb_cost += herb_price - herb_tax

                                                danyao_price = fangshi_data.get(potion_name)
                                                if danyao_price is None:
                                                    logger.warning(f"未找到丹药 {potion_name} 的价格将其价格视为 0")
                                                    danyao_price = 0
                                                danyao_tax = calculate_tax(danyao_price)
                                                profit = (danyao_price - danyao_tax) * 6 - herb_cost

                                                all_potion_recipes[potion_name].append((recipe, profit))

                                                # 更新背包
                                                update_herb_bag([main_herb], [guiding_herb], [secondary_herb], current_herb_bag)

                    if not possible:
                        break

            msg = ""
            for potion_name, recipes in all_potion_recipes.items():
                if recipes:
                    msg += f'\n{potion_name}:\n'
                    for recipe, profit in recipes:
                        msg += f'{recipe}\n理想收益:{profit / 10000}w\n'
                    msg += "-" * 31 + "\n"
            if msg:
                await bot.send_group_msg(group_id=group_id, message=MessageSegment.at(target_user_id) + msg)
            else:
                await bot.send_group_msg(group_id=group_id, message=MessageSegment.at(target_user_id) + " 无药可炼")

        # 清除用户：最后一页处理完毕后删除记录
        user_medicine_info.pop(current_nickname, None)
        alchemy_users.pop((group_id, current_nickname), None)

# 选择主药、辅药、药引等
def select_main_herbs(potion_id, data, herbs, herb_bag):
    lx = []
    el_co = data[potion_id]['el_co']
    ssd = list(el_co.items())
    for herb_id, herb_info in herbs.items():
        if int(ssd[0][0]) == herb_info['主药']['ty']:
            n2 = herb_info['主药']['po']
            n1 = n2 / int(ssd[0][1])
            if n1 <= 1.5:
                num = int(ssd[0][1]) // n2
                if int(ssd[0][1]) % n2 != 0:
                    num += 1
                if num <= 20 and herb_info['name'] in herb_bag and herb_bag[herb_info['name']] >= num:
                    lx.append(f"{herb_info['name']}{num}")
    return lx

def select_secondary_herbs(potion_id, data, herbs, herb_bag):
    lx = []
    el_co = data[potion_id]['el_co']
    ssd = list(el_co.items())
    for herb_id, herb_info in herbs.items():
        if int(ssd[1][0]) == herb_info['辅药']['ty']:
            n2 = herb_info['辅药']['po']
            n1 = n2 / int(ssd[1][1])
            if n1 <= 1.5:
                num = int(ssd[1][1]) // n2
                if int(ssd[1][1]) % n2 != 0:
                    num += 1
                if num <= 20 and herb_info['name'] in herb_bag and herb_bag[herb_info['name']] >= num:
                    lx.append(f"{herb_info['name']}{num}")
    return lx

def select_guiding_herbs(main_herb, data, herbs, herb_bag):
    lk = [s for s in main_herb if s.isdigit()]
    lx = []
    main_herb_name = main_herb[:-len(''.join(lk))]
    for herb_id, herb_info in herbs.items():
        if herb_info['name'] == main_herb_name:
            ss = herb_info['主药']['hh']
            ping = ss['ty'] * ss['po'] * int(''.join(lk))
            for sub_herb_id, sub_herb_info in herbs.items():
                ss1 = sub_herb_info["药引"]['hh']
                ping0 = ss1['ty'] * ss1['po']
                if ping != 0 and ping0 != 0 and ping * ping0 < 0 and abs(ping) % abs(ping0) == 0:
                    num = abs(ping) // abs(ping0)
                    if 1 <= num <= 20 and sub_herb_info['name'] in herb_bag and herb_bag[sub_herb_info['name']] >= num:
                        lx.append(f"{sub_herb_info['name']}{num}")
                elif ping == 0 and ping0 == 0:
                    if sub_herb_info['name'] in herb_bag and herb_bag[sub_herb_info['name']] >= 1:
                        lx.append(f"{sub_herb_info['name']}1")
    return lx

def calculate_recipes(main_herbs, guiding_herbs, secondary_herbs):
    result = []
    for a0 in main_herbs:
        for b0 in guiding_herbs:
            for c0 in secondary_herbs:
                price1 = f"配方主药{a0}药引{b0}"
                price2 = f"辅药{c0}丹炉寒铁铸心炉"
                priceText = f"{price1}{price2}"
                result.append(priceText)
    return result

def update_herb_bag(main_herbs, guiding_herbs, secondary_herbs, herb_bag):
    for herb in main_herbs:
        name = ''.join(filter(str.isalpha, herb))
        num = int(''.join(filter(str.isdigit, herb)))
        herb_bag[name] -= num
        if herb_bag[name] == 0:
            del herb_bag[name]
    for herb in guiding_herbs:
        name = ''.join(filter(str.isalpha, herb))
        num = int(''.join(filter(str.isdigit, herb)))
        herb_bag[name] -= num
        if herb_bag[name] == 0:
            del herb_bag[name]
    for herb in secondary_herbs:
        name = ''.join(filter(str.isalpha, herb))
        num = int(''.join(filter(str.isdigit, herb)))
        herb_bag[name] -= num
        if herb_bag[name] == 0:
            del herb_bag[name]

def can_use_recipe(recipe_herbs, herb_bag):
    temp_bag = herb_bag.copy()
    for herb in recipe_herbs:
        name = ''.join(filter(str.isalpha, herb))
        num = int(''.join(filter(str.isdigit, herb)))
        if name not in temp_bag or temp_bag[name] < num:
            return False
        temp_bag[name] -= num
    return True
    