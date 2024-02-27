import json
from django.http import HttpRequest
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings

from im.models import User, Group, Groupmember, Friend, Systemmsg, Systemop, Message
from websocket.views import push_sysmsg, push_message

from utils.utils_request import BAD_METHOD, request_failed, request_success, return_field
from utils.utils_require import CheckRequire, require
from utils.utils_jwt import auth_jwt_token
from utils.utils_msg import get_latest_msg


@CheckRequire
def search(req: HttpRequest):
    if req.method != "GET":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)
    
    id_searched = req.GET.get("group_id")
    name_searched = req.GET.get("group_name")
    qset = None

    if id_searched is not None:
        try:
            id_searched = int(id_searched)
        except:
            return request_failed(-2, f"Error type of [group_id]: {type(id_searched)}", 400)
        qset = Group.objects.filter(group_id=id_searched).exclude(group_name="")
    elif name_searched is not None and len(name_searched) > 0:
        qset = Group.objects.filter(group_name__contains=name_searched)
    else:
        return request_failed(-2, "Missing or error type of [group_id] or [group_name]", 400)

    return request_success({
        "result": [{
            "group_owner_name": item.group_owner.user_name,
            **(item.serialize()),
        } for item in qset]
    })

@CheckRequire
def create(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    owner = User.objects.filter(user_name=username).first()
    if owner is None:
        return request_failed(2, "User does not exsist", 400)
    
    body = json.loads(req.body.decode("utf-8"))
    group_name = require(body, "group_name", "string", err_msg="Missing or error type of [group_name]")
    member_ids = require(body, "member_ids", "list", err_msg="Missing or error type of [member_ids]")
    if group_name == "":
        return request_failed(-2, "Group name cannot be empty", 400)
    
    id_set = set()
    member_list = []
    for id_raw in member_ids:
        try:
            id = int(id_raw)
            if id == owner.user_id:
                return request_failed(2, "You cannot add yourself to the group", 400)
            member = User.objects.filter(user_id=id).first()
            if member is None:
                return request_failed(2, f"User with id {id} does not exsist", 400)
            if not Friend.objects.filter(user=owner, friend=member).exists():
                return request_failed(2, f"User with id {id} is not your friend", 400)
            if id not in id_set:
                id_set.add(id)
                member_list.append(member)
        except:
            return request_failed(-2, f"Error type of element in [member_ids]: {type(id_raw)}", 400)

    group = Group.objects.create(group_name=group_name, group_owner=owner)
    gm_list = [Groupmember(group=group, member_user=member, member_role="member") for member in member_list]
    gm_list.append(Groupmember(group=group, member_user=owner, member_role="admin"))
    Groupmember.objects.bulk_create(gm_list)

    sysop = Systemop.objects.create(
        user=owner,
        sysop_type="create_group",
        target_group=group,
        message=f"{owner.user_name} created group {group_name}",
        need_operation=False,
        result=""
    )
    msgs = [Systemmsg(
        sysop=sysop,
        target_user=gm.member_user,
        sysmsg_type=sysop.sysop_type,
        message=sysop.message,
        can_operate=False,
        result=""
    ) for gm in Groupmember.objects.filter(group=group)]
    Systemmsg.objects.bulk_create(msgs)
    update_user = []
    for msg in Systemmsg.objects.filter(sysop=sysop):
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)
    User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success({"group_id": group.group_id, "group_name": group_name})

@CheckRequire
def group_list(req: HttpRequest):
    if req.method != "GET":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    groups = [{
        "members": [return_field(gm.serialize(private=True), [
            "member_id",
            "member_name",
            "member_role",
            "join_time",
            "sent_msg_id",
            "ack_msg_id",
        ]) for gm in Groupmember.objects.filter(group=item.group)],
        "latest_msg": get_latest_msg(item),
        "do_not_disturb": item.do_not_disturb,
        "top": item.top,
        **(item.group.serialize()),
    } for item in Groupmember.objects.filter(member_user=user)]
    return request_success({"groups": groups})

@CheckRequire
def group_delete(req: HttpRequest):
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
    group_id = require(body, "group_id", "int", err_msg="Missing or error type of [group_id]")
    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    if group.group_owner is None:
        return request_failed(2, "Cannot delete friend group", 400)
    if group.group_owner.user_id != user.user_id:
        return request_failed(2, "You are not the owner of the group", 403)

    sysop = Systemop.objects.create(
        user=user,
        sysop_type="delete_group",
        message=f"group {group.group_name} is deleted",
        need_operation=False,
        result=""
    )
    msgs = [Systemmsg(
        sysop=sysop,
        target_user=gm.member_user,
        sysmsg_type=sysop.sysop_type,
        message=sysop.message,
        can_operate=False,
        result=""
    ) for gm in Groupmember.objects.filter(group=group)]
    group.delete()
    Systemmsg.objects.bulk_create(msgs)
    update_user = []
    for msg in Systemmsg.objects.filter(sysop=sysop):
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)
    User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success()

@CheckRequire
def join(req: HttpRequest):
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
    group_id = require(body, "group_id", "int", err_msg="Missing or error type of [group_id]")
    message = require(body, "message", "string", err_msg="Missing or error type of [message]")

    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    if group.group_owner is None:
        return request_failed(2, "Cannot join friend group", 400)
    if Groupmember.objects.filter(group=group, member_user=user).exists():
        return request_failed(2, "You are already in the group", 400)

    sysop = Systemop.objects.create(
        user=user,
        sysop_type="join_group",
        target_group=group,
        message=message,
        need_operation=True,
        result=""
    )
    msgs = [Systemmsg(
        sysop=sysop,
        target_user=user,
        sysmsg_type="join_group",
        message=message,
        can_operate=False,
        result="",
        sup_user=user,
        sup_group=group,
    )]
    for gm in Groupmember.objects.filter(group=group, member_role="admin"):
        msg = Systemmsg(
            sysop=sysop,
            target_user=gm.member_user,
            sysmsg_type="join_group",
            message=message,
            can_operate=True,
            result="",
            sup_user=user,
        )
        msgs.append(msg)

    Systemmsg.objects.bulk_create(msgs)
    update_user = []
    for msg in Systemmsg.objects.filter(sysop=sysop):
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)
    User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success()

@CheckRequire
def leave(req: HttpRequest):
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
    group_id = require(body, "group_id", "int", err_msg="Missing or error type of [group_id]")

    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    if group.group_owner is None:
        return request_failed(2, "Cannot leave friend group", 400)
    if group.group_owner.user_id == user.user_id:
        sysop = Systemop.objects.create(
            user=user,
            sysop_type="delete_group",
            message=f"group {group.group_name} is deleted",
            need_operation=False,
            result=""
        )
        msgs = [Systemmsg(
            sysop=sysop,
            target_user=gm.member_user,
            sysmsg_type=sysop.sysop_type,
            message=sysop.message,
            can_operate=False,
            result=""
        ) for gm in Groupmember.objects.filter(group=group)]
        group.delete()
        Systemmsg.objects.bulk_create(msgs)
        update_user = []
        for msg in Systemmsg.objects.filter(sysop=sysop):
            if push_sysmsg(msg.target_user, msg.sysmsg_id):
                update_user.append(msg.target_user)
        User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

        return request_success()
    else:
        gm = Groupmember.objects.filter(group=group, member_user=user).first()
        if gm is None:
            return request_failed(2, "You are not in the group", 400)

        sysop = Systemop.objects.create(
            user=user,
            sysop_type="leave_group",
            target_group=group,
            message=f"{user.user_name} left group {group.group_name}",
            need_operation=False,
            result=""
        )
        msgs = [Systemmsg(
            sysop=sysop,
            target_user=gm.member_user,
            sysmsg_type=sysop.sysop_type,
            message=sysop.message,
            can_operate=False,
            result="",
            sup_user=user,
            sup_group=group
        ) for gm in Groupmember.objects.filter(group=group)]
        gm.delete()
        Systemmsg.objects.bulk_create(msgs)
        update_user = []
        for msg in Systemmsg.objects.filter(sysop=sysop):
            if push_sysmsg(msg.target_user, msg.sysmsg_id):
                update_user.append(msg.target_user)
        User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

        return request_success()

@CheckRequire
def kick_user(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    origin = User.objects.filter(user_name=username).first()
    if origin is None:
        return request_failed(2, "User does not exsist", 400)
    
    body = json.loads(req.body.decode("utf-8"))
    group_id = require(body, "group_id", "int", err_msg="Missing or error type of [group_id]")
    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    if group.group_owner is None:
        return request_failed(2, "Cannot kick user from friend group", 400)

    gm_origin = Groupmember.objects.filter(group=group, member_user=origin).first()
    if gm_origin is None:
        return request_failed(2, "You are not in the group", 400)
    if gm_origin.member_role != "admin":
        return request_failed(2, "You are not the admin of the group", 403)

    user_id = require(body, "member_id", "int", err_msg="Missing or error type of [member_id]")
    target = User.objects.filter(user_id=user_id).first()
    if target is None:
        return request_failed(2, "Target user does not exsist", 400)
    if target.user_id == origin.user_id:
        return request_failed(2, "You cannot kick yourself", 400)
    
    gm_target = Groupmember.objects.filter(group=group, member_user=target).first()
    if gm_target is None:
        return request_failed(2, "Target user is not in the group", 400)
    if not (gm_target.member_role == "member" or group.group_owner.user_id == origin.user_id):
        return request_failed(2, "You don't have higher permission than target user", 403)

    sysop = Systemop.objects.create(
        user=origin,
        sysop_type="kick_user",
        target_group=group,
        message=f"{origin.user_name} kicked {target.user_name} from group {group.group_name}",
        need_operation=False,
        result=""
    )
    msgs = [Systemmsg(
        sysop=sysop,
        target_user=gm.member_user,
        sysmsg_type=sysop.sysop_type,
        message=sysop.message,
        can_operate=False,
        result="",
        sup_user=target,
        sup_group=group
    ) for gm in Groupmember.objects.filter(group=group)]
    gm_target.delete()
    Systemmsg.objects.bulk_create(msgs)
    update_user = []
    for msg in Systemmsg.objects.filter(sysop=sysop):
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)
    User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success()

@CheckRequire
def set_role(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    origin = User.objects.filter(user_name=username).first()
    if origin is None:
        return request_failed(2, "User does not exsist", 400)
    
    body = json.loads(req.body.decode("utf-8"))
    group_id = require(body, "group_id", "int", err_msg="Missing or error type of [group_id]")
    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    if group.group_owner is None:
        return request_failed(2, "Cannot set role in friend group", 400)

    gm_origin = Groupmember.objects.filter(group=group, member_user=origin).first()
    if gm_origin is None:
        return request_failed(2, "You are not in the group", 400)
    if group.group_owner.user_id != origin.user_id:
        return request_failed(2, "You are not the owner of the group", 403)

    user_id = require(body, "member_id", "int", err_msg="Missing or error type of [member_id]")
    target = User.objects.filter(user_id=user_id).first()
    if target is None:
        return request_failed(2, "Target user does not exsist", 400)
    if target.user_id == origin.user_id:
        return request_failed(2, "You cannot change your own role", 400)

    gm_target = Groupmember.objects.filter(group=group, member_user=target).first()
    if gm_target is None:
        return request_failed(2, "Target user is not in the group", 400)

    role = require(body, "member_role", "string", err_msg="Missing or error type of [member_role]")
    if role not in {"member", "admin", "owner"}:
        return request_failed(-2, f"Error type of [member_role]: {type(role)}", 400)

    gm_target.member_role = ("member" if role == "member" else "admin")
    gm_target.save(update_fields=["member_role"])
    sysop = None
    if role == "owner":
        group.group_owner = target
        group.save(update_fields=["group_owner"])
        sysop = Systemop.objects.create(
            user=origin,
            sysop_type="change_owner",
            target_group=group,
            message=f"the owner of group {group.group_name} is changed to {target.user_name}",
            need_operation=False,
            result=""
        )
    else:
        sysop = Systemop.objects.create(
            user=origin,
            sysop_type="set_role",
            target_group=group,
            message=f"{target.user_name}'s role in group {group.group_name} is changed to {role}",
            need_operation=False,
            result=""
        )
    msgs = [Systemmsg(
        sysop=sysop,
        target_user=gm.member_user,
        sysmsg_type=sysop.sysop_type,
        message=sysop.message,
        can_operate=False,
        result="",
        sup_group=group
    ) for gm in Groupmember.objects.filter(group=group)]
    Systemmsg.objects.bulk_create(msgs)
    update_user = []
    for msg in Systemmsg.objects.filter(sysop=sysop):
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)
    User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success()

@CheckRequire
def info(req: HttpRequest):
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

    members = [return_field(gm.serialize(), [
        "member_id",
        "member_name",
        "member_role",
        "join_time",
        "sent_msg_id",
        "ack_msg_id",
    ]) for gm in Groupmember.objects.filter(group=group)]
    return request_success({
        "members": members,
        "latest_msg": get_latest_msg(gm),
        "top": gm.top, 
        "do_not_disturb": gm.do_not_disturb, 
        **(group.serialize()),
    })

@CheckRequire
def avatar(req: HttpRequest):
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
    if gm.member_role != "admin":
        return request_failed(2, "You are not the admin of the group", 403)

    file: UploadedFile = req.FILES.get("file")
    if file is None:
        return request_failed(2, "File is required", 400)
    if file.content_type not in {"image/jpeg", "image/png", "image/gif"}:
        return request_failed(2, "File type not allowed", 400)

    with open(settings.MEDIA_ROOT / f"group{group.group_id}", "wb") as f:
        for chunk in file.chunks():
            f.write(chunk)

    sysop = Systemop.objects.create(
        user=user,
        sysop_type="avatar_group",
        message=f"admin of group {group.group_name} updated its avatar",
        need_operation=False,
        result=""
    )
    msgs = [Systemmsg(
        sysop=sysop,
        target_user=gm.member_user,
        sysmsg_type=sysop.sysop_type,
        message=sysop.message,
        can_operate=False,
        result="",
        sup_group=group
    ) for gm in Groupmember.objects.filter(group=group)]
    Systemmsg.objects.bulk_create(msgs)
    update_user = []
    for msg in Systemmsg.objects.filter(sysop=sysop):
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)
    User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success()

@CheckRequire
def announce(req: HttpRequest):
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
    group_id = require(body, "group_id", "int", err_msg="Missing or error type of [group_id]")

    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    gm = Groupmember.objects.filter(group=group, member_user=user, member_role="admin").first()
    if gm is None:
        return request_failed(2, "You are not in the group or not admin", 400)

    announcement = require(body, "announcement", "string", err_msg="Missing or error type of [announcement]")
    msg = Message.objects.create(
        sender=user,
        group=group,
        msg_body=announcement,
        msg_type="announcement",
    )
    update_list = []
    for member in Groupmember.objects.filter(group=group):
        if push_message(member, msg):
            update_list.append(member)
    
    Groupmember.objects.bulk_update(update_list, fields=["sent_msg_id"])
    return request_success()
    

@CheckRequire
def announcements(req: HttpRequest):
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

    announcements = [{
        "msg_id": msg.msg_id,
        "sender_id": msg.sender.user_id,
        "group_id": group_id, 
        "msg_body": msg.msg_body,
        "create_time": msg.create_time,
    } for msg in Message.objects.filter(group=group, msg_type="announcement")]
    return request_success({"announcements": announcements})

@CheckRequire
def preference(req: HttpRequest):
    if req.method != "PUT":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    body = json.loads(req.body.decode("utf-8"))
    group_id = require(body, "group_id", "int", err_msg="Missing or error type of [group_id]")

    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    gm = Groupmember.objects.filter(group=group, member_user=user).first()
    if gm is None:
        return request_failed(2, "You are not in the group", 400)
    
    if "do_not_disturb" in body:
        new_do_not_disturb = require(body, "do_not_disturb", "bool", "Error type of [do_not_disturb]")
        gm.do_not_disturb = new_do_not_disturb
    
    if "top" in body:
        new_top = require(body, "top", "bool", "Error type of [top]")
        gm.top = new_top

    if "do_not_disturb" in body or "top" in body:
        sysop = Systemop.objects.create(
            user=user,
            sysop_type="change_preference",
            target_user=user,
            target_group=group,
            message=f"{user.user_name} set group {group.group_name} do not disturb: {gm.do_not_disturb}; top: {gm.top}",
            need_operation=False,
            result=""
        )
        msg = Systemmsg.objects.create(
            sysop=sysop,
            target_user=user,
            sysmsg_type=sysop.sysop_type,
            message=sysop.message,
            can_operate=False,
            result="",
            sup_group=group
        )
        update_user = []
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)
        User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    gm.save()
    return request_success()

@CheckRequire
def modify(req: HttpRequest):
    if req.method != "PUT":
        return BAD_METHOD
    
    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    body = json.loads(req.body.decode("utf-8"))
    group_id = require(body, "group_id", "int", err_msg="Missing or error type of [group_id]")

    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        return request_failed(2, "Group does not exsist", 400)
    gm = Groupmember.objects.filter(group=group, member_user=user, member_role="admin").first()
    if gm is None:
        return request_failed(2, "You are not in the group or not admin", 400)
    
    if "group_name" in body:
        old_group_name = group.group_name
        new_group_name = require(body, "group_name", "string", "Error type of [group_name]")
        group.group_name = new_group_name
        group.save()
        sysop = Systemop.objects.create(
            user=user,
            sysop_type="modify_group_info",
            target_group=group,
            message=f"{user.user_name} change group {old_group_name} into {new_group_name}",
            need_operation=False,
            result=""
        )
        msgs = [Systemmsg(
            sysop=sysop,
            target_user=gm.member_user,
            sysmsg_type=sysop.sysop_type,
            message=sysop.message,
            can_operate=False,
            result="",
            sup_group=group
        ) for gm in Groupmember.objects.filter(group=group)]
        Systemmsg.objects.bulk_create(msgs)
        update_user = []
        for msg in Systemmsg.objects.filter(sysop=sysop):
            if push_sysmsg(msg.target_user, msg.sysmsg_id):
                update_user.append(msg.target_user)
        User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success()