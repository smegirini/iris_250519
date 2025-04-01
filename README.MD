Iris + IrisPy2 기반 샘플 봇

- 초기 설정

```
cd ~
git clone https://github.com/dolidolih/iris_bot
cd iris_bot
python -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python
```

```python
from helper.BotManager import BotManager
kv = BotManager("a").get_kv()
kv.put("admin",[YOUR_ADMIN_USER_ID])
exit()
```


- env 파일 설정

SECURE_1PSID, SECURE_1PSIDTS : Imagen3 무료 Web API 이용을 위한 쿠키. Chrome 시크릿창에서 https://gemini.google.com 방문하여 로그인 후 F12를 눌러 cookie 중 해당값 복사 붙여넣기 후 창 닫기
GEMINI_KEY : Gemini 정식 API 키. 무료/유료키 무관하며, 무료키 이용 시 분/일당 제한이 걸림. https://aistudio.google.com/apikey
X_NAVER_CLIENT_ID, X_NAVER_CLIENT_SECRET : 네이버 디벨로퍼에서 네이버 이미지 검색을 위한 API 키 발급. https://developers.naver.com/apps/#/list 사용 API에서 검색 선택택

- env 파일 적용
별도 서비스 관리자 없이 python 커맨드로 실행하는 경우

```
nano ~/.bashrc

export PYTHONBUFFERED=1
export SECURE_1PSID=""
export SECURE_1PSIDTS=""
export GEMINI_KEY=""
export X_NAVER_CLIENT_ID=""
export X_NAVER_CLIENT_SECRET=""
```

systemd를 이용하는 경우

```
sudo nano /etc/systemd/system/YOURSERVICE.service

EnvironmentFile=/home/dolidoli/ipy2/env 추가
```

docker를 이용하는 경우 : DockerFile에 ENV 추가, docker run에 -e로 추가, docker-compose.yml에 environment 추가 등