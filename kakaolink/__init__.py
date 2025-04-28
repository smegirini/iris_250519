import asyncio
from .KakaoLinkModule import KakaoLink
import os
import typing as t

class IrisLink:
    def __init__(
        self,
        iris_url: str,
    ):
        self.client = KakaoLink(
            iris_url=iris_url,
            default_app_key=os.environ.get("KAKAOLINK_APP_KEY"),
            default_origin=os.environ.get("KAKAOLINK_ORIGIN"),
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
        
        
    