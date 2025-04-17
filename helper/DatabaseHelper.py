from irispy2 import ChatContext, Bot
from irispy2.bot.models import Message
from helper.BotManager import BotManager
import json

def get_reply_user_id(message: Message):
    reply_chat = get_reply_chat(message)
    src_user_id = reply_chat['user_id']
    return int(src_user_id)

def get_reply_chat(message: Message):
    try:
        bot = BotManager().get_current_bot()
        src_log_id = json.loads(message.attachment)['src_logId']
        query = "select * from chat_logs where id = ?"    
        src_record = bot.api.query(query,[src_log_id])
        return src_record[0]
    except Exception as e:
        print(e)
        return None
    
def get_name_of_user_id(user_id: int):
    bot = BotManager().get_current_bot()
    query = "WITH info AS (SELECT ? AS user_id) SELECT COALESCE(open_chat_member.nickname, friends.name) AS name, COALESCE(open_chat_member.enc, friends.enc) AS enc FROM info LEFT JOIN db2.open_chat_member ON open_chat_member.user_id = info.user_id LEFT JOIN db2.friends ON friends.id = info.user_id;"
    result = bot.api.query(query,[user_id])
    if len(result) == 0:
        return None
    return result[0]['name']

def get_previous_record(log_id, n: int = 1):
    bot = BotManager().get_current_bot()
    if n < 0:
        raise ValueError("n must be greater than 0")
    
    query = """
        WITH RECURSIVE ChatHistory AS (
            SELECT *
            FROM chat_logs
            WHERE id = ?
            UNION ALL
            SELECT c.*
            FROM chat_logs c
            JOIN ChatHistory h ON c.id = h.prev_id
        )
        SELECT *
        FROM ChatHistory
        LIMIT 1 OFFSET ?;
        """
    record = bot.api.query(query, [log_id, n])
    return record[0] if record else None

def get_next_record(log_id, n: int = 1):
    n = n - 1
    if n < -1:
        raise ValueError("n must be greater than 0")
    bot = BotManager().get_current_bot()
    query = """
        WITH RECURSIVE ChatHistory AS (
            SELECT
                *,
                0 AS depth
            FROM
                chat_logs
            WHERE
                id = ?

            UNION ALL

            SELECT
                c.*,
                h.depth + 1
            FROM
                chat_logs c
            JOIN ChatHistory h ON c.prev_id = h.id
            WHERE
                h.depth < 100
                AND c.prev_id IS NOT NULL  -- Ensure prev_id is not NULL
                AND h.id IS NOT NULL       -- Ensure h.id is not NULL
                AND c.id IS NOT NULL       -- Ensure c.id is not NULL
        )
        SELECT *
        FROM ChatHistory
        WHERE depth = ? + 1
        LIMIT 1; 
        """
    record = bot.api.query(query, [log_id, n])
    return record[0] if record else None