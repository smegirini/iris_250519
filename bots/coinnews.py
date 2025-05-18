import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
import google.generativeai as genai

# 환경 변수에서 API 키 로드 (GOOGLE_API_KEY 우선, 없으면 GEMINI_KEY 사용)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_KEY")

logger = logging.getLogger(__name__)

# Gemini API 초기화
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel('gemini-2.0-flash-exp')
else:
    GEMINI_MODEL = None
    logger.error("GOOGLE_API_KEY(GEMINI_KEY)가 설정되지 않았습니다.")


def get_coin_news(hours: int = 1) -> str:
    """
    최근 hours시간 이내의 코인 뉴스를 수집하고 요약하여 반환합니다.
    예외 발생 시 에러 메시지를 반환합니다.
    """
    driver = None
    try:
        # Selenium 옵션 설정
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-shm-usage')

        # chromedriver 경로 (리눅스 apt 설치 경로)
        driver_path = "/usr/bin/chromedriver"
        if not os.path.exists(driver_path):
            return f"크롬 드라이버를 찾을 수 없습니다: {driver_path}"

        service = ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)

        base_url = "https://coinness.com"
        driver.get(base_url)
        time.sleep(2)

        # JS로 뉴스 데이터 추출
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
        results = driver.execute_script(script)
        if not results:
            return "수집된 뉴스가 없습니다."
        if len(results) > 10:
            results = results[:10]

        prompt = f"""
        다음은 최근 {hours}시간 동안의 주요 뉴스입니다:

        {chr(10).join([f'[뉴스 {idx+1}]\n제목: {news["title"]}\n내용: {news["content"]}\n' for idx, news in enumerate(results)])}
        
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
        if not GEMINI_MODEL:
            return "Gemini API 키가 설정되지 않았습니다."
        summary = GEMINI_MODEL.generate_content(prompt)
        if not summary or not summary.text:
            return "뉴스 요약을 생성할 수 없습니다."
        return summary.text
    except Exception as e:
        logger.error(f"뉴스 수집/요약 중 오류: {str(e)}")
        return f"뉴스 요약 중 오류가 발생했습니다: {str(e)}"
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass 