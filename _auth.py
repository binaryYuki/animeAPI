import datetime
import os
from logging import getLogger

import dotenv
import jwt
from fastapi import APIRouter, BackgroundTasks, Request
from starlette.responses import JSONResponse

logger = getLogger(__name__)

dotenv.load_dotenv()

authRoute = APIRouter(prefix='/api/auth', tags=['Auth', 'Authentication'])


async def generateJWT(payload: dict):
    """
    生成 JWT Token
    :return: str
    """
    # Use timezone-aware UTC datetime per deprecation guidance
    payload['exp'] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)
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
    pass


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
