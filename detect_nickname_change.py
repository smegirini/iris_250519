import requests
import time

detect_rooms = ["18398338829933617"]
refresh_second = 3

def detect_nickname_change(base_url):
    headers = {'Accept': 'application/json'}
    query = {"query":"select enc,nickname,user_id,involved_chat_id from db2.open_chat_member","bind":[]}
    
    members_database = {}

    while True:
        try:
            query_result = requests.post(f"{base_url}/query",headers={'Accept': 'application/json'},json=query).json()["data"]
            members = {}
            for member in query_result:
                members[member['user_id']] = {"nickname":member["nickname"],"involved_chat_id":member["involved_chat_id"]}
            
            if members_database != {}:
                for user_id in members_database.keys():
                    user = members_database[user_id]
                    new_user = members[user_id]
                    if user["nickname"] != new_user["nickname"]:
                        message = {
                            "type":"text",
                            "room":str(user["involved_chat_id"]),
                            "data":f"닉네임이 변경되었어요!\n{user['nickname']} -> {new_user['nickname']}"
                            }
                        if message["room"] in detect_rooms:
                            requests.post(f"{base_url}/reply",headers=headers,json=message)
            members_database = members
        except Exception as e:
            print("something went wrong")
            print(e)
        
        time.sleep(refresh_second)