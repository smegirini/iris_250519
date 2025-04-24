import asyncio
import requests
from .KakaoLinkModule import IKakaoLinkCookieStorage, IKakaoLinkAuthorizationProvider, KakaoLink
import os
import typing as t

class KakaoLinkCookieStorage(IKakaoLinkCookieStorage):
    def __init__(self):
        self.local_storage = {}

    async def save(self, cookies):
        self.local_storage = cookies

    async def load(self):
        return self.local_storage

class KakaoTalkAuthorizationProvider(IKakaoLinkAuthorizationProvider):
    def __init__(self, iris_url: str):
        self.iris_url = iris_url
        
    async def get_authorization(self) -> str:
        aot = requests.get(f"{self.iris_url}/aot").json()["aot"]
        access_token = f"{aot['access_token']}-{aot['d_id']}"
        print("got access token: ", access_token)
        return access_token

class IrisLink:
    def __init__(
        self,
        iris_url: str,
    ):
        self.cookie_storage = KakaoLinkCookieStorage()
        self.authorization_provider = KakaoTalkAuthorizationProvider(iris_url)
        self.client = KakaoLink(
            default_app_key=os.environ.get("KAKAOLINK_APP_KEY"),
            default_origin=os.environ.get("KAKAOLINK_ORIGIN"),
            authorization_provider=self.authorization_provider,
            cookie_storage=self.cookie_storage,
        )
        asyncio.run(self.client.init())
        
    def send(
        self,
        receiver_name: str,
        template_id: int,
        template_args: dict,
        app_key: str | None = None,
        origin: str | None = None,
        search_exact: bool = True,
        search_from: t.Union[
            t.Literal["ALL"], t.Literal["FRIENDS"], t.Literal["CHATROOMS"]
        ] = "ALL",
        search_room_type: t.Union[
            t.Literal["ALL"],
            t.Literal["OpenMultiChat"],
            t.Literal["MultiChat"],
            t.Literal["DirectChat"],
        ] = "ALL"
    ):
        asyncio.run(
            self.client.send(
                receiver_name=receiver_name,
                template_id=template_id,
                template_args=template_args,
                app_key=app_key,
                origin=origin,
                search_exact=search_exact,
                search_from=search_from,
                search_room_type=search_room_type,
            )
        )
        
        
    