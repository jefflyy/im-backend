from django.test import TestCase
from channels.testing.websocket import WebsocketCommunicator
from channels.db import database_sync_to_async as db_s2a
from asgiref.sync import async_to_sync

from im.models import User, Group, Groupmember, Systemmsg, Systemop
from websocket.consumers import ChatConsumer

from utils.utils_jwt import generate_jwt_token
from utils.utils_websocket import online
from utils.utils_assert import assertSingleSysmsg, assertSingleMessage

# Create your tests here.
class GroupTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="114514", user_email="bob@163.com")
        self.carol = User.objects.create(user_name="carol", password="1919810", user_email="carol@163.com")
        self.group = Group.objects.create(group_name="group", group_owner=self.alice)
        Groupmember.objects.create(group=self.group, member_user=self.alice, member_role="admin")
        Groupmember.objects.create(group=self.group, member_user=self.carol, member_role="member")

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

    def async_put(self, path, data, jwt_user_name):
        headers = {"Authorization": generate_jwt_token(jwt_user_name)}
        return self.async_client.put(path, data=data, content_type='application/json', **headers)

    # ! Test section
    @async_to_sync
    async def test_join_group(self):
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

        data = {"group_id": self.group.group_id, "message": ""}
        res = await self.async_post("/api/group/join", data, "bob")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "join_group", "", True, "", sup_user_id=self.bob.user_id)
        sysmsg_id = ret_a[0]["content"]["sysmsg_id"]
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "join_group", "", False, "", sup_user_id=self.bob.user_id, sup_group_id=self.group.group_id)

        data = {"sysmsg_id": sysmsg_id, "operation": "what"}
        res = await self.async_post("/api/sysmsg/handle", data, "alice")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

        data = {"sysmsg_id": sysmsg_id, "operation": "yes"}
        res = await self.async_post("/api/sysmsg/handle", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "join_group", "", False, "yes", sup_user_id=self.bob.user_id, sup_group_id=self.group.group_id)
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "join_group", "", False, "yes", sup_user_id=self.bob.user_id, sup_group_id=self.group.group_id)
        ret_c = await ws_c.receive_json_from()
        assertSingleSysmsg(self, ret_c, "join_group", "", False, "yes", sup_group_id=self.group.group_id)

        def sync_sub():
            self.assertTrue(Groupmember.objects.filter(group=self.group, member_user=self.bob).exists())
        await db_s2a(sync_sub)()

        await ws_a.disconnect()
        await ws_b.disconnect()
        await ws_c.disconnect()

    @async_to_sync
    async def test_create_group(self):
        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        _ = await ws.receive_json_from()

        group_name = "group2"
        data = {"group_name": group_name, "member_ids": []}
        res = await self.async_post("/api/group/create", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret = await ws.receive_json_from()
        assertSingleSysmsg(self, ret, "create_group", f"alice created group {group_name}", False, "")
        await ws.disconnect()

    @async_to_sync
    async def test_leave_group(self):
        def sync_sub():
            Groupmember.objects.create(group=self.group, member_user=self.bob, member_role="member")
        await db_s2a(sync_sub)()

        ws_a = self.get_ws("alice")
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()

        ws_b = self.get_ws("bob")
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        _ = await ws_b.receive_json_from()

        data = {"group_id": self.group.group_id}
        res = await self.async_post("/api/group/leave", data, "bob")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "leave_group", f"bob left group {self.group.group_name}", False, "", sup_user_id=self.bob.user_id, sup_group_id=self.group.group_id)
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "leave_group", f"bob left group {self.group.group_name}", False, "", sup_user_id=self.bob.user_id, sup_group_id=self.group.group_id)

        res = await self.async_post("/api/group/leave", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "delete_group", f"group {self.group.group_name} is deleted", False, "")

        await ws_a.disconnect()
        await ws_b.disconnect()

    @async_to_sync
    async def test_delete_group(self):
        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        _ = await ws.receive_json_from()

        data = {"group_id": self.group.group_id}
        res = await self.async_delete("/api/group/delete", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret = await ws.receive_json_from()
        assertSingleSysmsg(self, ret, "delete_group", f"group {self.group.group_name} is deleted", False, "")

        await ws.disconnect()

    @async_to_sync
    async def test_kick_user(self):
        def sync_sub():
            Groupmember.objects.create(group=self.group, member_user=self.bob, member_role="member")
        await db_s2a(sync_sub)()

        ws_a = self.get_ws("alice")
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()

        ws_b = self.get_ws("bob")
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        _ = await ws_b.receive_json_from()

        data = {"group_id": self.group.group_id, "member_id": self.bob.user_id}
        res = await self.async_post("/api/group/kick_user", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "kick_user", f"{self.alice.user_name} kicked {self.bob.user_name} from group {self.group.group_name}", False, "", sup_user_id=self.bob.user_id, sup_group_id=self.group.group_id)
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "kick_user", f"{self.alice.user_name} kicked {self.bob.user_name} from group {self.group.group_name}", False, "", sup_user_id=self.bob.user_id, sup_group_id=self.group.group_id)

        await ws_a.disconnect()
        await ws_b.disconnect()

    @async_to_sync
    async def test_set_role(self):
        def sync_sub():
            Groupmember.objects.create(group=self.group, member_user=self.bob, member_role="member")
        await db_s2a(sync_sub)()

        ws_a = self.get_ws("alice")
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()

        ws_b = self.get_ws("bob")
        connected, _ = await ws_b.connect()
        self.assertTrue(connected)
        _ = await ws_b.receive_json_from()

        data = {"group_id": self.group.group_id, "member_id": self.bob.user_id, "member_role": "admin"}
        res = await self.async_post("/api/group/set_role", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "set_role", f"{self.bob.user_name}'s role in group {self.group.group_name} is changed to admin", False, "", sup_group_id=self.group.group_id)
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "set_role", f"{self.bob.user_name}'s role in group {self.group.group_name} is changed to admin", False, "", sup_group_id=self.group.group_id)

        data = {"group_id": self.group.group_id, "member_id": self.bob.user_id, "member_role": "owner"}
        res = await self.async_post("/api/group/set_role", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret_a = await ws_a.receive_json_from()
        assertSingleSysmsg(self, ret_a, "change_owner", f"the owner of group {self.group.group_name} is changed to {self.bob.user_name}", False, "", sup_group_id=self.group.group_id)
        ret_b = await ws_b.receive_json_from()
        assertSingleSysmsg(self, ret_b, "change_owner", f"the owner of group {self.group.group_name} is changed to {self.bob.user_name}", False, "", sup_group_id=self.group.group_id)

        await ws_a.disconnect()
        await ws_b.disconnect()

    @async_to_sync
    async def test_announce_group(self):
        ws_a = self.get_ws("alice")
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()

        ws_c = self.get_ws("carol")
        connected, _ = await ws_c.connect()
        self.assertTrue(connected)
        _ = await ws_c.receive_json_from()

        data = {"group_id": self.group.group_id, "announcement": "THIS IS A GROUP"}
        res = await self.async_post("/api/group/announce", data, "alice")
        print(res.json())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret = await ws_c.receive_json_from()
        assertSingleMessage(self, ret, sender_id=self.alice.user_id, group_id=self.group.group_id, msg_type="announcement", msg_body="THIS IS A GROUP")
        await ws_a.disconnect()
        await ws_c.disconnect()

    @async_to_sync
    async def test_preference_group(self):
        ws = self.get_ws("alice")
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        _ = await ws.receive_json_from()

        data = {"group_id": self.group.group_id, "do_not_disturb": False, "top": True}
        res = await self.async_put("/api/group/preference", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret = await ws.receive_json_from()
        assertSingleSysmsg(self, ret, "change_preference", f"alice set group {self.group.group_name} do not disturb: {False}; top: {True}", False, "", sup_group_id=self.group.group_id)
        await ws.disconnect()

    @async_to_sync
    async def test_modify_group(self):
        ws_a = self.get_ws("alice")
        connected, _ = await ws_a.connect()
        self.assertTrue(connected)
        _ = await ws_a.receive_json_from()

        ws_c = self.get_ws("carol")
        connected, _ = await ws_c.connect()
        self.assertTrue(connected)
        _ = await ws_c.receive_json_from()

        data = {"group_id": self.group.group_id, "group_name": "new name"}
        res = await self.async_put("/api/group/modify", data, "alice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        ret = await ws_c.receive_json_from()
        assertSingleSysmsg(self, ret, "modify_group_info", f"{self.alice.user_name} change group group into new name", False, "", sup_group_id=self.group.group_id)
        await ws_a.disconnect()
        await ws_c.disconnect()
