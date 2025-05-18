from webpage_summary import get_webpage_summary
import re

def test_webpage_summary():
    msg = "공모가도 깨진 LG엔솔…삼바에 시총 3위 내줘 - https://n.news.naver.com/article/029/0002955139?sid=101"
    urls = re.findall(r'(https?://[^\s]+)', msg)
    if urls:
        url = urls[0]
        print(f"\n=== 테스트: {url} ===")
        result = get_webpage_summary(url)
        print(result)
    else:
        print("URL을 찾을 수 없습니다.")

if __name__ == "__main__":
    test_webpage_summary() 