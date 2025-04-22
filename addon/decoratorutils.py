from irispy2 import ChatContext
from helper import BotManager
from .patchclass import *
from .decoratorutils import *
from helper.DatabaseHelper import *
from types import MethodType
import json
from irispy2.bot.models import Message, Room, User

def admin_check(chat:ChatContext):
    kv = BotManager().get_kv()
    admins = kv.get('admin')
    if not admins:
        kv.put('admin', [])
        admins = []
    res = chat.sender.id in admins
    
    return res

def add_chat_addon(chat):
    chat.message.command, *param = chat.message.msg.split(" ", 1)
    chat.message.has_param = len(param) > 0
    chat.message.param = param[0] if chat.message.has_param else None
    chat.message.attachment = load_attachment(chat)
    chat.sender = PatchedUser(id=chat.sender.id, chat_id=chat.room.id, api=chat._ChatContext__api, name=chat.sender.name)
    chat.sender.avatar = Avatar(chat.sender.id, chat.room.id, chat._ChatContext__api)
    chat.api = chat._ChatContext__api
    chat.get_source = MethodType(get_source, chat)
    chat.get_previous_chat = MethodType(get_previous_chat, chat)
    chat.get_next_chat = MethodType(get_next_chat, chat)
    chat.room = PatchedRoom(chat.room.id, chat.room.name, chat._ChatContext__api)
    if chat.message.type in [71,27,2]:
        image = PatchedImage(chat)
        if image.url:
            chat.image = image
    return chat

def get_source(self):
    source_record = get_reply_chat(self.message)
    if source_record:
        source_chat = make_chat(self, source_record)
        return source_chat
    else:
        return None

def get_next_chat(self, n: int = 1):
    next_record = get_next_record(self.message.id, n)
    if next_record:
        next_chat = make_chat(self, next_record)
        return next_chat
    else:
        return None

def get_previous_chat(self, n: int = 1):
    previous_record = get_previous_record(self.message.id, n)
    if previous_record:
        previous_chat = make_chat(self, previous_record)
        return previous_chat
    else:
        return None

def load_attachment(self):
    try:
        attachment = json.loads(self.message.attachment)
        return attachment
    except Exception as e:
        return self.message.attachment

def make_chat(chat, record):
    v = {}
    try:
        v = json.loads(record["v"])
    except Exception:
        pass

    room = Room(id=int(record["chat_id"]), name=chat.room)
    sender = User(id=int(record["user_id"]), name=get_name_of_user_id(int(record["user_id"])))
    message = Message(
        id=int(record["id"]),
        type=int(record["type"]),
        msg=record["message"],
        attachment=record["attachment"],
        v=v,
    )

    new_chat = ChatContext(
        room=room, sender=sender, message=message, raw=record, api=chat.api
    )
    
    new_chat = add_chat_addon(new_chat)
    return new_chat
