from iris.decorators import is_admin, is_reply
from iris import ChatContext
from iris import PyKV
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'iris.db')

@is_admin
@is_reply
def ban_user(chat: ChatContext):
    replied_chat = chat.get_source()
    reply_user_id = replied_chat.sender.id
    reply_user_name = replied_chat.sender.name
    kv = PyKV(DB_PATH)
    ban_list = kv.get('ban')
    if not ban_list:
        ban_list = []
    if reply_user_id in ban_list:
        chat.reply("이미 밴 등록된 유저입니다.")
    else:
        ban_list.append(reply_user_id)
        print(ban_list)
        kv.put('ban',ban_list)
        chat.reply(f"[{reply_user_name}]님을 밴 목록에 등록하였습니다.")

@is_admin
@is_reply
def unban_user(chat: ChatContext):
    replied_chat = chat.get_source()
    reply_user_id = replied_chat.sender.id
    reply_user_name = replied_chat.sender.name
    kv = PyKV(DB_PATH)
    ban_list = kv.get('ban')
    if not ban_list:
        ban_list = []
    if reply_user_id in ban_list:
        ban_list.remove(reply_user_id)
        kv.put('ban',ban_list)
        chat.reply(f"[{reply_user_name}]님을 밴 목록에서 삭제하였습니다.")
        print(kv.get('ban'))
    else:
        chat.reply("밴 목록에 없는 유저입니다.")