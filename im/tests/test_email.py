from django.test import TestCase

from im.models import User

from utils.utils_jwt import check_jwt_token
from utils.utils_mail import get_code, verify_code, gen_code


class LoginTests(TestCase):
    # Initializer
    def setUp(self):
        self.test_user = User.objects.create(user_name="alice", password="123456", user_email="existing_email@163.com")

    # destructor
    def tearDown(self):
        User.objects.all().delete()

    # ! Test section
    def test_send_code(self):
        email = "random_email@163.com"
        data = {"email": email}
        
        res = self.client.post('/api/user/send_mail', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertIsNotNone(get_code(email))
        self.assertFalse(verify_code(email, -1))
        self.assertIsNone(get_code(email))

    def test_send_code_get(self):
        data = {}
        res = self.client.get('/api/user/send_mail', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)
    
    def test_verify_existing_email_correct_code(self):
        email = "existing_email@163.com"
        code = gen_code(email)
        data = {"email": email, "code": str(code)}

        res = self.client.post('/api/user/verify_mail', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertIsNone(get_code(email))
        self.assertEqual(res.json()['user_name'], self.test_user.user_name)
        self.assertEqual(res.json()['user_id'], self.test_user.user_id)
        payload_data = check_jwt_token(res.json()['jwt_token'])
        self.assertDictEqual(payload_data, {"username": self.test_user.user_name})

    def test_verify_nonexisting_email_correct_code(self):
        email = "random_email@163.com"
        code = gen_code(email)
        data = {"email": email, "code": str(code)}

        res = self.client.post('/api/user/verify_mail', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)
        self.assertIsNone(get_code(email))
    
    def test_verify_correct_email_wrong_code(self):
        email = "random_email@163.com"
        code = gen_code(email)
        data = {"email": email, "code": str(code ^ 1)}

        res = self.client.post('/api/user/verify_mail', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_verify_wrong_email(self):
        correct_email = "random_email@163.com"
        code = gen_code(correct_email)
        wrong_email = "other_email@163.com"
        verify_code(wrong_email, -1)
        data = {"email": wrong_email, "code": str(code)}

        res = self.client.post('/api/user/verify_mail', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)
        self.assertFalse(verify_code(correct_email, -1))

    def test_verify_mail_get(self):
        data = {}
        res = self.client.get('/api/user/verify_mail', data=data, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)