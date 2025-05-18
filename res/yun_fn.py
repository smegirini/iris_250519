from datetime import datetime, timedelta
import time
import re
import os
import string
import json
import urllib
import urllib3
import random
import ssl
import logging
import traceback
from socket import *
import subprocess
import http.client
from bs4 import BeautifulSoup as bs
import requests
import mariadb
import google.generativeai as genai
import anthropic
import numpy as np
from collections import Counter
from oauth2client.service_account import ServiceAccountCredentials
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
import logging
import requests
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import googleapiclient.discovery
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
import chromedriver_binary  # 자동으로 PATH에 추가됨
from dotenv import load_dotenv
import gspread

# .env 파일 로드
load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 로깅 설정
logging.basicConfig(
    filename='kakaotalk.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

logger = logging.getLogger(__name__)

# 구글 스프레드시트 설정
KEYFILE_PATH = os.getenv('GOOGLE_SHEET_KEYFILE_PATH')
SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GID = int(os.getenv('GOOGLE_SHEET_GID', 0))

def get_spread_sheet():
    """구글 스프레드시트 연결 및 워크시트 반환"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEYFILE_PATH, scope)
        client = gspread.authorize(creds)
        
        sheet_url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit'
        sheet = client.open_by_url(sheet_url).get_worksheet_by_id(GID)
        return sheet
    except Exception as e:
        logger.error(f"스프레드시트 연결 오류: {str(e)}")
        raise

def insert_link_comment(summary_id: int, room: str, sender: str, comment: str):
    try:
        logging.info(f"Attempting to insert comment for summary #{summary_id}")
        
        query = """
        INSERT INTO link_comments 
        (summary_id, room, sender, comment)
        VALUES (%s, %s, %s, %s)
        """
        params = (summary_id, room, sender, comment)
        
        conn, cur = get_conn()
        cur.execute(query, params)
        comment_id = cur.lastrowid
        conn.commit()
        cur.close()
        conn.close()
        
        logging.info(f"Successfully inserted comment with ID: {comment_id}")
        return comment_id
        
    except Exception as e:
        logging.error(f"Error inserting comment: {str(e)}")
        raise

def get_reply_msg(room: str, sender: str, msg: str, is_group_chat: bool = False, is_mention: bool = False, log_id: str = None, channel_id: str = None, user_hash: str = None):
    try:
        # '도우미' 방에서 '오픈채팅봇'의 메시지 처리
        if room == '도우미' and sender == '오픈채팅봇':
            logger.info(f"'도우미' 방에서 오픈채팅봇 메시지 수신: {msg}")
            
            # 주말 체크 (토요일: 5, 일요일: 6)
            today_weekday = datetime.now().weekday()
            if today_weekday >= 5:  # 주말인 경우
                logger.info(f"주말({today_weekday})로 인해 일정 알림을 전송하지 않습니다.")
                return f"📅 주말({['월','화','수','목','금','토','일'][today_weekday]}요일)로 인해 일정 알림을 전송하지 않습니다."
            
            # '금요일' 키워드 확인 - 알림 키워드와 상관없이 처리
            if '금요일' in msg:
                logger.info(f"'금요일' 키워드 감지: 요일={today_weekday}")
                
                # 실제 금요일인지 확인
                if today_weekday == 4:  # 금요일인 경우
                    logger.info("금요일 메시지 감지: 다음 주 일정 전송")
                    
                    # 다음 주 일정 메시지 생성
                    schedule_msg = check_next_week_schedules()
                    if schedule_msg:
                        # 지정된 방 목록
                        NOTIFICATION_ROOMS = ["2담당"]
                        success = False
                        
                        # 각 지정된 방에 메시지 전송
                        for target_room in NOTIFICATION_ROOMS:
                            try:
                                if send_socket_message(target_room, schedule_msg):
                                    insert_kakaotalk_message(
                                        room=target_room,
                                        sender='Digital Workforce',
                                        msg=schedule_msg,
                                        is_group_chat=False,
                                        is_mention=False,
                                        log_id=None,
                                        channel_id=None,
                                        user_hash=None
                                    )
                                    logger.info(f"다음 주 일정 알림 전송 완료: room={target_room}")
                                    success = True
                                else:
                                    logger.error(f"다음 주 일정 알림 전송 실패: room={target_room}")
                            except Exception as e:
                                logger.error(f"다음 주 일정 알림 전송 중 오류: room={target_room}, error={str(e)}")
                        
                        if success:
                            return f"✅ {len(NOTIFICATION_ROOMS)}개 방에 다음 주 일정 메시지를 전송했습니다."
                        else:
                            return "❌ 다음 주 일정 메시지 전송에 실패했습니다."
                    else:
                        return "❌ 전송할 다음 주 일정 메시지가 없습니다."
                else:
                    # 금요일이 아닌 경우 메시지 반환
                    weekday_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
                    current_weekday = weekday_names[today_weekday]
                    days_to_friday = 4 - today_weekday if today_weekday < 4 else 7 - today_weekday + 4
                    
                    logger.info(f"금요일 메시지 수신했으나 오늘은 {current_weekday}입니다. {days_to_friday}일 후에 금요일입니다.")
                    return f"❌ 오늘은 {current_weekday}입니다. 금요일 메시지는 금요일에만 작동합니다. {days_to_friday}일 후에 다시 시도해주세요."
            
            # '알림' 키워드가 있는 경우 일반 일정 메시지 처리
            if '알림' in msg:
                # 일반 일정 메시지 생성 (기존 로직)
                schedule_msg = check_today_schedules()
                if schedule_msg:
                    # 지정된 방 목록
                    NOTIFICATION_ROOMS = ["2담당"]
                    success = False
                    
                    # 각 지정된 방에 메시지 전송
                    for target_room in NOTIFICATION_ROOMS:
                        try:
                            if send_socket_message(target_room, schedule_msg):
                                insert_kakaotalk_message(
                                    room=target_room,
                                    sender='Digital Workforce',
                                    msg=schedule_msg,
                                    is_group_chat=False,
                                    is_mention=False,
                                    log_id=None,
                                    channel_id=None,
                                    user_hash=None
                                )
                                logger.info(f"일정 알림 전송 완료: room={target_room}")
                                success = True
                            else:
                                logger.error(f"일정 알림 전송 실패: room={target_room}")
                        except Exception as e:
                            logger.error(f"일정 알림 전송 중 오류: room={target_room}, error={str(e)}")
                    
                    if success:
                        return f"✅ {len(NOTIFICATION_ROOMS)}개 방에 일정 메시지를 전송했습니다."
                    else:
                        return "❌ 메시지 전송에 실패했습니다."
                else:
                    return "❌ 전송할 일정 메시지가 없습니다."

        # '#숫자' 패턴 확인
        if msg.startswith('#'):
            try:
                # 숫자 부분 추출
                summary_id = int(msg[1:].split()[0])
                comment = msg[msg.find(' '):].strip() if ' ' in msg else ""
                
                if not comment:
                    # 코멘트가 없으면 해당 요약 정보 조회
                    query = """
                    SELECT s.*, 
                           GROUP_CONCAT(CONCAT('- ', c.sender, ': ', c.comment) SEPARATOR '\n') as comments
                    FROM link_summaries s
                    LEFT JOIN link_comments c ON s.id = c.summary_id
                    WHERE s.id = %s
                    GROUP BY s.id
                    """
                    conn, cur = get_conn()
                    cur.execute(query, (summary_id,))
                    result = cur.fetchone()
                    cur.close()
                    conn.close()
                    
                    if result:
                        id, room, sender, link, title, channel_name, view_count, comment_count, summary, created_at, comments = result
                        
                        response = f"""{summary_id}번 컨텐츠 {'\u200b' * 500} ■공유자: {sender} 

■ 제목: {title}

{summary}

■ 댓글:
{comments if comments else '아직 댓글이 없습니다.'}

원문링크:
{link}"""
                        return response
                    else:
                        return f"❌ #{summary_id} 요약을 찾을 수 없습니다."
                
                else:
                    # 코멘트 저장
                    insert_link_comment(summary_id, room, sender, comment)
                    return f"✅ #{summary_id}에 의견이 등록되었습니다."
                    
            except ValueError:
                return None
            except Exception as e:
                logger.error(f"Error processing comment: {str(e)}")
                return f"❌ 의견 처리 중 오류가 발생했습니다: {str(e)}"
        
        # 일정 관련 명령어 처리
        if msg.startswith('등록 '):
            return register_schedule(room, sender, msg)
        elif msg.startswith('일정 '):
            return get_schedule(room, sender, msg)
        elif msg.startswith('삭제 '):
            return delete_schedule(room, sender, msg)
        
        # URL 처리 로직
        if msg.startswith('http'):
            if 'youtube.com' in msg or 'youtu.be' in msg:
                return summarize(room, sender, msg)
            elif 'blog.naver.com' in msg:
                return blog_summary(room, sender, msg)
            elif 'medium.com' in msg:
                return medium_summary(room, sender, msg)
            else:
                return web_summary(room, sender, msg)
                
    except Exception as e:
        logger.error(f"Error in get_reply_msg: {str(e)}")
        return None

def delete_schedule(room: str, sender: str, msg: str):
    """특정 날짜의 일정을 삭제하는 함수"""
    try:
        # '삭제 250121' 형식의 메시지 파싱
        parts = msg.split()
        if len(parts) != 2:
            return "❌ 올바른 형식이 아닙니다. (예: 삭제 250121)"
            
        date_str = parts[1]
        
        # 날짜 형식 검증 및 변환
        try:
            schedule_date = datetime.strptime(date_str, '%y%m%d').date()
        except ValueError:
            return "❌ 날짜 형식이 올바르지 않습니다. (예: 250121)"
            
        # 삭제 전에 해당 날짜의 일정이 있는지 확인
        check_query = """
        SELECT COUNT(*)
        FROM schedule
        WHERE schedule_date = %s AND sender = %s
        """
        check_params = (schedule_date, sender)
        count = fetch_val(check_query, check_params)
        
        if count == 0:
            return f"❌ {schedule_date}에 등록된 일정이 없습니다."
            
        # DB에서 해당 날짜의 일정 삭제
        query = """
        DELETE FROM schedule
        WHERE schedule_date = %s AND sender = %s
        """
        params = (schedule_date, sender)
        
        execute(query, params)
        
        return f"✅ {sender}님의 {schedule_date} 일정이 삭제되었습니다."
        
    except Exception as e:
        logger.error(f"일정 삭제 중 오류 발생: {str(e)}")
        return f"❌ 일정 삭제 중 오류가 발생했습니다: {str(e)}"


def insert_link_summary(room: str, sender: str, link: str, title: str, channel_name: str, view_count: int, comment_count: int, summary: str):
    try:
        logging.info(f"Attempting to insert link summary: {link}")
        
        query = """
        INSERT INTO link_summaries 
        (room, sender, link, title, channel_name, view_count, comment_count, summary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (room, sender, link, title, channel_name, view_count, comment_count, summary)
        
        logging.info(f"Parameters: {params}")
        
        # 실행 후 삽입된 ID 반환
        conn, cur = get_conn()
        cur.execute(query, params)
        inserted_id = cur.lastrowid  # 새로 삽입된 행의 ID
        conn.commit()
        cur.close()
        conn.close()
        
        logging.info(f"Successfully inserted link summary with ID: {inserted_id}")
        return inserted_id
        
    except Exception as e:
        logging.error(f"Error inserting link summary: {str(e)}")
        logging.error(f"Parameters that caused error: {params}")
        raise


def extract_youtube_id(url):
    # 정규 표현식 패턴 정의
    pattern = re.compile(r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:&|\/|$)')
    
    # 정규 표현식 검색
    match = pattern.search(url)
    
    # 매치된 경우 비디오 ID 반환, 그렇지 않으면 None 반환
    if match:
        return match.group(1)
    return None


# API 키 설정
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

def get_video_details(video_id):
    """YouTube Data API를 사용하여 비디오 상세 정보를 가져옵니다."""
    api_service_name = "youtube"
    api_version = "v3"
    DEVELOPER_KEY = YOUTUBE_API_KEY

    youtube = googleapiclient.discovery.build(
        api_service_name, api_version, developerKey=DEVELOPER_KEY
    )

    request = youtube.videos().list(
        part="snippet,statistics",
        id=video_id
    )
    response = request.execute()
    return response

def get_transcript(video_id):
    """자막을 가져옵니다."""
    try:
        # 한국어 자막 시도
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
        return transcript_list
    except (NoTranscriptFound, TranscriptsDisabled):
        logger.error(f"Korean transcript not found for video_id {video_id}")
        try:
            # 영어 자막 시도
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            return transcript_list
        except Exception as e:
            logger.error(f"Transcript processing error: {e}")
            return None

def generate_summary1(text):
    """Gemini API를 사용하여 영어 자막을 한국어로 번역하고 요약합니다."""

    prompt = f"""제공된 영상 대본의 제목이나 내용을 다음 작성 형식과 작성 지침을 반영해서 출력 하세요 ;
 

-----  작성 형식 -----   

■ 영상 요약
[7~10 문장으로 된 전체적인 내용, 기사의 목적]

■ 주요 인사이트
1. [주요 인사이트1, 1문장으로]
 - [1~3문장으로, 독자에게 주는 중요한 메시지, 해당 주제와 관련된 중요한 정보, 조언, 교훈]
2. [주요 인사이트2, 1문장으로]
 - [1~3문장으로, 독자에게 주는 중요한 메시지, 해당 주제와 관련된 중요한 정보, 조언, 교훈]
 
-----  작성 지침 -----
1. 결과물은 마크다운 문법을 사용하지 마세요. 
2. 글 전체 분량은 절대 500자가 넘지 않아야 합니다. 
3. 제공된 자막이나 내용만을 바탕으로 요약하세요. 추측하거나 외부 정보를 추가 하지 마세요. 
4. 내용이 길어 인사이트 추가가 필요할시 동일 양식으로 최대 5개 까지 추가 가능.
영어 자막:
{text}
"""



    try:
        api_key = os.getenv('GEMINI_API_KEY')
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise e

def summarize(room: str, sender: str, msg: str):
    url = msg.strip()

    # URL에서 video_id 추출 - 다양한 형태의 유튜브 URL 처리
    video_id = None
    
    # 정규표현식으로 패턴 추출을 시도
    try:
        # 라이브 스트림 형식 (https://www.youtube.com/live/VIDEO_ID)
        if '/live/' in url:
            video_id = url.split('/live/')[1].split('?')[0].split('/')[0]
        
        # 쇼츠 형식 (https://www.youtube.com/shorts/VIDEO_ID)
        elif '/shorts/' in url:
            video_id = url.split('/shorts/')[1].split('?')[0].split('/')[0]
        
        # 표준 watch 형식 (https://www.youtube.com/watch?v=VIDEO_ID)
        elif '/watch' in url:
            video_id = re.search(r'[?&]v=([^&]+)', url)
            video_id = video_id.group(1) if video_id else None
        
        # 단축 URL 형식 (https://youtu.be/VIDEO_ID)
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0].split('/')[0]
        
        # 임베디드 형식 (https://www.youtube.com/embed/VIDEO_ID)
        elif '/embed/' in url:
            video_id = url.split('/embed/')[1].split('?')[0].split('/')[0]
        
        # 채널 내 영상 형식 (https://www.youtube.com/v/VIDEO_ID)
        elif '/v/' in url:
            video_id = url.split('/v/')[1].split('?')[0].split('/')[0]
        
        # 애널리틱스 형식 (https://www.youtube.com/attribution_link?a=VIDEO_ID)
        elif 'attribution_link' in url:
            parsed_url = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            if 'u' in query_params:
                inner_url = query_params['u'][0]
                inner_parsed = urllib.parse.urlparse(inner_url)
                inner_params = urllib.parse.parse_qs(inner_parsed.query)
                if 'v' in inner_params:
                    video_id = inner_params['v'][0]
        
        # 재생목록 형식 - 첫 번째 비디오 ID 추출 (https://www.youtube.com/playlist?list=PLAYLIST_ID)
        elif '/playlist' in url:
            # 재생목록의 경우 첫 번째 비디오 ID를 추출하는 것은 복잡하므로
            # API를 통해 처리하거나 별도로 처리해야 함
            logger.warning(f"재생목록 URL 감지됨: {url}. 재생목록 요약은 지원되지 않습니다.")
            return f"⚠️ 재생목록 URL({url})은 현재 요약이 지원되지 않습니다. 개별 동영상 URL을 공유해주세요."
            
        # 유효한 video_id 확인 (11자리 영숫자) - 대부분의 유튜브 ID는 11자리
        if video_id and (not re.match(r'^[A-Za-z0-9_-]{11}$', video_id)):
            # 11자리가 아닌 경우는 대부분 잘못된 ID이거나 특수한 경우
            # 그러나 일부 라이브 스트림이나 특수 영상은 다른 길이를 가질 수 있음
            logger.warning(f"비표준 video_id 형식 감지: {video_id} (URL: {url})")
            # ID가 너무 길거나 짧으면 의심스럽지만, 처리는 시도
            if len(video_id) < 5 or len(video_id) > 20:
                logger.error(f"유효하지 않은 video_id: {video_id} (URL: {url})")
                return f"⚠️ 유효하지 않은 유튜브 URL 형식입니다: {url}"
    
    except Exception as e:
        logger.error(f"URL 파싱 오류: {str(e)} (URL: {url})")
        return f"⚠️ URL 처리 중 오류가 발생했습니다: {url}"
    
    # video_id를 추출하지 못한 경우
    if not video_id:
        logger.error(f"지원되지 않는 YouTube URL 형식: {url}")
        return f"⚠️ 지원되지 않는 유튜브 URL 형식입니다: {url}"

    # 기본 응답 데이터
    title = None
    channel_name = None
    view_count = None
    comment_count = None
    summary = None

    # YouTube Data API를 사용하여 비디오 정보 가져오기
    try:
        video_data = get_video_details(video_id)
        if 'items' in video_data and len(video_data['items']) > 0:
            item = video_data['items'][0]
            title = item['snippet']['title']
            channel_name = item['snippet']['channelTitle']
            view_count = int(item['statistics'].get('viewCount', 0))
            comment_count = int(item['statistics'].get('commentCount', 0))
        else:
            return f"❌ 영상 정보를 가져오지 못했습니다. (video_id: {video_id})"
    except Exception as e:
        logger.error(f"Video details fetch error: {e} (video_id: {video_id})")
        return f"❌ 영상 정보를 가져오지 못했습니다: {str(e)}"

    # 자막 가져오기
    transcript_list = get_transcript(video_id)
    if transcript_list:
        text = " ".join([item['text'] for item in transcript_list])
        max_length = 4096
        if len(text) > max_length:
            text = text[:max_length]

        try:
            summary = generate_summary1(text)
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            summary = "❌ 요약 생성 중 문제가 발생했습니다."
    else:
        # 자막이 없는 경우, 제목과 채널 정보만 표시
        summary = "❌ 자막 정보가 없어 요약을 생성할 수 없습니다."

    # DB에 저장
    try:
        # DB에 저장하고 ID 받기
        summary_id = insert_link_summary(
            room=room,
            sender=sender,
            link=url,
            title=title,
            channel_name=channel_name,
            view_count=view_count,
            comment_count=comment_count,
            summary=summary
        )
        
        send_msg = f"""■ {sender} / #{summary_id}

■ 제목 
{title}
* 채널: {channel_name}
* 조회수: {view_count} / 댓글수: {comment_count}

{summary}

원문링크:
{url}"""
        logger.info(f"Returning message: {send_msg[:100]}...")
        return send_msg
        
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        # DB 저장 실패해도 계속 진행
        send_msg = f"""■ {sender}

■ 제목 
{title}
* 채널: {channel_name}
* 조회수: {view_count} / 댓글수: {comment_count}

{summary}

원문링크:
{url}"""
        return send_msg


    
    

class TextProcessor:
    @staticmethod
    def extract_text_from_html(html: str) -> str:
        """HTML 컨텐츠에서 깔끔한 텍스트를 추출합니다."""
        soup = bs(html, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text(separator='\n', strip=True)

def extract_url(text: str):
    """텍스트에서 URL을 추출합니다."""
    url_pattern = r'(https?://[^\s]+)'
    urls = re.findall(url_pattern, text)
    return urls[0] if urls else None

def web_summary(room: str, sender: str, msg: str):
    try:
        # URL 추출
        url = extract_url(msg)
        
        if not url:
            return None
        
        # Medium 사이트 특별 처리
        if 'medium.com' in url:
            return medium_summary(room, sender, url)
            
        # Selenium 설정 - Windows 환경에 맞게 수정
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        
        try:
            # chromedriver_binary 사용 (자동으로 PATH에 추가됨)
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            time.sleep(3)  # 페이지 로딩 대기
            
            # 렌더링된 페이지에서 텍스트 추출
            soup = bs(driver.page_source, 'html.parser')
            title = soup.find('title')
            title = title.text.strip() if title else "제목 없음"
            
            # HTML에서 텍스트 추출
            text = TextProcessor.extract_text_from_html(driver.page_source)
            
            # 기존 프롬프트 사용
            prompt = f"""제공된 웹페이지 제목이나 내용을 다음 작성 형식과 작성 지침을 반영해서 출력하세요:

-----  작성 형식 -----   
■ 기사 요약
[7~10 문장으로 된 전체적인 내용, 기사의 목적]

■ 주요 인사이트
1. [주요 인사이트1, 1문장으로]
 - [1~3문장으로, 독자에게 주는 중요한 메시지]
2. [주요 인사이트2, 1문장으로]
 - [1~3문장으로, 독자에게 주는 중요한 메시지]

-----  작성 지침 -----
1. 결과물은 마크다운 문법을 사용하지 마세요.
2. 글 전체 분량은 절대 500자가 넘지 않아야 합니다.
3. 제공된 내용만을 바탕으로 요약하세요.
4. 내용이 길어 인사이트 추가가 필요할시 동일 양식으로 최대 5개 까지 추가 가능.

기사 제목: {title}
{text}
"""
        
            try:
                # 기존 LLM 호출 방식 사용
                api_key = os.getenv('GEMINI_API_KEY')
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                response = model.generate_content(prompt)
                summary = response.text
                
                # DB에 저장
                try:
                    summary_id = insert_link_summary(
                        room=room,
                        sender=sender,
                        link=url,
                        title=title,
                        channel_name="",
                        view_count=0,
                        comment_count=0,
                        summary=summary
                    )
                    
                    send_msg = f"""■ {sender} / #{summary_id}

■ 제목 : {title}
{summary}

원문링크 :
{url.strip()}"""
                    
                except Exception as e:
                    # DB 저장 실패시 요약번호 없이 출력
                    send_msg = f"""■ {sender}
            
■ 제목 : {title}
{summary}

■원문링크 :
{url.strip()}"""

                logger.info(f"Returning message: {send_msg[:100]}...")
                return send_msg
                
            except Exception as e:
                return f"요약 생성 중 오류가 발생했습니다: {str(e)}"
            
        finally:
            if 'driver' in locals():
                driver.quit()
        
    except Exception as e:
        log(f"web_summary 오류: {traceback.format_exc()}")
        return f"{sender}님, 요약 처리 중 오류가 발생했습니다: {str(e)}"


def my_talk_analyize(room: str, sender: str, msg: str):

    conn, cur = get_conn()

    query =f"""
SELECT msg
FROM kt_message
WHERE 
	room = %s
	AND sender = %s
ORDER BY ID DESC 
LIMIT 500
"""
    params = (room, sender)
    cur.execute(query, params)
    rows = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # 수다쟁이들의 메세지를 바탕으로 성격 분석하기
    text = ''
    for row in rows:
        text += f"{row[0]}\n"
    
    system = '''다음은 메신저에서 한 사람이 작성했던 최근 대화 메세지 목록입니다.
    메세지들을 분석하여 작성자의 성격, 말투, 좋아하는 것, 싫어하는 것을 분석해주세요.
    각 항목별로 분석근거가 무엇인지 메세지의 일부를 예시로 작성해주세요
    

[출력 양식]
1. 성격
- 
예시)

2. 말투
-
예시)

3. 좋아하는 것
-
예시)

4. 싫어하는 것
-
예시)
'''
    prompt = f'###메세지###\n{text}'
    try:
        answer = gemini20_flash(system="대화 분석을 위한 시스템", prompt=prompt)
        if not answer:
            return "죄송합니다. 대화 분석에 실패했습니다 😢"
            
        send_msg = f"🔮 {sender}님의 대화 분석 결과\n\n{answer}"
        return send_msg
        
    except Exception as e:
        logger.error(f"대화 분석 오류: {str(e)}")
        return "죄송합니다. 대화 분석 중 오류가 발생했습니다 😢"


def talk_analyize(room: str, sender: str, msg: str, interval_day: int = 0):
    dt_text = "오늘" if interval_day == 0 else "어제"
    
    try:
        # DB에서 데이터 가져오기
        conn, cur = get_conn()
        
        query = """
        SELECT sender, COUNT(*) AS cnt
        FROM kt_message 
        WHERE room = %s
            AND DATE(created_at) = CURDATE() + %s
            AND sender NOT IN ('윤봇', '오픈채팅봇', '팬다 Jr.','Digital Workforce')
        GROUP BY sender
        ORDER BY cnt desc
        LIMIT 10
        """
        params = (room, interval_day)
        cur.execute(query, params)
        rows = cur.fetchall()
        
        if len(rows) == 0:
            return f"{dt_text} 대화가 없었어요😥"
        
        # 대화 내용 수집
        text = ''
        for row in rows:
            text += f"닉네임: {row[0]}\n메시지 수: {row[1]}\n\n"
        
        prompt = f"""다음은 {dt_text}의 대화 참여자 통계입니다. 각 사람의 대화 참여도를 분석해주세요:

{text}

분석 결과를 친근하고 재미있게 작성해주세요. 이모티콘도 적절히 사용해주세요."""

        # Gemini로 시도
        answer = gemini20_flash(system="대화 분석을 위한 시스템", prompt=prompt)
        
                # 둘 다 실패시
        if not answer:
            return "죄송합니다. 대화 분석에 실패했습니다 😢"
            
        send_msg = f"🔮 {dt_text}의 수다왕 분석\n\n{answer}"
        return send_msg
        
    except Exception as e:
        print(f"Error in talk_analyize: {str(e)}")
        return "죄송합니다. 대화 분석 중 오류가 발생했습니다 😢"
    finally:
        if 'conn' in locals():
            conn.close()





def talk_rank(room: str, sender: str, msg: str, interval_day):
    query = "CALL proc_talk_rank(?, ?)"
    params = (room, interval_day)
    rows = fetch_all(query, params)

    content = []
    total_count = 0
    for row in rows[:19]:
        rank = row[0]
        sender = row[1]
        cnt = row[2]
        rate = row[3]

        if rank in [1, 2, 3]:
            text = f"[{rank}위] {sender} {str(cnt)}개({rate})"
        else:
            text = f"{rank}. {sender} {str(cnt)}개({rate})"
        content.append(text)
        total_count += cnt

    day = "오늘" if interval_day == 0 else "어제"
    send_msg = f"💬{day} {str(total_count)}개의 대화가 있었어요\n\n"
    send_msg += "\n".join(content)
    # send_msg += '\n' + word_cloud(room, sender, msg, interval_day, '')
    return send_msg



def exchange(room: str, sender: str, msg: str):
    url = "https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW"
    soup = request(url, method="get", result="bs")

    today = soup.select_one(".no_today").get_text().replace("원", "").strip()
    date = soup.select_one(".date").get_text().replace(".", "/")

    return f"""💲실시간 환율💰
👉{today}원👈
기준일시:{date}"""




# ==================================================
# Common Functions
# ==================================================

def insert_kakaotalk_message(room, sender, msg, is_group_chat, is_mention, log_id, channel_id, user_hash):
    """카카오톡 메시지를 DB에 저장하는 함수"""
    try:
        conn, cur = get_conn()
        query = """
            INSERT INTO kakaotalk_message 
            (room, sender, msg, is_group_chat, is_mention, log_id, channel_id, user_hash, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        params = (room, sender, msg, is_group_chat, is_mention, log_id, channel_id, user_hash)
        
        cur.execute(query, params)
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Message saved to DB - room: {room}, sender: {sender}, msg: {msg[:50]}...")
    except mariadb.Error as e:
        logger.error(f"MariaDB Error: {e}")
        raise
    except Exception as e:
        logger.error(f"DB 저장 중 오류 발생: {str(e)}")
        raise

def request(url, method='get', result='text', params=None, data=None, json=None, headers=None, cookies=None):
    context = ssl._create_unverified_context()
    response = requests.request(
        method, url, params=params, data=data, json=json,
        headers=headers, cookies=cookies, verify=False, timeout=10
    )
    if result.lower() == 'text':
        return response.text
    elif result.lower() == 'json':
        return response.json()
    elif result.lower() == 'bs':
        return bs(response.text, 'html.parser')

def execute(sql, params = None):
    conn, cur = get_conn()
    cur.execute(sql, params)
    cur.close()
    conn.close()

def fetch_val(sql, params = None):
    conn, cur = get_conn()
    cur.execute(sql, params)
    result = cur.fetchone()[0]
    cur.close()
    conn.close()
    return result

def fetch_one(sql, params = None):
    conn, cur = get_conn()
    cur.execute(sql, params)
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def fetch_all(sql, params = None):
    conn, cur = get_conn()
    cur.execute(sql, params)
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result

def get_conn():
    conn = mariadb.connect(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT', 3306)),
        database=os.getenv('DB_NAME'),
        autocommit=True
    )
    cur = conn.cursor()
    return conn, cur


def log(text):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], text)
    logging.info(text)

def blog_summary(room: str, sender: str, msg: str):
    try:
        logger.info(f"Starting blog_summary with URL: {msg}")
        url = msg.strip()
        
        # 네이버 블로그 iframe URL 변환
        if 'blog.naver.com' in url:
            logger.info("Converting blog URL to iframe URL...")
            # 블로그 글 번호 추출
            blog_id = url.split('blog.naver.com/')[1].split('/')[0]
            post_id = url.split('/')[-1]
            if '?' in post_id:
                post_id = post_id.split('?')[0]
            iframe_url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={post_id}&redirect=Dlog"
            url = iframe_url
        
        logger.info("Requesting webpage...")
        soup = request(url, 'get', 'bs')
        logger.info("Webpage received")
        
        logger.info("Extracting title...")
        # 네이버 블로그 제목 추출
        title_element = soup.find('div', {'class': 'se-module se-module-text se-title-text'})
        if title_element:
            title = title_element.get_text(strip=True)
        else:
            # 백업 제목 검색
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text
            else:
                title = "제목 없음"
        
        logger.info(f"Title extracted: {title}")
        
        logger.info("Extracting body text...")
        # 네이버 블로그 본문 추출
        content_element = soup.find('div', {'class': 'se-main-container'})
        if content_element:
            body_text = content_element.get_text(separator='\n', strip=True)[:10000]
        else:
            # 구버전 블로그 형식 시도
            content_element = soup.find('div', {'class': 'post-view'})
            if content_element:
                body_text = content_element.get_text(separator='\n', strip=True)[:10000]
            else:
                body_text = ""
        logger.info("Body text extracted")

        logger.info("Generating summary...")
        prompt = f"""제공된 블로그 포스트의 제목이나 내용을 다음 작성 형식과 작성 지침을 반영해서 출력 하세요 ;

-----  작성 형식 -----   
■ 기사 요약
[7~10 문장으로 된 전체적인 내용, 글의 목적]

■ 주요 포인트
1. [주요 포인트1, 1문장으로]
 - [1~3문장으로, 독자에게 주는 중요한 메시지나 정보]
2. [주요 포인트2, 1문장으로]
 - [1~3문장으로, 독자에게 주는 중요한 메시지나 정보]
 
-----  작성 지침 -----
1. 결과물은 마크다운 문법을 사용하지 마세요. 
2. 글 전체 분량은 절대 500자가 넘지 않아야 합니다. 
3. 제공된 내용만을 바탕으로 요약하세요. 추측하거나 외부 정보를 추가 하지 마세요. 
4. 내용이 길어 인사이트 추가가 필요할시 동일 양식으로 최대 5개 까지 추가 가능.

블로그 제목: {title}
{body_text}
"""
        
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content(prompt)
            summary = response.text
            logger.info("Summary generated successfully")
            
            # DB에 저장하고 ID 받기
            try:
                logger.info("Saving to database...")
                summary_id = insert_link_summary(
                    room=room,
                    sender=sender,
                    link=url,
                    title=title,
                    channel_name="",
                    view_count=0,
                    comment_count=0,
                    summary=summary
                )
                logger.info("Saved to database successfully")
                send_msg = f"""■ {sender} / #{summary_id}

■ 제목
{summary}

■ 원문링크 :
{url.strip()}"""
            except Exception as e:
                logger.error(f"DB 저장 오류: {str(e)}")
                # DB 저장 실패시 요약번호 없이 출력
                send_msg = f"""■ {sender}
            
■ 제목 : {title}
{summary}

■원문링크 :
{url.strip()}"""

            logger.info(f"Returning message: {send_msg[:100]}...")
            return send_msg
            
        except Exception as e:
            logger.error(f"AI Summary generation error: {str(e)}")
            return f"요약 생성 중 오류가 발생했습니다: {str(e)}"
            
    except Exception as e:
        logger.error(f"Blog summary error: {str(e)}")
        return f"블로그 처리 중 오류가 발생했습니다: {str(e)}"

def medium_summary(room: str, sender: str, url: str):
    try:
        logger.info(f"시작: Medium 아티클 처리 - {url}")
        
        # Windows 환경에 맞는 Selenium 설정 - 더 많은 옵션 추가
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # 봇 감지 우회를 위한 추가 설정
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--lang=ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7')
        chrome_options.add_argument('--start-maximized')
        
        # 추가 성능 최적화 설정
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-setuid-sandbox')
        
        # 쿠키 허용
        chrome_options.add_argument('--enable-cookies')
        
        MAX_RETRIES = 2  # 최대 재시도 횟수
        driver = None
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Medium 페이지 접근 시도 #{attempt+1}")
                
                # chromedriver_binary 사용 (자동으로 PATH에 추가됨)
                driver = webdriver.Chrome(options=chrome_options)
                
                # 봇 탐지 속성 무효화
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # 사용자 에이전트 설정
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'})
                
                # 타임아웃 설정
                driver.set_page_load_timeout(30)
                
                # 페이지 로드
                driver.get(url)
                logger.info("Medium 페이지 초기 로드 완료")
                
                # 충분한 로딩 시간 제공
                time.sleep(5)
                
                # 스크롤 동작 추가 - 실제 사용자 행동 시뮬레이션
                for scroll in range(3):
                    # 랜덤하게 스크롤 (사람처럼 보이기 위해)
                    scroll_height = random.randint(300, 500)
                    driver.execute_script(f"window.scrollBy(0, {scroll_height});")
                    time.sleep(random.uniform(0.5, 1.5))  # 랜덤 지연
                
                # 페이지 전체 높이로 스크롤
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(1.5)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1.5)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # 팝업 처리
                try:
                    # 여러 유형의 팝업 버튼 찾기 시도
                    popup_selectors = [
                        'button[data-testid="close-button"]',
                        'button.close-button',
                        'div.overlay-dialog button',
                        'div.overlay button',
                        'button[aria-label="close"]',
                        'button.dismiss'
                    ]
                    
                    for selector in popup_selectors:
                        buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                        if buttons:
                            logger.info(f"팝업 버튼 발견: {selector}")
                            buttons[0].click()
                            time.sleep(1.5)
                            break
                except Exception as e:
                    logger.warning(f"팝업 처리 중 오류 (무시됨): {str(e)}")
                
                # 페이지 소스 가져오기
                page_source = driver.page_source
                
                # 봇 감지 여부 확인
                bot_detection_phrases = [
                    "잠시만 기다리십시오",
                    "사람인지 확인",
                    "Please wait",
                    "human verification",
                    "You're not a robot, right?",
                    "bot check"
                ]
                
                is_bot_detected = any(phrase in page_source for phrase in bot_detection_phrases)
                
                if is_bot_detected and attempt < MAX_RETRIES - 1:
                    logger.warning(f"봇 감지됨, 재시도 #{attempt+1}")
                    if driver:
                        driver.quit()
                    time.sleep(3)  # 재시도 전 대기
                    continue
                
                soup = bs(page_source, 'html.parser')
                
                # 다양한 방법으로 제목 추출 시도
                title = None
                
                # 메타 태그에서 제목 검색
                meta_title = soup.find('meta', {'property': 'og:title'})
                if meta_title and meta_title.get('content'):
                    title = meta_title.get('content')
                    logger.info(f"메타 태그에서 제목 추출: {title}")
                
                # h1 태그에서 제목 검색
                if not title:
                    h1_tags = soup.find_all('h1')
                    for h1 in h1_tags:
                        if h1.text.strip() and len(h1.text.strip()) > 5:
                            title = h1.text.strip()
                            logger.info(f"H1 태그에서 제목 추출: {title}")
                            break
                
                # Medium 특정 클래스에서 제목 검색
                if not title:
                    title_candidates = [
                        soup.select_one('h1[data-testid="article-title"]'),
                        soup.select_one('h1.pw-post-title'),
                        soup.select_one('h1.article-title')
                    ]
                    
                    for candidate in title_candidates:
                        if candidate and candidate.text.strip():
                            title = candidate.text.strip()
                            logger.info(f"특정 클래스에서 제목 추출: {title}")
                            break
                
                # 최종 대안
                if not title or len(title) < 5:
                    title = url.split('/')[-1].replace('-', ' ').title()
                    logger.info(f"URL에서 제목 추출: {title}")
                
                # 내용 추출 시도
                article_text = ""
                
                # 1. article 태그 찾기
                article = soup.find('article')
                if article:
                    # 스크립트와 스타일 태그 제거
                    for script in article(["script", "style"]):
                        script.decompose()
                    article_text = article.get_text(separator='\n', strip=True)
                    logger.info("Article 태그에서 내용 추출")
                
                # 2. Medium 특정 섹션 찾기
                if not article_text or len(article_text) < 100:
                    content_selectors = [
                        'section[data-testid="article-body-section"]',
                        'div.section-content',
                        'div.postArticle-content',
                        'div[data-field="body"]'
                    ]
                    
                    for selector in content_selectors:
                        sections = soup.select(selector)
                        if sections:
                            article_text = '\n'.join([section.get_text(separator='\n', strip=True) for section in sections])
                            logger.info(f"선택자 {selector}에서 내용 추출")
                            break
                
                # 3. 일반 텍스트 추출
                if not article_text or len(article_text) < 100:
                    # 전체 본문 영역 선택
                    main_content = soup.find('main')
                    if main_content:
                        article_text = main_content.get_text(separator='\n', strip=True)
                        logger.info("Main 태그에서 내용 추출")
                
                # 4. 마지막 대안 - 전체 페이지에서 추출
                if not article_text or len(article_text) < 100:
                    article_text = TextProcessor.extract_text_from_html(page_source)
                    logger.info("전체 페이지에서 내용 추출")
                
                # 내용이 있는지 최종 확인
                if not article_text or len(article_text.strip()) < 100 or is_bot_detected:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"내용 불충분, 재시도 #{attempt+1}")
                        if driver:
                            driver.quit()
                        time.sleep(3)  # 재시도 전 대기
                        continue
                    else:
                        # 대체 메시지 생성
                        logger.error("Medium 아티클 내용을 가져오지 못했습니다")
                        
                        # Medium URL에서 제목과 주제 파싱 시도
                        url_parts = url.split('/')
                        if len(url_parts) > 5:
                            possible_topic = url_parts[4] if len(url_parts) > 4 else ""
                            possible_title = url_parts[-1].replace('-', ' ').title()
                            
                            fallback_text = f"""
Medium 아티클 "{possible_title}"은(는) 접근 제한으로 인해 직접 내용을 가져올 수 없습니다.

■ 접근 제한 이유
- Medium의 봇 감지 시스템이 자동 접근을 차단했습니다.
- 해당 콘텐츠는 로그인이 필요하거나 유료 콘텐츠일 수 있습니다.

■ 접근 방법
- 웹 브라우저에서 직접 URL을 방문해 보세요.
- 로그인이 필요한 경우 Medium 계정으로 로그인하세요.

주제 분야: {possible_topic.replace('-', ' ').title() if possible_topic else "알 수 없음"}
"""
                            # DB에 저장
                            try:
                                summary_id = insert_link_summary(
                                    room=room,
                                    sender=sender,
                                    link=url,
                                    title=title,
                                    channel_name="",
                                    view_count=0,
                                    comment_count=0,
                                    summary=fallback_text
                                )
                                
                                send_msg = f"""■ {sender} / #{summary_id}

■ Medium 접근 제한 콘텐츠
{fallback_text}

원문링크 :
{url.strip()}"""
                                
                                return send_msg
                                
                            except Exception as e:
                                logger.error(f"DB 저장 오류: {str(e)}")
                                return f"Medium 아티클 '{possible_title}'에 접근할 수 없습니다. 직접 브라우저에서 확인해보세요: {url}"
                
                # 내용이 충분하면 Gemini API로 요약
                logger.info("요약 생성 시작")
                prompt = f"""제공된 Medium 아티클의 제목과 내용을 다음 작성 형식과 작성 지침을 반영해서 출력하세요:

-----  작성 형식 -----   
■ 기사 요약
[7~10 문장으로 된 전체적인 내용, 기사의 목적]

■ 주요 인사이트
1. [주요 인사이트1, 1문장으로]
 - [1~3문장으로, 독자에게 주는 중요한 메시지]
2. [주요 인사이트2, 1문장으로]
 - [1~3문장으로, 독자에게 주는 중요한 메시지]

-----  작성 지침 -----
1. 결과물은 마크다운 문법을 사용하지 마세요.
2. 글 전체 분량은 절대 500자가 넘지 않아야 합니다.
3. 제공된 내용만을 바탕으로 요약하세요.
4. 내용이 길어 인사이트 추가가 필요할시 동일 양식으로 최대 5개 까지 추가 가능.

기사 제목: {title}
기사 내용:
{article_text[:8000]}  # 너무 긴 내용은 자르기
"""
                
                # Gemini API 호출
                api_key = os.getenv('GEMINI_API_KEY')
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                response = model.generate_content(prompt)
                summary = response.text
                logger.info("요약 생성 완료")
                
                # DB에 저장
                try:
                    summary_id = insert_link_summary(
                        room=room,
                        sender=sender,
                        link=url,
                        title=title,
                        channel_name="",
                        view_count=0,
                        comment_count=0,
                        summary=summary
                    )
                    
                    send_msg = f"""■ {sender} / #{summary_id}

■ 제목 : {title}
{summary}

원문링크 :
{url.strip()}"""
                    logger.info("요약 메시지 생성 완료")
                    break  # 성공했으므로 반복 중단
                    
                except Exception as e:
                    logger.error(f"DB 저장 오류: {str(e)}")
                    # DB 저장 실패시 요약번호 없이 출력
                    send_msg = f"""■ {sender}
            
■ 제목 : {title}
{summary}

■원문링크 :
{url.strip()}"""
                    break  # 계속 진행
                
            except Exception as e:
                logger.error(f"Medium 처리 중 오류 발생 (시도 #{attempt+1}): {str(e)}")
                if driver:
                    driver.quit()
                driver = None
                
                # 마지막 시도가 아니면 재시도
                if attempt < MAX_RETRIES - 1:
                    time.sleep(3)  # 재시도 전 대기
                else:
                    # 모든 시도 실패 시
                    return f"Medium 아티클 처리 중 오류가 발생했습니다. 직접 브라우저에서 확인해보세요: {url}"
            
        return send_msg
            
    except Exception as e:
        logger.error(f"Medium 요약 중 예상치 못한 오류: {str(e)}")
        return f"Medium 아티클 요약 중 오류가 발생했습니다: {str(e)}"
        
    finally:
        # 드라이버 정리
        if 'driver' in locals() and driver:
            try:
                driver.quit()
                logger.info("Chrome 드라이버 정리 완료")
            except:
                pass

def gemini20_flash(system: str, prompt: str):
    """Gemini 2.0 Flash 모델을 사용한 응답 생성"""
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        full_prompt = f"{system}\n\n{prompt}"
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        return None

def register_schedule(room: str, sender: str, msg: str):
    """일정을 등록하는 함수"""
    try:
        # '등록 250121 연차' 형식의 메시지 파싱
        parts = msg.split()
        if len(parts) < 3:
            return "❌ 올바른 형식이 아닙니다. (예: 등록 250121 연차)"
            
        date_str = parts[1]
        content = ' '.join(parts[2:])  # 세 번째 단어부터 끝까지를 내용으로
        
        # 날짜 형식 검증 및 변환
        try:
            schedule_date = datetime.strptime(date_str, '%y%m%d').date()
        except ValueError:
            return "❌ 날짜 형식이 올바르지 않습니다. (예: 250121)"
            
        # DB에 저장
        query = """
        INSERT INTO schedule (sender, schedule_date, content)
        VALUES (%s, %s, %s)
        """
        params = (sender, schedule_date, content)
        
        execute(query, params)
        
        response = f"✅ {sender}님의 일정이 등록되었습니다.\n📅 날짜: {schedule_date}\n📝 내용: {content}"
        # 직접 메시지 전송하지 않고 응답만 반환
        return response
        
    except Exception as e:
        logger.error(f"일정 등록 중 오류 발생: {str(e)}")
        return f"❌ 일정 등록 중 오류가 발생했습니다: {str(e)}"

def get_schedule(room: str, sender: str, msg: str):
    """특정 날짜의 일정을 조회하는 함수"""
    try:
        # '일정 250121' 형식의 메시지 파싱
        parts = msg.split()
        if len(parts) != 2:
            return "❌ 올바른 형식이 아닙니다. (예: 일정 250121)"
            
        date_str = parts[1]
        
        # 날짜 형식 검증 및 변환
        try:
            schedule_date = datetime.strptime(date_str, '%y%m%d').date()
        except ValueError:
            return "❌ 날짜 형식이 올바르지 않습니다. (예: 250121)"
            
        # DB에서 해당 날짜의 일정 조회
        query = """
        SELECT sender, content
        FROM schedule
        WHERE schedule_date = %s
        ORDER BY sender
        """
        params = (schedule_date,)
        
        rows = fetch_all(query, params)
        
        if not rows:
            return f"📅 {schedule_date}에 등록된 일정이 없습니다."
            
        # 결과 포맷팅
        schedules = [f"- {row[0]}: {row[1]}" for row in rows]
        response = f"📅 {schedule_date} 일정\n\n" + "\n".join(schedules)
        
        return response
        
    except Exception as e:
        logger.error(f"일정 조회 중 오류 발생: {str(e)}")
        return f"❌ 일정 조회 중 오류가 발생했습니다: {str(e)}"

def get_system_settings():
    """스프레드시트에서 시스템 설정을 가져오는 함수"""
    try:
        # 스프레드시트 체크 대신 항상 'on' 반환
        settings = {'socket_send': 'on'}
        logger.debug(f"Socket send setting: {settings['socket_send']}")
        return settings
        
    except Exception as e:
        logger.error(f"설정 조회 중 오류 발생: {str(e)}")
        return {'socket_send': 'on'}  # 에러 발생시에도 'on' 반환

def is_socket_send_enabled():
    """소켓 메시지 전송 기능이 활성화되어 있는지 확인"""
    try:
        settings = get_system_settings()  # settings 변수 추가
        enabled = settings.get('socket_send', 'off') == 'on'
        logger.debug(f"Socket send enabled: {enabled}")
        return enabled
    except Exception as e:
        logger.error(f"소켓 상태 확인 중 오류 발생: {str(e)}")
        return False

def send_socket_message(room: str, msg: str):
    """소켓 메시지 전송 함수"""
    if not is_socket_send_enabled():
        return False
        
    client_socket = None
    try:
        client_socket = socket(AF_INET, SOCK_STREAM)
        client_socket.settimeout(10)  # 타임아웃을 5초에서 10초로 증가
        
        # 연결 시도
        logger.info(f"Attempting to connect to socket server for room: {room}")
        client_socket.connect(("192.168.0.210", 9501))
        
        data = {
            "name": "send",
            "data": {
                "room": room,
                "msg": msg
            }
        }
        
        message = json.dumps(data) + "\n"
        client_socket.sendall(message.encode("utf-8"))
        
        # 응답 대기
        response = ""
        while True:
            try:
                chunk = client_socket.recv(1024).decode('utf-8')
                if not chunk:
                    break
                response += chunk
                if '\n' in response:
                    break
            except timeout:
                logger.error("Socket server response timeout")
                return False
                
        if response:
            logger.info(f"Message sent successfully to room: {room}")
            return True
            
        return False
            
    except ConnectionRefusedError:
        logger.error("Socket server connection refused")
        return False
    except Exception as e:
        logger.error(f"Socket message send error: {str(e)}")
        return False
    finally:
        if client_socket:
            client_socket.close()

def check_today_schedules():
    """오늘 날짜의 일정을 확인하고 메시지를 생성하는 함수
    매주 월요일에는 해당 주의 평일(월~금) 전체 일정을 표시"""
    try:
        today = datetime.now().date()
        weekday = today.weekday()  # 0: 월요일, 1: 화요일, ..., 6: 일요일
        
        # 월요일인 경우 (weekday == 0)
        if weekday == 0:
            # 이번 주 월요일(today)부터 금요일까지의 일정 조회
            this_monday = today
            this_friday = this_monday + timedelta(days=4)
            
            query = """
            SELECT schedule_date, sender, content
            FROM schedule
            WHERE schedule_date BETWEEN %s AND %s
            ORDER BY schedule_date, sender
            """
            params = (this_monday, this_friday)
            
            rows = fetch_all(query, params)
            
            if not rows:
                return (f"📅 이번 주({this_monday} ~ {this_friday}) 등록된 일정이 없습니다.\n"
                       "🔔 알리지 못한 일정은 메시지 부탁드립니다.\n"
                       "명령어 : 등록 날짜 내용, 삭제 날짜, 일정 날짜\n"
                       "전체일정 : https://m.site.naver.com/1CBsM")
            
            # 날짜별로 일정 그룹화
            schedules_by_date = {}
            for row in rows:
                date, sender, content = row
                if date not in schedules_by_date:
                    schedules_by_date[date] = []
                schedules_by_date[date].append(f"- {sender}: {content}")
            
            # 결과 포맷팅 - 요일 추가
            weekday_names = ["월", "화", "수", "목", "금"]
            response_parts = [f"📅 이번 주 일정 알림\n ({this_monday} ~ {this_friday})"]
            
            for i in range(5):  # 월~금
                date = this_monday + timedelta(days=i)
                weekday_name = weekday_names[i]
                
                if date in schedules_by_date:
                    response_parts.append(f"\n[{date} ({weekday_name})]")
                    response_parts.extend(schedules_by_date[date])
                else:
                    response_parts.append(f"\n[{date} ({weekday_name})] 일정 없음")
            
            response_parts.append("\n전체일정 : https://m.site.naver.com/1CBsM")
            response = "\n".join(response_parts)
            
            return response
        
        # 월요일이 아닌 경우 - 기존대로 오늘 일정만 표시
        else:
            # DB에서 오늘 날짜의 일정 조회
            query = """
            SELECT sender, content
            FROM schedule
            WHERE schedule_date = %s
            ORDER BY sender
            """
            params = (today,)
            
            rows = fetch_all(query, params)
            
            if not rows:
                return (f"📅 {today}에 등록된 일정이 없습니다.\n"
                       "🔔 알리지 못한 일정은 메시지 부탁드립니다.\n"
                       "명령어 : 등록 날짜 내용,삭제 날짜,일정 날짜\n"
                       "전체일정 : https://m.site.naver.com/1CBsM")
                
            # 결과 포맷팅
            schedules = [f"- {row[0]}: {row[1]}" for row in rows]
            response = f"📅 {today} 일정 알림\n\n" + "\n".join(schedules) + "\n\n전체일정 : https://m.site.naver.com/1CBsM"
            
            return response
        
    except Exception as e:
        logger.error(f"일정 조회 중 오류 발생: {str(e)}")
        return f"❌ 일정 조회 중 오류가 발생했습니다: {str(e)}"

def check_next_week_schedules():
    """다음 주 월요일부터 금요일까지의 일정을 확인하고 메시지를 생성하는 함수"""
    try:
        today = datetime.now().date()
        
        # 다음 주 월요일과 금요일 계산
        days_until_next_monday = (7 - today.weekday()) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7  # 오늘이 월요일이면 7일 후
            
        next_monday = today + timedelta(days=days_until_next_monday)
        next_friday = next_monday + timedelta(days=4)
        
        # DB에서 다음 주 일정 조회
        query = """
        SELECT schedule_date, sender, content
        FROM schedule
        WHERE schedule_date BETWEEN %s AND %s
        ORDER BY schedule_date, sender
        """
        params = (next_monday, next_friday)
        
        rows = fetch_all(query, params)
        
        # 날짜별로 일정 그룹화
        schedules_by_date = {}
        for row in rows:
            date, sender, content = row
            if date not in schedules_by_date:
                schedules_by_date[date] = []
            schedules_by_date[date].append(f"- {sender}: {content}")
        
        # 결과 포맷팅 - 요일 추가
        weekday_names = ["월", "화", "수", "목", "금"]
        response_parts = [f"📅 다음 주 일정 안내\n ({next_monday} ~ {next_friday})"]
        response_parts.append("\n✨ 다음주 일정 등록 부탁드립니다 ✨")
        
        for i in range(5):  # 월~금
            date = next_monday + timedelta(days=i)
            weekday_name = weekday_names[i]
            
            if date in schedules_by_date:
                response_parts.append(f"\n[{date} ({weekday_name})]")
                response_parts.extend(schedules_by_date[date])
            else:
                response_parts.append(f"\n[{date} ({weekday_name})] 일정 없음")
        
        response_parts.append("\n전체일정 : https://m.site.naver.com/1CBsM")
        response_parts.append("\n명령어 : 등록 날짜 내용, 삭제 날짜, 일정 날짜")
        response = "\n".join(response_parts)
        
        return response
        
    except Exception as e:
        logger.error(f"다음 주 일정 조회 중 오류 발생: {str(e)}")
        return f"❌ 다음 주 일정 조회 중 오류가 발생했습니다: {str(e)}"
