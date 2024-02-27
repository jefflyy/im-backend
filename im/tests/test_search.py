from django.test import TestCase
from im.models import User, Friend, Group, Groupmember

from utils.utils_jwt import generate_jwt_token
from utils.utils_request import return_field

# Create your tests here.
class SearchTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="114514", user_email="bob@163.com")
        self.group = Group.objects.create(group_name="test_group", group_owner=self.alice)
        Groupmember.objects.create(group=self.group, member_user=self.alice, member_role="admin")
        self.group_ab = Group.objects.create(group_name="")
        Groupmember.objects.create(group=self.group_ab, member_user=self.alice, member_role="")
        Groupmember.objects.create(group=self.group_ab, member_user=self.bob, member_role="")
        Friend.objects.create(user=self.alice, friend=self.bob, group=self.group_ab)
        Friend.objects.create(user=self.bob, friend=self.alice, group=self.group_ab)

    # destructor
    def tearDown(self):
        Friend.objects.all().delete()
        Groupmember.objects.all().delete()
        Group.objects.all().delete()
        User.objects.all().delete()

    def test_search_user_no_jwt(self):
        data = {}
        res = self.client.get('/api/user/search', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_search_user_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.get('/api/user/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_search_user_id_found(self):
        data = {"user_id": self.bob.user_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/user/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(res.json()['result'], [return_field(self.bob.serialize(), [
            "user_id",
            "user_name",
            "register_time",
            "login_time",
            "user_email",
        ])])

    def test_search_user_id_not_found(self):
        data = {"user_id": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/user/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(res.json()['result'], [])

    def test_search_user_id_wrong_type(self):
        data = {"user_id": "ff14"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/user/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_search_user_name_found(self):
        data = {"user_name": "bob"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/user/search', data=data, content_type='application/json', **headers)
        print(res.json())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(res.json()['result'], [return_field(self.bob.serialize(), [
            "user_id",
            "user_name",
            "register_time",
            "login_time",
            "user_email",
        ])])

    def test_search_user_name_not_found(self):
        data = {"user_name": "Mr. not-exist"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/user/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(res.json()['result'], [])

    def test_search_user_name_fuzzy(self):
        bob2 = User.objects.create(user_name="secondbob", password="114514", user_email="bob2@163.com")
        data = {"user_name": "bob"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/user/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertSetEqual(set(user["user_id"] for user in res.json()["result"]), {self.bob.user_id, bob2.user_id})

    def test_search_user_wrong_parameter(self):
        data = {"id": 2}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/user/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_search_user_post(self):
        res = self.client.post('/api/user/search')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_search_group_no_jwt(self):
        data = {}
        res = self.client.get('/api/group/search', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_search_group_wrong_jwt(self):
        data = {}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.get('/api/group/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_search_group_id_found(self):
        data = {"group_id": self.group.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(res.json()['result'], [{
            "group_owner_name": self.group.group_owner.user_name,
            **(self.group.serialize()),
        }])

    def test_search_group_id_not_found(self):
        data = {"group_id": self.group_ab.group_id}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(res.json()['result'], [])

    def test_search_group_id_wrong_type(self):
        data = {"group_id": "0x01"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_search_group_name_found(self):
        data = {"group_name": "test_group"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(res.json()['result'], [{
            "group_owner_name": self.group.group_owner.user_name,
            **(self.group.serialize()),
        }])

    def test_search_group_name_fuzzy(self):
        group2 = Group.objects.create(group_name="test_group2", group_owner=self.alice)
        Groupmember.objects.create(group=group2, member_user=self.alice, member_role="admin")

        data = {"group_name": "test_group"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertSetEqual(set(group["group_id"] for group in res.json()["result"]), {self.group.group_id, group2.group_id})

    def test_search_group_name_not_found(self):
        data = {"group_name": "Gr. not-exist"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertEqual(res.json()['result'], [])

    def test_search_group_wrong_parameter(self):
        data = {"group_name": ""}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/group/search', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_search_group_post(self):
        res = self.client.post('/api/group/search')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)
