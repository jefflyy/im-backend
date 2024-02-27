from django.test import TestCase

from im.models import User

from utils.utils_mail import gen_code
from utils.utils_jwt import generate_jwt_token, auth_jwt_token


class ModifyTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="114514", user_email="bob@163.com")

    # destructor
    def tearDown(self):
        User.objects.all().delete()

    # ! Test section
    def test_modify_get(self):
        res = self.client.get('/api/user/modify', data={}, content_type="application/json")
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_modify_no_jwt(self):
        res = self.client.put('/api/user/modify', data={}, content_type="application/json")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_wrong_jwt(self):
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.put('/api/user/modify', data={}, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_user_name_existing(self):
        data = {"user_name": "bob"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/user/modify', data=data, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_email_existing(self):
        data = {"user_email": "bob@163.com"}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/user/modify', data=data, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_email_wrong_code(self):
        email = "new_email@163.com"
        data = {"user_email": email, "code": -1}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/user/modify', data=data, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_modify_all_success(self):
        user_id = self.alice.user_id

        email = "new_email@163.com"
        code = gen_code(email)
        data = {"user_name": "carol", "password": "654321", "user_email": email, "code": code}
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.put('/api/user/modify', data=data, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["code"], 0)
        
        content = res.json()
        self.assertTrue("user_name" in content.keys())
        self.assertEqual(content["user_name"], "carol")
        self.assertTrue("jwt_token" in content.keys())
        self.assertEqual(auth_jwt_token(content["jwt_token"]), "carol")
        self.assertEqual(content["user_id"], user_id)

        user = User.objects.filter(user_id=user_id).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.user_name, "carol")
        self.assertEqual(user.password, "654321")
        self.assertEqual(user.user_email, "new_email@163.com")
