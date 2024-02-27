from django.test import TestCase
from channels.testing.websocket import WebsocketCommunicator
from channels.db import database_sync_to_async as db_s2a
from asgiref.sync import async_to_sync, sync_to_async

from im.models import User, Friend, Group, Groupmember, Message, Systemop, Systemmsg
from websocket.consumers import ChatConsumer

from utils.utils_jwt import generate_jwt_token
from utils.utils_websocket import online
from utils.utils_assert import assertSingleSysmsg, assertSingleMessage

class MsgUserTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")
        self.carol = User.objects.create(user_name="carol", password="123456", user_email="carol@163.com")
        self.eve = User.objects.create(user_name="eve", password="123456", user_email="eve@163.com")
        self.test_group = Group.objects.create(group_name="test_group", group_owner=self.alice)
        Groupmember.objects.create(group=self.test_group, member_user=self.alice, member_role="admin", do_not_disturb=True)
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="member")
        Groupmember.objects.create(group=self.test_group, member_user=self.carol, member_role="member")
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

    def async_post(self, path, data, jwt_user_name):
        headers = {"Authorization": generate_jwt_token(jwt_user_name)}
        return self.async_client.post(path, data=data, content_type='application/json', **headers)

    def async_put(self, path, data, jwt_user_name):
        headers = {"Authorization": generate_jwt_token(jwt_user_name)}
        return self.async_client.put(path, data=data, content_type='application/json', **headers)

    # ! Test section
    @async_to_sync
    async def test_logout_success(self):
        ws = self.get_ws('alice')
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        _ = await ws.receive_json_from()

        res = await self.async_post('/api/user/logout', {}, 'alice')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertFalse(online('alice'))

        await ws.disconnect()

    @async_to_sync
    async def test_cancel_success(self):
        ws_a = self.get_ws('alice')
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()

        ws_b = self.get_ws('bob')
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        _ = await ws_b.receive_json_from()

        ws_c = self.get_ws('carol')
        connected, _ = await ws_c.connect()
        self.assertTrue(connected)
        _ = await ws_c.receive_json_from()

        res = await self.async_post('/api/user/cancel', {}, 'alice')
        print(res.json())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertFalse(online('alice'))
        self.assertFalse(await db_s2a(User.objects.filter(user_name="alice").exists)())

        ret_b = await ws_b.receive_json_from()
        print(ret_b)
        self.assertEqual(len(ret_b), 3)
        assertSingleSysmsg(self, [ret_b[0]], "cancel_user_friend", f"friend user {self.alice.user_id} canceled its account", False, "")
        assertSingleSysmsg(self, [ret_b[1]], "cancel_user_group_member", f"groupmember user {self.alice.user_id} canceled its account", False, "", sup_group_id=self.group_ab.group_id)
        assertSingleSysmsg(self, [ret_b[2]], "cancel_user_group_owner", f"groupowner user {self.alice.user_id} canceled its account", False, "")

        ret_c = await ws_c.receive_json_from()
        print(ret_c)
        self.assertEqual(len(ret_c), 1)
        assertSingleSysmsg(self, [ret_c[0]], "cancel_user_group_owner", f"groupowner user {self.alice.user_id} canceled its account", False, "")
        await ws_a.disconnect()
        await ws_b.disconnect()
        await ws_c.disconnect()

    @async_to_sync
    async def test_login_no_jwt(self):
        ws = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/chat/alice")
        connected, _ = await ws.connect()
        self.assertFalse(connected)

    @async_to_sync
    async def test_login_wrong_jwt(self):
        ws = self.get_ws("david")
        connected, _ = await ws.connect()
        self.assertFalse(connected)

    @async_to_sync
    async def test_login_correct_jwt(self):
        ws = self.get_ws('alice')
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        ret = await ws.receive_json_from()
        self.assertTrue(online('alice'))
        self.assertListEqual(ret, [])
        await ws.disconnect()
        self.assertFalse(online('alice'))

    @async_to_sync
    async def test_login_wrong_username(self):
        ws = self.get_ws('')
        connected, _ = await ws.connect()
        self.assertFalse(connected)

    @async_to_sync
    async def test_modify_user(self):
        ws_a = self.get_ws('alice')
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()

        ws_b = self.get_ws('bob')
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        _ = await ws_b.receive_json_from()

        ws_c = self.get_ws('carol')
        connected, _ = await ws_c.connect()
        self.assertTrue(connected)
        _ = await ws_c.receive_json_from()

        data = {"user_name": "alicia", "password": "lzxjuchfaes"}
        res = await self.async_put("/api/user/modify", data, "alice")
        print(res.json())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_b = await ws_b.receive_json_from()
        print(ret_b)
        self.assertEqual(len(ret_b), 3)
        assertSingleSysmsg(self, [ret_b[0]], "modify_user_info_friend", f"user {self.alice.user_id} modified user info", False, "")
        assertSingleSysmsg(self, [ret_b[1]], "modify_user_info_group", f"user {self.alice.user_id} modified user info", False, "", sup_group_id=self.test_group.group_id)
        assertSingleSysmsg(self, [ret_b[2]], "modify_user_info_group", f"user {self.alice.user_id} modified user info", False, "", sup_group_id=self.group_ab.group_id)

        ret_c = await ws_c.receive_json_from()
        print(ret_c)
        self.assertEqual(len(ret_c), 1)
        assertSingleSysmsg(self, [ret_c[0]], "modify_user_info_group", f"user {self.alice.user_id} modified user info", False, "", sup_group_id=self.test_group.group_id)

        await ws_a.disconnect()
        await ws_b.disconnect()
        await ws_c.disconnect()