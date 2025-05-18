from iris import ChatContext
from iris import PyKV
#from helper.DatabaseHelper import *  # DatabaseHelper는 irispy-client 구조에서는 사용하지 않음
from .decoratorutils import *

def on_message_chat_addon(func):
    def wrapper(*args,**kwargs):
        chat: ChatContext = args[0]
        chat = add_chat_addon(chat)
        return func(chat)
    return wrapper

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

def is_admin(func):
    def wrapper(*args,**kwargs):
        chat = args[0]
        return func(*args, **kwargs) if admin_check(chat) else None
    return wrapper

def is_not_banned(func):
    def wrapper(*args,**kwargs):
        chat: ChatContext = args[0]
        if admin_check(chat):
            return func(*args, **kwargs)
        kv = PyKV()
        bans = kv.get('ban')
        if not bans:
            kv.put('ban',[])
            bans = []
        res = chat.sender.id in bans
        return "" if res else func(*args, **kwargs)
    return wrapper