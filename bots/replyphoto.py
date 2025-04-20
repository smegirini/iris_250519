from addon import *
from helper.ImageHelper import ImageHelper as ih
from irispy2 import ChatContext

def reply_photo(chat: ChatContext, kl):
    match chat.message.command:
        case "!tt":
            send_tiger(chat)
        case "!ttt":
            send_triple_tiger(chat)
        case "!프사":
            send_avatar(chat)
        case "!프사링":
            send_avatar_kakaolink(chat, kl)

def send_tiger(chat: ChatContext):
    chat.reply_media("IMAGE", [open("res/aaa.jpeg", "rb")])

def send_triple_tiger(chat: ChatContext):
    chat.reply_media("IMAGE", [open("res/aaa.jpeg", "rb"), open("res/aaa.jpeg", "rb"), open("res/aaa.jpeg", "rb")])

@is_reply
def send_avatar(chat: ChatContext):
    avatar = chat.get_source().sender.avatar.img
    ih.send_image(chat, avatar)
    
@is_reply
def send_avatar_kakaolink(chat: ChatContext, kl):
    avatar = chat.get_source().sender.avatar
    kl.send(
        receiver_name=chat.room.name,
        template_id=3139,
        template_args={
            "IMAGE_WIDTH" : avatar.img.width,
            "IMAGE_HEIGHT" : avatar.img.height,
            "IMAGE_URL" : avatar.url
            },
    )