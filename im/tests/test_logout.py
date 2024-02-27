from django.test import TestCase

from im.models import User

from utils.utils_jwt import generate_jwt_token


class LoginTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")

    # destructor
    def tearDown(self):
        User.objects.all().delete()

    # ! Test section
    def test_logout_get(self):
        res = self.client.get('/api/user/logout', data={}, content_type="application/json")
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_logout_no_jwt(self):
        res = self.client.post('/api/user/logout', data={}, content_type="application/json")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_logout_wrong_jwt(self):
        headers= {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post('/api/user/logout', data={}, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)
