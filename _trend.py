import datetime
import json
import logging
from json import JSONDecodeError
from typing import Optional

import httpx
from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi_limiter.depends import RateLimiter
from starlette.requests import Request
from starlette.responses import JSONResponse

from _redis import get_key, set_key
from _utils import _getRandomUserAgent, generate_vv_detail as gen_vv

trendingRoute = APIRouter(prefix='/api/trending', tags=['Trending'])

ALLOWED_PERIODS = {'day', 'week', 'month', 'all'}
ALLOWED_TYPE_IDS = {1, 2, 3, 4}


async def gen_url(typeID: int, period: str, amount=10):
    if period not in ALLOWED_PERIODS:
        return JSONResponse(status_code=400, content={'error': 'Invalid period parameter, must be one of: day, week, month, all'})
    if typeID not in ALLOWED_TYPE_IDS:
        return JSONResponse(status_code=400, content={'error': 'Invalid typeID parameter, must be one of: 1 --> 电影, 2 --> 电视剧（连续剧）, 3 --> 综艺, 4 --> 动漫'})
    vv = await gen_vv()
    return f"https://api.olelive.com/v1/pub/index/vod/data/rank/{period}/{typeID}/{amount}?_vv={vv}"


async def gen_url_v2(typeID: int, amount=10):
    if typeID not in ALLOWED_TYPE_IDS:
        return JSONResponse(status_code=400, content={'error': 'Invalid typeID parameter, must be one of: 1 --> 电影, 2 --> 电视剧（连续剧）, 3 --> 综艺, 4 --> 动漫'})
    vv = await gen_vv()
    return f"https://api.olelive.com/v1/pub/index/vod/hot/{typeID}/0/{amount}?_vv={vv}"


@trendingRoute.post('/{period}/trend')
async def fetch_trending_data(request: Request, period: Optional[str] = 'day'):
    try:
        body = await request.json()
        try:
            typeID = body['params']['typeID']
            logging.info(f"typeID1: {typeID}")
        except KeyError:
            return JSONResponse(status_code=400, content={'error': "Where is your param?"})
    except JSONDecodeError as e:
        logging.error(f"JSONDecodeError: {e}, hint: request.json() failed, step fetch_trending_data")
        return JSONResponse(status_code=400, content={'error': "Where is your param?"})

    if period is None:
        logging.error(f"period: {period}, hint: period is None, step fetch_trending_data")
        return JSONResponse(status_code=400, content={'error': 'Missing required parameters: period'})
    if typeID is None:
        logging.info(f"typeID: {typeID}, hint:typeID is None, step fetch_trending_data")
        return JSONResponse(status_code=400, content={'error': 'Missing required parameters: typeID'})
    if period not in ALLOWED_PERIODS:
        logging.error(f"period: {period}, hint:period not in ['day', 'week', 'month', 'all]")
        return JSONResponse(status_code=400, content={'error': 'Invalid period parameter, must be one of: day, week, month, all'})
    if typeID not in ALLOWED_TYPE_IDS:
        logging.error(f"typeID: {typeID}, hint:typeID not in [1,2,3,4]")
        return JSONResponse(status_code=400, content={'error': 'Invalid typeID parameter, must be one of: 1 --> 电影, 2 --> 电视剧（连续剧）, 3 --> 综艺, 4 --> 动漫'})

    url = await gen_url(typeID, period, amount=10)
    logging.info(f"Fetching trending data from: {url}")

    resp = None
    api_payload = None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={'User-Agent': _getRandomUserAgent()}, timeout=30)
            api_payload = resp.json()
            return JSONResponse(status_code=200, content=api_payload)
    except httpx.RequestError as e:
        logging.debug(f"snapshot: {api_payload}")
        return JSONResponse(status_code=500, content={'error': f"An error occurred: {e}"})
    except httpx.HTTPStatusError as e:
        logging.debug(f"snapshot: {api_payload}")
        return JSONResponse(status_code=500, content={'error': f"An HTTP error occurred: {e}"})
    except Exception as e:
        raw_text = resp.text if resp is not None else ""
        logging.debug(f"snapshot: {api_payload}")
        return JSONResponse(status_code=500, content={'error': f"An error occurred: {e}, response: {raw_text}"})


@trendingRoute.api_route('/v2/{typeID}', methods=['POST'], dependencies=[Depends(RateLimiter(times=2, seconds=1))])
async def fetch_trending_data_v2(request: Request, typeID: Optional[int] = None):
    try:
        amount = request.query_params['amount']
    except KeyError:
        amount = 10

    if typeID is None:
        logging.info(f"typeID: {typeID}, hint:typeID is None, step fetch_trending_data")
        return JSONResponse(status_code=400, content={'error': 'Missing required parameters: typeID'})
    if typeID not in ALLOWED_TYPE_IDS:
        logging.error(f"typeID: {typeID}, hint:typeID not in [1,2,3,4]")
        return JSONResponse(status_code=400, content={'error': 'Invalid typeID parameter, must be one of: 1 --> 电影, 2 --> 电视剧（连续剧）, 3 --> 综艺, 4 --> 动漫'})

    redis_key = f"trending_v2_cache_{datetime.datetime.now().strftime('%Y-%m-%d')}_{typeID}_{amount}"
    cached = await get_key(redis_key)
    if cached:
        logging.info(f"Hit cache for key: {redis_key}")
        return JSONResponse(status_code=200, content=json.loads(cached))

    url = await gen_url_v2(typeID, amount)
    logging.info(f"Fetching trending data from: {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers={'User-Agent': _getRandomUserAgent()}, timeout=30)
            payload = json.dumps(response.json())
            await set_key(redis_key, payload, 60 * 60 * 24)
            return JSONResponse(status_code=200, content=json.loads(payload))
    except httpx.RequestError as e:
        return JSONResponse(status_code=500, content={'error': f"An error occurred: {e}"})
