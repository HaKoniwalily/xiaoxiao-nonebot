async def at_me(bot: Bot, event: GroupMessageEvent) -> bool:
    self_id = str((await bot.get_login_info())["user_id"])
    return self_id in str(event)