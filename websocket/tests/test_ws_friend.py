from django.test import TestCase
from channels.testing.websocket import WebsocketCommunicator
from channels.db import database_sync_to_async as db_s2a
from asgiref.sync import async_to_sync

from im.models import User, Friend, Group, Groupmember, Message, Systemop, Systemmsg
from websocket.consumers import ChatConsumer

from utils.utils_jwt import generate_jwt_token
from utils.utils_websocket import online
from utils.utils_assert import assertSingleMessage, assertSingleSysmsg

# Create your tests here.
class FriendTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="114514", user_email="bob@163.com")

    # destructor
    def tearDown(self):
        Friend.objects.all().delete()
        Group.objects.all().delete()
        User.objects.all().delete()

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

    def async_delete(self, path, data, jwt_user_name):
        headers = {"Authorization": generate_jwt_token(jwt_user_name)}
        return self.async_client.delete(path, data=data, content_type='application/json', **headers)

    # ! Test section
    @async_to_sync
    async def test_apply_friend_yes_both_online(self):
        self.assertFalse(await db_s2a(Friend.objects.filter(user=self.alice, friend=self.bob).exists)())
        self.assertFalse(await db_s2a(Friend.objects.filter(user=self.bob, friend=self.alice).exists)())

        ws_a = self.get_ws('alice')
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        self.assertTrue(online('alice'))
        _ = await ws_a.receive_json_from()

        ws_b = self.get_ws('bob')
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        self.assertTrue(online('bob'))
        _ = await ws_b.receive_json_from()

        data = {"friend_user_id": self.bob.user_id, "message": "hello"}
        res = await self.async_post('/api/friend/apply', data, 'alice')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "apply_friend", "hello", False, "", sup_user_id=self.bob.user_id)
        sysmsg_id_a = ret_a[0]["content"]["sysmsg_id"]
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "apply_friend", "hello", True, "", sup_user_id=self.alice.user_id)
        sysmsg_id_b = ret_b[0]["content"]["sysmsg_id"]

        # use this environment to test sysmsg.handle
        data = {"sysmsg_id": sysmsg_id_a, "operation": "yes"}
        res = await self.async_post('/api/sysmsg/handle', data, 'alice')
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 2)

        data = {"sysmsg_id": sysmsg_id_b, "operation": "yes"}
        res = await self.async_post('/api/sysmsg/handle', data, 'bob')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "apply_friend", "hello", False, "yes", sup_user_id=self.bob.user_id)
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "apply_friend", "hello", False, "yes", sup_user_id=self.alice.user_id)

        res = await self.async_get('/api/friend/list', {}, 'alice')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        group_id = res.json()['friends'][0]["group_id"]
        await ws_a.send_json_to({
            "type": "message",
            "content": {
                "group_id": group_id,
                "msg_type": "text",
                "msg_body": "hello",
            }
        })
        ret_a = await ws_a.receive_json_from()
        assertSingleMessage(self, ret_a, self.alice.user_id, group_id, "text", "hello")
        ret_b = await ws_b.receive_json_from()
        assertSingleMessage(self, ret_b, self.alice.user_id, group_id, "text", "hello")

        await ws_a.disconnect()
        await ws_b.disconnect()

    @async_to_sync
    async def test_delete_friend_both_online(self):
        def sync_sub1():
            group = Group.objects.create(group_name="")
            Friend.objects.create(user=self.alice, friend=self.bob, group=group)
            Friend.objects.create(user=self.bob, friend=self.alice, group=group)
        
        await db_s2a(sync_sub1)()

        ws_a = self.get_ws('alice')
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()

        ws_b = self.get_ws('bob')
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        _ = await ws_b.receive_json_from()

        data = {"id": self.bob.user_id}
        res = await self.async_delete('/api/friend/delete', data, 'alice')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "delete_friend", "you removed bob from friend list", False, "", sup_user_id=self.bob.user_id)
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "delete_friend", "alice removed you from friend list", False, "", sup_user_id=self.alice.user_id)

        def sync_sub2():
            self.assertFalse(Friend.objects.filter(user=self.alice, friend=self.bob).exists())
            self.assertFalse(Friend.objects.filter(user=self.bob, friend=self.alice).exists())
        
        await db_s2a(sync_sub2)()
        await ws_a.disconnect()
        await ws_b.disconnect()

    @async_to_sync
    async def test_delete_friend_both_offline(self):
        def sync_sub1():
            group = Group.objects.create(group_name="")
            Friend.objects.create(user=self.alice, friend=self.bob, group=group)
            Friend.objects.create(user=self.bob, friend=self.alice, group=group)
        
        await db_s2a(sync_sub1)()

        data = {"id": self.bob.user_id}
        res = await self.async_delete('/api/friend/delete', data, 'alice')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ws_a = self.get_ws('alice')
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        self.assertTrue(online('alice'))

        ws_b = self.get_ws('bob')
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        self.assertTrue(online('bob'))

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "delete_friend", "you removed bob from friend list", False, "", sup_user_id=self.bob.user_id)
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "delete_friend", "alice removed you from friend list", False, "", sup_user_id=self.alice.user_id)

        await ws_a.disconnect()
        await ws_b.disconnect()
        self.assertFalse(online('alice'))
        self.assertFalse(online('bob'))

        def sync_sub2():
            self.assertFalse(Friend.objects.filter(user=self.alice, friend=self.bob).exists())
            self.assertFalse(Friend.objects.filter(user=self.bob, friend=self.alice).exists())

        await db_s2a(sync_sub2)()
