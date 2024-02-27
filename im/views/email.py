import json
from django.http import HttpRequest, HttpResponse

from im.models import User
from utils.utils_request import BAD_METHOD, request_failed, request_success, return_field
from utils.utils_require import MAX_CHAR_LENGTH, CheckRequire, require
from utils.utils_time import get_timestamp
from utils.utils_jwt import generate_jwt_token, check_jwt_token
from utils.utils_mail import send_code, verify_code


@CheckRequire
def send_mailcode(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    body = json.loads(req.body.decode("utf-8"))
    
    email = require(body, "email", "email", err_msg="Missing or error type of [email]")
    
    send_code(email)
    return request_success()


@CheckRequire
def verify_mailcode(req: HttpRequest):
    if req.method != "POST":
        return BAD_METHOD

    body = json.loads(req.body.decode("utf-8"))
    
    email = require(body, "email", "email", err_msg="Missing or error type of [email]")
    code = require(body, "code", "int", err_msg="Missing or error type of [code]")

    if not verify_code(email, code):
        return request_failed(2, "Incorrect [email] or [code]", 401)
    
    user = User.objects.filter(user_email=email).first()
    if user:
        user.login_time = get_timestamp()
        user.save(update_fields=["login_time"])

        return request_success({
            "jwt_token": generate_jwt_token(user.user_name),
            "user_name": user.user_name,
            "user_id": user.user_id
        })
    else:
        return request_failed(2, "No such user", 400)
