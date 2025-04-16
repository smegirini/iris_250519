from irispy2 import ChatContext
from helper.BotManager import BotManager

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
        kv = BotManager().get_kv()
        res = chat.sender.id in kv.get('ban')
        return "" if res else func(*args, **kwargs)
    return wrapper

def admin_check(chat:ChatContext):
    kv = BotManager().get_kv()
    res = chat.sender.id in kv.get('admin')
    return res
