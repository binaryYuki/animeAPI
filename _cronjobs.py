import json
import logging

from fastapi_utils.tasks import repeat_every
from httpx import AsyncClient

from _redis import delete_key, get_key, get_keys_by_pattern, redis_client, set_key as redis_set_key

logger = logging.getLogger(__name__)


async def logPushTask(taskId: str, data: dict):
    """
    记录推送任务
    :param taskId: str
    :param data: dict
    :return: Boolean
    :example: {'data': {'baseURL': 'https://api.day.app/uKeSrwm3ainGgn5SAmRyg9/', 'msg': 'You have a new notification!', 'push_receiver': 'yuki', 'icon': 'https://static.olelive.com/snap/fa77502e442ee6bbd39be20b2a2810ee.jpg?_n=202409290554', 'click_url': 'https://example.com', 'is_passive': False, 'headers': {'Authorization': 'Bearer your_token_here', 'Content-Type': 'application/json'}, 'log_data': {'push_id': '12345', 'push_receiver': 'user@example.com', 'push_by': 'system'}}, 'result': 'success'}
    """
    pass

@repeat_every(seconds=30, wait_first=True)  # wait_first=True 表示等待第一次执行 也就是启动时执行
async def pushTaskExecQueue() -> bool:
    """
    Process push tasks from the Redis keys matching 'pushTask:*' pattern.
    :return: Boolean indicating success.
    """
    try:
        all_keys = await get_keys_by_pattern('pushTask:*')
        if not all_keys:
            return False
        logger.info(f"Found {len(all_keys)} push tasks in the queue.")

        async with AsyncClient() as client:
            for key in all_keys:
                value = await get_key(key)
                if not value:
                    continue

                data = json.loads(value)
                logger.info(f"Processing push task: {data}")
                url = (
                    f"{data['baseURL']}{data['msg']}?"
                    f"icon={data['icon']}&"
                    f"url={data['click_url']}&"
                    f"passive={data['is_passive']}"
                )
                url.replace("//", "/").replace("https:/", "https://")
                response = await client.post(url)
                if response.status_code == 200:
                    await delete_key(key)
                    data['result'] = 'success'
                    logger.info(f"Push task successful: {data}")
                else:
                    data['result'] = 'failed'
                    logger.error(f"Failed to push task: {data}")

                try:
                    # taskID 取 pushTask: 后面的字符串
                    taskID = key.split(":")[1]
                    print(taskID)
                    await logPushTask(taskID, data)
                except Exception as e:
                    logger.error(f"Failed to log push task: {e}", exc_info=True)

        return True

    except Exception as e:
        logger.error(f"Error in pushTaskExecQueue: {e}", exc_info=True)
        return False


@repeat_every(seconds=3 * 60, wait_first=True)
async def keerRedisAlive():
    """
    Keep Redis alive avoid server from cool startup
    """
    await redis_set_key("alive", "yes", ex=60 * 60 * 24)
    # print("Redis is alive")
    await redis_client.delete("alive")
    return True


@repeat_every(seconds=3 * 60, wait_first=True)
async def keepMySQLAlive():
    """
    Keep MySQL alive avoid server from cool startup
    """
    pass
