from django.test import TestCase, RequestFactory
from channels.testing.websocket import WebsocketCommunicator
from django.core.files.uploadedfile import SimpleUploadedFile
from channels.db import database_sync_to_async as db_s2a
from asgiref.sync import async_to_sync, sync_to_async

from im.models import User, Friend, Group, Groupmember, Message, Systemop, Systemmsg
from websocket.consumers import ChatConsumer
from im.views.group import avatar as group_avatar
from im.views.users import avatar as user_avatar

from utils.utils_jwt import generate_jwt_token
from utils.utils_websocket import online
from utils.utils_assert import assertSingleSysmsg, assertSingleMessage

from django.conf import settings
from PIL import Image
from random import randint
import io, os, json

class AvatarTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")
        self.test_group = Group.objects.create(group_name="test_group", group_owner=self.alice)
        Groupmember.objects.create(group=self.test_group, member_user=self.alice, member_role="admin", do_not_disturb=True)
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="member")
        self.group_ab = Group.objects.create(group_name="")
        Groupmember.objects.create(group=self.group_ab, member_user=self.alice, member_role="")
        Groupmember.objects.create(group=self.group_ab, member_user=self.bob, member_role="", top=True)
        Friend.objects.create(user=self.alice, friend=self.bob, group=self.group_ab)
        Friend.objects.create(user=self.bob, friend=self.alice, group=self.group_ab)

    # destructor
    def tearDown(self):
        User.objects.all().delete()
        Friend.objects.all().delete()
        Group.objects.all().delete()

    # ! Utility functions
    def get_ws(self, user_name: str):
        token = generate_jwt_token(user_name)
        return WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{user_name}?{token}")

    # ! Test section
    @async_to_sync
    async def test_avatar_group_success(self):
        ws_b = self.get_ws('bob')
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        _ = await ws_b.receive_json_from()

        img = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (randint(0, 255), randint(0, 255), randint(0, 255)))
        f = io.BytesIO()
        img.save(f, format="PNG")
        f.seek(0)
        req = RequestFactory().post(f"/api/group/avatar?group_id={self.test_group.group_id}")
        req.META["HTTP_AUTHORIZATION"] = generate_jwt_token("alice")
        req.FILES.update({"file": SimpleUploadedFile("avatar.png", f.read(), "image/png")})
        res = await db_s2a(group_avatar)(req)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.content)["code"], 0)
        path = os.path.join(settings.MEDIA_ROOT, f"group{self.test_group.group_id}")
        self.assertTrue(os.path.exists(path))
        os.remove(path)

        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "avatar_group", f"admin of group {self.test_group.group_name} updated its avatar", False, "", sup_group_id=self.test_group.group_id)

        await ws_b.disconnect()

    @async_to_sync
    async def test_avatar_user_success(self):
        ws_b = self.get_ws('bob')
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        _ = await ws_b.receive_json_from()

        img = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (randint(0, 255), randint(0, 255), randint(0, 255)))
        f = io.BytesIO()
        img.save(f, format="PNG")
        f.seek(0)
        req = RequestFactory().post(f"/api/user/avatar")
        req.META["HTTP_AUTHORIZATION"] = generate_jwt_token("alice")
        req.FILES.update({"file": SimpleUploadedFile("avatar.png", f.read(), "image/png")})
        res = await db_s2a(user_avatar)(req)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.content)["code"], 0)
        path = os.path.join(settings.MEDIA_ROOT, f"user{self.alice.user_id}")
        self.assertTrue(os.path.exists(path))
        os.remove(path)

        ret_b = await ws_b.receive_json_from()
        for ret in ret_b:
            if ret["content"]["sysmsg_type"] == "avatar_friend":
                assertSingleSysmsg(self, [ret], "avatar_friend", f"friend user {self.alice.user_name} updated its avatar", False, "", sup_user_id=self.alice.user_id)
            if ret["content"]["sysmsg_type"] == "avatar_groupmember":
                assertSingleSysmsg(self, [ret], "avatar_groupmember", f"groupmember {self.alice.user_name} updated its avatar", False, "", sup_group_id=self.test_group.group_id, sup_user_id=self.alice.user_id)

        await ws_b.disconnect()
