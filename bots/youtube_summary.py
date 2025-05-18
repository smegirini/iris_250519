import os
import re
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Gemini API 키 로드 (GOOGLE_API_KEY, GEMINI_KEY, GEMINI_API_KEY 중 하나)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    raise RuntimeError("Gemini API 키가 설정되어 있지 않습니다.")

_executor = ThreadPoolExecutor()

def extract_youtube_id(url: str) -> str:
    """유튜브 URL에서 video_id 추출"""
    # 다양한 유튜브 URL 패턴 지원
    patterns = [
        r"youtu\.be/([\w-]{11})",
        r"youtube\.com/watch\?v=([\w-]{11})",
        r"youtube\.com/embed/([\w-]{11})",
        r"youtube\.com/v/([\w-]{11})",
        r"youtube\.com/live/([\w-]{11})",
        r"youtube\.com/shorts/([\w-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # 쿼리 파라미터에서 v 추출
    v_match = re.search(r"[?&]v=([\w-]{11})", url)
    if v_match:
        return v_match.group(1)
    return None

def get_youtube_transcript(video_id: str) -> str:
    """한글 자막 우선, 없으면 영어 자막, 자동 생성 자막까지 반환. 실패시 None 반환"""
    try:
        # 여러 한글 코드 시도
        for lang in ['ko', 'ko-Hang', 'ko-KR']:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                return " ".join([item['text'] for item in transcript])
            except Exception:
                continue
        # 영어 fallback
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            return " ".join([item['text'] for item in transcript])
        except Exception:
            pass
        # 자동 생성 자막 fallback
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            for transcript in transcript_list:
                if transcript.is_generated:
                    return " ".join([item['text'] for item in transcript.fetch()])
        except Exception:
            pass
        return None
    except Exception:
        return None

def get_youtube_summary(url: str) -> str:
    """
    유튜브 링크에서 자막을 추출해 Gemini API로 요약. 프롬프트는 yun_fn.py의 generate_summary1과 동일하게 사용.
    """
    video_id = extract_youtube_id(url)
    if not video_id:
        return "유효한 유튜브 링크가 아닙니다."
    transcript = get_youtube_transcript(video_id)
    if not transcript:
        return "자막을 찾을 수 없어 요약이 불가능합니다."
    prompt = f'''제공된 영상 대본의 제목이나 내용을 다음 작성 형식과 작성 지침을 반영해서 출력 하세요 ;
 
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
{transcript}
'''
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini 요약 생성 중 오류: {str(e)}"

async def get_youtube_summary_async(url: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, get_youtube_summary, url) 