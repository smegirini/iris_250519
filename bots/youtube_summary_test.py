from youtube_summary import get_youtube_summary

def test_youtube_summary():
    # 자막이 있는 유튜브 영상 예시
    urls = [
        "https://youtu.be/xL1c9PMPItw?si=B4ZMF-Kpe2zhFvDP"
    ]
    for url in urls:
        print(f"\n=== 테스트: {url} ===")
        result = get_youtube_summary(url)
        print(result)

if __name__ == "__main__":
    test_youtube_summary() 