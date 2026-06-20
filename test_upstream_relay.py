import re
import asyncio
import sys

import httpx

from _utils import vv_generator


def check_vv_generator_format() -> bool:
    """
    校验 vv_generator 返回一个非空的十六进制字符串。
    纯本地检查，不依赖网络。
    """
    vv = vv_generator()

    if not isinstance(vv, str):
        print("❌ vv 应该是字符串")
        return False

    if len(vv) <= 20:
        print(f"❌ vv 看起来太短，可能生成失败: {vv}")
        return False

    if not re.fullmatch(r"[0-9a-f]+", vv):
        print(f"❌ vv 包含非十六进制字符: {vv}")
        return False

    print(f"✅ vv_generator 格式正常: {vv}")
    return True


async def check_upstream_relay_search() -> bool:
    """
    请求上游轻量接口，验证 relay 是否可达。
    会真正访问 api.olelive.com。
    """
    vv = vv_generator()
    url = f"https://api.olelive.com/v1/pub/index/vod/hot/4/0/1?_vv={vv}"
    headers = {"User-Agent": "animeapi-test/1.0"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code != 200:
            print(f"❌ 上游返回非 200 状态: {resp.status_code}")
            print(f"响应内容: {resp.text}")
            return False

        try:
            data = resp.json()
        except Exception as e:
            print(f"❌ 上游返回内容无法解析为 JSON: {e}")
            print(f"响应内容: {resp.text}")
            return False

        if not isinstance(data, (dict, list)):
            print(f"❌ 上游返回的数据不是 JSON 对象或数组: {type(data)}")
            return False

        print("✅ 上游 relay 可达，返回 JSON 数据")
        print(data)
        return True

    except httpx.TimeoutException:
        print("❌ 请求上游超时")
        return False
    except httpx.RequestError as e:
        print(f"❌ 请求上游失败: {e}")
        return False


async def main() -> int:
    print("开始检查 vv_generator...")
    vv_ok = check_vv_generator_format()

    print("\n开始检查上游 relay...")
    upstream_ok = await check_upstream_relay_search()

    if vv_ok and upstream_ok:
        print("\n🎉 全部检查通过")
        return 0

    print("\n💥 检查未通过")
    return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)