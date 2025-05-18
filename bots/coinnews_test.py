from coinnews import get_coin_news

def test_get_coin_news():
    print("=== 1시간 뉴스 테스트 ===")
    print(get_coin_news(1))
    print("\n=== 3시간 뉴스 테스트 ===")
    print(get_coin_news(3))
    print("\n=== 0시간(에러) 테스트 ===")
    print(get_coin_news(0))
    print("\n=== 음수(에러) 테스트 ===")
    print(get_coin_news(-2))

if __name__ == "__main__":
    test_get_coin_news() 