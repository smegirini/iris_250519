import json
import requests
import time

base_url = "http://172.30.10.66:3000"
request_json = {"query":"select enc,nickname,user_id,involved_chat_id from db2.open_chat_member","bind":[]}
headers = {'Accept': 'application/json'}
detect_rooms = ["18398338829933617"]
refresh_second = 3

members_database = {}

while True:
    try:
        query_result = requests.post(f"{base_url}/query",headers=headers,json=request_json).json()["data"]
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
    except Exception as e:
        print("something went wrong")
        print(e)
                
    members_database = members
    time.sleep(refresh_second)