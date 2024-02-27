from django.test import TestCase
from im.models import User, Friend, Group

from utils.utils_request import return_field
from utils.utils_jwt import generate_jwt_token

# Create your tests here.
class FriendTests(TestCase):
    # Initializer
    def setUp(self):
        self.test_user = User.objects.create(user_name="alice", password="123456", user_email="existing_email@163.com")

    # destructor
    def tearDown(self):
        Friend.objects.all().delete()
        Group.objects.all().delete()
        User.objects.all().delete()

    # ! Test section
    def test_friend_list_post(self):
        data = {}
        res = self.client.post('/api/friend/list', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_friend_list_no_jwt(self):
        data = {}
        res = self.client.get('/api/friend/list', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_friend_list_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.get('/api/friend/list', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_friend_list_success(self):
        bob = User.objects.create(user_name="bob", password="114514", user_email="bob@163.com")
        group = Group.objects.create(group_name="")
        Friend.objects.create(user=self.test_user, friend=bob, group=group)
        Friend.objects.create(user=bob, friend=self.test_user, group=group)

        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/friend/list', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue("friends" in res.json())
        friends = res.json()["friends"]
        self.assertIsInstance(friends, list)
        self.assertListEqual(friends, [{
            "group_id": group.group_id,
            **return_field(bob.serialize(), [
                "user_id",
                "user_name",
                "user_email",
                "register_time",
                "login_time",
            ]),
        }])

    def test_friend_delete_put(self):
        data = {}
        res = self.client.put('/api/friend/delete', data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_friend_delete_no_jwt(self):
        data = {}
        res = self.client.delete('/api/friend/delete', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_friend_delete_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.delete('/api/friend/delete', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_friend_delete_nonexisting_user(self):
        data = {"id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.delete('/api/friend/delete', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_friend_delete_nonexisting_relationship(self):
        bob = User.objects.create(user_name="bob", password="114514", user_email="bob@163.com")

        data = {"id": bob.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.delete('/api/friend/delete', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_friend_delete_success(self):
        bob = User.objects.create(user_name="bob", password="114514", user_email="bob@163.com")
        group = Group.objects.create(group_name="")
        Friend.objects.create(user=self.test_user, friend=bob, group=group)
        Friend.objects.create(user=bob, friend=self.test_user, group=group)

        data = {"id": bob.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.delete('/api/friend/delete', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertFalse(Friend.objects.filter(user=self.test_user, friend=bob).exists())
        self.assertFalse(Friend.objects.filter(user=bob, friend=self.test_user).exists())

    def test_apply_friend_get(self):
        res = self.client.get('/api/friend/apply', data={}, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_apply_friend_no_jwt(self):
        res = self.client.post('/api/friend/apply', data={}, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_apply_friend_nonexisting_user(self):
        data = {"friend_user_id": -1, "message": "hello"}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token(self.test_user.user_name)}
        res = self.client.post('/api/friend/apply', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_apply_friend_oneself(self):
        data = {"friend_user_id": self.test_user.user_id, "message": "hello"}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token(self.test_user.user_name)}
        res = self.client.post('/api/friend/apply', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_apply_friend_existing_friendship(self):
        target = User.objects.create(user_name='bob', password='114514', user_email='bob@163.com')
        group = Group.objects.create(group_name="")
        Friend.objects.create(user=self.test_user, friend=target, group=group)
        Friend.objects.create(user=target, friend=self.test_user, group=group)

        data = {"friend_user_id": target.user_id, "message": "hello"}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token(self.test_user.user_name)}
        res = self.client.post('/api/friend/apply', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)
