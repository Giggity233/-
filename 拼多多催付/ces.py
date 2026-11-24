import requests
BASE_URL="http://117.72.204.36:8000"
response = requests.get(
    f"{BASE_URL}/api/v1/robot-cookies/",
    params={"platform": "pdd"},
    timeout=15,
)
response.raise_for_status()
robot_cookies = response.json()["data"]
print(robot_cookies)