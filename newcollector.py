from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import requests
import re
from bs4 import BeautifulSoup
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
import uvicorn
import json
import asyncio
from typing import List, Union
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import pytz
import google.generativeai as genai
import time
from datetime import datetime, timedelta
from pydantic import BaseModel
import sys
import shutil

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Summary API",
    description="YouTube 영상 요약 및 뉴스 수집 API",
    version="1.0.0"
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("Missing required environment variables")

class URLExtractor:
    @staticmethod
    def extract_url(text: str) -> Optional[str]:
        """Extract URL from text."""
        url_pattern = r'(https?://[^\s]+)'
        urls = re.findall(url_pattern, text)
        return urls[0] if urls else None

    @staticmethod
    def extract_youtube_id(url: str) -> Optional[str]:
        """Extract YouTube ID from URL."""
        try:
            query = urlparse(url)
            if query.hostname == 'youtu.be':
                return query.path[1:]
            elif query.hostname in ('www.youtube.com', 'youtube.com'):
                if query.path == '/watch':
                    return parse_qs(query.query)['v'][0]
                elif query.path.startswith(('/embed/', '/v/')):
                    return query.path.split('/')[2]
            return None
        except Exception as e:
            logger.error(f"Error extracting YouTube ID: {e}")
            return None

class TextProcessor:
    @staticmethod
    def extract_text_from_html(html: str) -> str:
        """Extract clean text from HTML content."""
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text(separator='\n', strip=True)

    @staticmethod
    def format_transcript(transcript: list) -> str:
        """Convert YouTube transcript to formatted text."""
        return " ".join(item.get('text', '') for item in transcript)

class TextSummarizer:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.7
        )
        self.summary_prompt = PromptTemplate(
            template="""제공된 유튜브 영상의 자막이나 내용을 분석하고 상세하게 요약 하세요. 요약은 영상을 보지 않거나 기사를 직접 읽지 않고도 내용을 충분히 이해할수 있을 정도로 자세해야 합니다. 단, 결과물은 절대 2500자를 넘어서는 안됩니다. (중요) 다음 형식으로 출력 하세요 ;

📚 내용 개요
[3-5문장으로 전체적인 내용, 목표, 대상 독자 또는 시청자 설명]

🧑‍💻 내용 상세 요약 
섹션 1 : [섹션 제목 또는 주제]
-[섹션의 주요 내용 상세 설명]

섹션 2 : [섹션 제목 또는 주제]
-[섹션의 주요 내용 상세 설명]

[필요한 만큼 섹션 추가]

💬 결론
[내용의 주요 내용을 요약하고, 이 기술/개념의 중요성이나 실제 적용 가능성에 대한 간단한 논평]


📢지침 :
1. 각 섹션을 최대한 상세하게 작성하세요. 특히 주요 개념 설명과 내용 상세 요약은 매우 자세히 기술하세요. 
2. 내용의 논리적 흐름과 구조를 파악하여 섹션을 구성하세요. 
3. 코드 스니펫이나 중요한 문장은 내용에서 언급된 대로 최대한 정확하게 재현하세요. 불확실한 부분은 [불확실] 표시를 하세요. 
4. 전문 용어를 사용 할시에는 간단한 설명을 텃붙이세요. 
5. 시각적 표현 (그래프, 다이어 그램) 에 대해 언급된 설명을 최대한 자세히 텍스트로 묘사하세요. 
6. 작성자가 언급한 팁, 주의사항, 실제 사례 등을 포함 하세요 
7. 내용의 흐름에 따라 논리적으로 요약하세요. 
8. 마크다운 문법을 사용하지 마세요. 

⚠️ 주의사항:
- 글 전체 분량은 절대 2500자가 넘지 않아야 합니다. 
- 제공된 자막이나 내용만을 바탕으로 요약하세요. 추측하거나 외부 정보를 추가 하지 마세요. 
- 요약은 상세해야 하지만, 불필요한 반복은 피하세요. 
- 중요한 개념이나 단계가 누락되지 않도록 주의하세요. 
- 자막의 특성상 일부 기술 용어나 코드가 부정확할 수 있음을 감안 하세요.

**결과물은 마크다운이나 특수한 형식 없이 순수한 텍스트로 작성 하세요 **

: {text}""",
            input_variables=["text"]
        )
        self.chain = self.summary_prompt | self.llm

    async def summarize(self, text: str) -> str:
        """Summarize text using Gemini model."""
        try:
            response = await self.chain.ainvoke({"text": text})
            return response.content
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            raise HTTPException(status_code=500, detail="Summarization failed")
        
class YouTubeTranscriptExtractor:
    @staticmethod
    async def get_transcript(video_id: str) -> str:
        try:
            # 먼저 한국어 자막 시도
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
            return " ".join(item['text'] for item in transcript_list)
        except Exception as e:
            logger.info(f"한국어 자막이 없어 영어 자막을 사용합니다: {e}")
            try:
                # 영어 자막 그대로 사용
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                return " ".join(item['text'] for item in transcript_list)
            except Exception as e:
                logger.error(f"영어 자막 추출 오류: {e}")
                raise HTTPException(status_code=500, detail="자막을 가져올 수 없습니다.")

class NewsCollector:
    def __init__(self):
        logger.info("NewsCollector 초기화 시작")
        self.base_url = "https://coinness.com"
        self.timezone = pytz.timezone('Asia/Seoul')
        self.driver = None
        self._driver_closed = False  # 드라이버 종료 상태 추적
        
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        try:
            logger.info("Chrome driver 초기화 시도")
            try:
                # 직접 경로 지정 방법만 사용
                from selenium.webdriver.chrome.service import Service as ChromeService
                
                # 현재 디렉토리의 크롬 드라이버 사용
                driver_path = os.path.join(os.getcwd(), "chromedriver.exe")
                if os.path.exists(driver_path):
                    logger.info(f"직접 지정한 드라이버 사용: {driver_path}")
                    service = ChromeService(executable_path=driver_path)
                    
                    self.driver = webdriver.Chrome(
                        service=service,
                        options=chrome_options
                    )
                    self.driver.implicitly_wait(10)
                    logger.info("Chrome driver 초기화 성공")
                else:
                    logger.error(f"크롬 드라이버를 찾을 수 없습니다: {driver_path}")
                    raise Exception(f"크롬 드라이버를 찾을 수 없습니다: {driver_path}")
            except Exception as e:
                logger.error(f"Chrome driver 초기화 실패: {str(e)}")
                # 추가 디버깅 정보
                import platform
                logger.info(f"시스템 정보: {platform.platform()}, {platform.architecture()}")
                raise
            
            logger.info("Gemini API 초기화 시도")
            genai.configure(api_key=GOOGLE_API_KEY)
            self.gemini = genai.GenerativeModel('gemini-2.0-flash-exp')
            logger.info("Gemini API 초기화 성공")
        except Exception as e:
            logger.error(f"NewsCollector 초기화 중 오류 발생: {str(e)}")
            self.close_driver()  # 안전한 종료 메서드 사용
            raise

    def close_driver(self):
        """안전하게 드라이버를 종료하는 메서드"""
        if hasattr(self, 'driver') and self.driver is not None and not self._driver_closed:
            try:
                self.driver.quit()
                logger.info("Chrome driver 종료")
                self._driver_closed = True
            except Exception as e:
                logger.error(f"Chrome driver 종료 중 오류 발생: {str(e)}")
                
    def __del__(self):
        """소멸자에서 드라이버 종료 처리"""
        self.close_driver()

    def get_news_within_hours(self, hours: int) -> str:
        logger.info(f"뉴스 수집 시작: 최근 {hours}시간")
        try:
            return self.get_news_with_selenium(hours)
        except Exception as e:
            logger.error(f"뉴스 수집 중 오류 발생: {str(e)}")
            raise
        finally:
            self.close_driver()  # 안전한 종료 메서드 사용

    def get_news_with_selenium(self, hours: int) -> str:
        try:
            logger.info(f"Selenium을 사용한 뉴스 수집 시작 ({hours}시간)")
            self.driver.get(self.base_url)
            logger.info("웹페이지 로딩 완료")
            time.sleep(2)
            
            script = """
            function getNewsData() {
                const newsItems = document.querySelectorAll('[class*="BreakingNews"]');
                const results = [];
                
                newsItems.forEach(item => {
                    const titleElement = item.querySelector('[class*="Title"]');
                    const contentElement = item.querySelector('[class*="Contents"]');
                    
                    if (titleElement && contentElement) {
                        results.push({
                            title: titleElement.textContent.trim(),
                            content: contentElement.textContent.trim(),
                            time: new Date().toISOString()
                        });
                    }
                });
                
                return results;
            }
            return getNewsData();
            """
            
            results = self.driver.execute_script(script)
            logger.info(f"수집된 뉴스 항: {len(results)}")
            
            if not results:
                logger.warning("수집된 뉴스가 없습니다")
                return "수집된 뉴스가 없습니다."
            
            if len(results) > 10:
                logger.info(f"수집된 뉴스가 많아 최근 10개만 사용합니다 (전체: {len(results)}개)")
            results = results[:10]

            if not any(news.get("content") for news in results):
                logger.warning("뉴스 내용이 없는 항목이 있습니다")
            
            # 개선된 프롬프트
            prompt = f"""
            다음은 최근 {hours}시간 동안의 주요 뉴스입니다:

            {chr(10).join([f'[뉴스 {idx+1}]\n제목: {news["title"]}\n내용: {news["content"]}\n' for idx, news in enumerate(results[:10])])}
            
            위 뉴스들을 다음 형식으로 요약해주세요:

            [주요 뉴스 요약]
            1. 첫 번째 뉴스 핵심
            2. 두 번째 뉴스 핵심
            ...

            [상세 내용]
            - 각 뉴스의 중요한 세부사항
            - 연관된 뉴스들의 관계
            - 전반적인 시장 동향

            주의사항:
            - 간단명료하게 작성
            - 객관적 사실 위주로 작성
            - 불필요한 부연설명 제외
            - 마크다운 문법을 사용하지 말고 순수한 텍스트로 작성
            """
            
            logger.debug(f"생성된 프롬프트:\n{prompt}")
            summary = self.gemini.generate_content(prompt)
            if not summary or not summary.text:
                logger.error("Gemini API가 빈 응답을 반환했습니다")
                return "뉴스 요약을 생성할 수 없습니다."
            return summary.text
            
        except Exception as e:
            logger.error(f"Gemini API 호출 중 오류 발생: {str(e)}")
            return f"뉴스 요약 중 오류가 발생했습니다: {str(e)}"

class NewsRequest(BaseModel):
    hours: int
    sender: str

@app.get("/")
async def root():
    return {
        "message": "서버가 정상적으로 실행중입니다",
        "endpoints": {
            "뉴스 조회": "/news",
            "메시지 응답": "/reply",
            "API 문서": "/docs"
        }
    }

@app.post("/reply")
async def get_reply(request: dict):
    msg = request.get('msg', '')
    sender = request.get('sender', '사용자')
    room = request.get('room', '')
    
    logger.info(f"Received message - Room: {room}, Sender: {sender}, Message: {msg}")
    
    # URL 처리
    url = URLExtractor.extract_url(msg)
    if url:
        youtube_id = URLExtractor.extract_youtube_id(url)
        if youtube_id:
            # YouTube 처리
            try:
                transcript = await YouTubeTranscriptExtractor.get_transcript(youtube_id)
                summarizer = TextSummarizer()
                summary = await summarizer.summarize(transcript)
                return JSONResponse(content={"response": summary})
            except Exception as e:
                logger.error(f"YouTube processing error: {e}")
                return JSONResponse(content={"response": f"동영상 처리 중 오류가 발생했습니다: {str(e)}"})
        else:
            # 일반 URL 처리
            try:
                response = requests.get(url)
                text = TextProcessor.extract_text_from_html(response.text)
                summarizer = TextSummarizer()
                summary = await summarizer.summarize(text)
                return JSONResponse(content={"response": summary})
            except Exception as e:
                logger.error(f"URL processing error: {e}")
                return JSONResponse(content={"response": f"웹페이지 처리 중 오류가 발생했습니다: {str(e)}"})
    
    # #뉴스 명령어 처리
    if msg.startswith('#뉴스'):
        try:
            logger.info("뉴스 명령어 감지")
            hours_str = msg[3:].strip()  # '#뉴스' 이후의 숫자 추출
            hours = int(hours_str) if hours_str else 1
            
            if hours <= 0:
                return JSONResponse(
                    content={"response": "올바른 시간을 입력해주세요 (1 이상의 숫자)"}
                )
            
            logger.info(f"뉴스 수집 시작: {hours}시간")
            collector = None
            try:
                collector = NewsCollector()
                news_summary = collector.get_news_within_hours(hours)
                logger.info("뉴스 수집 완료")
                
                if not news_summary:
                    return JSONResponse(
                        content={"response": f"최근 {hours}시간 동안의 뉴스를 찾을 수 없습니다."}
                    )
                
                response_msg = f"{sender}님, 최근 {hours}시간 뉴스입니다:\n\n{news_summary}"
                return JSONResponse(content={"response": response_msg})
                
            finally:
                if collector and hasattr(collector, 'driver'):
                    collector.close_driver()  # 안전한 종료 메서드 사용
                    logger.info("Chrome driver 정리 완료")
                
        except ValueError:
            return JSONResponse(
                content={"response": "올바른 숫자를 입력해주세요 (예: #뉴스1, #뉴스3)"}
            )
        except Exception as e:
            logger.error(f"뉴스 처리 중 오류 발생: {str(e)}")
            return JSONResponse(
                content={"response": f"뉴스 수집 중 오류가 발생했습니다: {str(e)}"}
            )
    
    # $ 명령어 처리 (개념 설명)
    if msg.startswith('$') and not msg.startswith('$뉴스'):  # $뉴스 명령어 제외
        topic = msg[1:].strip()
        logger.info(f"Processing concept explanation for: {topic}")
        
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                return JSONResponse(
                    content={"response": "API 키가 설정되지 않았습니다."},
                    status_code=500
                )
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = f"""
            {topic}에 대해 다음 형식으로 설명해주세요:
            
            1. 정의: 간단명료한 정의
            2. 주요 특징: 2-3가지 핵심 특징
            3. 활용 분야: 실제 사되는 분야들
            4. 예시: 구체적인 예시 1-2개
            """
            
            response = model.generate_content(prompt)
            result = response.text
            
            return JSONResponse(
                content={"response": f"{sender}님, {topic}에 대한 설명입니다:\n\n{result}"},
                status_code=200
            )
            
        except Exception as e:
            logger.error(f"Concept explanation error: {e}")
            return JSONResponse(
                content={"response": f"설명 생성 중 오류가 발생했습니다: {str(e)}"},
                status_code=500
            )
    
    # 기타 메시지
    return JSONResponse(content={"response": ""})

@app.on_event("startup")
async def startup_event():
    try:
        logging.info("=== Server starting ===")
        
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            logger.error("GOOGLE_API_KEY not found")
            return
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        test_response = model.generate_content("Say 'Server started successfully!'")
        logger.info(f"Gemini API test: {test_response.text}")
        
        # Chrome driver 테스트
        logger.info("Chrome driver 테스트 시작")
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        test_driver = None
        try:
            # 직접 경로 지정 방법만 사용
            from selenium.webdriver.chrome.service import Service as ChromeService
            
            # 현재 디렉토리의 크롬 드라이버 사용
            driver_path = os.path.join(os.getcwd(), "chromedriver.exe")
            if os.path.exists(driver_path):
                logger.info(f"직접 지정한 드라이버 사용: {driver_path}")
                service = ChromeService(executable_path=driver_path)
                
                test_driver = webdriver.Chrome(
                    service=service,
                    options=chrome_options
                )
                # 간단한 테스트 수행
                test_driver.get("about:blank")
                logger.info("Chrome driver 테스트 성공")
            else:
                logger.error(f"크롬 드라이버를 찾을 수 없습니다: {driver_path}")
                raise Exception(f"크롬 드라이버를 찾을 수 없습니다: {driver_path}")
        except Exception as e:
            logger.error(f"Chrome driver 테스트 실패: {str(e)}")
            # 추가 디버깅 정보
            import platform
            logger.info(f"시스템 정보: {platform.platform()}, {platform.architecture()}")
        finally:
            # 안전하게 드라이버 종료
            if test_driver is not None:
                try:
                    test_driver.quit()
                    logger.info("테스트 Chrome driver 종료 성공")
                except Exception as e:
                    logger.error(f"테스트 Chrome driver 종료 실패: {str(e)}")
        
    except Exception as e:
        logger.error(f"Startup test failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
