import re
pattern = r"花费时间：(\d+(\.\d+)?)(?:\(原\d+(\.\d+)?\))?分钟"
xuanshang = "花费时间：2.5(原60.0)分钟"
match = re.search(pattern, xuanshang, re.DOTALL)
if match:
    xuanshang_minute = float(match.group(1))
    print(f"秘境{xuanshang_minute}分钟后完成"+match.group(3))