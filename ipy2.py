from irispy2 import Bot, ChatContext
from irispy2.bot.models import ErrorContext
from bots.gemini import get_gemini
from bots.pyeval import python_eval, real_eval
from bots.stock import create_stock_image
from bots.imagen import get_imagen
from bots.lyrics import get_lyrics, find_lyrics
from bots.replyphoto import reply_photo
from helper.Admin import is_not_banned
from helper.Addon import on_message_chat_addon
from helper.BanControl import ban_user, unban_user
from helper.BotManager import BotManager
from bots.text2image import draw_text
from bots.coin import get_coin_info
import sys

iris_url = sys.argv[1]
bot = BotManager(iris_url).get_current_bot()

@bot.on_event("message")
@is_not_banned
@on_message_chat_addon
def on_message(chat: ChatContext):
    try:
        match chat.message.command:
            
            case "!hhi":
                chat.reply(f"Hello {chat.sender.name}")

            case "!tt" | "!ttt" | "!프사":
                reply_photo(chat)

            #make your own help.png or remove !iris
            case "!iris":
                chat.reply_media("IMAGE", [open("res/help.png", "rb")])

            case "!gi" | "!i2i" | "!분석":
                get_gemini(chat)
            
            case "!ipy":
                python_eval(chat)
            
            case "!iev":
                real_eval(chat)
            
            case "!ban":
                ban_user(chat)
            
            case "!unban":
                unban_user(chat)

            case "!주식":
                create_stock_image(chat)

            case "!ig":
                get_imagen(chat)
            
            case "!가사찾기":
                find_lyrics(chat)

            case "!노래가사":
                get_lyrics(chat)

            case "!텍스트" | "!사진" | "!껄무새" | "!멈춰" | "!지워" | "!진행" | "!말대꾸" | "!텍스트추가":
                draw_text(chat)
            
            case "!코인" | "!내코인" | "!바낸" | "!김프" | "!달러" | "!코인등록" | "!코인삭제":
                get_coin_info(chat)
            
    except Exception as e :
        print(e)
    finally:
        BotManager().close_kv_connection()
        sys.stdout.flush()
            

#입장감지
@bot.on_event("new_member")
def on_newmem(chat: ChatContext):
    #chat.reply(f"Hello {chat.sender.name}")
    pass

#퇴장감지
@bot.on_event("del_member")
def on_delmem(chat: ChatContext):
    #chat.reply(f"Bye {chat.sender.name}")
    pass


@bot.on_event("error")
def on_error(err: ErrorContext):
    print(err.event, "이벤트에서 오류가 발생했습니다", err.exception)
    #sys.stdout.flush()


if __name__ == "__main__":
    bot.run()
