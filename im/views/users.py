import json
from django.http import HttpRequest, HttpResponse
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings

from im.models import User, Group, Groupmember, Friend, Systemmsg, Systemop, Message
from websocket.views import push_sysmsg, push_message
from utils.utils_request import (
    BAD_METHOD,
    request_failed,
    request_success,
    return_field,
)
from utils.utils_require import MAX_CHAR_LENGTH, CheckRequire, require
from utils.utils_time import get_timestamp
from utils.utils_jwt import generate_jwt_token, auth_jwt_token
from utils.utils_mail import verify_code
from utils.utils_websocket import logout_user


@CheckRequire
def register(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    body = json.loads(req.body.decode("utf-8"))
    
    username = require(body, "user_name", "string", err_msg="Missing or error type of [user_name]")
    password = require(body, "password", "string", err_msg="Missing or error type of [password]")
    email = require(body, "user_email", "email", err_msg="Missing or error type of [user_email]")
    code = require(body, "email_code", "int", err_msg="Missing or error type of [email_code]")
    
    # assert 0 < len(username) <= 50, "Bad length of [user_name]"
    # assert 0 < len(password) <= 20, "Bad length of [password]"

    user_byname = User.objects.filter(user_name=username).first()
    user_byemail = User.objects.filter(user_email=email).first()
    
    if user_byname:
        return request_failed(2, "This username is lready registered", 400)
    
    elif user_byemail:
        return request_failed(2, "This email is already registered", 400)

    else:
        if not verify_code(email, code):
            return request_failed(2, "email verification failed", 400)

        user = User.objects.create(
            user_name=username,
            password=password,
            user_email=email
        )
        return request_success({
            "jwt_token": generate_jwt_token(user.user_name),
            "user_name": user.user_name,
            "user_id": user.user_id
        })


@CheckRequire
def login(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    body = json.loads(req.body.decode("utf-8"))

    username = require(
        body, "user_name", "string", err_msg="Missing or error type of [user_name]"
    )
    password = require(
        body, "password", "string", err_msg="Missing or error type of [password]"
    )

    user = User.objects.filter(user_name=username).first()

    if user and password == user.password:
        user.login_time = get_timestamp()
        user.save(update_fields=["login_time"])
        return request_success(
            {
                "user_id": user.user_id,
                "jwt_token": generate_jwt_token(username),
            }
        )
    else:
        return request_failed(2, "Invalid [user_name] or [password]", 401)


@CheckRequire
def logout(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    user_name = auth_jwt_token(jwt_token)
    if user_name is None:
        return request_failed(2, "Invalid or expired jwt token", 401)

    user_logout = User.objects.filter(user_name=user_name).first()
    if user_logout is None:
        return request_failed(2, "this user not exist in data", 400)
    else:
        logout_user(user_name, jwt_token)
        return request_success()


@CheckRequire
def modify(req: HttpRequest):
    if req.method != "PUT":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    user_name = auth_jwt_token(jwt_token)
    if user_name is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    
    user = User.objects.filter(user_name=user_name).first()
    if user is None:
        return request_failed(2, "this user not exist in data", 400)

    body = json.loads(req.body.decode("utf-8"))
    if "user_name" in body:
        new_user_name = require(body, "user_name", "string", "Error type of [user_name]")
        if User.objects.filter(user_name=new_user_name).exists():
            return request_failed(2, "[user_name] already used", 400)
        user.user_name = new_user_name
    
    if "password" in body:
        new_password = require(body, "password", "string", "Error type of [password]")
        user.password = new_password
    
    if "user_email" in body:
        new_user_email = require(body, "user_email", "email", "Error type of [user_email]")
        if User.objects.filter(user_email=new_user_email).exists():
            return request_failed(2, "[user_email] already used", 400)
        code = require(body, "code", "int", "Missing or error type of [code]")
        if not verify_code(new_user_email, code):
            return request_failed(2, "email verification failed", 400)
        user.user_email = new_user_email

    user.save()
    
    if "user_name" in body or "user_email" in body:
        sysop = Systemop.objects.create(
            user=user,
            sysop_type="modify_user_info_friend",
            message=f"user {user.user_id} modified user info",
            need_operation=False,
            result=""
        )
        friends = Friend.objects.filter(user=user)
        msgs = [Systemmsg(
            sysop=sysop,
            target_user=friend.friend,
            sysmsg_type=sysop.sysop_type,
            message=sysop.message,
            can_operate=False,
            result=""
        ) for friend in friends]
        Systemmsg.objects.bulk_create(msgs)

        sysop = Systemop.objects.create(
            user=user,
            sysop_type="modify_user_info_group",
            message=f"user {user.user_id} modified user info",
            need_operation=False,
            result=""
        )
        #groups = [gm.group for gm in Groupmember.objects.filter(member_user=user) if gm.member_role != ""]
        groups = [gm.group for gm in Groupmember.objects.filter(member_user=user)]
        for group in groups:
            msgs = [Systemmsg(
                sysop=sysop,
                target_user=gm.member_user,
                sysmsg_type=sysop.sysop_type,
                message=sysop.message,
                can_operate=False,
                result="",
                sup_group=gm.group
            #) for gm in Groupmember.objects.filter(group=group) if gm.member_user is not user and gm.member_user not in friends]
            ) for gm in Groupmember.objects.filter(group=group) if gm.member_user is not user]
            Systemmsg.objects.bulk_create(msgs)
        update_user = []
        for msg in Systemmsg.objects.filter(sysop=sysop):
            if push_sysmsg(msg.target_user, msg.sysmsg_id):
                update_user.append(msg.target_user)
        User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success({
        "jwt_token": generate_jwt_token(user.user_name),
        "user_name": user.user_name,
        "user_id": user.user_id,
    })


@CheckRequire
def cancel(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    user_name = auth_jwt_token(jwt_token)
    if user_name is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    
    user = User.objects.filter(user_name=user_name).first()
    if user is None:
        return request_failed(2, "this user not exist in data", 400)

    sysop = Systemop.objects.create(
        user=user,
        sysop_type="cancel_user_friend",
        message=f"friend user {user.user_id} canceled its account",
        need_operation=False,
        result=""
    )
    friends = Friend.objects.filter(user=user)
    msgs = [Systemmsg(
        sysop=sysop,
        target_user=friend.friend,
        sysmsg_type=sysop.sysop_type,
        message=sysop.message,
        can_operate=False,
        result=""
    ) for friend in friends]
    Systemmsg.objects.bulk_create(msgs)

    sysop = Systemop.objects.create(
        user=user,
        sysop_type="cancel_user_group_member",
        message=f"groupmember user {user.user_id} canceled its account",
        need_operation=False,
        result=""
    )
    groups_member = [gm.group for gm in Groupmember.objects.filter(member_user=user) if gm.group.group_owner is None or gm.group.group_owner.user_id is not user.user_id]
    for group in groups_member:
        msgs = [Systemmsg(
            sysop=sysop,
            target_user=gm.member_user,
            sysmsg_type=sysop.sysop_type,
            message=sysop.message,
            can_operate=False,
            result="",
            sup_group=gm.group
        ) for gm in Groupmember.objects.filter(group=group) if gm.member_user.user_id is not user.user_id]
        Systemmsg.objects.bulk_create(msgs)
    
    sysop = Systemop.objects.create(
        user=user,
        sysop_type="cancel_user_group_owner",
        message=f"groupowner user {user.user_id} canceled its account",
        need_operation=False,
        result=""
    )
    groups_owner = [gm.group for gm in Groupmember.objects.filter(member_user=user) if gm.group.group_owner is not None and gm.group.group_owner.user_id is user.user_id]
    for group in groups_owner:
        msgs = [Systemmsg(
            sysop=sysop,
            target_user=gm.member_user,
            sysmsg_type=sysop.sysop_type,
            message=sysop.message,
            can_operate=False,
            result=""
        ) for gm in Groupmember.objects.filter(group=group) if gm.member_user.user_id is not user.user_id]
        Systemmsg.objects.bulk_create(msgs)

    update_user = []
    for msg in Systemmsg.objects.filter(sysop=sysop):
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)
    User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    logout_user(user_name, jwt_token)
    for friend in Friend.objects.filter(user=user):
        friend.group.delete()
    user.delete()
    return request_success()

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
    
    id_searched = req.GET.get("user_id")
    name_searched = req.GET.get("user_name")
    qset = None

    if id_searched is not None:
        try:
            id_searched = int(id_searched)
        except:
            return request_failed(-2, f"Error type of [user_id]: {type(id_searched)}", 400)
        qset = User.objects.filter(user_id=id_searched)
    elif name_searched is not None:
        qset = User.objects.filter(user_name__contains=name_searched)
    else:
        return request_failed(-2, "Missing or error type of [user_id] or [user_name]", 400)

    return request_success({
        "result": [return_field(item.serialize(), [
            "user_id",
            "user_name",
            "register_time",
            "login_time",
            "user_email",
        ]) for item in qset]
    })

@CheckRequire
def avatar(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    jwt_token = req.headers.get("Authorization")
    username = auth_jwt_token(jwt_token)
    if username is None:
        return request_failed(2, "Invalid or expired jwt token", 401)
    user = User.objects.filter(user_name=username).first()
    if user is None:
        return request_failed(2, "User does not exsist", 400)

    file: InMemoryUploadedFile = req.FILES.get("file")
    if file is None:
        return request_failed(2, "File is required", 400)
    if file.content_type not in {"image/jpeg", "image/png", "image/gif"}:
        return request_failed(2, "File type not allowed", 400)

    with open(settings.MEDIA_ROOT / f"user{user.user_id}", "wb") as f:
        for chunk in file.chunks():
            f.write(chunk)

    sysop = Systemop.objects.create(
        user=user,
        sysop_type="avatar_friend",
        message=f"friend user {user.user_name} updated its avatar",
        need_operation=False,
        result=""
    )
    friends = Friend.objects.filter(user=user)
    msgs = [Systemmsg(
        sysop=sysop,
        target_user=friend.friend,
        sysmsg_type=sysop.sysop_type,
        message=sysop.message,
        can_operate=False,
        result="",
        sup_user=user,
    ) for friend in friends]
    Systemmsg.objects.bulk_create(msgs)

    sysop = Systemop.objects.create(
        user=user,
        sysop_type="avatar_groupmember",
        message=f"groupmember {user.user_name} updated its avatar",
        need_operation=False,
        result=""
    )
    groups = [gm.group for gm in Groupmember.objects.filter(member_user=user).exclude(member_role="")]
    for group in groups:
        msgs = [Systemmsg(
            sysop=sysop,
            target_user=gm.member_user,
            sysmsg_type=sysop.sysop_type,
            message=sysop.message,
            can_operate=False,
            result="",
            sup_group=gm.group,
            sup_user=user,
        ) for gm in Groupmember.objects.filter(group=group) if gm.member_user.user_id is not user.user_id]
        Systemmsg.objects.bulk_create(msgs)

    update_user = []
    for msg in Systemmsg.objects.filter(sysop=sysop).order_by("-sysmsg_id"):
        if push_sysmsg(msg.target_user, msg.sysmsg_id):
            update_user.append(msg.target_user)
    User.objects.bulk_update(update_user, fields=["read_sysmsg_id"])

    return request_success()
