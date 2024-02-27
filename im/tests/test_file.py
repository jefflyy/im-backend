from django.test import TestCase
from django.core.files import File as DjangoFile
from django.http import FileResponse
from urllib3 import encode_multipart_formdata
import os, shutil

from im.models import User, Group, Groupmember, Message, File

from utils.utils_jwt import generate_jwt_token


class FileTests(TestCase):
    # Initializer
    def setUp(self):
        self.alice = User.objects.create(user_name="alice", password="123456", user_email="alice@163.com")
        self.bob = User.objects.create(user_name="bob", password="123456", user_email="bob@163.com")
        self.group = Group.objects.create(group_name="test_group", group_owner=self.alice)
        Groupmember.objects.create(group=self.group, member_user=self.alice, member_role="admin")

    # destructor
    def tearDown(self):
        User.objects.all().delete()
        if os.path.exists("database/msg"):
            shutil.rmtree("database/msg")

    # ! Test section
    def test_upload_file_no_jwt(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        res = self.client.post('/api/file/upload', data=data, content_type=content_type)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_file_wrong_jwt(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.post('/api/file/upload', data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_file_no_group_id(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post('/api/file/upload', data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_file_nonexisting_group(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post(f"/api/file/upload?group_id=-1", data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_file_not_member(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
        res = self.client.post(f"/api/file/upload?group_id={self.group.group_id}", data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_file_no_file(self):
        raw_data = {}
        data, content_type = encode_multipart_formdata(raw_data)
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.post(f"/api/file/upload?group_id={self.group.group_id}", data=data, content_type=content_type, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_upload_file_success(self):
        with open("pytest.ini", "rb") as f:
            raw_data = {"file": f.read()}
            data, content_type = encode_multipart_formdata(raw_data)
            idx = data.find(b'name="file"') + 11
            data = data[:idx] + b'; filename="pytest.ini"\r\nContent-Type: text/plain' + data[idx:]
            headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
            res = self.client.post(f"/api/file/upload?group_id={self.group.group_id}", data=data, content_type=content_type, **headers)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()['code'], 0)

    def test_upload_file_get(self):
        res = self.client.get('/api/file/upload')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)

    def test_download_file_no_jwt(self):
        res = self.client.get('/api/file/download')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['code'], 2)

    def test_download_file_wrong_jwt(self):
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("carol")}
        res = self.client.get('/api/file/download', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_download_file_no_msg_id(self):
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/file/download', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_download_file_nonexisting_msg(self):
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/file/download?msg_id=-1', **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_download_file_not_member(self):
        with open("pytest.ini", "rb") as f:
            msg = Message.objects.create(
                sender=self.alice,
                group=self.group,
                msg_body=f.name,
                msg_type="text/plain",
            )
            file = File.objects.create(
                msg=msg,
                file=DjangoFile(f),
            )
            data = {"msg_id": msg.msg_id}
            headers = {"HTTP_AUTHORIZATION": generate_jwt_token("bob")}
            res = self.client.get('/api/file/download', data=data, **headers)
            self.assertEqual(res.status_code, 403)
            self.assertEqual(res.json()['code'], 2)

    def test_download_file_no_file(self):
        msg = Message.objects.create(
            sender=self.alice,
            group=self.group,
            msg_body="hello",
            msg_type="message",
        )
        data = {"msg_id": msg.msg_id}
        headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
        res = self.client.get('/api/file/download', data=data, **headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 2)

    def test_download_file_recalled(self):
        with open("pytest.ini", "rb") as f:
            msg = Message.objects.create(
                sender=self.alice,
                group=self.group,
                msg_body="",
                msg_type="recall",
            )
            file = File.objects.create(
                msg=msg,
                file=DjangoFile(f),
            )
            data = {"msg_id": msg.msg_id}
            headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
            res = self.client.get('/api/file/download', data=data, **headers)
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json()['code'], 2)

    def test_download_file_success(self):
        with open("pytest.ini", "rb") as f:
            msg = Message.objects.create(
                sender=self.alice,
                group=self.group,
                msg_body=f.name,
                msg_type="text/plain",
            )
            content = f.read()
            File.objects.create(
                msg=msg,
                file=DjangoFile(f),
            )
            data = {"msg_id": msg.msg_id}
            headers = {"HTTP_AUTHORIZATION": generate_jwt_token("alice")}
            res: FileResponse = self.client.get('/api/file/download', data=data, **headers)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res['Content-Disposition'], 'attachment; filename="pytest.ini"')
            self.assertEqual(res['Content-Type'], 'application/octet-stream')
            self.assertEqual(b"".join(res.streaming_content), content)

    def test_download_file_post(self):
        res = self.client.post('/api/file/download')
        self.assertEqual(res.status_code, 405)
        self.assertEqual(res.json()['code'], -3)
