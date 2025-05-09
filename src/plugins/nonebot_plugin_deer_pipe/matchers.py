from .constants import PLUGIN_VERSION
from .database import (
    attend,
    attend_past,
    get_avatar,
    update_avatar,
    get_deer_map,
)
from .image import generate_calendar

from datetime import datetime
from nonebot import on_regex, logger
from nonebot.adapters import Event
from nonebot.matcher import Matcher
from nonebot.params import RegexGroup
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import (
    Alconna,
    AlconnaMatcher,
    Args,
    Match,
    on_alconna,
)
from nonebot_plugin_alconna.uniseg import At, UniMessage
from nonebot_plugin_userinfo import EventUserInfo, UserInfo
from typing import Tuple, Optional


enabled_groups = set()

switch_handler = on_regex(r'^鹿(开|关)(?:\s*(\d*))?$', block=True, permission=SUPERUSER)
@switch_handler.handle()
async def _(matcher: Matcher, event: Event, regex_group: Tuple[str, ...] = RegexGroup()) -> None:
    global enabled_groups
    action = regex_group[0]
    group_id = regex_group[1] if len(regex_group) > 1 else None
    
    current_group_id = getattr(event, 'group_id', None)
    
    # 关闭
    if action == "关":
        if group_id:
            target_group_str = str(group_id)
            if target_group_str in enabled_groups:
                enabled_groups.remove(target_group_str)
                await UniMessage.text(f"群{target_group_str}鹿关").finish(reply_to=True)
            else:
                await UniMessage.text(f"群{target_group_str}未鹿").finish(reply_to=True)
        else:
            # 没有指定群号则关闭所有群
            enabled_groups.clear()
            await UniMessage.text("🦌关").finish(reply_to=True)
        return
    
    # 开启
    target_group = group_id or current_group_id
    if not target_group:
        await UniMessage.text("请在群聊中使用或指定群号").finish(reply_to=True)
        return
    
    target_group_str = str(target_group)
    enabled_groups.add(target_group_str)
    
    if group_id:
        await UniMessage.text(f"在群{target_group_str}开🦌").finish(reply_to=True)
    else:
        await UniMessage.text(f"开🦌").finish(reply_to=True)


# Matchers
deer: AlconnaMatcher = on_alconna(Alconna("🦌", Args["target?", At]), aliases={"鹿"})
deer_past: AlconnaMatcher = on_alconna(
    Alconna("补🦌", Args["day", int]), aliases={"补鹿"}
)
deer_calendar: AlconnaMatcher = on_alconna(
    Alconna("🦌历", Args["target?", At]), aliases={"鹿历"}
)
deer_help: AlconnaMatcher = on_alconna(Alconna("🦌帮助"), aliases={"鹿帮助"})


# 辅助函数：获取当前群ID
def get_current_group_id(event: Event) -> Optional[str]:
    return str(getattr(event, 'group_id', None)) if hasattr(event, 'group_id') else None


# Handlers
@deer.handle()
async def _(event: Event, target: Match[At], user_info: UserInfo = EventUserInfo()) -> None:
    group_id = get_current_group_id(event)
    if group_id and group_id not in enabled_groups:
        return

    now: datetime = datetime.now()

    if target.available:
        user_id: str = target.result.target
        avatar: bytes | None = await get_avatar(user_id)
    else:
        user_id: str = user_info.user_id
        avatar: bytes | None = (
            await user_info.user_avatar.get_image()
            if user_info.user_avatar is not None
            else None
        )
        await update_avatar(user_id, avatar)

    deer_map: dict[int, int] = await attend(user_id, now)
    img: bytes = generate_calendar(now, deer_map, avatar)

    if target.available:
        await (
            UniMessage.text("成功帮")
            .at(user_id)
            .text("🦌了")
            .image(raw=img)
            .finish(reply_to=True)
        )
    else:
        await UniMessage.text("成功🦌了").image(raw=img).finish(reply_to=True)


@deer_past.handle()
async def _(event: Event, day: Match[int], user_info: UserInfo = EventUserInfo()) -> None:
    group_id = get_current_group_id(event)
    if group_id and group_id not in enabled_groups:
        return

    now: datetime = datetime.now()
    user_id = user_info.user_id
    avatar: bytes | None = (
        await user_info.user_avatar.get_image()
        if user_info.user_avatar is not None
        else None
    )
    await update_avatar(user_id, avatar)

    if day.result < 1 or day.result >= now.day:
        await UniMessage.text("不是合法的补🦌日期捏").finish(reply_to=True)

    ok, deer_map = await attend_past(user_id, now, day.result)
    img: bytes = generate_calendar(now, deer_map, avatar)

    if ok:
        await UniMessage.text("成功补🦌").image(raw=img).finish(reply_to=True)
    else:
        await (
            UniMessage.text("不能补🦌已经🦌过的日子捏")
            .image(raw=img)
            .finish(reply_to=True)
        )


@deer_calendar.handle()
async def _(event: Event, target: Match[At], user_info: UserInfo = EventUserInfo()) -> None:
    group_id = get_current_group_id(event)
    if group_id and group_id not in enabled_groups:
        return

    now: datetime = datetime.now()

    if target.available:
        user_id: str = target.result.target
        avatar: bytes | None = await get_avatar(user_id)
    else:
        user_id: str = user_info.user_id
        avatar: bytes | None = (
            await user_info.user_avatar.get_image()
            if user_info.user_avatar is not None
            else None
        )
        await update_avatar(user_id, avatar)

    deer_map: dict[int, int] = await get_deer_map(user_id, now)
    img: bytes = generate_calendar(now, deer_map, avatar)

    await UniMessage.image(raw=img).finish(reply_to=True)


# @deer_top.handle()
# async def _() -> None:
#     pass


@deer_help.handle()
async def _(event: Event) -> None:
    group_id = get_current_group_id(event)
    if group_id and group_id not in enabled_groups:
        return

    status_text = "启用" if group_id in enabled_groups else "禁用"

    await (
        UniMessage.text(f"== 🦌管插件 v{PLUGIN_VERSION} 帮助 ==\n")
        .text(f"[签到状态] 当前签到功能已{status_text}\n\n")
        .text("[🦌] 🦌管1次\n")
        .text("[🦌 @xxx] 帮xxx🦌管1次\n")
        .text("[补🦌 x] 补🦌本月x日\n")
        .text("[🦌历] 看本月🦌日历\n")
        .text("[🦌历 @xxx] 看xxx的本月🦌日历\n")
        # .text("[🦌榜] 看本月🦌排行榜\n")
        .text("[🦌帮助] 打开帮助\n\n")
        .text("* 以上命令中的“🦌”均可换成“鹿”字\n\n")
        .text("== 插件代码仓库 ==\n")
        .text("https://github.com/SamuNatsu/nonebot-plugin-deer-pipe")
        .finish(reply_to=True)
    )