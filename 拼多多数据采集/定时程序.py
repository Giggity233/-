import time
from datetime import datetime
# 导入别的文件中的main函数，other_module是你的另一个py文件名
from 店铺数据 import main


def run_loop():
    last_run_hour = -1
    # 需要执行的小时：7,9,11,13,15,17,19,21,23
    target_hours = {7, 9, 11, 13, 15, 17, 19, 21, 23}
    while True:
        now = datetime.now()
        current_h = now.hour
        # 判断：当前小时在目标集合内，且本小时还没执行
        if current_h in target_hours and current_h != last_run_hour:
            print(f"【{now}】到达采集时间点 {current_h}点，开始执行main")
            try:
                main()
            except Exception as e:
                print(f"执行main出错：{type(e).__name__}: {e}")
            last_run_hour = current_h

        time.sleep(60)  # 60秒检查一次


if __name__ == "__main__":
    run_loop()