from iris import ChatContext
from iris.bot.models import ErrorContext
from bots.gemini import get_gemini
from bots.pyeval import python_eval, real_eval
from bots.stock import create_stock_image
from bots.imagen import get_imagen
from bots.lyrics import get_lyrics, find_lyrics
from bots.replyphoto import reply_photo
from bots.text2image import draw_text
from bots.coin import get_coin_info
from bots.pdf_summary import get_pdf_summary, extract_pdf_data, auto_pdf_summary
from bots.coinnews import get_coin_news
from bots.youtube_summary import get_youtube_summary, get_youtube_summary_async
from bots.webpage_summary import get_webpage_summary, get_webpage_summary_async

from iris.decorators import *
from helper.BanControl import ban_user, unban_user
from helper import BotManager
from kakaolink import IrisLink

from bots.detect_nickname_change import detect_nickname_change
import sys, threading
import re
import asyncio
import inspect

iris_url = sys.argv[1]
# bot = BotManager(iris_url).get_current_bot()

# 안전하게 이벤트 루프에서 태스크를 실행하는 함수
def safe_create_task(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.create_task(coro)

# chat.reply가 동기/비동기 모두 지원될 때 안전하게 호출하는 함수
def reply_auto(chat, *args, **kwargs):
    reply_func = chat.reply
    if inspect.iscoroutinefunction(reply_func):
        safe_create_task(reply_func(*args, **kwargs))
    else:
        reply_func(*args, **kwargs)

@bot.on_event("message")
@is_not_banned
@on_message_chat_addon
def on_message(chat: ChatContext):
    try:
        # PDF 자동 요약 기능 실행 (명령어 처리 전에 실행)
        auto_pdf_summary(chat)
        
        msg = chat.message.msg.strip()
        # 메시지 전체에서 URL이 어디에 있든 인식 (줄바꿈/띄어쓰기 모두 대응)
        urls = re.findall(r'https?://[^\s]+', msg)
        if urls:
            url = urls[0]
            video_id = None
            import urllib
            try:
                if '/live/' in url:
                    video_id = url.split('/live/')[1].split('?')[0].split('/')[0]
                elif '/shorts/' in url:
                    video_id = url.split('/shorts/')[1].split('?')[0].split('/')[0]
                elif '/watch' in url:
                    m = re.search(r'[?&]v=([^&]+)', url)
                    video_id = m.group(1) if m else None
                elif 'youtu.be/' in url:
                    video_id = url.split('youtu.be/')[1].split('?')[0].split('/')[0]
                elif '/embed/' in url:
                    video_id = url.split('/embed/')[1].split('?')[0].split('/')[0]
                elif '/v/' in url:
                    video_id = url.split('/v/')[1].split('?')[0].split('/')[0]
                elif 'attribution_link' in url:
                    parsed_url = urllib.parse.urlparse(url)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    if 'u' in query_params:
                        inner_url = query_params['u'][0]
                        inner_parsed = urllib.parse.urlparse(inner_url)
                        inner_params = urllib.parse.parse_qs(inner_parsed.query)
                        if 'v' in inner_params:
                            video_id = inner_params['v'][0]
                elif '/playlist' in url:
                    reply_auto(chat, f"⚠️ 재생목록 URL({url})은 현재 요약이 지원되지 않습니다. 개별 동영상 URL을 공유해주세요.")
                    return
                # 유효한 video_id 확인 (11자리 영숫자)
                if video_id and (not re.match(r'^[A-Za-z0-9_-]{11}$', video_id)):
                    if len(video_id) < 5 or len(video_id) > 20:
                        reply_auto(chat, f"⚠️ 유효하지 않은 유튜브 URL 형식입니다: {url}")
                        return
            except Exception:
                video_id = None
            import asyncio
            if video_id:
                try:
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(handle_youtube_summary(chat, url))
                    loop.run_until_complete(task)
                except RuntimeError:
                    asyncio.run(handle_youtube_summary(chat, url))
                return
            else:
                try:
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(handle_webpage_summary(chat, url))
                    loop.run_until_complete(task)
                except RuntimeError:
                    asyncio.run(handle_webpage_summary(chat, url))
                return

        match chat.message.command:
            
            case "!hhi":
                reply_auto(chat, f"Hello {chat.sender.name}")

            case "!tt" | "!ttt" | "!프사" | "!프사링":
                reply_photo(chat, kl)

            #make your own help.png or remove !iris
            case "!iris":
                chat.reply_media([open("res/help.png", "rb")])

            case "!gi" | "!i2i" | "!분석":
                get_gemini(chat)
            
            case "!ipy":
                python_eval(chat)
            
            case "!iev":
                real_eval(chat, kl)
            
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
            
            case "!pdf" | "!요약" | "!pdf요약":
                get_pdf_summary(chat)
            
            case "!pdf추출" | "!pdf데이터":
                extract_pdf_data(chat)
            
            case cmd if cmd.startswith("#뉴스"):
                try:
                    hours_str = cmd[3:].strip()
                    hours = int(hours_str) if hours_str else 1
                    if not (1 <= hours <= 24):
                        reply_auto(chat, "시간은 1~24 사이의 숫자만 입력할 수 있습니다. 예: #뉴스3")
                        return
                    result = get_coin_news(hours)
                    reply_auto(chat, f"{chat.sender.name}님, 최근 {hours}시간 뉴스입니다:\n\n{result}")
                except ValueError:
                    reply_auto(chat, "올바른 숫자를 입력해주세요 (예: #뉴스1, #뉴스3)")
                except Exception as e:
                    reply_auto(chat, f"뉴스 수집 중 오류가 발생했습니다: {str(e)}")
            
    except Exception as e :
        print(e)
    finally:
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

# 웹/유튜브 요약 비동기 처리 함수
async def handle_youtube_summary(chat, url):
    result = await get_youtube_summary_async(url)
    await chat.reply(result)

async def handle_webpage_summary(chat, url):
    result = await get_webpage_summary_async(url)
    await chat.reply(result)

if __name__ == "__main__":
    #닉네임감지를 사용하지 않는 경우 주석처리
    nickname_detect_thread = threading.Thread(target=detect_nickname_change, args=(iris_url,))
    nickname_detect_thread.start()
    #카카오링크를 사용하지 않는 경우 주석처리
    kl = IrisLink(iris_url)
    bot.run()
