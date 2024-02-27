from django.test import TestCase
from im.models import User, Friend, Group, Groupmember, Message

from utils.utils_jwt import generate_jwt_token

# Create your tests here.
class GroupTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")
        self.carol = User.objects.create(user_name="carol", password="123456", user_email="carol@163.com")
        self.eve = User.objects.create(user_name="eve", password="123456", user_email="eve@163.com")
        self.test_group = Group.objects.create(group_name="test_group", group_owner=self.alice)
        Groupmember.objects.create(group=self.test_group, member_user=self.alice, member_role="admin", do_not_disturb=True)
        self.group_ab = Group.objects.create(group_name="")
        Groupmember.objects.create(group=self.group_ab, member_user=self.alice, member_role="")
        Groupmember.objects.create(group=self.group_ab, member_user=self.bob, member_role="", top=True)
        Friend.objects.create(user=self.alice, friend=self.bob, group=self.group_ab)
        Friend.objects.create(user=self.bob, friend=self.alice, group=self.group_ab)
        self.test_group_new = Group.objects.create(group_name="test_group_new", group_owner=self.alice)
        Groupmember.objects.create(group=self.test_group_new, member_user=self.alice, member_role="admin")
        Groupmember.objects.create(group=self.test_group_new, member_user=self.bob, member_role="member", do_not_disturb=True)
        Groupmember.objects.create(group=self.test_group_new, member_user=self.carol, member_role="member")
        Message.objects.create(sender=self.alice, group=self.test_group_new, msg_body="THIS IS A GROUP", msg_type="announcement")

    # destructor
    def tearDown(self):
        Friend.objects.all().delete()
        Group.objects.all().delete()
        User.objects.all().delete()

    # ! Test section
    def test_create_group_no_jwt(self):
        data = {}
        res = self.client.post('/api/group/create', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_create_group_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/group/create', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_create_group_no_body(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/create', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_create_group_id_wrong_type(self):
        data = {"group_name": "test_group", "member_ids": ["bob"]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/create', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_create_group_emtpy_name(self):
        data = {"group_name": "", "member_ids": [self.bob.user_id]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/create', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_create_group_add_self(self):
        data = {"group_name": "test_group", "member_ids": [self.alice.user_id]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/create', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_create_group_nonexisting_user(self):
        data = {"group_name": "test_group", "member_ids": [-1]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/create', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_create_group_not_friend(self):
        data = {"group_name": "test_group", "member_ids": [self.carol.user_id]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/create', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_create_group_success(self):
        data = {"group_name": "new_group", "member_ids": [self.bob.user_id]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/create', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        ret = res.json()
        self.assertTrue("group_name" in ret and "group_id" in ret)
        self.assertEqual(ret["group_name"], "new_group")

    def test_create_group_get(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/create', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_list_group_no_jwt(self):
        data = {}
        res = self.client.get('/api/group/list', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_list_group_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.get('/api/group/list', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_list_group_success(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        gm = Groupmember.objects.filter(group=self.test_group, member_user=self.alice).first()
        gm.sent_msg_id = msg.msg_id
        gm.ack_msg_id = msg.msg_id
        gm.save(update_fields=["sent_msg_id", "ack_msg_id"])

        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/list', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        ret = res.json()
        self.assertTrue("groups" in ret)
        group_list = sorted(ret["groups"], key=lambda x: x["group_id"])
        self.assertIsInstance(group_list, list)
        self.assertEqual(len(group_list), 3)
        
        group = group_list[0]
        group["members"][0]["group_id"] = group["group_id"]
        self.assertEqual(
            {
                "members": [gm.serialize(private=True)],
                "latest_msg": msg.serialize(),
                **(self.test_group.serialize()),
                "do_not_disturb": gm.do_not_disturb,
                "top": gm.top,
            },
            group
        )

        group = group_list[1]
        self.assertEqual(group["group_id"], self.group_ab.group_id)
        self.assertEqual(group["group_name"], "")
        self.assertIsNone(group["group_owner_id"])
        self.assertIsNone(group["latest_msg"])
        self.assertSetEqual(set(item["member_id"] for item in group["members"]), {self.alice.user_id, self.bob.user_id})
        self.assertListEqual([item["member_role"] for item in group["members"]], ["", ""])

    def test_list_group_post(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/list', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_delete_group_no_jwt(self):
        data = {}
        res = self.client.delete('/api/group/delete', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_group_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.delete('/api/group/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_group_nonexisting(self):
        data = {"group_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.delete('/api/group/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_friend_group(self):
        data = {"group_id": self.group_ab.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.delete('/api/group/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_group_not_owner(self):
        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.delete('/api/group/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_group_success(self):
        group_id = self.test_group.group_id
        data = {"group_id": group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.delete('/api/group/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertFalse(Group.objects.filter(group_id=group_id).exists())

    def test_delete_group_post(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_join_group_no_jwt(self):
        data = {}
        res = self.client.post('/api/group/join', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_join_group_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/group/join', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_join_group_nonexisting(self):
        data = {"group_id": -1, "message": ""}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/join', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_join_friend_group(self):
        data = {"group_id": self.group_ab.group_id, "message": ""}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/join', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_join_group_member(self):
        data = {"group_id": self.test_group.group_id, "message": ""}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/join', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_join_group_get(self):
        data = {}
        res = self.client.get('/api/group/join', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_leave_group_no_jwt(self):
        data = {}
        res = self.client.post('/api/group/leave', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_leave_group_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/group/leave', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_leave_group_nonexisting(self):
        data = {"group_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/leave', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_leave_friend_group(self):
        data = {"group_id": self.group_ab.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/leave', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_leave_group_owner(self):
        group_id = self.test_group.group_id
        data = {"group_id": group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/leave', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertFalse(Group.objects.filter(group_id=group_id).exists())

    def test_leave_group_not_member(self):
        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.post('/api/group/leave', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_leave_group_member(self):
        Groupmember.objects.create(group=self.test_group, member_user=self.carol, member_role="member")
        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.post('/api/group/leave', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertFalse(Groupmember.objects.filter(group=self.test_group, member_user=self.carol).exists())

    def test_leave_group_get(self):
        data = {}
        res = self.client.get('/api/group/leave', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_kick_user_no_jwt(self):
        data = {}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_nonexisting_group(self):
        data = {"group_id": -1, "member_id": self.bob.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_friend_group(self):
        data = {"group_id": self.group_ab.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_self_not_admin(self):
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="member")
        data = {"group_id": self.test_group.group_id, "member_id": self.alice.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_self_not_member(self):
        data = {"group_id": self.test_group.group_id, "member_id": self.alice.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_target_nonexisting(self):
        data = {"group_id": self.test_group.group_id, "member_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_oneself(self):
        data = {"group_id": self.test_group.group_id, "member_id": self.alice.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_target_not_member(self):
        data = {"group_id": self.test_group.group_id, "member_id": self.carol.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_target_higher_permission(self):
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="admin")
        data = {"group_id": self.test_group.group_id, "member_id": self.alice.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 2)

    def test_kick_user_success(self):
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="member")
        data = {"group_id": self.test_group.group_id, "member_id": self.bob.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/kick_user', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertFalse(Groupmember.objects.filter(group=self.test_group, member_user=self.bob).exists())

    def test_kick_user_get(self):
        data = {}
        res = self.client.get('/api/group/kick_user', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_set_role_no_jwt(self):
        data = {}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_set_role_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_set_role_nonexisting_group(self):
        data = {"group_id": -1, "member_id": self.bob.user_id, "member_role": "admin"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_set_role_friend_group(self):
        data = {"group_id": self.group_ab.group_id, "member_id": self.bob.user_id, "member_role": "admin"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_set_role_self_not_member(self):
        data = {"group_id": self.test_group.group_id, "member_id": self.alice.user_id, "member_role": "admin"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_set_role_self_not_owner(self):
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="member")
        data = {"group_id": self.test_group.group_id, "member_id": self.alice.user_id, "member_role": "admin"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 2)

    def test_set_role_target_nonexisting(self):
        data = {"group_id": self.test_group.group_id, "member_id": -1, "member_role": "admin"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_set_role_oneself(self):
        data = {"group_id": self.test_group.group_id, "member_id": self.alice.user_id, "member_role": "admin"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_set_role_target_not_member(self):
        data = {"group_id": self.test_group.group_id, "member_id": self.carol.user_id, "member_role": "admin"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_set_role_admin(self):
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="member")
        data = {"group_id": self.test_group.group_id, "member_id": self.bob.user_id, "member_role": "admin"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue(Groupmember.objects.filter(group=self.test_group, member_user=self.bob, member_role="admin").exists())

    def test_set_role_owner(self):
        group_id = self.test_group.group_id
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="member")
        data = {"group_id": self.test_group.group_id, "member_id": self.bob.user_id, "member_role": "owner"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue(Groupmember.objects.filter(group=self.test_group, member_user=self.bob, member_role="admin").exists())
        self.assertEqual(Group.objects.get(group_id=group_id).group_owner.user_id, self.bob.user_id)

    def test_set_role_wrong_type(self):
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="member")
        data = {"group_id": self.test_group.group_id, "member_id": self.bob.user_id, "member_role": "cat"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/set_role', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_set_role_put(self):
        data = {}
        res = self.client.put('/api/group/set_role', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_info_no_jwt(self):
        data = {}
        res = self.client.get('/api/group/info', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_info_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.get('/api/group/info', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_info_no_params(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/info', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_info_wrong_param_type(self):
        data = {"group_id": "alpha"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/info', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_info_nonexisting_group(self):
        data = {"group_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/info', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_info_not_member(self):
        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.get('/api/group/info', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_info_success(self):
        gm = Groupmember.objects.filter(group=self.test_group, member_user=self.alice).first()
        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/info', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        ret = res.json()
        self.assertSetEqual(set(ret.keys()), {"code", "info", "group_id", "group_name", "group_owner_id", "create_time", "members", "latest_msg", "top", "do_not_disturb"})
        self.assertEqual(ret["group_id"], self.test_group.group_id)
        self.assertEqual(ret["group_name"], self.test_group.group_name)
        self.assertEqual(ret["group_owner_id"], self.alice.user_id)
        self.assertEqual(ret["top"], False)
        self.assertEqual(ret["do_not_disturb"], True)
        self.assertIsNone(ret["latest_msg"])
        members = ret["members"]
        self.assertIsInstance(members, list)
        self.assertEqual(len(members), 1)
        self.assertEqual(
            {
                "group_id": ret["group_id"],
                **(members[0]),
                "top": ret["top"],
                "do_not_disturb": ret["do_not_disturb"],
            },
            gm.serialize()
        )

    def test_info_friend_group(self):
        data = {"group_id": self.group_ab.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.get('/api/group/info', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        ret = res.json()
        self.assertSetEqual(set(ret.keys()), {"code", "info", "group_id", "group_name", "group_owner_id", "create_time", "members", "latest_msg", "top", "do_not_disturb"})
        self.assertEqual(ret["group_id"], self.group_ab.group_id)
        self.assertEqual(ret["group_name"], "")
        self.assertEqual(ret["top"], True)
        self.assertEqual(ret["do_not_disturb"], False)
        self.assertIsNone(ret["group_owner_id"])
        self.assertIsNone(ret["latest_msg"])
        self.assertSetEqual({member["member_id"] for member in ret["members"]}, {self.alice.user_id, self.bob.user_id})

    def test_info_post(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/info', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_announce_get(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/announce', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_announce_no_jwt(self):
        data = {}
        res = self.client.post('/api/group/announce', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_announce_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("davido")}
        res = self.client.post('/api/group/announce', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_announce_no_params(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/announce', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_announce_wrong_param_type(self):
        data = {"group_id": "alpha"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/announce', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_announce_nonexisting_group(self):
        data = {"group_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/announce', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_announce_not_member(self):
        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.post('/api/group/announce', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_announce_not_admin(self):
        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/group/announce', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_announce_success(self): # is it ok? -> add a test in websocket/tests/test_ws_group
        data = {"group_id": self.test_group_new.group_id, "announcement": "THIS IS A GROUP"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/announce', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

    def test_announcements_post(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/announcements', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_announcements_no_jwt(self):
        data = {}
        res = self.client.get('/api/group/announcements', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_announcements_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("davido")}
        res = self.client.get('/api/group/announcements', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_announcements_no_params(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/announcements', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_announcements_wrong_param_type(self):
        data = {"group_id": "alpha"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/announcements', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_announcements_nonexisting_group(self):
        data = {"group_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/announcements', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_announcements_not_member(self):
        data = {"group_id": self.test_group_new.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("eve")}
        res = self.client.get('/api/group/announcements', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_announcements_success(self):
        data = {"group_id": self.test_group_new.group_id, "announcement": "THIS IS A GROUP"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.get('/api/group/announcements', data=data, content_type='application/json', **headers)
        ret = res.json()
        print(ret)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertSetEqual(set(ret.keys()), {"code", "info", "announcements"})
        self.assertEqual(len(ret["announcements"]), 1)
        announcement = ret["announcements"][0]
        self.assertEqual(announcement["sender_id"], 1)
        self.assertEqual(announcement["group_id"], 3)
        self.assertEqual(announcement["msg_body"], "THIS IS A GROUP")

    def test_preference_post(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/preference', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_preference_no_jwt(self):
        data = {}
        res = self.client.put('/api/group/preference', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_preference_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("davido")}
        res = self.client.put('/api/group/preference', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_preference_no_params(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/group/preference', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_preference_wrong_param_type(self):
        data = {"group_id": "aloha"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/group/preference', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_preference_nonexisting_group(self):
        data = {"group_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/group/preference', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_preference_not_member(self):
        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.put('/api/group/preference', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)
    
    def test_preference_success(self):
        data = {"group_id": self.test_group_new.group_id, "do_not_disturb": True}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.put('/api/group/preference', data=data, content_type='application/json', **headers)
        ret = res.json()
        print(ret)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(Groupmember.objects.filter(group=self.test_group_new, member_user=self.bob).first().do_not_disturb, True)

    def test_preference_success1(self):
        data = {"group_id": self.test_group_new.group_id, "do_not_disturb": False, "top": True}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.put('/api/group/preference', data=data, content_type='application/json', **headers)
        ret = res.json()
        print(ret)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(Groupmember.objects.filter(group=self.test_group_new, member_user=self.bob).first().do_not_disturb, False)
        self.assertEqual(Groupmember.objects.filter(group=self.test_group_new, member_user=self.bob).first().top, True)
        
    def test_modify_post(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/modify', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_modify_no_jwt(self):
        data = {}
        res = self.client.put('/api/group/modify', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("davido")}
        res = self.client.put('/api/group/modify', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_no_params(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/group/modify', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_modify_wrong_param_type(self):
        data = {"group_id": "aloha"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/group/modify', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_modify_nonexisting_group(self):
        data = {"group_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/group/modify', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_not_member(self):
        data = {"group_id": self.test_group.group_id, "group_name": "new name"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.put('/api/group/modify', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_not_admin(self):
        data = {"group_id": self.test_group_new.group_id, "group_name": "new name"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.put('/api/group/modify', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_success(self):
        data = {"group_id": self.test_group_new.group_id, "group_name": "new name"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/group/modify', data=data, content_type='application/json', **headers)
        ret = res.json()
        print(ret)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue(Group.objects.filter(group_name="new name").exists())