from fastapi import APIRouter, FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from _crypto import decryptData
from _db import create_vod_sub, unsubscribe_vod_sub

app = FastAPI()

# OpenIdConnect configuration

# Router for user-related endpoints
userRoute = APIRouter(prefix='/api/user', tags=['User', 'User Management', 'oauth2'])


def checkSubSum(data: dict):
    """
    检查数据是否合法
    :param data: json
    :return:  bool
    """
    if 'sub_id' not in data:
        return False
    if 'sub_by' not in data:
        return False
    return True


@userRoute.api_route('/subscribe', methods=['POST'])
async def subscribe(request: Request):
    """
    订阅接口
    id = Column(Integer(), primary_key=True, index=True, autoincrement=True)
    sub_id = Column(String(32), index=True, unique=True)
    sub_by = Column(String(36), ForeignKey('users.id'))
    sub_channel = Column(String(32), default=SubChannelEnum.OLE_VOD.value)  # 将 Enum 映射为字符串
    sub_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))  # 使用 UTC 时间
    sub_needSync = Column(Boolean, default=False)  # 取搜索是的year 判断是否需要同步
    :return:
    """
    try:
        data = await request.json()
        print(data)
    except Exception as e:
        return JSONResponse(status_code=400, content={'error': 'Invalid JSON data'})
    if not checkSubSum(data):
        return JSONResponse(status_code=400, content={'error': 'Invalid JSON data'})
    data = await decryptData(data)
    sub = create_vod_sub(data)
    return JSONResponse(status_code=200, content={'msg': 'success', 'db_data': sub})


@userRoute.api_route('/unsubscribe', methods=['POST'])
async def unsubscribe(request: Request):
    """
    取消订阅接口
    :return:
    """
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse(status_code=400, content={'error': 'Invalid JSON data'})
    if not checkSubSum(data):
        return JSONResponse(status_code=400, content={'error': 'Invalid JSON data'})
    data = await decryptData(data)
    # 取消订阅
    sub = unsubscribe_vod_sub(data)
    return JSONResponse(status_code=200, content={'msg': 'success', 'exec_status': sub})
