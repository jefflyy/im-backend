from django.test import TestCase
from channels.testing.websocket import WebsocketCommunicator
from asgiref.sync import async_to_sync

from im.models import User, Group, Groupmember
from websocket.consumers import ChatConsumer

from utils.utils_jwt import generate_jwt_token
from utils.utils_assert import assertSingleMessage

# Create your tests here.
class MessagingTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="114514", user_email="bob@163.com")
        # self.carol = User.objects.create(user_name="carol", password="1919810", user_email="carol@163.com")
        self.group1 = Group.objects.create(group_name="group1")
        Groupmember.objects.create(group=self.group1, member_user=self.alice, member_role="member")
        Groupmember.objects.create(group=self.group1, member_user=self.bob, member_role="member")
        # Groupmember.objects.create(group=self.group1, member_user=self.carol, member_role="member")
        self.group2 = Group.objects.create(group_name="group2")

    # destructor
    def tearDown(self):
        Group.objects.all().delete()
        User.objects.all().delete()

    # ! Utility functions
    def get_ws(self, user_name: str):
        token = generate_jwt_token(user_name)
        return WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{user_name}?{token}")

    # ! Test section
    @async_to_sync
    async def test_send_message_to_correct_group(self):
        ws_a = self.get_ws('alice')
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()
        await ws_a.send_json_to({
            "type": "message",
            "content": {
                "group_id": self.group1.group_id,
                "msg_type": "text",
                "msg_body": "hello",
            }
        })
        ret = await ws_a.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group1.group_id, "text", "hello")
        await ws_a.disconnect()

        ws_b = self.get_ws('bob')
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        ret = await ws_b.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group1.group_id, "text", "hello")
        await ws_b.disconnect()

    @async_to_sync
    async def test_send_message_wrong_format(self):
        ws = self.get_ws('alice')
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        _ = await ws.receive_json_from()
        await ws.send_json_to({
            "what": "what",
            "content": "nothing",
        })
        ret = await ws.receive_json_from()
        self.assertListEqual(ret, [{"type": "error", "content": "Invalid json format"}])
        await ws.disconnect()

    @async_to_sync
    async def test_reply_message_success(self):
        ws = self.get_ws('alice')
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        _ = await ws.receive_json_from()
        await ws.send_json_to({
            "type": "message",
            "content": {
                "group_id": self.group1.group_id,
                "msg_type": "text",
                "msg_body": "hello",
            }
        })
        ret = await ws.receive_json_from()
        msg_id = ret[0]["content"]["msg_id"]
        await ws.send_json_to({
            "type": "message",
            "content": {
                "group_id": self.group1.group_id,
                "msg_type": "text",
                "msg_body": "hello too",
                "reply_msg_id": msg_id,
            }
        })
        ret = await ws.receive_json_from()
        assertSingleMessage(self, ret, self.alice.user_id, self.group1.group_id, "text", "hello too", reply_msg_id=msg_id)
        await ws.disconnect()
