import json
from django.http import HttpRequest
from django.core.files.base import ContentFile
from django.conf import settings
import random
from hashlib import md5
from requests import post

from im.models import User, Group, Groupmember, Message, Systemop, Systemmsg, File, Userdelmsg
from websocket.views import push_sysmsg, push_message

from utils.utils_jwt import auth_jwt_token
from utils.utils_request import BAD_METHOD, request_success, request_failed
from utils.utils_require import CheckRequire, require
from utils.utils_msg import get_file_set, RECALL_TIME_LIMIT
from utils.utils_time import get_timestamp


@CheckRequire
def fetch(req: HttpRequest):
    if req.method != "GET":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    group_id = req.GET.get("group_id")
    if group_id is None:
        return request_failed(-2, "Missing [group_id]", 400)
    try:
        group_id = int(group_id)
    except:
        return request_failed(-2, f"Error type of [group_id]: {type(group_id)}", 400)
    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    gm = Groupmember.objects.filter(group=group, member_user=user).first()
    if gm is None:
        return request_failed(2, "You are not in the group", 400)

    delids = Userdelmsg.objects.filter(user=user, msg__group=group).values("msg__msg_id")
    qset = Message.objects.filter(group=group, msg_id__lte=gm.ack_msg_id).exclude(msg_id__in=delids)
    msgs = [item.serialize() for item in qset]
    return request_success({"msgs": msgs})

@CheckRequire
def ack(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    body = json.loads(req.body.decode("utf-8"))
    group_id = require(body, "group_id", "int", "Missing or error type of [group_id]")
    msg_id = require(body, "msg_id", "int", "Missing or error type of [msg_id]")

    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    gm = Groupmember.objects.filter(group=group, member_user=user).first()
    if gm is None:
        return request_failed(2, "You are not in the group", 400)

    if msg_id > gm.ack_msg_id:
        try:
            latest_msg = Message.objects.filter(group=group).latest("msg_id")
            if msg_id > latest_msg.msg_id:
                return request_failed(2, "Cannot ack future message", 400)
        except Message.DoesNotExist:
            return request_failed(2, "Group has no message", 400)

        gm.ack_msg_id = msg_id
        gm.save(update_fields=["ack_msg_id"])

        sysop = Systemop.objects.create(
            user=user,
            sysop_type="ack_msg",
            target_group=group,
            message=f"{user.user_name} ack message in group {group.group_name}",
            need_operation=False,
            result="",
        )
        msgs = [Systemmsg(
            sysop=sysop,
            target_user=gm.member_user,
            sysmsg_type=sysop.sysop_type,
            message=sysop.message,
            can_operate=False,
            result="",
            sup_group=group,
        ) for gm in Groupmember.objects.filter(group=group)]
        Systemmsg.objects.bulk_create(msgs)
        update_user = []
        for msg in Systemmsg.objects.filter(sysop=sysop):
            if push_sysmsg(msg.target_user, msg.sysmsg_id):
                update_user.append(msg.target_user)
        User.objects.bulk_update(update_user, ["read_sysmsg_id"])

    return request_success()

@CheckRequire
def recall(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    body = json.loads(req.body.decode("utf-8"))
    msg_id = require(body, "msg_id", "int", "Missing or error type of [msg_id]")

    msg = Message.objects.filter(msg_id=msg_id).first()
    if msg is None:
        return request_failed(2, "Message does not exsist", 400)
    group = msg.group
    gm_origin = Groupmember.objects.filter(group=group, member_user=user).first()
    if gm_origin is None:
        return request_failed(2, "You are not in the group", 400)
    sender = msg.sender
    gm_target = Groupmember.objects.filter(group=group, member_user=sender).first()

    if msg.msg_type == "recall":
        return request_failed(2, "Message already recalled", 400)
    admin = (group.group_owner is not None and group.group_owner.user_id == user.user_id) or (gm_origin.member_role == "admin" and gm_target.member_role != "admin")
    self = (sender.user_id == user.user_id)
    if not (admin or self):
        return request_failed(2, "You have no permission to recall this message", 403)
    if (not admin) and self and (get_timestamp() - msg.create_time > RECALL_TIME_LIMIT):
        return request_failed(2, "Message cannot be recalled after 2 minutes", 400)

    msg.msg_type = "recall"
    msg.msg_body = f"{user.user_name} recalled a message from {sender.user_name}"
    msg.save(update_fields=["msg_type", "msg_body"])

    update_list = []
    for gm in Groupmember.objects.filter(group=group):
        if push_message(gm, msg):
            update_list.append(gm)
    Groupmember.objects.bulk_update(update_list, ["sent_msg_id"])
    return request_success()

@CheckRequire
def msg_delete(req: HttpRequest):
    if req.method != "DELETE":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    body = json.loads(req.body.decode("utf-8"))
    msg_id = require(body, "msg_id", "int", "Missing or error type of [msg_id]")

    msg = Message.objects.filter(msg_id=msg_id).first()
    if msg is None:
        return request_failed(2, "Message does not exsist", 400)
    group = msg.group
    gm = Groupmember.objects.filter(group=group, member_user=user).first()
    if gm is None:
        return request_failed(2, "You are not in the group", 400)

    if Userdelmsg.objects.filter(user=user, msg=msg).exists():
        return request_failed(2, "Message already deleted", 400)
    else:
        Userdelmsg.objects.create(
            user=user,
            msg=msg,
        )
        delmsg = Message(
            msg_id=msg_id,
            sender=user,
            group=group,
            msg_type="delete",
            msg_body=f"{user.user_name} deleted a message",
        )
        if push_message(gm, delmsg):
            gm.save(update_fields=["sent_msg_id"])
        return request_success()

@CheckRequire
def forward(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    body = json.loads(req.body.decode("utf-8"))
    origin_group_id = require(body, "origin_group_id", "int", "Missing or error type of [origin_group_id]")
    target_group_id = require(body, "target_group_id", "int", "Missing or error type of [target_group_id]")
    msg_ids = require(body, "msg_ids", "list", "Missing or error type of [msg_ids]")

    origin = Group.objects.filter(group_id=origin_group_id).first()
    if origin is None:
        return request_failed(2, "Origin group does not exsist", 400)
    if not Groupmember.objects.filter(group=origin, member_user=user).exists():
        return request_failed(2, "You are not in the origin group", 400)
    target = Group.objects.filter(group_id=target_group_id).first()
    if target is None:
        return request_failed(2, "Target group does not exsist", 400)
    if not Groupmember.objects.filter(group=target, member_user=user).exists():
        return request_failed(2, "You are not in the target group", 400)

    ids = set()
    for raw_id in msg_ids:
        try:
            id = int(raw_id)
        except:
            return request_failed(-2, f"Error type of [msg_id]: {type(id)}", 400)
        if id not in ids:
            ids.add(id)
    if not ids:
        return request_failed(-2, "cannot forward 0 message", 400)

    content = []
    file_set = set()
    for id in ids:
        msg = Message.objects.filter(group=origin, msg_id=id).first()
        if msg is None:
            return request_failed(2, f"Message with id {id} does not exsist", 400)
        if msg.msg_type == "recall":
            return request_failed(2, f"Message with id {id} is recalled", 400)
        if msg.msg_type != "text":
            file_set.add(msg.msg_id)

        fw_msg = {
            "msg_id": msg.msg_id,
            "sender_name": msg.sender.user_name,
            "msg_type": msg.msg_type,
            "msg_body": msg.msg_body,
            "create_time": msg.create_time,
        }
        content.append(fw_msg)

    msg = Message.objects.create(
        sender=user,
        group=target,
        msg_body="forward message",
        msg_type="forward",
    )
    File.objects.create(
        msg=msg,
        file=ContentFile(json.dumps(content).encode("utf-8"), name="forward.json"),
        name="forward.json",
    )
    File.objects.create(
        msg=msg,
        file=ContentFile(json.dumps(list(file_set)).encode("utf-8"), name="files.json"),
        name="files.json",
    )

    update_list = []
    for gm in Groupmember.objects.filter(group=target):
        if push_message(gm, msg):
            update_list.append(gm)
    Groupmember.objects.bulk_update(update_list, ["sent_msg_id"])

    return request_success()

@CheckRequire
def translate(req: HttpRequest):
    if req.method != "GET":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)
    
    query = req.GET.get("query")
    if query is None:
        return request_failed(-2, "Missing [query]", 400)
    
    url = settings.TRANSLATE_URL
    appid = settings.TRANSLATE_APPID
    key = settings.TRANSLATE_KEY
    salt_length = settings.TRANSLATE_SALT_LENGTH
    salt = "".join([str(random.randint(0, 9)) for _ in range(salt_length)])
    sign = md5((appid + query + salt + key).encode("utf-8")).hexdigest()

    res = post(url, data={
        "q": query,
        "from": "auto",
        "to": "zh",
        "appid": appid,
        "salt": salt,
        "sign": sign,
    }, headers={
        "Content-Type": "application/x-www-form-urlencoded",
    })

    if res.status_code != 200:
        return request_failed(2, "Translate failed", 400)
    return request_success({
        "ret": res.json()["trans_result"][0]["dst"]
    })
