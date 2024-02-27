from django.test import TestCase
from channels.testing.websocket import WebsocketCommunicator
from channels.db import database_sync_to_async as db_s2a
from asgiref.sync import async_to_sync

from im.models import User, Group, Groupmember, Systemmsg, Systemop, Message
from websocket.consumers import ChatConsumer

from utils.utils_jwt import generate_jwt_token
from utils.utils_assert import assertSingleSysmsg, assertSingleMessage

# Create your tests here.
class MsgopTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")
        self.group = Group.objects.create(group_name="group", group_owner=self.alice)
        Groupmember.objects.create(group=self.group, member_user=self.alice, member_role="admin")
        Groupmember.objects.create(group=self.group, member_user=self.bob, member_role="member")
        self.msg = Message.objects.create(group=self.group, sender=self.alice, msg_type="text", msg_body="hello")

    # destructor
    def tearDown(self):
        Systemmsg.objects.all().delete()
        Systemop.objects.all().delete()
        Groupmember.objects.all().delete()
        Group.objects.all().delete()
        User.objects.all().delete()

    # ! Utility functions
    def get_ws(self, user_name: str):
        token = generate_jwt_token(user_name)
        return WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{user_name}?{token}")

    def async_post(self, path, data, jwt_user_name):
        headers = {"Authorization": generate_jwt_token(jwt_user_name)}
        return self.async_client.post(path, data=data, content_type='application/json', **headers)

    def async_delete(self, path, data, jwt_user_name):
        headers = {"Authorization": generate_jwt_token(jwt_user_name)}
        return self.async_client.delete(path, data=data, content_type='application/json', **headers)

    # ! Test functions
    @async_to_sync
    async def test_ack_msg_success(self):
        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        ret1 = await ws.receive_json_from()
        await ws.disconnect()

        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        ret2 = await ws.receive_json_from()
        self.assertListEqual(ret1, ret2)

        data = {"group_id": self.group.group_id, "msg_id": self.msg.msg_id}
        res = await self.async_post("/api/msg/ack", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["code"], 0)

        ret = await ws.receive_json_from()
        assertSingleSysmsg(self, ret, "ack_msg", f"{self.alice.user_name} ack message in group {self.group.group_name}", False, "", sup_group_id=self.group.group_id)

        gm = await db_s2a(Groupmember.objects.filter(group=self.group, member_user=self.alice).first)()
        self.assertEqual(gm.ack_msg_id, self.msg.msg_id)
        await ws.disconnect()

        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        ret3 = await ws.receive_json_from()
        self.assertListEqual(ret3, [])
        await ws.disconnect()

    @async_to_sync
    async def test_recall_msg_success(self):
        ws_a = self.get_ws("alice")
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        ret = await ws_a.receive_json_from()
        self.assertEqual(len(ret), 1)

        msg_id = self.msg.msg_id
        data = {"msg_id": msg_id}
        res = await self.async_post("/api/msg/recall", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["code"], 0)

        ret = await ws_a.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group.group_id, "recall", f"{self.alice.user_name} recalled a message from {self.alice.user_name}")

        ws_b = self.get_ws("bob")
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        ret = await ws_b.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group.group_id, "recall", f"{self.alice.user_name} recalled a message from {self.alice.user_name}")
        await ws_b.disconnect()

        msg = await db_s2a(Message.objects.filter(msg_id=msg_id).first)()
        self.assertEqual(msg.msg_type, "recall")

        await ws_a.disconnect()

    @async_to_sync
    async def test_delete_msg_success(self):
        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        _ = await ws.receive_json_from()

        data = {"msg_id": self.msg.msg_id}
        res = await self.async_delete("/api/msg/delete", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["code"], 0)

        ret = await ws.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group.group_id, "delete", f"{self.alice.user_name} deleted a message")

        msg = await db_s2a(Message.objects.filter(msg_id=self.msg.msg_id).first)()
        self.assertEqual(msg, self.msg)

        await ws.disconnect()

    @async_to_sync
    async def test_delete_msg_then_login(self):
        data = {"msg_id": self.msg.msg_id}
        res = await self.async_delete("/api/msg/delete", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["code"], 0)

        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        ret = await ws.receive_json_from()
        self.assertListEqual(ret, [])
        await ws.disconnect()
