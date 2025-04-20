from irispy2.bot._internal.iris import IrisAPI
from functools import cached_property
from dataclasses import dataclass, field
import typing as t
from helper.ImageHelper import ImageHelper as ih

@dataclass(repr=False)
class Avatar:
    _id: int = field(init=False)
    _api: IrisAPI = field(init=False, repr=False)

    def __init__(self, id: int, chat_id: int, api: IrisAPI):
        self._id = id
        self._api = api
        self._chat_id = chat_id

    @cached_property
    def url(self) -> t.Optional[str]:
        try:
            if self._id < 10000000000:
                query = "SELECT T2.o_profile_image_url FROM chat_rooms AS T1 JOIN db2.open_profile AS T2 ON T1.link_id = T2.link_id WHERE T1.id = ?"
                results = self._api.query(query, [self._chat_id])
                fetched_url = results[0].get("o_profile_image_url")
            else:
                query = "SELECT original_profile_image_url,enc FROM db2.open_chat_member WHERE user_id = ?"
                results = self._api.query(query, [self._id])
                fetched_url = results[0].get("original_profile_image_url")
            return fetched_url
            
        except Exception as e:
            return None

    @cached_property
    def img(self) -> t.Optional[bytes]:
        avatar_url = self.url

        if not avatar_url:
            return None

        try:
            image_data = ih.get_image_from_url(avatar_url)
            return image_data
        except Exception as e:
            return None

    def __repr__(self) -> str:
        return f"Avatar(id={self._id})"

@dataclass(repr=False)
class PatchedRoom:
    _api: IrisAPI = field(init=False, repr=False)

    def __init__(self, id: int, name: str, api: IrisAPI):
        self.id = id
        self.name = name
        self._api = api

    @cached_property
    def type(self) -> t.Optional[str]:
        try:
            results = self._api.query(
                'select type from chat_rooms where id = ?',
                [self.id]
            )
            if results and results[0]:
                fetched_type = results[0].get("type")
                return fetched_type
            else:
                return None

        except Exception as e:
            return None

    def __repr__(self) -> str:
        return f"Room(id={self.id}, name={self.name}, patched)"
    
@dataclass
class PatchedUser:
    def __init__(self, id: int, chat_id: int, api: IrisAPI, name: str = None):
        self.id = id
        self._chat_id = chat_id
        self._api = api
    
    @cached_property
    def name(self) -> t.Optional[str]:
        try:
            query = "SELECT T2.nickname FROM chat_rooms AS T1 JOIN db2.open_profile AS T2 ON T1.link_id = T2.link_id WHERE T1.id = ?"
            results = self._api.query(query, [self._chat_id])
            nickname = results[0].get("nickname")
            return nickname
            
        except Exception as e:
            return None
    
    def __repr__(self) -> str:
        return f"User(id=Bot, name={self.name})"