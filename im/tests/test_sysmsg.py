from django.test import TestCase

from im.models import User, Systemop, Systemmsg

from utils.utils_jwt import generate_jwt_token
from utils.utils_sysmsg import extract_sysmsg

# Create your tests here.
class ImTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")

    # ! Test section
    def test_handle_sysmsg_get(self):
        res = self.client.get('/api/sysmsg/handle', data={}, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_handle_sysmsg_no_jwt(self):
        res = self.client.post('/api/sysmsg/handle', data={}, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_handle_sysmsg_wrong_jwt(self):
        data = {"sysmsg_id": 1, "operation": "yes"}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/sysmsg/handle', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_handle_sysmsg_nonexisting(self):
        data = {"sysmsg_id": -1, "operation": "yes"}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token('alice')}
        res = self.client.post('/api/sysmsg/handle', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_handle_sysmsg_wrong_operation(self):
        sysop = Systemop.objects.create(
            user=self.alice,
            sysop_type="apply_friend",
            target_user=self.bob,
            message="",
            need_operation=True,
            result=""
        )
        sysmsg = Systemmsg.objects.create(
            sysop=sysop,
            target_user=self.bob,
            sysmsg_type="apply_friend",
            message="",
            can_operate=True,
            result=""
        )
        data = {"sysmsg_id": sysmsg.sysmsg_id, "operation": "zan_shi_bu_neng_gei_ni_ming_que_de_da_fu"}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token('bob')}
        res = self.client.post('/api/sysmsg/handle', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_handle_sysmsg_wrong_type(self):
        sysop = Systemop.objects.create(
            user=self.alice,
            sysop_type="incorrect type",
            target_user=self.bob,
            message="",
            need_operation=True,
            result=""
        )
        sysmsg = Systemmsg.objects.create(
            sysop=sysop,
            target_user=self.bob,
            sysmsg_type="incorrect type",
            message="",
            can_operate=True,
            result=""
        )
        data = {"sysmsg_id": sysmsg.sysmsg_id, "operation": "yes"}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token('bob')}
        res = self.client.post('/api/sysmsg/handle', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], -2)

    def test_handle_sysmsg_already_completed(self):
        sysop = Systemop.objects.create(
            user=self.alice,
            sysop_type="apply_friend",
            target_user=self.bob,
            message="",
            need_operation=False,
            result=""
        )
        sysmsg = Systemmsg.objects.create(
            sysop=sysop,
            target_user=self.bob,
            sysmsg_type="apply_friend",
            message="",
            can_operate=True,
            result=""
        )
        data = {"sysmsg_id": sysmsg.sysmsg_id, "operation": "yes"}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token('bob')}
        res = self.client.post('/api/sysmsg/handle', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 410)
        self.assertEqual(res.json()['code'], 2)

    def test_handle_sysmsg_apply_friend_oneself(self):
        sysop = Systemop.objects.create(
            user=self.alice,
            sysop_type="apply_friend",
            target_user=self.alice,
            message="",
            need_operation=True,
            result=""
        )
        sysmsg = Systemmsg.objects.create(
            sysop=sysop,
            target_user=self.alice,
            sysmsg_type="apply_friend",
            message="",
            can_operate=True,
            result=""
        )
        data = {"sysmsg_id": sysmsg.sysmsg_id, "operation": "yes"}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token('alice')}
        res = self.client.post('/api/sysmsg/handle', data=data, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_fetch_sysmsg_no_jwt(self):
        res = self.client.get('/api/sysmsg/fetch', data={}, content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_fetch_sysmsg_wrong_jwt(self):
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.get('/api/sysmsg/fetch', data={}, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_fetch_sysmsg_success(self):
        sysop = Systemop.objects.create(
            user=self.alice,
            sysop_type="apply_friend",
            target_user=self.bob,
            message="",
            need_operation=True,
            result=""
        )
        sysmsg = Systemmsg.objects.create(
            sysop=sysop,
            target_user=self.bob,
            sysmsg_type="apply_friend",
            message="",
            can_operate=True,
            result=""
        )
        self.bob.read_sysmsg_id = sysmsg.sysmsg_id
        self.bob.save(update_fields=["read_sysmsg_id"])

        headers = {"HTTP_AUTHORIZATION": generate_jwt_token('bob')}
        res = self.client.get('/api/sysmsg/fetch', data={}, content_type='application/json', **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        self.assertTrue("sysmsgs" in res.json())
        self.assertListEqual(res.json()['sysmsgs'], [extract_sysmsg(sysmsg)])

    def test_fetch_sysmsg_post(self):
        res = self.client.post('/api/sysmsg/fetch', data={}, content_type='application/json')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)
