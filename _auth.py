import datetime
import json
import os
from logging import getLogger

import dotenv
import jwt
from fastapi import APIRouter, BackgroundTasks, Request
from sqlalchemy import text
from starlette.responses import JSONResponse

from _db import SessionLocal, User, WebHookStorage

logger = getLogger(__name__)

dotenv.load_dotenv()

authRoute = APIRouter(prefix='/api/auth', tags=['Auth', 'Authentication'])


async def generateJWT(payload: dict):
    """
    生成 JWT Token
    :return: str
    """
    payload['exp'] = datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    return jwt.encode(payload, os.getenv('SESSION_SECRET'), algorithm="HS256")


async def eventVerifier(event: str):
    """
    Verifies the event received from the webhook
    :param event:
    :return: Boolean
    """
    allowedEvent = ['PostRegister', 'PostResetPassword', 'PostSignIn']
    if event in allowedEvent:
        return True
    return False


async def timeFrameVerifier(timeStamp: str):
    """
    Verifies the time frame received from the webhook
    :param timeStamp: str (time frame)
    :return: Boolean
    """
    try:
        if (datetime.datetime.strptime(timeStamp, '%Y-%m-%dT%H:%M:%S.%fZ') >
                datetime.datetime.now() - datetime.timedelta(minutes=1)):
            return True
        else:
            return False
    except ValueError:
        return False


async def store_webhook_data(data: dict):
    """
    :param data:
    """
    async with SessionLocal() as session:
        async with session.begin():
            webhook = WebHookStorage(
                hook_id=data["hookId"],
                event=data["event"],
                session_id=data["sessionId"],
                user_agent=data["userAgent"],
                user_ip=data["userIp"],
                sessionId=data["sessionId"],
            )
            data = data['user']
            user = User(
                id=data['id'],
                username=data['username'],
                primaryEmail=data['primaryEmail'],
                primaryPhone=data['primaryPhone'],
                name=data['name'],
                avatar=data['avatar'],
                customData=json.dumps(data['customData']),  # 将字典序列化为JSON字符串
                identities=json.dumps(data['identities']),
                profile=json.dumps(data['profile']),
                applicationId=data['applicationId'],
                lastSignInAt=data['lastSignInAt'] / 1000,
                createdAt=data['createdAt'] / 1000,
                updatedAt=data['updatedAt'] / 1000,
            )
            # 通过 id 判断用户是否存在 如果存在就更新用户信息 否则插入新用户
            user_exist = await session.execute(text(f"SELECT * FROM users WHERE id='{data['id']}'"))
            user_exist = user_exist.fetchone()
            if user_exist:
                await session.execute(
                    text(f"UPDATE users SET username='{data['username']}', primaryEmail='{data['primaryEmail']}', "
                         f"primaryPhone='{data['primaryPhone']}', name='{data['name']}', avatar='{data['avatar']}', "
                         f"customData='{json.dumps(data['customData'])}', identities='{json.dumps(data['identities'])}', "
                         f"profile='{json.dumps(data['profile'])}', applicationId='{data['applicationId']}', "
                         f"lastSignInAt='{data['lastSignInAt'] / 1000}', createdAt='{data['createdAt'] / 1000}', "
                         f"updatedAt='{data['updatedAt'] / 1000}' WHERE id='{data['id']}'"))
            else:
                session.add(user)
            session.add(webhook)
            await session.commit()
            await session.close()


@authRoute.api_route('/hook', methods=['POST'])
async def logtoEventHandler(request: Request, background_tasks: BackgroundTasks):
    """

    :param request:
    :param background_tasks:
    :return:
    """
    try:
        data = await request.json()
    except Exception as e:
        logger.debug(e)
        return JSONResponse(status_code=401, content={'error': 'Invalid request'})
    if not await eventVerifier(data.get('event')) or not await timeFrameVerifier(data.get('createdAt')):
        return JSONResponse(status_code=401, content={'error': 'Invalid request', 'step': 2})
    background_tasks.add_task(store_webhook_data, data)
    return JSONResponse(status_code=200, content={'message': 'Webhook received successfully'})


@authRoute.api_route('/jwt', methods=['POST'])
async def generateJWTToken(request: Request):
    """
    生成 JWT Token
    :param request:
    :return:
    """
    try:
        data = await request.json()
        payload = {
            "sub": data.get('sub'),
            "name": data.get('name'),
            "picture": data.get('picture'),
            "username": data.get('username'),
            "sid": data.get('sid'),
            "exp": data.get('exp'),
        }
        token = await generateJWT(payload)
        return JSONResponse(status_code=200, content={'token': token})
    except KeyError:
        return JSONResponse(status_code=401, content={'error': 'Invalid request'})
    except Exception as e:
        return JSONResponse(status_code=401, content={'error': str(e)})


@authRoute.api_route('/verify', methods=['POST'])
async def verifyJWTToken(request: Request):
    """
    验证 JWT Token
    :param request:
    :return: JSONResponse
    """
    try:
        data = await request.json()
        token = data.get('token')
        payload = jwt.decode(token, os.getenv('SESSION_SECRET'), algorithms=["HS256"])
        return JSONResponse(status_code=200, content={'payload': payload, 'header': jwt.get_unverified_header(token)})
    except jwt.ExpiredSignatureError:
        return JSONResponse(status_code=401, content={'error': 'Token expired'})
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=401, content={'error': 'Invalid token'})
    except Exception as e:
        return JSONResponse(status_code=401, content={'error': str(e)})
