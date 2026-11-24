import json
import time
from DrissionPage import Chromium, ChromiumOptions

# 1. 读取同级目录下的答案文件
with open('titledown.json', 'r', encoding='utf-8') as f:
    answers = [s.strip() for s in json.load(f)['data'] if s.strip()]
print(f'共加载 {len(answers)} 条答案')


def match_answers(option_text: str):
    """返回该选项命中的所有答案（用于多选调试）"""
    t = option_text.strip()
    if not t:
        return []
    hits = []
    for ans in answers:
        if t == ans or ans in t or t in ans:
            hits.append(ans)
    return hits


def safe_click(ele, desc=''):
    try:
        ele.click()
        return True
    except Exception as e:
        print(f'  点击失败 [{desc}]: {e}')
        return False

while True:
    group = input("请输入组号（例如 1 表示 group1）：").strip()
    if group.isdigit() and int(group) > 0:
        break
    print("组号请输入大于 0 的整数。")

while True:
    ports = input("请输入端口号喵：").strip()
    if ports.isdigit() and 0 < int(ports) <= 65535:
        break
    print("端口号请输入 1 到 65535 之间的整数。")

group_name = f"group{group}"
user_data_path = rf"D:\aibot\{group_name}\{ports}\user-data\EBWebView"
print(f"连接浏览器：{user_data_path}（端口号：{ports}）")
options = (
    ChromiumOptions()
    .set_local_port(int(ports))
    .set_user_data_path(user_data_path)
    .existing_only()
)
browser = Chromium(options)
page = browser.latest_tab

cookies = page.cookies(all_domains=True, all_info=True)
print("当前浏览器 Cookie：")
print(json.dumps(cookies, ensure_ascii=False, indent=2))

max_rounds = 500
round_no = 0

while round_no < max_rounds:
    round_no += 1

    # 2. 判断题目是否还存在，不存在就停止
    title_ele = page.ele(
        'x://div[@class="question-item"]//div[@class="question-title"]',
        timeout=3
    )
    if not title_ele:
        print('没有更多题目了，脚本结束')
        break

    try:
        title = title_ele.text
    except Exception:
        title = ''
    print(f'\n[第 {round_no} 题] {title}')

    # 3. 收集当前题目的所有选项
    radios = page.eles('x://span[@class="el-radio__label"]', timeout=1)
    checks = page.eles('x://span[@class="el-checkbox__label"]', timeout=1)
    options = list(radios) + list(checks)
    print(f'  选项类型: 单选 {len(radios)} 项, 多选 {len(checks)} 项')

    if not options:
        print('  未找到任何选项，停止')
        break

    # 4. 遍历所有选项，命中的都点（天然支持一题多选）
    selected = []
    for idx, opt in enumerate(options):
        try:
            text = opt.text
        except Exception:
            continue

        hits = match_answers(text)
        if not hits:
            continue

        print(f'  选项[{idx}] "{text}"  <-- 命中 {hits}')
        if safe_click(opt, text):
            selected.append(text)
        time.sleep(0.15)   # 多选之间留点间隔，避免勾选被吞

    print(f'  本题共选择 {len(selected)} 项: {selected}')

    if not selected:
        print('  ⚠ 本题没匹配到任何答案，建议人工介入。')
        # 若想没答案就停止，取消下一行注释
        # break

    time.sleep(0.3)

    # 5. 点击“确认”
    confirm = page.ele('x://span[@class="btn-item" and text()="确认"]', timeout=3)
    if confirm:
        safe_click(confirm, '确认')
    time.sleep(0.3)

    # 6. 点击“我已了解，下一题”（不一定每页都有）
    next_btn = page.ele("我已了解，下一题", timeout=2)
    if next_btn:
        safe_click(next_btn, '下一题')
        time.sleep(0.5)
    else:
        time.sleep(0.5)

print('答题流程结束')
input()
