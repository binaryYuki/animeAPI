import datetime
import hashlib
import json
import logging
import urllib
import urllib.parse
import uuid
from typing import Optional

from fake_useragent import UserAgent
from httpx import AsyncClient

from _redis import get_key, set_key  # noqa

ua = UserAgent()

logger = logging.getLogger(__name__)


def he(char):
    # 将字符转换为二进制字符串，保持至少6位长度
    return bin(int(char))[2:].zfill(6)


def C(t):
    # 使用 hashlib 生成 MD5 哈希值
    return hashlib.md5(t.encode('utf-8')).hexdigest()


def vv_generator():
    """
    生成 vv 参数
    :return:
    """
    # 获取当前法国时间的 Unix 时间戳（秒）
    france_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))
    timestamp = int(france_time.timestamp())

    # 将时间戳转换为字符串
    t = str(timestamp)

    r = ["", "", "", ""]

    # 遍历时间戳字符串并处理二进制表示
    for char in t:
        e = he(char)
        r[0] += e[2] if len(e) > 2 else '0'
        r[1] += e[3] if len(e) > 3 else '0'
        r[2] += e[4] if len(e) > 4 else '0'
        r[3] += e[5] if len(e) > 5 else '0'

    a = []

    # 将二进制字符串转换为十六进制字符串
    for binary_str in r:
        hex_str = format(int(binary_str, 2), 'x').zfill(3)
        a.append(hex_str)

    n = C(t)

    # 组合最终结果字符串
    vv = n[:3] + a[0] + n[6:11] + a[1] + n[14:19] + a[2] + n[22:27] + a[3] + n[30:]

    return vv


async def generate_vv_detail():
    """
    生成 vv 参数
    :return:  str
    """
    vv = await get_key('vv')

    if not vv:
        vv = vv_generator()
        success = await set_key('vv', vv, 60 * 5)
        if not success:
            raise Exception('Failed to set vv')

    return vv


def _getRandomUserAgent():
    return ua.random


async def pushNotification(baseURL: str, msg: str, icon: str = '', click_url: str = '', is_passive: bool = False,
                           headers: Optional[dict] = None):
    """
    推送通知
    :param baseURL: 推送服务基础 URL
    :param msg: 推送消息内容
    :param icon: 图标 URL，可选
    :param click_url: 点击跳转 URL，可选
    :param is_passive: 是否被动推送（静默）
    :param headers: 额外请求头，可选
    :return: bool 是否推送成功
    """
    # url = https://api.day.app/uKeSrwm3ainGgn5SAmRyg9/{msg}?icon={icon}&url={url}&passive={is_passive}
    if headers is None:
        headers = {}
    print(f"Pushing notification to {baseURL}/{msg}?")
    url = f'{baseURL}/{msg}?'
    if icon:
        url += f'&icon={icon}'
    if click_url:
        url += f'&url={click_url}'
    if is_passive:
        url += f'&passive=true'
    print(f"Pushing to {url}")
    async with AsyncClient() as client:
        response = await client.post(url, headers=headers)
        print(response.status_code)
        if response.status_code != 200:
            return False
        else:
            return True


# url 编码关键词
def url_encode(keyword):
    # ensure str input and use urllib.parse.quote for encoding
    if isinstance(keyword, bytes):
        keyword = keyword.decode('utf-8', errors='ignore')
    return urllib.parse.quote(str(keyword))


async def generatePushTask(baseURL: str, msg: str, user_id: str, receiver: str, icon=None, click_url=None,
                           is_passive=None, headers: Optional[dict] = None, taskID: str = uuid.uuid4().hex,
                           push_receiver: str = "yuki", push_by: str = "system"):
    """
    生成推送任务并暂存到 Redis 队列
    :param baseURL: 推送服务基础 URL
    :param msg: 推送消息内容
    :param user_id: 用户 ID
    :param receiver: 接收者标识
    :param icon: 图标 URL，可选
    :param click_url: 点击跳转 URL，可选
    :param is_passive: 是否被动推送（静默）
    :param headers: 请求头，可选
    :param taskID: 任务 ID（默认随机）
    :param push_receiver: 推送接收者（日志）
    :param push_by: 推送发起者（日志）
    :return: bool
    示例： generatePushTask("https://api.day.app/uKeSrwm3ainGgn5SAmRyg9/", "You have a new notification!", str(12345),
                           "https://example.com", False, None, None, None, uuid.uuid4().hex, "system",
                            "bark")
    """
    data = {
        "baseURL": baseURL,
        "msg": msg,
        "push_receiver": receiver,
        "icon": icon if icon else "https://static.olelive.com/snap/fa77502e442ee6bbd39be20b2a2810ee.jpg?_n=202409290554",
        "click_url": click_url if click_url else "",
        "is_passive": is_passive if is_passive is not None else False,
        "headers": headers if headers else {
            "content-type": "application/json",
        },
        "log_data": {
            "push_id": taskID,
            "push_receiver": push_receiver,
            "push_by": push_by if push_by else "system",
            "user_id": user_id
        }
    }
    await set_key(f"pushTask:{taskID}", json.dumps(data), 60 * 5)
    return True


if __name__ == '__main__':
    print(vv_generator())
    print(_getRandomUserAgent())
