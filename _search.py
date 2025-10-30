import datetime
import json
import logging
from http.client import HTTPException
from time import time

import httpx
from fastapi import BackgroundTasks, Depends
from fastapi.routing import APIRouter
from fastapi_limiter.depends import RateLimiter
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from _crypto import decryptData
from _redis import delete_key as redis_delete_key, get_key as redis_get_key, key_exists as redis_key_exists, \
    set_key as redis_set_key
from _utils import _getRandomUserAgent, generate_vv_detail, url_encode

searchRouter = APIRouter(prefix='/api/query/ole', tags=['Search', 'Search Api'])


async def _getProxy():
    return None  # 废弃接口，直接返回 None


async def checkSum(data):
    """
    解密数据
    :param data:  加密数据
    :return:  解密后的数据
    """
    try:
        timestamp = data.get('timestamp')
        if not await checkTimeStamp(timestamp):
            raise HTTPException("Invalid Request, timestamp expired")
    except Exception as e:
        raise HTTPException("Invalid Request")
    try:
        data = await decryptData(data.get('data'))
    except Exception as e:
        logging.error(e)
        raise HTTPException("Invalid Request")
    return json.loads(data)


async def checkTimeStamp(ts):
    """
    检查时间戳是否在有效范围内 1分钟
    """
    if int(time()) - int(ts) > 60:
        return False
    return True


async def search_api(keyword, page=1, size=4):
    """
    搜索 API
    :param keyword:  搜索关键词
    :param page:  页码
    :param size:  每页数量x`
    :return:  返回搜索结果
    """
    vv = await generate_vv_detail()
    # 关键词是个中文字符串，需要进行 URL 编码
    keyword = url_encode(keyword)
    base_url = f"https://api.olelive.com/v1/pub/index/search/{keyword}/vod/0/{page}/{size}?_vv={str(vv)}"
    headers = {
        'User-Agent': _getRandomUserAgent(),
        'Referer': 'https://www.olevod.com/',
        'Origin': 'https://www.olevod.com/',
    }
    logging.info(f"Search API: {base_url}")
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url, headers=headers)
    if response.status_code != 200:
        logging.error(f"Upstream Error, base_url: {base_url}, headers: {headers}")
        raise Exception("Upstream Error")
    return response.json()


async def link_keywords(keyword):
    vv = await generate_vv_detail()
    if type(vv) is bytes:
        vv = vv.decode()
    # 关键词是个中文字符串，需要进行 URL 编码
    keyword_encoded = url_encode(keyword)
    base_url = f"https://api.olelive.com/v1/pub/index/search/keywords/{keyword_encoded}?_vv={vv}"
    headers = {
        'User-Agent': _getRandomUserAgent(),
        'Referer': 'https://www.olevod.com/',
        'Origin': 'https://www.olevod.com/',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'accept': 'application/json, text/plain, */*',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url, headers=headers)
    if response.status_code != 200:
        return JSONResponse(content={"error": "Upstream Error"}, status_code=507)
    try:
        words = response.json()["data"][0]["words"]
        words = [word for word in words if word != "" and word != keyword]
        # 去重 以及 空字符串
        words2 = list(set(words))
        words3 = list(sorted(words2, key=lambda x: len(x)))
        newResponse = response.json()
        newResponse["data"][0]["words"] = words3
        return newResponse
    except Exception as e:
        return response.json()


@searchRouter.api_route('/search', dependencies=[Depends(RateLimiter(times=3, seconds=1))], methods=['POST'],
                        name='search')
async def search(request: Request, background_tasks: BackgroundTasks):
    """
    搜索接口
    """
    data = await request.json()
    data = await checkSum(data)
    keyword, page, size = data.get('keyword'), data.get('page'), data.get('size')
    if keyword == '' or keyword == 'your keyword':
        return JSONResponse({}, status_code=200)
    page, size = int(page), int(size)
    try:
        id = f"search_{keyword}_{page}_{size}_{datetime.datetime.now().strftime('%Y-%m-%d')}"
        if await redis_key_exists(id):
            data = json.loads(await redis_get_key(id))
            data["msg"] = "cached"
            return JSONResponse(data)
    except Exception as e:
        pass
    try:
        result = await search_api(keyword, page, size)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    if result and result['data']['total'] == 0:
        return JSONResponse({"error": "No result Found"}, status_code=200)
    if result:
        background_tasks.add_task(redis_set_key, id, json.dumps(result), ex=86400)  # 缓存一天
    try:
        return JSONResponse(result)
    except:
        return JSONResponse(json.dumps(result), status_code=200)


@searchRouter.api_route('/keyword', dependencies=[Depends(RateLimiter(times=2, seconds=1))], methods=['POST'],
                        name='keyword')
async def keyword(request: Request):
    data = await request.json()
    try:
        data = await checkSum(data)
    except HTTPException as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logging.info(f"Invalid Request: {data}, {e}")
        return JSONResponse({"error": "Invalid Request"}, status_code=400)
    _keyword = data.get('keyword')
    if _keyword == '' or _keyword == 'your keyword':
        return JSONResponse({}, status_code=200)
    if _keyword == 'Yuki Forever💗':
        return JSONResponse(
            {"code": 0, "data": [{"type": "vod", "words": ["每一个未来的瞬间", "都有你的名字", "Yuki Forever💗"]}],
             "msg": "ok"}, status_code=200)
    redis_key = f"keyword_{datetime.datetime.now().strftime('%Y-%m-%d')}_{_keyword}"
    try:
        if await redis_get_key(redis_key):
            data = await redis_get_key(redis_key)
            data = json.loads(data)
            data["msg"] = "cached"
        else:
            data = await link_keywords(_keyword)
            await redis_set_key(redis_key, json.dumps(data), ex=86400)  # 缓存一天
    except Exception as e:
        logging.error("Error: " + str(e), stack_info=True)
        return JSONResponse({"error": str(e)}, status_code=501)
    try:
        return JSONResponse(data)
    except:
        return JSONResponse(json.loads(data), status_code=200)


@searchRouter.api_route('/detail', methods=['POST'], name='detail',
                        dependencies=[Depends(RateLimiter(times=2, seconds=1))])
async def detail(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    data = await checkSum(data)
    try:
        id = data.get('id')
    except Exception as e:
        return JSONResponse({"error": "Invalid Request, missing param: id"}, status_code=400,
                            headers={"X-Error": str(e)})

    # Try to return cached detail (cache for 30 minutes)
    redis_key = f"detail_{id}"
    try:
        cached = await redis_get_key(redis_key)
        if cached:
            cached_data = json.loads(cached)
            # mark as cached so clients can know
            if isinstance(cached_data, dict):
                cached_data["msg"] = "cached"
            return JSONResponse(cached_data, status_code=200)
    except Exception:
        # if redis lookup fails, continue to fetch upstream
        vv = await generate_vv_detail()
        url = f"https://api.olelive.com/v1/pub/vod/detail/{id}/true?_vv={vv}"
        headers = {
            'User-Agent': _getRandomUserAgent(),
            'Referer': 'https://www.olevod.com/',
            'Origin': 'https://www.olevod.com/',
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
            response_data = response.json()
            # cache the response for 30 minutes (1800 seconds) in background
            try:
                background_tasks.add_task(redis_set_key, redis_key, json.dumps(response_data), ex=1800)
            except Exception:
                # if scheduling background task fails, attempt immediate set but don't block on errors
                try:
                    await redis_set_key(redis_key, json.dumps(response_data), ex=1800)
                except Exception:
                    pass
            return JSONResponse(response_data, status_code=200)
        except Exception:
            return JSONResponse({"error": "Upstream Error"}, status_code=501)


@searchRouter.api_route('/report/keyword', methods=['POST'], name='report_keyword',
                        dependencies=[Depends(RateLimiter(times=1, seconds=3))])
async def report_keyword(request: Request):
    """
    上报搜索关键词 针对搜索结果为空的情况
    """
    # purge cache for the keyword and search result
    data = await request.json()
    # print(data, "checkpoint 1")
    data = await checkSum(data)
    # print(data, "checkpoint 2")
    keyword = data.get('keyword')
    if keyword == '' or keyword == 'your keyword':
        return JSONResponse({}, status_code=200)
    try:
        key = f"keyword_{datetime.datetime.now().strftime('%Y-%m-%d')}_{keyword}"
        await redis_delete_key(key)
    except Exception as e:
        logging.error("Error: " + str(e), stack_info=True)
        return JSONResponse({"error": 'trace stack b1'}, status_code=501)
    return RedirectResponse(url='/api/query/ole/keyword', status_code=308)
