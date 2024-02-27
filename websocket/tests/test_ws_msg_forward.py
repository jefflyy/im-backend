from django.test import TestCase
from channels.testing.websocket import WebsocketCommunicator
from channels.db import database_sync_to_async as db_s2a
from asgiref.sync import async_to_sync
import os, shutil, aiofiles, json

from im.models import User, Group, Groupmember, Message, File
from websocket.consumers import ChatConsumer

from utils.utils_jwt import generate_jwt_token
from utils.utils_assert import assertSingleMessage

# Create your tests here.
class MsgForwardTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.group = Group.objects.create(group_name="group", group_owner=self.alice)
        self.gm = Groupmember.objects.create(group=self.group, member_user=self.alice, member_role="admin")
        self.msg = Message.objects.create(group=self.group, sender=self.alice, msg_type="text", msg_body="hello")
        self.gm.sent_msg_id = self.msg.msg_id
        self.gm.ack_msg_id = self.msg.msg_id
        self.gm.save(update_fields=["sent_msg_id", "ack_msg_id"])

    # destructor
    def tearDown(self):
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

    # ! Test section
    @async_to_sync
    async def test_forward_msg_text_and_nested_forward(self):
        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        _ = await ws.receive_json_from()

        data = {
            "origin_group_id": self.group.group_id,
            "target_group_id": self.group.group_id,
            "msg_ids": [self.msg.msg_id, self.msg.msg_id],
        }
        res = await self.async_post("/api/msg/forward", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        ret = await ws.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group.group_id, "forward", "forward message")
        fwmsg_id = ret[0]["content"]["msg_id"]

        file = await db_s2a(File.objects.filter(msg__msg_id=fwmsg_id).first)()
        self.assertIsNotNone(file)
        fw1_content = None
        async with aiofiles.open(file.file.path, "r") as f:
            fw1_content = await f.read()
            fw_msg = json.loads(fw1_content)
            self.assertIsInstance(fw_msg, list)
            self.assertEqual(len(fw_msg), 1)
            msg = fw_msg[0]
            self.assertSetEqual(set(msg.keys()), {"msg_id", "sender_name", "msg_type", "msg_body", "create_time"})
            self.assertEqual(msg["msg_id"], self.msg.msg_id)
            self.assertEqual(msg["sender_name"], self.alice.user_name)
            self.assertEqual(msg["msg_type"], "text")
            self.assertEqual(msg["msg_body"], "hello")

        data = {
            "origin_group_id": self.group.group_id,
            "target_group_id": self.group.group_id,
            "msg_ids": [fwmsg_id],
        }
        res = await self.async_post("/api/msg/forward", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        ret = await ws.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group.group_id, "forward", "forward message")
        nfwmsg_id = ret[0]["content"]["msg_id"]

        file = await db_s2a(File.objects.filter(msg__msg_id=nfwmsg_id).first)()
        self.assertIsNotNone(file)
        async with aiofiles.open(file.file.path, "r") as f:
            fw2_content = await f.read()
            fw_msg = json.loads(fw2_content)
            self.assertIsInstance(fw_msg, list)
            self.assertEqual(len(fw_msg), 1)
            msg = fw_msg[0]
            self.assertSetEqual(set(msg.keys()), {"msg_id", "sender_name", "msg_type", "msg_body", "create_time"})
            self.assertEqual(msg["msg_id"], fwmsg_id)
            self.assertEqual(msg["sender_name"], self.alice.user_name)
            self.assertEqual(msg["msg_type"], "forward")
            self.assertEqual(msg["msg_body"], "forward message")

        await ws.disconnect()
