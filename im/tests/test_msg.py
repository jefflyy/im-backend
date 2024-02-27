from django.test import TestCase
from im.models import User, Group, Groupmember, Message, File, Userdelmsg

from utils.utils_jwt import generate_jwt_token

# Create your tests here.
class MessageTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")
        self.test_group = Group.objects.create(group_name="test_group", group_owner=self.alice)
        Groupmember.objects.create(group=self.test_group, member_user=self.alice, member_role="admin")
        self.test_group_2 = Group.objects.create(group_name="test_group_2", group_owner=self.bob)
        Groupmember.objects.create(group=self.test_group_2, member_user=self.bob, member_role="admin")
        self.group_ab = Group.objects.create(group_name="")
        Groupmember.objects.create(group=self.group_ab, member_user=self.alice, member_role="")
        Groupmember.objects.create(group=self.group_ab, member_user=self.bob, member_role="")

    # destructor
    def tearDown(self):
        Message.objects.all().delete()
        Groupmember.objects.all().delete()
        Group.objects.all().delete()
        User.objects.all().delete()

    # ! Test section
    def test_fetch_msg_no_jwt(self):
        data = {}
        res = self.client.get('/api/msg/fetch', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_fetch_msg_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.get('/api/msg/fetch', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_fetch_msg_no_params(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/msg/fetch', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_fetch_msg_wrong_param_type(self):
        data = {"group_id": "ww"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/msg/fetch', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_fetch_msg_nonexisting_group(self):
        data = {"group_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/msg/fetch', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_fetch_msg_not_member(self):
        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.get('/api/msg/fetch', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_fetch_msg_success(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        gm = Groupmember.objects.filter(group=self.test_group, member_user=self.alice).first()
        gm.sent_msg_id = msg.msg_id
        gm.ack_msg_id = msg.msg_id
        gm.save(update_fields=["sent_msg_id", "ack_msg_id"])

        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/msg/fetch', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        res = res.json()
        self.assertTrue("msgs" in res)
        self.assertListEqual(res["msgs"], [msg.serialize()])

    def test_fetch_msg_post(self):
        res = self.client.post('/api/msg/fetch')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_ack_msg_no_jwt(self):
        data = {}
        res = self.client.post('/api/msg/ack', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_ack_msg_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/msg/ack', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_ack_msg_nonexisting_group(self):
        data = {"group_id": -1, "msg_id": 1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/ack', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_ack_msg_not_member(self):
        data = {"group_id": self.test_group.group_id, "msg_id": 1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/msg/ack', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_ack_msg_group_has_no_msg(self):
        data = {"group_id": self.test_group.group_id, "msg_id": 1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/ack', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_ack_future_msg(self):
        Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        data = {"group_id": self.test_group.group_id, "msg_id": 114514}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/ack', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_ack_msg_get(self):
        res = self.client.get('/api/msg/ack')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_recall_msg_no_jwt(self):
        data = {}
        res = self.client.post('/api/msg/recall', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_recall_msg_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/msg/recall', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_recall_msg_nonexisting(self):
        data = {"msg_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/recall', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_recall_msg_not_member(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        data = {"msg_id": msg.msg_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/msg/recall', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_recall_msg_permission_denied(self):
        Groupmember.objects.create(group=self.test_group, member_user=self.bob, member_role="member")
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        data = {"msg_id": msg.msg_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/msg/recall', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 2)

    def test_recall_msg_recalled(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="recall", msg_body="")
        data = {"msg_id": msg.msg_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/recall', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_recall_msg_excced_time(self):
        msg = Message.objects.create(sender=self.alice, group=self.group_ab, msg_type="text", msg_body="hello")
        msg.create_time = 0
        msg.save(update_fields=["create_time"])
        data = {"msg_id": msg.msg_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/recall', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_recall_msg_file(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text/plain", msg_body="pytest.ini")
        File.objects.create(msg=msg)
        data = {"msg_id": msg.msg_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/recall', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue(File.objects.filter(msg=msg).exists())

    def test_recall_msg_get(self):
        res = self.client.get('/api/msg/recall')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_delete_msg_no_jwt(self):
        data = {}
        res = self.client.delete('/api/msg/delete', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_msg_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.delete('/api/msg/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_msg_nonexisting(self):
        data = {"msg_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.delete('/api/msg/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_msg_not_member(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        data = {"msg_id": msg.msg_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.delete('/api/msg/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_msg_already_deleted(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        Userdelmsg.objects.create(user=self.alice, msg=msg)
        data = {"msg_id": msg.msg_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.delete('/api/msg/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_delete_msg_post(self):
        res = self.client.post('/api/msg/delete')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_delete_msg_then_fetch_msg(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        gm = Groupmember.objects.filter(group=self.test_group, member_user=self.alice).first()
        gm.sent_msg_id = msg.msg_id
        gm.ack_msg_id = msg.msg_id
        gm.save(update_fields=["sent_msg_id", "ack_msg_id"])

        data = {"msg_id": msg.msg_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.delete('/api/msg/delete', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)

        data = {"group_id": self.test_group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/msg/fetch', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        res = res.json()
        self.assertTrue("msgs" in res)
        self.assertListEqual(res["msgs"], [])

        delmsg = Message.objects.filter(msg_id=msg.msg_id).first()
        self.assertEqual(delmsg, msg)

    def test_forward_msg_no_jwt(self):
        data = {}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_forward_msg_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_forward_msg_origin_group_nonexisting(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        data = {"origin_group_id": -1, "target_group_id": self.test_group.group_id, "msg_ids": [msg.msg_id]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_forward_msg_origin_group_not_member(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        data = {"origin_group_id": self.test_group.group_id, "target_group_id": self.test_group_2.group_id, "msg_ids": [msg.msg_id]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_forward_msg_target_group_nonexisting(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        data = {"origin_group_id": self.test_group.group_id, "target_group_id": -1, "msg_ids": [msg.msg_id]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_forward_msg_target_group_not_member(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="text", msg_body="hello")
        data = {"origin_group_id": self.test_group.group_id, "target_group_id": self.test_group_2.group_id, "msg_ids": [msg.msg_id]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_forward_msg_id_wrong_type(self):
        data = {"origin_group_id": self.test_group.group_id, "target_group_id": self.test_group.group_id, "msg_ids": ["ww"]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_forward_msg_nonexisting(self):
        data = {"origin_group_id": self.test_group.group_id, "target_group_id": self.test_group.group_id, "msg_ids": [-1]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_forward_msg_recalled(self):
        msg = Message.objects.create(sender=self.alice, group=self.test_group, msg_type="recall", msg_body="")
        data = {"origin_group_id": self.test_group.group_id, "target_group_id": self.test_group.group_id, "msg_ids": [msg.msg_id]}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_forward_zero_msg(self):
        data = {"origin_group_id": self.test_group.group_id, "target_group_id": self.test_group.group_id, "msg_ids": []}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/msg/forward', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_forward_msg_get(self):
        res = self.client.get('/api/msg/forward')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_translate_no_jwt(self):
        res = self.client.get('/api/msg/translate')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_translate_wrong_jwt(self):
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.get('/api/msg/translate', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_translate_no_param(self):
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/msg/translate', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_translate_failed(self):
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/msg/translate?query=hello', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)
