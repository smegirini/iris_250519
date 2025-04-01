import requests
import time
from PIL import Image
from io import BytesIO, BufferedReader
from loguru import logger
import json

class ImageHelper:
    image_directory = "/home/dolidoli/res/temppic/"
    
    @classmethod
    def get_photo_url(cls, record) -> str:
        attachment = json.loads(record["attachment"])
        try:
            if record["type"] == 71:
                url = attachment["C"]["THL"][0]["TH"]["THU"]
            elif record["type"] == 27:
                url = attachment["imageUrls"][0]
            else:
                url = attachment["url"]
            return url
        except Exception as e:
            print(e)
            return None

    @classmethod
    def download_img_from_url(cls, url):
        try:
            res = requests.get(url)
            return res.content
        except Exception as e:
            print(e)
            return None

    @classmethod
    def save_img(cls, byte_img) -> str :
        try:
            img = Image.open(BytesIO(byte_img))
            img.convert("RGBA")
            filepath = cls.image_directory + str(time.time()) + ".png"
            img.save(filepath,"png")
            return filepath
        except Exception as e:
            print(e)
            return None

    @classmethod
    def send_image(cls, chat, img):
        buffered_reader = cls.image_to_buffered_reader(img)
        chat.reply_media(
            "IMAGE",
            [buffered_reader]
        )

    @classmethod
    def get_image_from_url(cls, url: str) -> Image:
        response = cls.download_img_from_url(url)
        img = Image.open(BytesIO(response))
        img = img.convert("RGBA")
        return img

    @classmethod
    def image_to_buffered_reader(cls, img: Image) -> BufferedReader:
        image_bytes_io = BytesIO()
        img = img.convert("RGBA")
        img.save(image_bytes_io, format="PNG")
        image_bytes_io.seek(0)
        buffered_reader = BufferedReader(image_bytes_io)
        return buffered_reader
