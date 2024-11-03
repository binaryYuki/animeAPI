import datetime
import logging
import os
from enum import Enum as PyEnum
from uuid import uuid4

import dotenv
import sqlalchemy
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

# === DATABASE Configuration ===
DATABASE_URL = os.getenv("MYSQL_CONN_STRING")
if not DATABASE_URL:
    raise ValueError("MYSQL_CONN_STRING is not set")
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+asyncmy://", 1)
# === DATABASE ===

# Set up SQLAlchemy
Base = declarative_base()  # 这里是一个基类，所有的 ORM 类都要继承这个类
engine = create_async_engine(DATABASE_URL, pool_size=20, max_overflow=0, pool_recycle=600,
                             pool_pre_ping=True)
# noinspection PyTypeChecker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)


# 枚举类型定义
class SubChannelEnum(PyEnum):
    """
    validator
    """
    OLE_VOD = "ole_vod"


class User(Base):
    __tablename__ = "users"

    userId = Column(String(36), primary_key=True, index=True, default=uuid4().hex)
    id = Column(String(12), index=True, unique=True)
    username = Column(String(32), index=True, unique=True)
    primaryEmail = Column(String(64), index=True, unique=True)
    primaryPhone = Column(String(16), default="")
    name = Column(String(32), default="")
    avatar = Column(String(256), default="")
    customData = Column(String(256), default='{}')
    identities = Column(Text(), default='[]')
    profile = Column(String(256), default="")
    applicationId = Column(String(21), default="")
    lastSignInAt = Column(Integer(), default=datetime.datetime.now().timestamp())
    createdAt = Column(Integer(), default=datetime.datetime.now().timestamp())
    updatedAt = Column(Integer(), default=datetime.datetime.now().timestamp())

    vod_subs = relationship("VodSub", back_populates="user")
    push_logs = relationship("PushLog", back_populates="user")  # 增加 PushLog 关系


class VodSub(Base):
    __tablename__ = "vod_subs"

    id = Column(Integer(), primary_key=True, index=True, autoincrement=True)
    sub_id = Column(String(32), index=True, unique=True)
    sub_by = Column(String(36), ForeignKey('users.id'))
    sub_channel = Column(String(32), default=SubChannelEnum.OLE_VOD.value)  # 将 Enum 映射为字符串
    sub_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))  # 使用 UTC 时间
    sub_needSync = Column(Boolean, default=False)  # 取搜索是的year 判断是否需要同步

    # 外键关联到 VodInfo 表
    vod_info_id = Column(Integer, ForeignKey('vod_info.id'))
    vod_info = relationship("VodInfo", back_populates="subs")
    user = relationship("User", back_populates="vod_subs")

    def to_dict(self):
        """

        :return:
        """
        return {
            "sub_id": self.sub_id,
            "sub_by": self.sub_by,
            "sub_channel": self.sub_channel,
            "sub_at": self.sub_at,
            "vod_info_id": self.vod_info_id
        }

    async def save(self):
        """
        保存数据
        """
        async with SessionLocal() as session:
            async with session.begin():
                session.add(self)
                await session.commit()


class VodInfo(Base):
    __tablename__ = "vod_info"

    id = Column(Integer(), primary_key=True, index=True, autoincrement=True, unique=True)
    vod_id = Column(String(32), index=True, unique=True, nullable=False)
    vod_name = Column(String(32), index=True, default="")
    vod_typeId = Column(Integer(), index=True, default=0)
    vod_typeId1 = Column(Integer(), index=True, default=0)
    vod_remarks = Column(String(24), default="")  # Remarks or status of the VOD (e.g., "完结" means "completed")
    vod_is_vip = Column(Boolean, default=False)
    vod_episodes = Column(Integer(), default=0)
    vod_urls = Column(String(256), default="")
    vod_new = Column(Boolean, default=False)
    vod_version = Column(String(16), default="未知")
    vod_score = Column(Float(), default=0.0)
    vod_year = Column(Integer(), default=0)

    # 添加 relationship，反向关系到 VodSub
    subs = relationship("VodSub", back_populates="vod_info")

    def to_dict(self):
        """

        :return:
        """
        # noinspection PyTypeChecker
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
            if column.name != 'subs'  # Exclude the 'subs' relationship
        }


class PushLog(Base):
    """
    推送日志
    :param push_id: 推送 ID
    :param push_receiver: 接收者 ID
    :param push_channel: 推送渠道
    :param push_at: 推送时间
    :param push_by: 推送者系统明
    :param push_result: 推送结果
    :param push_message: 推送消息
    :param push_server: 推送服务器
    :param user: User 对象
    """
    __tablename__ = "push_logs"

    id = Column(Integer(), primary_key=True, index=True, autoincrement=True, unique=True)
    push_id = Column(String(32), index=True, unique=True)
    push_receiver = Column(String(36))
    push_channel = Column(String(32), default=SubChannelEnum.OLE_VOD.value)  # 将 Enum 映射为字符串
    push_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))  # 使用 UTC 时间
    push_by = Column(String(36))
    push_result = Column(Boolean, default=False)
    push_message = Column(String(256), default="")
    push_server = Column(String(32), default="")

    user_id = Column(String(36), ForeignKey('users.userId'))
    user = relationship("User", back_populates="push_logs")

    def to_dict(self):
        """

        :return:
        """
        return {
            "push_id": self.push_id,
            "push_by": self.push_by,
            "push_channel": self.push_channel,
            "push_at": self.push_at,
            "push_result": self.push_result,
            "push_message": self.push_message
        }


# 创建或修改数据库中的表
async def init_db():
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all, checkfirst=False)
        except OperationalError as e:
            logging.info("重建数据库表, 原因: %s", str(e))
            # # 删除所有表
            # await conn.run_sync(Base.metadata.drop_all)
            # # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            raise RuntimeError(f"Database initialization failed: {str(e)}")


async def test_db_connection():
    try:
        async with SessionLocal() as session:
            async with session.begin():
                # 执行一个简单的查询
                result = await session.execute(text("SELECT 1"))
                assert result.scalar() == 1
                return True
    except Exception as e:
        raise ConnectionError(f"Database connection failed: {str(e)}")


async def cache_vod_data(data):
    """

    :param data:
    """
    try:
        db: SessionLocal = SessionLocal()
        for vod_data in data["data"]["data"]:
            if vod_data["type"] == "vod":
                for item in vod_data["list"]:
                    # 查找是否存在相同的 vod_id
                    # noinspection PyTypeChecker
                    stmt = select(VodInfo).where(VodInfo.vod_id == str(item["id"]))
                    result = await db.execute(stmt)
                    db_vod = result.scalar_one_or_none()
                    episode_list = item.get("episodes", [])
                    if episode_list:
                        item["episodes"] = len(episode_list)
                    if db_vod:
                        # 更新现有数据
                        db_vod.vod_name = item["name"]
                        db_vod.vod_typeId = item["typeId"]
                        db_vod.vod_typeId1 = item["typeId1"]
                        db_vod.vod_remarks = item["remarks"]
                        db_vod.vod_is_vip = item["vip"]
                        db_vod.vod_episodes = item.get("episodes", 0)
                        db_vod.vod_urls = item.get("pic", "")
                        db_vod.vod_new = item.get("new", False)
                        db_vod.vod_version = item.get("version", "未知")
                        db_vod.vod_score = item.get("score", 0.0)
                        db_vod.vod_year = item.get("year", 0)
                    else:
                        # 插入新数据
                        new_vod = VodInfo(
                            vod_id=str(item["id"]),
                            vod_name=item["name"],
                            vod_typeId=item["typeId"],
                            vod_typeId1=item["typeId1"],
                            vod_remarks=item["remarks"],
                            vod_is_vip=item["vip"],
                            vod_episodes=item.get("episodes", 0),
                            vod_urls=item.get("pic", ""),
                            vod_new=item.get("new", False),
                            vod_version=item.get("version", "未知"),
                            vod_score=item.get("score", 0.0),
                            vod_year=item.get("year", 0)
                        )
                        db.add(new_vod)

                    await db.commit()
        await db.close()
    except sqlalchemy.exc.OperationalError:
        # retry
        await cache_vod_data(data)
    except Exception as e:
        logger.error("Error while caching data: %s", str(e))


class requestUpdate(Base):
    __tablename__ = "request_update"

    id = Column(Integer(), primary_key=True, index=True, autoincrement=True, unique=True)
    request_id = Column(String(32), index=True, unique=True, default=uuid4().hex)
    request_by = Column(String(36), ForeignKey('users.id'), default="Anonymous")
    request_channel = Column(String(32), default=SubChannelEnum.OLE_VOD.value)  # 将 Enum 映射为字符串
    request_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))  # 使用 UTC 时间
    request_result = Column(Boolean, default=False)
    request_vod = Column(String(256), default="")
    request_vod_channel = Column(String(32), default="", nullable=True)

    def to_dict(self):
        """

        :return:
        """
        # search username by userId
        return {
            "request_id": self.request_id,
            "request_by": self.request_by,
            "request_channel": self.request_channel,
            "request_at": self.request_at,
            "request_result": self.request_result,
            "request_vod": self.request_vod,
            "request_vod_channel": self.request_vod_channel
        }


class WebHookStorage(Base):
    __tablename__ = 'webhook_storage'

    id = Column(String(32), primary_key=True, index=True, default=uuid4().hex)
    hook_id = Column(String(32))
    event = Column(String(24))
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    session_id = Column(String(32))
    user_agent = Column(String(256), default="")
    user_ip = Column(String(128), default="")
    user_id = Column(String(32), default="")
    sessionId = Column(String(32), default="")

    application = Text()

    def __repr__(self):
        return f"<WebHookStorage(hook_id='{self.hook_id}', event='{self.event}')>"


async def create_vod_sub(data):
    """
    create vod sub
    :param data:
    :return:
    """
    async with SessionLocal() as session:
        async with session.begin():
            # 查询用户是否存在
            stmt = select(User).where(User.id == data['sub_by'])
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user is None:
                # 如果不存在，则会导致数据库错误
                raise ValueError(f"User with id {data['sub_by']} does not exist")

            # 如果存在，则插入 VodSub 对象
            vod_sub = VodSub(sub_id=data['sub_id'], sub_by=data['sub_by'])
            session.add(vod_sub)
            await session.commit()
            # 重新从数据库中查询 VodSub 对象
            stmt = select(VodSub).where(VodSub.sub_id == data['sub_id'])
            data = await session.execute(stmt)
            return data.scalar_one_or_none()


async def unsubscribe_vod_sub(data):
    """
    unsubscribe vod sub
    :param data:
    :return:
    """
    async with SessionLocal() as session:
        async with session.begin():
            # 查询用户是否存在
            stmt = select(User).where(User.id == data['sub_by'])
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user is None:
                # 如果不存在，则会导致数据库错误
                raise ValueError(f"User with id {data['sub_by']} does not exist")

            # 如果存在，则删除 VodSub 对象
            stmt = select(VodSub).where(VodSub.sub_id == data['sub_id'])
            result = await session.execute(stmt)
            vod_sub = result.scalar_one_or_none()
            if vod_sub:
                session.delete(vod_sub)
                await session.commit()
                return True
            return False
