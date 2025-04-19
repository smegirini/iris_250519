from Addon import *
from helper.ImageHelper import ImageHelper as ih
from irispy2 import ChatContext
from Addon import *

def reply_photo(chat: ChatContext):
    match chat.message.command:
        case "!tt":
            send_tiger(chat)
        case "!ttt":
            send_triple_tiger(chat)
        case "!프사":
            send_avatar(chat)

def send_tiger(chat: ChatContext):
    chat.reply_media("IMAGE", [open("res/aaa.jpeg", "rb")])

def send_triple_tiger(chat: ChatContext):
    chat.reply_media("IMAGE", [open("res/aaa.jpeg", "rb"), open("res/aaa.jpeg", "rb"), open("res/aaa.jpeg", "rb")])

@is_reply
def send_avatar(chat: ChatContext):
    avatar = chat.get_source().sender.avatar.img
    ih.send_image(chat, avatar)