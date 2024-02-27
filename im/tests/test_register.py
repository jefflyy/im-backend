from django.test import TestCase

from im.models import User

from utils.utils_mail import gen_code


class LoginTests(TestCase):
    # Initializer
    def setUp(self):
        self.test_user = User.objects.create(user_name="alice", password="123456", user_email="existing_email@163.com")

    # destructor
    def tearDown(self):
        User.objects.all().delete()

    # ! Test section
    def test_register_new_user_new_email(self):
        email = "new_email@163.com"
        code = gen_code(email)
        data = {
            "user_name": "carol",
            "password": "123456",
            "user_email": email,
            "email_code": str(code),
        }

        res = self.client.post('/api/user/register', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue(res.json()['jwt_token'].count('.') == 2)
        self.assertTrue(User.objects.filter(user_name="carol").exists())

    def test_register_new_user_new_email_wrong_code(self):
        email = "new_email@163.com"
        data = {
            "user_name": "carol",
            "password": "123456",
            "user_email": email,
            "email_code": "1145",
        }

        res = self.client.post('/api/user/register', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_register_existing_user(self):
        email = "new_email@163.com"
        code = gen_code(email)
        data = {
            "user_name": "alice",
            "password": "123456",
            "user_email": email,
            "email_code": str(code),
        }

        res = self.client.post('/api/user/register', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)
    
    def test_register_new_user_existing_email(self):
        email = "existing_email@163.com"
        code = gen_code(email)
        data = {
            "user_name": "david",
            "password": "123456",
            "user_email": email,
            "email_code": str(code),
        }

        res = self.client.post('/api/user/register', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)
    
    def test_register_get(self):
        data = {}
        res = self.client.get('/api/user/register', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)