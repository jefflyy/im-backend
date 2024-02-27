import json
from django.http import HttpRequest, JsonResponse

from im.models import User, Friend, Group, Groupmember, Systemmsg, Systemop
from websocket.views import push_sysmsg

from utils.utils_request import (
    BAD_METHOD,
    request_failed,
    request_success,
)
from utils.utils_require import MAX_CHAR_LENGTH, CheckRequire, require
from utils.utils_time import get_timestamp
from utils.utils_jwt import auth_jwt_token
from utils.utils_sysmsg import extract_sysmsg


def handle_sysmsg_teardown(sysop: Systemop, operation: str):
    sysop.need_operation = False
    sysop.result = operation
    sysop.update_time = get_timestamp()
    sysop.save(update_fields=["need_operation", "result", "update_time"])

    msgs = list(Systemmsg.objects.filter(sysop=sysop))
    for msg in msgs:
        msg.update_time = get_timestamp()
        msg.can_operate = False
        msg.result = operation

    Systemmsg.objects.bulk_update(msgs, fields=["update_time", "can_operate", "result"])

    update_user = []
    for msg in msgs:
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)

    if len(update_user) > 0:
        User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

def handle_apply_friend(sysmsg: Systemmsg, operation: str) -> JsonResponse:
    sysop: Systemop = sysmsg.sysop
    origin: User = sysop.user
    target: User = sysop.target_user
    if origin.user_id == target.user_id:
        return request_failed(2, "Cannot add yourself as friend", 400)
    
    if operation == "yes":
        group = Group.objects.create(group_name="")
        Groupmember.objects.create(group=group, member_user=origin, member_role="")
        Groupmember.objects.create(group=group, member_user=target, member_role="")
        Friend.objects.create(user=origin, friend=target, group=group)
        Friend.objects.create(user=target, friend=origin, group=group)
    elif operation != "no":
        return request_failed(2, "Unsupported [operation]", 400)

    handle_sysmsg_teardown(sysop, operation)
    return request_success()

def handle_join_group(sysmsg: Systemmsg, operation: str) -> JsonResponse:
    sysop: Systemop = sysmsg.sysop
    origin: User = sysop.user
    target: Group = sysop.target_group
    if operation == "yes":
        create_list = []
        update_list = []
        for gm in Groupmember.objects.filter(group=target):
            msg = Systemmsg.objects.filter(sysop=sysop, target_user=gm.member_user).first()
            if msg is not None:
                msg.sup_group = target
                update_list.append(msg)
            else:
                create_list.append(Systemmsg(
                    sysop=sysop,
                    target_user=gm.member_user,
                    sysmsg_type="join_group",
                    message=sysop.message,
                    can_operate=False,
                    result="",
                    sup_group=target,
                ))
        Systemmsg.objects.bulk_update(update_list, fields=["sup_group"])
        Systemmsg.objects.bulk_create(create_list)
        Groupmember.objects.create(group=target, member_user=origin, member_role="member")
    elif operation != "no":
        return request_failed(2, "Unsupported [operation]", 400)

    handle_sysmsg_teardown(sysop, operation)
    return request_success()


@CheckRequire
def handle(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    user_name = auth_jwt_token(jwt_token)
    if user_name is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=user_name).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    body = json.loads(req.body.decode("utf-8"))
    sysmsg_id = require(body, "sysmsg_id", "int", err_msg="Missing or error type of [sysmsg_id]")
    operation = require(body, "operation", "string", err_msg="Missing or error type of [operation]")

    msg = Systemmsg.objects.filter(sysmsg_id=sysmsg_id).first()
    if msg is None:
        return request_failed(2, "Incorrect [sysmsg_id]", 400)

    if msg.target_user != user or not msg.can_operate:
        return request_failed(2, "Cannot operate", 403)

    sysop = msg.sysop
    if not sysop.need_operation:
        return request_failed(2, "Operation already completed", 410)

    if sysop.sysop_type == "apply_friend":
        return handle_apply_friend(msg, operation)
    elif sysop.sysop_type == "join_group":
        return handle_join_group(msg, operation)

    return request_failed(-2, "Unsupported [sysop_type]", 400)

@CheckRequire
def fetch(req: HttpRequest):
    if req.method != "GET":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    user_name = auth_jwt_token(jwt_token)
    if user_name is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=user_name).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    msgs = [extract_sysmsg(msg) for msg in Systemmsg.objects.filter(target_user=user, sysmsg_id__lte=user.read_sysmsg_id)]
    return request_success({"sysmsgs": msgs})
