from random import randint
from django.core.mail import send_mail

from django.conf import settings

from .utils_time import get_timestamp


code_reg = {}

def gen_code(mail: str) -> int:
    now_time = get_timestamp()
    if mail in code_reg:
        (code, create_time) = code_reg[mail]
        if now_time - create_time <= settings.EMAIL_CODE_TIMEOUT:
            return code
    
    code = randint(settings.EMAIL_CODE_MIN, settings.EMAIL_CODE_MAX)
    code_reg[mail] = (code, now_time)
    return code

def get_code(mail: str) -> int:
    return code_reg[mail][0] if mail in code_reg else None

def verify_code(mail: str, user_code: int) -> bool:
    now_time = get_timestamp()
    if mail in code_reg:
        (server_code, create_time) = code_reg.pop(mail)
        return now_time - create_time <= settings.EMAIL_CODE_TIMEOUT and user_code == server_code
    else:
        return False

def send_code(mail: str) -> int:
    code = gen_code(mail)
    send_mail(
        "verification-code",
        f"your verfication code is {code}",
        settings.EMAIL_HOST_USER,
        [mail],
        fail_silently=False,
    )
    return code
