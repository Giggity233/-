"""按与拼多多采集器相同的时间点执行抖音数据采集。"""

import time
from datetime import datetime

from 店铺数据 import main


def run_loop() -> None:
    last_run_hour = -1
    target_hours = {7, 9, 11, 13, 15, 17, 19, 21, 23}
    while True:
        now = datetime.now()
        current_hour = now.hour
        if current_hour in target_hours and current_hour != last_run_hour:
            print(f"【{now}】到达采集时间点 {current_hour} 点，开始执行 main")
            try:
                main()
            except Exception as error:
                print(f"执行 main 出错：{type(error).__name__}: {error}")
            last_run_hour = current_hour
        time.sleep(60)


if __name__ == "__main__":
    run_loop()
