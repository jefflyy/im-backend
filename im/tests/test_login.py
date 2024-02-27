from django.test import TestCase

from im.models import User


class LoginTests(TestCase):
    # Initializer
    def setUp(self):
        self.test_user = User.objects.create(user_name="alice", password="123456", user_email="existing_email@163.com")

    # destructor
    def tearDown(self):
        User.objects.all().delete()

    # ! Test section
    def test_login_existing_user_correct_password(self):
        data = {"user_name": "alice", "password": "123456"}
        res = self.client.post('/api/user/login', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue(res.json()['jwt_token'].count('.') == 2)
        self.assertEqual(res.json()['user_id'], self.test_user.user_id)
    
    def test_login_existing_user_wrong_password(self):
        data = {"user_name": "alice", "password": "114514"}
        res = self.client.post('/api/user/login', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)
    
    def test_login_nonexisting_user(self):
        data = {"user_name": "bob", "password": "123456"}
        res = self.client.post('/api/user/login', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)
    
    def test_login_get(self):
        data = {}
        res = self.client.get('/api/user/login', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)
