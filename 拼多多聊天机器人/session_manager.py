import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 创建全局会话对象，用于复用连接
_session = None

def get_session() -> requests.Session:
    """
    获取全局会话对象，自动处理连接复用和重试
    
    返回:
        requests.Session: 配置好的会话对象
    """
    global _session
    if _session is None:
        _session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,  # 总重试次数
            backoff_factor=1,  # 重试间隔时间因子
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
            allowed_methods=["HEAD", "GET", "POST"]  # 允许重试的方法
        )
        
        # 创建HTTP适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=100,  # 连接池大小
            pool_maxsize=200       # 最大连接数
        )
        
        # 挂载适配器到会话
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
        
        # 设置默认超时时间
        _session.timeout = 15
        
        # 添加默认请求头
        _session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        })
    
    return _session

def close_session():
    """
    关闭会话，释放资源
    """
    global _session
    if _session is not None:
        _session.close()
        _session = None
