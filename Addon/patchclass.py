from irispy2.bot._internal.iris import IrisAPI
from functools import cached_property
from dataclasses import dataclass, field
import typing as t
from helper.ImageHelper import ImageHelper as ih

@dataclass(repr=False)
class Avatar:
    _id: int = field(init=False)
    _api: IrisAPI = field(init=False, repr=False)

    def __init__(self, id: int, api: IrisAPI):
        self._id = id
        self._api = api

    @cached_property
    def url(self) -> t.Optional[str]:
        try:
            results = self._api.query(
                'select original_profile_image_url,enc from db2.open_chat_member where user_id = ?',
                [self._id]
            )
            if results and results[0]:
                fetched_url = results[0].get("original_profile_image_url")
                return fetched_url
            else:
                return None

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