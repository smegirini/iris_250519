import time, datetime
import sys
from iris import Bot, PyKV
import pytz

detect_rooms = ["18435182482529739","18300699845509107","18317062785073220","18317852760569916","18314764046587380","18318872076615818"]
refresh_second = 3
MAX_RETRIES = 3

def detect_nickname_change(base_url):
    bot = Bot(base_url)
    kv = PyKV()
    query = "select enc,nickname,user_id,involved_chat_id from db2.open_chat_member"
    
    # KV 스토리지 접근 시 예외 처리 추가
    try:
        history = kv.get('user_history')
    except Exception as e:
        print(f"Error accessing KV storage: {type(e).__name__} - {str(e)}")
        history = None
    
    members = {}
    
    if not history:
        # 초기 데이터 로드 시 재시도 로직 추가
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                query_result = bot.api.query(query=query, bind=[])
                history = {}
                for member in query_result:
                    history[member['user_id']] = {"history": [{
                        "nickname":member["nickname"],
                        "involved_chat_id":member["involved_chat_id"],
                        "date":""
                    }]
                    }
                kv.put('user_history',history)
                print(f"Successfully initialized history with {len(history)} users")
                break
            except Exception as e:
                retry_count += 1
                print(f"Failed to initialize history (attempt {retry_count}/{MAX_RETRIES}): {type(e).__name__} - {str(e)}")
                if retry_count >= MAX_RETRIES:
                    print("Max retries reached for initialization, continuing with empty history")
                    history = {}
                time.sleep(1)
    
    while True:
        try:
            changed = False
            
            # 데이터베이스 쿼리 재시도 로직
            retry_count = 0
            query_success = False
            
            while retry_count < MAX_RETRIES and not query_success:
                try:
                    query_result = bot.api.query(query=query, bind=[])
                    query_success = True
                except Exception as e:
                    retry_count += 1
                    print(f"Database query failed (attempt {retry_count}/{MAX_RETRIES}): {type(e).__name__} - {str(e)}")
                    if retry_count >= MAX_RETRIES:
                        print("Max retries reached for database query, skipping this cycle")
                        time.sleep(refresh_second)
                        continue
                    time.sleep(1)
            
            if not query_success:
                continue
                
            members = {}
            for member in query_result:
                members[member['user_id']] = {"nickname":member["nickname"],"involved_chat_id":member["involved_chat_id"]}
            
            # 새 사용자 추가
            for user_id in members.keys():
                if user_id not in history:
                    history[user_id] = {"history" : [{
                        "nickname":members[user_id]["nickname"],
                        "involved_chat_id":members[user_id]["involved_chat_id"],
                        "date": ""
                    }]
                    }
                    print(f"Added new user {user_id} with nickname {members[user_id]['nickname']}")
            
            # 방어적 프로그래밍 - 사용자 ID 존재 확인
            for user_id in list(history.keys()):
                if user_id not in members:
                    # 불필요한 로그 제거 - 사용자가 현재 멤버가 아닌 경우 출력하지 않음
                    continue
                
                try:
                    user = history[user_id]["history"][-1]
                    new_user = members[user_id]
                    
                    # 닉네임 비교 전 타입 확인 및 변환
                    old_nickname = str(user["nickname"]) if user["nickname"] is not None else ""
                    new_nickname = str(new_user["nickname"]) if new_user["nickname"] is not None else ""
                    
                    if old_nickname != new_nickname:
                        korean = pytz.timezone('Asia/Seoul')
                        time_string = datetime.datetime.now(korean).strftime("%y%m%d %H:%M")
                        history[user_id]["history"].append(
                            {
                                "nickname":new_user["nickname"],
                                "involved_chat_id":new_user["involved_chat_id"],
                                "date":time_string
                            }
                        )
                        
                        print(f"Detected nickname change for user {user_id}: {old_nickname} -> {new_nickname}")
                        
                        if user["involved_chat_id"] in detect_rooms:
                            user_history = []
                            for change in history[user_id]["history"]:
                                user_history.append(f"ㄴ{'[' + change['date'] + ']' if not change['date'] == '' else ''} {change['nickname']}")
                            
                            user_history.reverse()
                            history_string = "\n".join(user_history)
                            
                            message = f"닉네임이 변경되었어요!\n{old_nickname} -> {new_nickname}\n" + "\u200b"*600 + "\n" + history_string
                            
                            # 메시지 전송 예외 처리 추가
                            try:
                                bot.api.reply(int(new_user["involved_chat_id"]),message.strip())
                                print(f"Sent notification to chat {new_user['involved_chat_id']}")
                            except Exception as e:
                                print(f"Failed to send message to chat {new_user['involved_chat_id']}: {type(e).__name__} - {str(e)}")
                                
                        changed = True
                except Exception as e:
                    print(f"Error processing user {user_id}: {type(e).__name__} - {str(e)}")
            
            # 히스토리 저장 예외 처리
            if changed:
                try:
                    kv.put('user_history',history)
                    print("Updated user history in KV storage")
                except Exception as e:
                    print(f"Failed to update history in KV storage: {type(e).__name__} - {str(e)}")
                    
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            print(f"Error type: {error_type}")
            print(f"Error message: {error_msg}")
            print(f"Error details: {e}")
            # 스택 트레이스 출력
            print("Stack trace:", file=sys.stderr)
            import traceback
            traceback.print_exc()
        
        # 로깅 최소화를 위해 각 주기 종료 메시지 삭제
        time.sleep(refresh_second)