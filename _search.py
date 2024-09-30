import datetime
import json
import logging
import urllib.parse

import httpx
from fastapi import BackgroundTasks, Depends
from fastapi.routing import APIRouter
from fastapi_limiter.depends import RateLimiter
from starlette.requests import Request
from starlette.responses import JSONResponse

from _db import cache_vod_data
from _redis import get_key as redis_get_key, key_exists as redis_key_exists, set_key as redis_set_key
from _utils import _getRandomUserAgent, generate_vv_detail

searchRouter = APIRouter(prefix='/api/query/ole', tags=['Search', 'Search Api'])


async def _getProxy():
    return None  # 废弃接口，直接返回 None


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


# url 编码关键词
def url_encode(keyword):
    return urllib.parse.quote(keyword.encode())


@searchRouter.api_route('/search', dependencies=[Depends(RateLimiter(times=5, seconds=1))], methods=['POST'],
                        name='search')
async def search(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
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
        await cache_vod_data(result)
        await redis_set_key(id, result, ex=86400)  # 缓存一天
    try:
        return JSONResponse(result)
    except:
        return JSONResponse(json.dumps(result), status_code=200)


@searchRouter.api_route('/keyword', dependencies=[Depends(RateLimiter(times=1, seconds=1))], methods=['POST'],
                        name='keyword')
async def keyword(request: Request):
    data = await request.json()
    keyword = data.get('keyword')
    if keyword == '' or keyword == 'your keyword':
        return JSONResponse({}, status_code=200)
    redis_key = f"keyword_{datetime.datetime.now().strftime('%Y-%m-%d')}_{keyword}"
    try:
        if await redis_get_key(redis_key):
            data = await redis_get_key(redis_key)
            data = json.loads(data)
            data["msg"] = "cached"
        else:
            data = await link_keywords(keyword)
            await redis_set_key(redis_key, json.dumps(data), ex=86400)  # 缓存一天
    except Exception as e:
        logging.error("Error: " + str(e), stack_info=True)
        return JSONResponse({"error": str(e)}, status_code=501)
    try:
        return JSONResponse(data)
    except:
        return JSONResponse(json.loads(data), status_code=200)


@searchRouter.api_route('/detail', methods=['POST'], name='detail',
                        dependencies=[Depends(RateLimiter(times=1, seconds=3))])
async def detail(request: Request):
    data = await request.json()
    try:
        id = data.get('id')
    except Exception as e:
        return JSONResponse({"error": "Invalid Request, missing param: id"}, status_code=400,
                            headers={"X-Error": str(e)})
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
        return JSONResponse(response_data, status_code=200)
    except:
        return JSONResponse({"error": "Upstream Error"}, status_code=501)
    # direct play https://player.viloud.tv/embed/play?url=https://www.olevod.com/vod/detail/5f4b3b7b7f3c1d0001b2b3b3&autoplay=1
