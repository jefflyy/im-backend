from django.test import TestCase
from channels.testing.websocket import WebsocketCommunicator
from channels.db import database_sync_to_async as db_s2a
from asgiref.sync import async_to_sync

from im.models import User, Group, Groupmember, Systemmsg, Systemop
from websocket.consumers import ChatConsumer

from utils.utils_jwt import generate_jwt_token

class WsSysmsgTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.group = Group.objects.create(group_name="group", group_owner=self.alice)
        Groupmember.objects.create(group=self.group, member_user=self.alice, member_role="admin")
        sysop = Systemop.objects.create(user=self.alice, sysop_type="", message="", need_operation=True, result="")
        self.sysmsg = Systemmsg.objects.create(sysop=sysop, target_user=self.alice, sysmsg_type="", message="", can_operate=True, result="")

    # destructor
    def tearDown(self):
        User.objects.all().delete()

    # ! Utility functions
    def get_ws(self, user_name: str):
        token = generate_jwt_token(user_name)
        return WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{user_name}?{token}")

    # ! Test section
    @async_to_sync
    async def test_login_fetch_sysmsg(self):
        async def fetch_once():
            ws = self.get_ws("alice")
            connected, _ = await ws.connect()
            self.assertTrue(connected)
            ret = await ws.receive_json_from()
            await ws.disconnect()
            return ret

        ret1 = await fetch_once()
        self.assertIsInstance(ret1, list)
        self.assertEqual(len(ret1), 1)
        ret2 = await fetch_once()
        self.assertListEqual(ret1, ret2)

        self.sysmsg.can_operate = False
        await db_s2a(self.sysmsg.save)(update_fields=["can_operate"])
        ret3 = await fetch_once()
        self.assertListEqual(ret3, [])
