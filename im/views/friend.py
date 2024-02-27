import json
from django.http import HttpRequest

from im.models import User, Friend, Systemmsg, Systemop
from websocket.views import push_sysmsg

from utils.utils_request import BAD_METHOD, request_failed, request_success, return_field
from utils.utils_require import CheckRequire, require
from utils.utils_jwt import auth_jwt_token


@CheckRequire
def friend_list(req: HttpRequest):
    if req.method != "GET":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Permission denied", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    friends = [{
        "group_id": item.group.group_id,
        **return_field(item.friend.serialize(), [
            "user_id",
            "user_name",
            "user_email",
            "register_time",
            "login_time",
        ]),
    } for item in Friend.objects.filter(user=user)]

    return request_success({"friends": friends})

@CheckRequire
def friend_delete(req: HttpRequest):
    if req.method != "DELETE":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Permission denied", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)
    
    body = json.loads(req.body.decode("utf-8"))
    friend_id = require(body, "id", "int", err_msg="Missing or error type of [id]")

    friend = User.objects.filter(user_id=friend_id).first()
    if friend is None:
        return request_failed(2, "Friend does not exsist", 400)

    relation1 = Friend.objects.filter(user=user, friend=friend).first()
    if relation1 is None:
        return request_failed(2, "Friendship not found", 400)

    relation1.group.delete()
    sysop = Systemop.objects.create(
        user=user,
        sysop_type="delete_friend",
        target_user=friend,
        message="{user.user_name} removed {friend.user_name} from friend list",
        need_operation=False,
        result=""
    )
    sysmsg_to_origin = Systemmsg.objects.create(
        sysop=sysop,
        target_user=user,
        sysmsg_type="delete_friend",
        message=f"you removed {friend.user_name} from friend list",
        can_operate=False,
        result="",
        sup_user=friend,
    )
    sysmsg_to_target = Systemmsg.objects.create(
        sysop=sysop,
        target_user=friend,
        sysmsg_type="delete_friend",
        message=f"{user.user_name} removed you from friend list",
        can_operate=False,
        result="",
        sup_user=user,
    )

    update_user = []
    if push_sysmsg(user, sysmsg_to_origin.sysmsg_id):
        update_user.append(user)
    if push_sysmsg(friend, sysmsg_to_target.sysmsg_id):
        update_user.append(friend)
    if len(update_user) > 0:
        User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success()

@CheckRequire
def apply(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    user_name = auth_jwt_token(jwt_token)
    if user_name is None:
        return request_failed(2, "Invalid or expired jwt token", 401)

    user = User.objects.filter(user_name=user_name).first()
    assert user is not None, "User does not exsist"

    body = json.loads(req.body.decode("utf-8"))
    friend_user_id = require(body, "friend_user_id", "int", err_msg="Missing or error type of [friend_user_id]")
    message = require(body, "message", "string", err_msg="Missing or error type of [message]")

    if friend_user_id == user.user_id:
        return request_failed(2, "cannot add oneself as friend", 400)

    target = User.objects.filter(user_id=friend_user_id).first()
    if target is None:
        return request_failed(2, "user with id [friend_user_id] does not exsist", 400)

    if Friend.objects.filter(user=user, friend=target).exists() or Friend.objects.filter(user=target, friend=user).exists():
        return request_failed(2, "They are friends already", 400)

    sysop = Systemop.objects.create(
        user=user,
        sysop_type="apply_friend",
        target_user=target,
        message=message,
        need_operation=True,
        result=""
    )
    sysmsg_to_origin = Systemmsg.objects.create(
        sysop=sysop,
        target_user=user,
        sysmsg_type="apply_friend",
        message=message,
        can_operate=False,
        result="",
        sup_user=target,
    )
    sysmsg_to_target = Systemmsg.objects.create(
        sysop=sysop,
        target_user=target,
        sysmsg_type="apply_friend",
        message=message,
        can_operate=True,
        result="",
        sup_user=user,
    )

    update_user = []
    if push_sysmsg(user, sysmsg_to_origin.sysmsg_id):
        update_user.append(user)
    if push_sysmsg(target, sysmsg_to_target.sysmsg_id):
        update_user.append(target)
    if len(update_user) > 0:
        User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success()
