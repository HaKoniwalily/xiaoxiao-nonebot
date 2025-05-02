import json
import re
import asyncio
import os
from configparser import ConfigParser
from pathlib import Path
from nonebot.rule import Rule
from nonebot.log import logger
from nonebot import on_regex, on_message
from nonebot.permission import SUPERUSER
from nonebot.params import RegexGroup
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, MessageSegment
from nonebot.matcher import Matcher
from typing import Optional, Tuple, Dict, Any

# 配置文件路径
config_path = Path("config/lianjin.json")
group_path = Path("config/config.json")
with open(group_path, "r", encoding="utf-8-sig") as f:
   CONFIG: Dict[str, bool] = json.load(f)
config_path.parent.mkdir(parents=True, exist_ok=True)
bot_root_parent_dir = Path(os.path.abspath(os.path.join(os.getcwd(), "..")))
pill_path = bot_root_parent_dir / "pill.ini" 
fangshi_path = bot_root_parent_dir / "fangshi.ini" 

# 启用炼丹辅助的群号
allowed_group_ids = CONFIG.get("炼丹与行情辅助")

# 加载炼金数据
def load_lianjin_data() -> Dict[str, int]:
    """加载炼金价格数据"""
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {}

def save_lianjin_data(data: Dict[str, int]):
    """保存炼金价格数据"""
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 加载丹方数据
def load_pill_recipes() -> Dict[str, list]:
    """加载丹方"""
    config = ConfigParser(allow_no_value=True)
    if pill_path.exists():
        config.read(pill_path, encoding="utf-8-sig")
        recipes = {}
        for section in config.sections():
            recipes[section] = list(config.options(section))
        return recipes
    else:
        logger.warning(f"{pill_path}丹方不存在")
        return {}

# 加载坊市价格数据
def load_fangshi_data():
    """加载坊市价格数据"""
    fangshi_data = {}
    if fangshi_path.exists():
        with open(fangshi_path, "r", encoding="utf-8-sig") as f:
            for line in f.readlines():
                if '=' in line:
                    material, prices = line.strip().split('=')
                    price_list = prices.split('/')
                    fangshi_data[material] = int(price_list[0])  # 取第一个价格
    return fangshi_data

def load_page_data() -> Dict[str, int]:
    """加载药材页数数据"""
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            page_mapping = {}
            for key, materials in data.items():
                if key.isdigit():
                    page_num = int(key)
                    for material in materials:
                        page_mapping[material] = page_num
            return page_mapping
    return {}

# 计算丹药推荐上架价格与税收
def shangjia_price(pill_name):
    # 初始化默认值和存储字典
    danyao_price = 0
    fangshi_dict = {}
    
    # 读取配置文件
    if fangshi_path.exists():
        with open(fangshi_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    material, prices = line.split('=', 1)
                    fangshi_dict[material] = list(map(int, prices.split('/')))
    
    # 处理指定丹药
    if pill_name in fangshi_dict:
        prices = fangshi_dict[pill_name][:4]  # 取前四个价格
        
        # 筛选有效价格
        valid_prices = []
        for i in range(1, len(prices)):
            if prices[i] < prices[i-1]:
                valid_prices.append(prices[i])
        
        # 确定最终价格
        if not valid_prices:
            chosen_price = prices[0]
        else:
            average = sum(prices)/len(prices)
            price_diffs = [(p, abs(p - average)) for p in valid_prices]
            min_diff = min(diff for _, diff in price_diffs)
            candidates = [p for p, diff in price_diffs if diff == min_diff]
            chosen_price = min(candidates)
        
        danyao_price = chosen_price
    
    # 计算税收
    tax_rate = 0.30
    if danyao_price <= 5000000:
        tax_rate = 0.05
    elif danyao_price <= 10000000:
        tax_rate = 0.10
    elif danyao_price <= 15000000:
        tax_rate = 0.15
    elif danyao_price <= 20000000:
        tax_rate = 0.20
        
    tax = int(danyao_price * tax_rate)
    
    return (danyao_price, danyao_price-tax)

def calculate_cost(recipe: str, lianjin_data: Dict[str, int], fangshi_data: Dict[str, int], page_data: Dict[str, int]) -> Tuple[int, int, Dict[str, int]]:
    """计算配方的炼金成本和坊市成本，并返回药材页数"""
    total_cost = 0
    fangshi_cost = 0
    parts = ["主药", "药引", "辅药"]
    material_pages = {}
    
    for part in parts:
        part_pattern = rf"{part}(\S+?)(\d+)"
        materials = re.findall(part_pattern, recipe)
        
        for material, quantity in materials:
            quantity = int(quantity)
            
            # 计算炼金成本
            material_price = lianjin_data.get(material)
            total_cost += material_price * quantity if material_price else 0
            
            # 计算坊市成本
            fangshi_price = fangshi_data.get(material, 0)       
            fangshi_cost += fangshi_price * quantity
            
            # 记录药材页数
            material_pages[material] = page_data.get(material)

    return total_cost, fangshi_cost, material_pages

# 查丹方功能
async def at_me(bot: Bot, event: GroupMessageEvent) -> bool:
    """判断群"""
    message = str(event.message)
    self_id = str((await bot.get_login_info())["user_id"])
    return "查丹方" in message and (self_id in str(event) or event.group_id in allowed_group_ids)

query_rule = Rule(at_me)
query = on_message(rule=query_rule, block=False)

@query.handle()
async def handle_lianjin(bot: Bot, event: Event, matcher: Matcher):
    """处理查丹方请求"""
    message = str(event.message)
    matched = re.search(r"^查丹方\s*(.*?)\s*$", message)
    if matched:
        pill_name = matched.group(1).strip()
        lianjin_data = load_lianjin_data()
        fangshi_data = load_fangshi_data()
        page_data = load_page_data()  # 加载页数数据
        pill_recipes = load_pill_recipes()

        if pill_name not in pill_recipes:
            await query.finish(f"未找到{pill_name}的配方!")

        recipes = pill_recipes[pill_name]
        recipe_prices = []

        for recipe in recipes:
            total_cost, fangshi_cost, material_pages = calculate_cost(recipe, lianjin_data, fangshi_data, page_data)
            recipe_prices.append((recipe, fangshi_cost, total_cost, material_pages))

        # 按坊市价格排序，选择最低的2个
        recipe_prices.sort(key=lambda x: x[1])
        top_2_recipes = recipe_prices[:2]
        pill_price = fangshi_data.get(pill_name, 0)
        pill_cost = lianjin_data.get(pill_name, 0)
        
        results = []
        price, aftertax_price = shangjia_price(pill_name)
        
        # 添加丹药价格信息
        results.append(
            f"推荐上架价格:{int(price/10000)}w\n"
            f"丹药坊市价:{int(pill_price/10000)}*6={int(pill_price*6/10000)}w\n"
            f"丹药炼金价:{pill_cost}*6={pill_cost*6}w\n"
        )

        # 处理每个配方
        for recipe, fangshi_cost, total_cost, material_pages in top_2_recipes:
            # 构建页数信息
            pages_info = " ".join([f"({page})" for mat, page in material_pages.items()])
            
            results.extend([
                f"配方{recipe}丹炉寒铁铸心炉",
                f"药材炼金价:{total_cost}w",
                f"药材坊市价:{int(fangshi_cost/10000)}w",
                f"药材页数:{pages_info}",
                f"炼金收益(6丹):{int(pill_cost*6-fangshi_cost/10000)}w",
                f"上架收益:{int((aftertax_price*6-fangshi_cost)/10000)}w\n"
            ])

        await query.finish("\n".join(results))

# 保存丹方功能
async def liandan(bot: Bot, event: GroupMessageEvent) -> bool:
    """判断是否保存丹方"""
    return "配方" in str(event.message) and "菜单" not in str(event.message) and str(event.user_id) == "3889001741"

liandan_rule = Rule(liandan)
liandan_matcher = on_message(rule=liandan_rule, block=False)

@liandan_matcher.handle()
async def liandan(event: GroupMessageEvent):
    """保存丹方并计算成本"""
    liandan_msg = str(event.message)
    name_match = re.search(r"名字：(.*?)\n", liandan_msg)
    pill_name = name_match.group(1) if name_match else "未知"
    recipe_match = re.search(r"配方：(.*?)丹炉", liandan_msg)
    recipe = recipe_match.group(1).strip() if recipe_match else "未知"

    # 加载数据
    lianjin_data = load_lianjin_data()
    fangshi_data = load_fangshi_data()
    page_data = load_page_data()

    # 计算成本
    total_cost, fangshi_cost, material_pages = calculate_cost(recipe, lianjin_data, fangshi_data, page_data)
    pill_price = fangshi_data.get(pill_name)
    pill_cost = lianjin_data.get(pill_name)

    # 返回结果
    price, aftertax_price = shangjia_price(pill_name)
    if event.group_id in allowed_group_ids:
        await query.send(f"配方{recipe}丹炉寒铁铸心炉")
        result = f"丹药坊市价:{int(pill_price/10000)}*6={int(pill_price*6/10000)}w\n"
        result += f"丹药炼金价:{pill_cost}*6={pill_cost*6}w\n"
        result += f"药材炼金价:{total_cost}w\n"
        result += f"药材坊市价:{int(fangshi_cost/10000)}w\n"
        result += f"炼金收益(6丹):{int(pill_cost*6-fangshi_cost/10000)}w\n"
        result += f"{int(price/10000)}w上架总收益:{int((aftertax_price*6-fangshi_cost)/10000)}w"
        await query.finish(result)

# 编辑炼金价格功能
lianjin = on_regex(r"^(添加|删除)炼金\s*(.+?)\s*(\d+)?$", priority=1, block=True, permission=SUPERUSER)

@lianjin.handle()
async def handle_lianjin(bot: Bot, event: Event, matcher: Matcher, args: Tuple[Optional[str], ...] = RegexGroup()):
    """编辑炼金价格"""
    action = args[0]
    lianjin_content = args[1].strip()
    price = args[2]
    lianjin_data = load_lianjin_data()

    if action == "添加" and price:
        lianjin_data[lianjin_content] = int(price)
        save_lianjin_data(lianjin_data)
        await matcher.send(f"{lianjin_content}已更新为:{price}")
    elif action == "添加":
        await matcher.send("请提供炼金值(单位w)")
    elif action == "删除":
        if lianjin_content in lianjin_data:
            del lianjin_data[lianjin_content]
            save_lianjin_data(lianjin_data)
            await matcher.send(f"成功删除 {lianjin_content}")
        else:
            await matcher.send(f"没有找到 {lianjin_content}")
