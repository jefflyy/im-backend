from django.http import HttpRequest, FileResponse
from django.http.response import HttpResponseBase
from django.core.files.uploadedfile import UploadedFile

from im.models import User, Group, Groupmember, Message, File
from websocket.views import push_message

from utils.utils_jwt import auth_jwt_token
from utils.utils_request import BAD_METHOD, request_success, request_failed
from utils.utils_msg import get_file_set

def upload(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    user_name = auth_jwt_token(jwt_token)
    if user_name is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=user_name).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    group_id = None
    try:
        group_id = int(req.GET.get("group_id"))
    except:
        return request_failed(2, "Missing or error type of [group_id]", 400)
    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    gm = Groupmember.objects.filter(group=group, member_user=user).first()
    if gm is None:
        return request_failed(2, "You are not in the group", 400)

    file: UploadedFile = req.FILES.get("file")
    if file is None:
        return request_failed(2, "File is required", 400)

    msg = Message.objects.create(
        sender=user,
        group=group,
        msg_body=file.name,
        msg_type=file.content_type,
    )
    File.objects.create(
        msg=msg,
        file=file,
        name=file.name,
    )
    update_list = []
    for member in Groupmember.objects.filter(group=group):
        if push_message(member, msg):
            update_list.append(member)
    
    Groupmember.objects.bulk_update(update_list, fields=["sent_msg_id"])
    return request_success()

def download(req: HttpRequest) -> HttpResponseBase:
    if req.method != "GET":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    user_name = auth_jwt_token(jwt_token)
    if user_name is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=user_name).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    msg_id = None
    try:
        msg_id = int(req.GET.get("msg_id"))
    except:
        return request_failed(2, "Missing or error type of [msg_id]", 400)
    msg = Message.objects.filter(msg_id=msg_id).first()
    if msg is None:
        return request_failed(2, "Message does not exsist", 400)
    qset = File.objects.filter(msg=msg)
    if msg.msg_type == "forward":
        qset = qset.filter(name="forward.json")
    if not qset.exists():
        return request_failed(2, "File does not exsist", 400)

    try:
        # download file inside forward message
        forward_msg_id = int(req.GET.get("forward_msg_id"))
        fw = Message.objects.filter(msg_id=forward_msg_id).first()
        assert msg.msg_id in get_file_set(fw), "This message is not in the forward message"
    except:
        # download file directly
        gm = Groupmember.objects.filter(group=msg.group, member_user=user).first()
        if gm is None:
            return request_failed(2, "No permission to download this file", 403)
        if msg.msg_type == "recall":
            return request_failed(2, "This message has been recalled", 400)

    file = qset.first()
    response = FileResponse(file.file, content_type="application/octet-stream", as_attachment=True, filename=file.name)
    return response
