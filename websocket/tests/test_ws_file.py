from django.test import TestCase, RequestFactory
from django.http import FileResponse
from django.core.files import File as DjangoFile
from django.core.files.uploadedfile import SimpleUploadedFile
from channels.testing.websocket import WebsocketCommunicator
from channels.db import database_sync_to_async as db_s2a
from asgiref.sync import async_to_sync
from urllib3 import encode_multipart_formdata
import os, shutil, aiofiles, json

from im.models import User, Group, Groupmember, Message, File
from websocket.consumers import ChatConsumer
from im.views.file import upload

from utils.utils_jwt import generate_jwt_token
from utils.utils_assert import assertSingleMessage

# Create your tests here.
class FileTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")
        self.group = Group.objects.create(group_name="test_group", group_owner=self.alice)
        self.group2 = Group.objects.create(group_name="test_group2", group_owner=self.alice)
        gm = Groupmember.objects.create(group=self.group, member_user=self.alice, member_role="admin")
        Groupmember.objects.create(group=self.group2, member_user=self.alice, member_role="admin")
        Groupmember.objects.create(group=self.group2, member_user=self.bob, member_role="member")
        with open("pytest.ini", "rb") as f:
            self.msg = Message.objects.create(
                sender=self.alice,
                group=self.group,
                msg_body="pytest.ini",
                msg_type="text/plain",
            )
            File.objects.create(
                msg=self.msg,
                file=DjangoFile(f),
            )
            gm.sent_msg_id = self.msg.msg_id
            gm.ack_msg_id = self.msg.msg_id
            gm.save(update_fields=["sent_msg_id", "ack_msg_id"])


    # destructor
    def tearDown(self):
        File.objects.all().delete()
        Message.objects.all().delete()
        Groupmember.objects.all().delete()
        Group.objects.all().delete()
        User.objects.all().delete()
        if os.path.exists("database/msg"):
            shutil.rmtree("database/msg")

    # ! Utility functions
    def get_ws(self, user_name: str):
        token = generate_jwt_token(user_name)
        return WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{user_name}?{token}")

    def async_post(self, path, data, jwt_user_name):
        headers = {"Authorization": generate_jwt_token(jwt_user_name)}
        return self.async_client.post(path, data=data, content_type='application/json', **headers)

    def async_get(self, path, data, jwt_user_name):
        headers = {"Authorization": generate_jwt_token(jwt_user_name)}
        return self.async_client.get(path, data=data, content_type='application/json', **headers)

    # ! Test section
    @async_to_sync
    async def test_upload_file_success(self):
        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        _ = await ws.receive_json_from()
        res = None
        async with aiofiles.open("pytest.ini", "rb") as f:
            req = RequestFactory().post("/api/file/upload?group_id=1")
            req.META["HTTP_AUTHORIZATION"] = generate_jwt_token("alice")
            req.FILES.update({"file": SimpleUploadedFile("pytest.ini", await f.read(), "text/plain")})
            res = await db_s2a(upload)(req)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.content)["code"], 0)
        ret = await ws.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group.group_id, "text/plain", "pytest.ini")

        def sync_sub(msg_id):
            msg = Message.objects.filter(msg_id=msg_id).first()
            self.assertIsNotNone(msg)
            file = File.objects.filter(msg=msg).first()
            self.assertIsNotNone(file)
            self.assertEqual(file.file.name, f"database/msg/{msg_id}/pytest.ini")
            self.assertEqual(file.name, "pytest.ini")

        await db_s2a(sync_sub)(ret[0]["content"]["msg_id"])
        await ws.disconnect()

    @async_to_sync
    async def test_download_file_in_forward_message(self):
        ws_a = self.get_ws("alice")
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()

        data = {
            "origin_group_id": self.group.group_id,
            "target_group_id": self.group2.group_id,
            "msg_ids": [self.msg.msg_id],
        }
        res = await self.async_post("/api/msg/forward", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret = await ws_a.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group2.group_id, "forward", "forward message")
        await ws_a.disconnect()
        fw_msg_id = ret[0]["content"]["msg_id"]

        ws_b = self.get_ws("bob")
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        ret = await ws_b.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group2.group_id, "forward", "forward message")
        await ws_b.disconnect()

        data = {
            "msg_id": self.msg.msg_id,
            "forward_msg_id": fw_msg_id,
        }
        res = await self.async_get("/api/file/download", data, "bob")
        self.assertEqual(res.status_code, 200)

        data = {"msg_id": fw_msg_id}
        res: FileResponse = await self.async_get("/api/file/download", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Disposition'], 'attachment; filename="forward.json"')
