from irispy2 import ChatContext
from irispy2.bot._internal.iris import IrisAPI
from functools import cached_property
from dataclasses import dataclass, field
import typing as t
from types import MethodType
from helper.ImageHelper import ImageHelper as ih
from helper.DatabaseHelper import get_reply_chat, get_name_of_user_id
import json
from irispy2.bot.models import Message, Room, User

@dataclass(repr=False)
class Avatar:
    _id: int = field(init=False)
    _api: IrisAPI = field(init=False, repr=False) # Keep API internal

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

def on_message_chat_addon(func):
    def wrapper(*args,**kwargs):
        chat: ChatContext = args[0]
        chat = add_chat_addon(chat)
        return func(chat)
    return wrapper

def add_chat_addon(chat):
    chat.message.command, *param = chat.message.msg.split(" ", 1)
    chat.message.has_param = len(param) > 0
    chat.message.param = param[0] if chat.message.has_param else None
    chat.sender.avatar = Avatar(chat.sender.id, chat._ChatContext__api)
    chat.api = chat._ChatContext__api
    chat.get_source = MethodType(get_source, chat)
    return chat

def has_param(func):
    def wrapper(*args,**kwargs):
        chat: ChatContext = args[0]
        return func(*args, **kwargs) if chat.message.has_param else None
    return wrapper

def is_reply(func):
    def wrapper(*args,**kwargs):
        chat: ChatContext = args[0]
        if chat.message.type == 26:
            return func(*args, **kwargs)
        else:
            chat.reply("메세지에 답장하여 요청하세요.")
            return None
    return wrapper

def get_source(self):
    source_record = get_reply_chat(self.message)
    if source_record:
        v = {}
        try:
            v = json.loads(source_record["v"])
        except Exception:
            pass

        room = Room(id=int(source_record["chat_id"]), name=self.room)
        sender = User(id=int(source_record["user_id"]), name=get_name_of_user_id(int(source_record["user_id"])))
        message = Message(
            id=int(source_record["id"]),
            type=int(source_record["type"]),
            msg=source_record["message"],
            attachment=source_record["attachment"],
            v=v,
        )

        source_chat = ChatContext(
            room=room, sender=sender, message=message, raw=source_record, api=self.api
        )
        
        source_chat = add_chat_addon(source_chat)
        return source_chat
    else:
        return None


