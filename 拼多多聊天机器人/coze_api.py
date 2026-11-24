import json
from session_manager import get_session

TOKEN = "sat_Z9GMso2FjmvB3PpO6JGO1CONb3UBRJvUgCWUf1O2KgJmOAqHxIj08j7CggfF8Bhw"


def cozehuoquid():  # 对话流要先建一次会话，拿 conversation_id
    url = "https://api.coze.cn/v1/conversation/create"
    headers = {
        "Authorization": "Bearer " + TOKEN,
        "Content-Type": "application/json"
    }
    session = get_session()
    with session.post(url, headers=headers, timeout=10) as response:
        return response.json()['data']['id']


def cozeduihua(conversation_id, testdata, workflow_id):  # 上传coze的接口（对话流）
    url = "https://api.coze.cn/v1/workflows/chat"
    headers = {
        "Authorization": "Bearer " + TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "workflow_id": workflow_id,
        "parameters": {
            "CONVERSATION_NAME": "Default",
            "USER_INPUT": str(testdata['content']),
            "userid": str(testdata['userid']),
            "shopid": str(testdata['shopid']),
            "username": str(testdata['username']),
            "msgid": str(testdata['msgid']),
            "template_name": str(testdata['template_name']),
            "anti": str(testdata['anti']),
            "cook": str(testdata['cook']),
            "rgmisid": str(testdata.get('zrgmisid', ''))
        },
        "additional_messages": [
            {
                "content": testdata['content'],
                "content_type": "text",
                "role": "user",
                "type": "question"
            }
        ],
        "conversation_id": conversation_id,
    }
    print(payload)
    try:
        session = get_session()
        with session.post(url, json=payload, headers=headers, stream=True, timeout=60) as response:
            answer_content = None
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data:'):
                        try:
                            data = json.loads(decoded[5:])
                            if data.get('type') == 'answer':
                                answer_content = data.get('content', '')
                        except json.JSONDecodeError:
                            continue
            if answer_content is None:  # 没有任何 answer 时把 HTTP 状态打出来，避免静默 None
                print("Coze没有返回answer，HTTP状态:", response.status_code)
            return answer_content
    except Exception as e:
        print("Coze调用异常:", e)
        return None
