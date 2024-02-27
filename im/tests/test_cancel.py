from django.test import TestCase

from im.models import User, Friend, Group, Groupmember

from utils.utils_jwt import generate_jwt_token


class CancelTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")

    # destructor
    def tearDown(self):
        User.objects.all().delete()

    # ! Test section
    def test_cancel_get(self):
        res = self.client.get('/api/user/cancel', data={}, content_type="application/json")
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_cancel_no_jwt(self):
        res = self.client.post('/api/user/cancel', data={}, content_type="application/json")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_cancel_wrong_jwt(self):
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/user/cancel', data={}, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_cancel_friend(self):
        bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")
        group = Group.objects.create(group_name="")
        Groupmember.objects.create(group=group, member_user=self.alice, member_role="")
        Groupmember.objects.create(group=group, member_user=bob, member_role="")
        Friend.objects.create(user=self.alice, friend=bob, group=group)
        Friend.objects.create(user=bob, friend=self.alice, group=group)
        self.test_group = Group.objects.create(group_name="test_group", group_owner=self.alice)
        Groupmember.objects.create(group=self.test_group, member_user=self.alice, member_role="admin")
        Groupmember.objects.create(group=self.test_group, member_user=bob, member_role="member")

        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/user/cancel', data={}, content_type="application/json", **headers)
        print(res.json())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertFalse(User.objects.filter(user_name="alice").exists())
        self.assertFalse(Group.objects.exists())
        self.assertFalse(Groupmember.objects.exists())
        self.assertFalse(Friend.objects.exists())
