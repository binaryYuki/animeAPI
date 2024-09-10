import datetime
import logging
import os
from enum import Enum as PyEnum

import dotenv
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

dotenv.load_dotenv()

# === DATABASE Configuration ===
DATABASE_URL = os.getenv("MYSQL_CONN_STRING")
if not DATABASE_URL:
    raise ValueError("MYSQL_CONN_STRING is not set")
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+asyncmy://", 1)
# === DATABASE ===

# Set up SQLAlchemy
Base = declarative_base()  # 这里是一个基类，所有的 ORM 类都要继承这个类
engine = create_async_engine(DATABASE_URL, echo=False)  # 创建一个引擎
# noinspection PyTypeChecker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)  # 异步会话类


# 枚举类型定义
class SubChannelEnum(PyEnum):
    OLE_VOD = "ole_vod"


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, index=True)
    username = Column(String(32), unique=True, index=True)
    email = Column(String(128), unique=True)
    email_verified = Column(Boolean, default=False)
    avatar = Column(String(256), default="")
    is_active = Column(Boolean, default=True)
    oidc_sub = Column(String(64), default="")
    sub_limit = Column(Integer(), default=3)
    bark_token = Column(String(64), default="")
    bark_server = Column(String(64), default="")
    push_logs = relationship("PushLog", back_populates="user")  # 修正: 使用 relationship 并 back_populates
    sub = relationship("VodSub", back_populates="user")  # 修正: 使用 relationship 并 back_populates
    last_login = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))  # 使用 UTC 时间
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))  # 使用 UTC 时间

    # 将用户与收藏功能和观看影视记录关系绑定
    favorites = relationship("UserFavorite", back_populates="user")
    watch_history = relationship("UserWatchHistory", back_populates = "user")

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "avatar": self.avatar,
            "username": self.username,
            "email_verified": self.email_verified,
            "is_active": self.is_active,
            "last_login": self.last_login.strftime("%Y-%m-%d %H:%M:%S"),
            "sub_limit": self.sub_limit
        }

    def check_token(self, token):
        return self.bark_token == token


class VodSub(Base):
    __tablename__ = "vod_subs"

    id = Column(Integer(), primary_key=True, index=True, autoincrement=True)
    sub_id = Column(String(32), index=True, unique=True)
    sub_by = Column(String(36), ForeignKey('users.user_id'))
    sub_channel = Column(String(32), default=SubChannelEnum.OLE_VOD.value)  # 将 Enum 映射为字符串
    sub_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))  # 使用 UTC 时间

    # 外键关联到 VodInfo 表
    vod_info_id = Column(Integer, ForeignKey('vod_info.id'))
    vod_info = relationship("VodInfo", back_populates="subs")  # 使用 back_populates 创建双向关系
    user = relationship("User", back_populates="sub")

    def to_dict(self):
        return {
            "sub_id": self.sub_id,
            "sub_by": self.sub_by,
            "sub_channel": self.sub_channel,
            "sub_at": self.sub_at,
            "vod_info_id": self.vod_info_id
        }


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

    #添加于收藏和观看历史的关系
    favorited = relationship("UserFavorite", back_populates = "vod_info")
    watched = relationship("UserWatchHistory", back_populates = "vod_info")

    # 添加 relationship，反向关系到 VodSub
    subs = relationship("VodSub", back_populates="vod_info")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
            if column.name != 'subs'  # Exclude the 'subs' relationship
        }


class PushLog(Base):
    __tablename__ = "push_logs"

    id = Column(Integer(), primary_key=True, index=True, autoincrement=True, unique=True)
    push_id = Column(String(32), index=True, unique=True)
    push_receiver = Column(String(36), ForeignKey('users.user_id'))
    push_channel = Column(String(32), default=SubChannelEnum.OLE_VOD.value)  # 将 Enum 映射为字符串
    push_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))  # 使用 UTC 时间
    push_result = Column(Boolean, default=False)
    push_message = Column(String(256), default="")
    push_server = Column(String(32), default="")

    user = relationship("User", back_populates="push_logs")

    def to_dict(self):
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
            logging.info("重建数据库表")
            # # 删除所有表
            # await conn.run_sync(Base.metadata.drop_all)
            # # 创建所有表
            # await conn.run_sync(Base.metadata.create_all)
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
    db: SessionLocal = SessionLocal()
    for vod_data in data["data"]["data"]:
        if vod_data["type"] == "vod":
            for item in vod_data["list"]:
                # 查找是否存在相同的 vod_id
                stmt = select(VodInfo).where(VodInfo.vod_id == str(item["id"]))
                result = await db.execute(stmt)
                db_vod = result.scalar_one_or_none()
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
                        vod_score=item.get("score", 0.0)
                    )
                    db.add(new_vod)

                await db.commit()
    await db.close()


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    id = Column(Integer(), primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey('users.user_id'))
    vod_id = Column(String(32), ForeignKey(VodInfo.vod_id))
    favorite_at = Column(DateTime, default = datetime.datetime.now(datetime.timezone.utc))

    user = relationship("User", back_populates = "favorites")
    vod_info = relationship("VodInfo", back_populates = "favorited")

    def to_dict(self):
        return {
           "user_id": self.user_id,
           "vod_id": self.vod_id,
           "favorite_at": self.favorite_at
        }


class UserWatchHistory(Base):
    __tablename__ = "user_watch_history"


    id = Column(Integer(), primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey('users.user_id'), nullable = False)
    vod_id = Column(String(32), ForeignKey('vod_info.vod_id'),nullable = False )
    watch_at = Column(DateTime, default = datetime.datetime.now(datetime.timezone.utc))
    watch_duration = Column(Float, default = 0.0)

    user = relationship("User", back_populates = "wathc_history")
    vod_info = relationship("VodInfo", back_populates = "watched")

    def to_dict(self):
        return {
           "user_id": self.user_id,
           "vod_id": self.vod_id,
           "watch_at": self.watch_at.isoformat(),
           "watch_duration": self.watch_duration
        }
