from iris.bot.models import Message
from iris import PyKV

def get_reply_user_id(message: Message):
    reply_chat = get_reply_chat(message)
    src_user_id = reply_chat['user_id']
    return int(src_user_id)

def get_reply_chat(message: Message):
    try:
        kv = PyKV()
        src_log_id = message.attachment['src_logId']
        # chat.api 등으로 쿼리 필요 (irispy-client 구조에 맞게 수정 필요)
        # query = "select * from chat_logs where id = ?"    
        # src_record = bot.api.query(query,[src_log_id])
        # return src_record[0]
        return None  # TODO: chat.api로 대체 필요
    except Exception as e:
        print(e)
        return None
    
def get_name_of_user_id(user_id: int):
    # chat.api 등으로 쿼리 필요 (irispy-client 구조에 맞게 수정 필요)
    return None  # TODO: chat.api로 대체 필요

def get_previous_record(log_id, n: int = 1):
    # chat.api 등으로 쿼리 필요 (irispy-client 구조에 맞게 수정 필요)
    return None  # TODO: chat.api로 대체 필요

def get_next_record(log_id, n: int = 1):
    # chat.api 등으로 쿼리 필요 (irispy-client 구조에 맞게 수정 필요)
    return None  # TODO: chat.api로 대체 필요