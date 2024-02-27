from django.test import TestCase
from django.conf import settings
from urllib3 import encode_multipart_formdata
from PIL import Image
from random import randint
import io, os

from im.models import User, Group, Groupmember

from utils.utils_jwt import generate_jwt_token


class AvatarTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")
        self.carol = User.objects.create(user_name="carol", password="123456", user_email="carol@163.com")
        self.group = Group.objects.create(group_name="test_group", group_owner=self.alice)
        Groupmember.objects.create(group=self.group, member_user=self.alice, member_role="admin")
        Groupmember.objects.create(group=self.group, member_user=self.bob, member_role="member")

    # destructor
    def tearDown(self):
        User.objects.all().delete()

    # ! Test section
    def test_upload_user_avatar_no_jwt(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        res = self.client.post('/api/user/avatar', data=data, content_type=content_type)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_user_avatar_wrong_jwt(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/user/avatar', data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_user_avatar_no_file(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/user/avatar', data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_user_avatar_wrong_file_type(self):
        with open("pytest.ini", "rb") as f:
            raw_data = {"file": f.read()}
            data, content_type = encode_multipart_formdata(raw_data)
            idx = data.find(b'name="file"') + 11
            data = data[:idx] + b'; filename="pytest.ini"\r\nContent-Type: text/plain' + data[idx:]
            headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
            res = self.client.post('/api/user/avatar', data=data, content_type=content_type, **headers)
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json()['code'], 2)

    def test_upload_user_avatar_success(self):
        img = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (randint(0, 255), randint(0, 255), randint(0, 255)))
        f = io.BytesIO()
        img.save(f, format="PNG")
        f.seek(0)
        raw_data = {"file": f.read()}
        data, content_type = encode_multipart_formdata(raw_data)
        idx = data.find(b'name="file"') + 11
        data = data[:idx] + b'; filename="avatar.png"\r\nContent-Type: image/png' + data[idx:]
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/user/avatar', data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        path = os.path.join(settings.MEDIA_ROOT, f"user{self.alice.user_id}")
        self.assertTrue(os.path.exists(path))
        os.remove(path)

    def test_upload_user_avatar_get(self):
        res = self.client.get('/api/user/avatar')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_upload_group_avatar_no_jwt(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        res = self.client.post('/api/group/avatar', data=data, content_type=content_type)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_group_avatar_wrong_jwt(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("david")}
        res = self.client.post('/api/group/avatar', data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_group_avatar_no_group_id(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/group/avatar', data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_group_avatar_nonexisting_group(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post(f"/api/group/avatar?group_id=-1", data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_group_avatar_not_member(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.post(f"/api/group/avatar?group_id={self.group.group_id}", data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_group_avatar_not_admin(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post(f"/api/group/avatar?group_id={self.group.group_id}", data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_group_avatar_no_file(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post(f"/api/group/avatar?group_id={self.group.group_id}", data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_group_avatar_wrong_file_type(self):
        with open("pytest.ini", "rb") as f:
            raw_data = {"file": f.read()}
            data, content_type = encode_multipart_formdata(raw_data)
            idx = data.find(b'name="file"') + 11
            data = data[:idx] + b'; filename="pytest.ini"\r\nContent-Type: text/plain' + data[idx:]
            headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
            res = self.client.post(f"/api/group/avatar?group_id={self.group.group_id}", data=data, content_type=content_type, **headers)
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json()['code'], 2)

    def test_upload_group_avatar_success(self):
        img = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (randint(0, 255), randint(0, 255), randint(0, 255)))
        f = io.BytesIO()
        img.save(f, format="PNG")
        f.seek(0)
        raw_data = {"file": f.read()}
        data, content_type = encode_multipart_formdata(raw_data)
        idx = data.find(b'name="file"') + 11
        data = data[:idx] + b'; filename="avatar.png"\r\nContent-Type: image/png' + data[idx:]
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post(f"/api/group/avatar?group_id={self.group.group_id}", data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], 0)
        path = os.path.join(settings.MEDIA_ROOT, f"group{self.group.group_id}")
        self.assertTrue(os.path.exists(path))
        os.remove(path)

    def test_upload_group_avatar_get(self):
        res = self.client.get('/api/group/avatar')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)
