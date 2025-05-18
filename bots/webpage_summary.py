import os
import time
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid

# Gemini API 키 로드 (GOOGLE_API_KEY, GEMINI_KEY, GEMINI_API_KEY 중 하나)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    raise RuntimeError("Gemini API 키가 설정되어 있지 않습니다.")

def extract_text_from_html(html: str) -> str:
    """HTML에서 텍스트만 추출"""
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup(["script", "style"]):
        script.decompose()
    return soup.get_text(separator='\n', strip=True)

def make_prompt(title: str, text: str) -> str:
    return f'''제공된 웹페이지 제목이나 내용을 다음 작성 형식과 작성 지침을 반영해서 출력하세요:

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
{text[:4000]}
'''

def parse_naver_blog(url: str):
    # iframe URL 변환
    blog_id = url.split('blog.naver.com/')[1].split('/')[0]
    post_id = url.split('/')[-1].split('?')[0]
    iframe_url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={post_id}&redirect=Dlog"
    resp = requests.get(iframe_url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    title = soup.find('div', {'class': 'se-module se-module-text se-title-text'})
    if title:
        title = title.get_text(strip=True)
    else:
        title = soup.find('title').text if soup.find('title') else "제목 없음"
    content = soup.find('div', {'class': 'se-main-container'})
    if content:
        text = content.get_text(separator='\n', strip=True)
    else:
        # 구버전 블로그 형식 시도
        content = soup.find('div', {'class': 'post-view'})
        text = content.get_text(separator='\n', strip=True) if content else ""
    return title, text

def parse_medium(url: str):
    # requests로 시도, 안되면 fallback 없음
    try:
        resp = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        })
        soup = BeautifulSoup(resp.text, 'html.parser')
        # 제목
        title = None
        meta_title = soup.find('meta', {'property': 'og:title'})
        if meta_title and meta_title.get('content'):
            title = meta_title.get('content')
        if not title:
            h1 = soup.find('h1')
            title = h1.text.strip() if h1 else "제목 없음"
        # 본문
        article = soup.find('article')
        if article:
            text = article.get_text(separator='\n', strip=True)
        else:
            text = extract_text_from_html(resp.text)
        return title, text
    except Exception:
        return None, None

def parse_general_with_requests(url: str):
    try:
        resp = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        })
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = soup.find('title').text if soup.find('title') else "제목 없음"
        text = extract_text_from_html(resp.text)
        return title, text
    except Exception as e:
        return None, f"웹페이지 요약 생성 중 오류: {str(e)}"

def parse_general_with_selenium(url: str):
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    driver_path = "/usr/bin/chromedriver"
    if not os.path.exists(driver_path):
        return None, f"크롬 드라이버를 찾을 수 없습니다: {driver_path}"
    driver = None
    try:
        service = ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        time.sleep(3)
        # 스크롤 다운 (중간, 끝)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(1.5)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        # 고유 임시 파일명 생성 및 저장
        temp_filename = f"selenium_page_source_{uuid.uuid4().hex}.html"
        with open(temp_filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        # article 태그 우선 추출
        try:
            article = driver.find_element(By.CSS_SELECTOR, "article")
            text = article.text
        except Exception:
            text = extract_text_from_html(driver.page_source)
        title = driver.title or "제목 없음"
        return title, text
    except Exception as e:
        return None, f"웹페이지 요약 생성 중 오류: {str(e)}"
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        # 임시 파일 삭제
        try:
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                os.remove(temp_filename)
        except Exception:
            pass

def get_webpage_summary(url: str) -> str:
    # 네이버 블로그
    if 'blog.naver.com' in url:
        title, text = parse_naver_blog(url)
    # 미디엄
    elif 'medium.com' in url:
        title, text = parse_medium(url)
    # 기타
    else:
        title, text = parse_general_with_requests(url)
        # requests로 추출 실패(100자 미만) 시 selenium fallback
        if not title or not text or len(text) < 100:
            title, text = parse_general_with_selenium(url)
    if not title or not text or len(text) < 100:
        return "웹페이지에서 충분한 텍스트를 추출하지 못했습니다."
    prompt = make_prompt(title, text)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"웹페이지 요약 생성 중 오류: {str(e)}"

_executor = ThreadPoolExecutor()

async def get_webpage_summary_async(url: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, get_webpage_summary, url) 