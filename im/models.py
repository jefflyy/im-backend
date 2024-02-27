from django.db import models
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from utils import utils_time
from utils.utils_require import MAX_CHAR_LENGTH

# Create your models here.

class User(models.Model):
    user_id = models.BigAutoField(primary_key=True)
    user_name = models.CharField(max_length=MAX_CHAR_LENGTH, unique=True)
    password = models.CharField(max_length=MAX_CHAR_LENGTH)
    register_time = models.FloatField(default=utils_time.get_timestamp)
    login_time = models.FloatField(null=True)
    user_email = models.EmailField(unique=True)
    read_sysmsg_id = models.BigIntegerField(default=-1)
    
    class Meta:
        indexes = [models.Index(fields=["user_name", "user_email"])]
        
    def serialize(self):
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "password": self.password,
            "register_time": self.register_time,
            "login_time": self.login_time,
            "user_email": self.user_email,
        }

    def __str__(self) -> str:
        return self.user_name


class Group(models.Model):
    group_id = models.BigAutoField(primary_key=True)
    group_name = models.CharField(max_length=MAX_CHAR_LENGTH)
    create_time = models.FloatField(default=utils_time.get_timestamp)
    group_owner = models.ForeignKey(to=User, on_delete=models.CASCADE, null=True)

    class Meta:
        indexes = [models.Index(fields=["group_name"])]

    def serialize(self):
        return {
            "group_id": self.group_id,
            "group_name": self.group_name,
            "create_time": self.create_time,
            "group_owner_id": self.group_owner.user_id if self.group_owner is not None else None,
        }

    def __str__(self):
        return f"{self.group_owner.user_name}'s group {self.group_name}" if self.group_owner is not None else f"Friend Group"


class Friend(models.Model):
    user = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name='user')
    friend = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name='friend')
    group = models.ForeignKey(to=Group, on_delete=models.CASCADE, related_name='friend_group')
    update_time = models.FloatField(default=utils_time.get_timestamp)

    def serialize(self):
        return {
            "user_id": self.user.user_id,
            "friend_id": self.friend.user_id,
            "group_id": self.group.group_id,
            "update_time": self.update_time,
        }

    def __str__(self) -> str:
        return f"{self.user.user_name}'s friend {self.friend.user_name}"


class Groupmember(models.Model):
    group = models.ForeignKey(to=Group, on_delete=models.CASCADE)
    member_user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    member_role = models.CharField(max_length=MAX_CHAR_LENGTH)
    join_time = models.FloatField(default=utils_time.get_timestamp)
    sent_msg_id = models.BigIntegerField(default=-1)
    ack_msg_id = models.BigIntegerField(default=-1)
    do_not_disturb = models.BooleanField(default=False)
    top = models.BooleanField(default=False)

    def serialize(self, private=False):
        if private:
            return {
            "group_id": self.group.group_id,
            "member_id": self.member_user.user_id,
            "member_name": self.member_user.user_name,
            "member_role": self.member_role,
            "join_time": self.join_time,
            "sent_msg_id": self.sent_msg_id,
            "ack_msg_id": self.ack_msg_id,
            }
        return {
            "group_id": self.group.group_id,
            "member_id": self.member_user.user_id,
            "member_name": self.member_user.user_name,
            "member_role": self.member_role,
            "join_time": self.join_time,
            "sent_msg_id": self.sent_msg_id,
            "ack_msg_id": self.ack_msg_id,
            "do_not_disturb": self.do_not_disturb,
            "top": self.top,
        }

    def __str__(self) -> str:
        return f"{self.member_user.user_name} is a {self.member_role} of group {self.group.group_name}"

class Message(models.Model):
    msg_id = models.BigAutoField(primary_key=True)
    sender = models.ForeignKey(to=User, on_delete=models.CASCADE)
    group = models.ForeignKey(to=Group, on_delete=models.CASCADE)
    msg_body = models.CharField(max_length=MAX_CHAR_LENGTH)
    msg_type = models.CharField(max_length=MAX_CHAR_LENGTH)
    create_time = models.FloatField(default=utils_time.get_timestamp)
    reply_msg_id = models.BigIntegerField(null=True)

    def serialize(self):
        return {
            "msg_id": self.msg_id,
            "sender_id": self.sender.user_id,
            "group_id": self.group.group_id,
            "msg_body": self.msg_body,
            "msg_type": self.msg_type,
            "create_time": self.create_time,
            "reply_msg_id": self.reply_msg_id,
        }

    def __str__(self) -> str:
        return f"{self.sender.user_name} sent '{self.msg_body}' in group {self.group.group_id}"

class Systemop(models.Model):
    sysop_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name='source_user')
    sysop_type = models.CharField(max_length=MAX_CHAR_LENGTH)
    target_user = models.ForeignKey(to=User, on_delete=models.CASCADE, null=True, related_name='target_user')
    target_group = models.ForeignKey(to=Group, on_delete=models.CASCADE, null=True, related_name='target_group')
    message = models.CharField(max_length=MAX_CHAR_LENGTH)
    need_operation = models.BooleanField(default=False)
    result = models.CharField(max_length=MAX_CHAR_LENGTH)
    create_time = models.FloatField(default=utils_time.get_timestamp)
    update_time = models.FloatField(null=True)

    def serialize(self):
        return {
            "sysop_id": self.sysop_id,
            "user_id": self.user.user_id,
            "sysop_type": self.sysop_type,
            "target_user_id": (None if self.target_user is None else self.target_user.user_id),
            "target_group_id": (None if self.target_group is None else self.target_group.group_id),
            "message": self.message,
            "need_operation": self.need_operation,
            "create_time": self.create_time,
            "update_time": self.update_time,
        }

    def __str__(self) -> str:
        if self.target_user is not None and self.target_group is None:
            return f"{self.user.user_name} try making system operation to {self.target_user.user_name}"
        elif self.target_user is None and self.target_group is not None:
            return f"{self.user.user_name} try making system operation to {self.target_group.group_name}"
        elif self.target_user is not None and self.target_group is not None:
            return f"{self.user.user_name} try making system operation to {self.target_user.user_name} in {self.target_group.group_name}"
        
        raise ValueError

class Systemmsg(models.Model):
    sysmsg_id = models.BigAutoField(primary_key=True)
    sysop = models.ForeignKey(to=Systemop, on_delete=models.CASCADE)
    target_user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    sysmsg_type = models.CharField(max_length=MAX_CHAR_LENGTH)
    message = models.CharField(max_length=MAX_CHAR_LENGTH)
    create_time = models.FloatField(default=utils_time.get_timestamp)
    update_time = models.FloatField(default=utils_time.get_timestamp)
    can_operate = models.BooleanField(default=False)
    result = models.CharField(max_length=MAX_CHAR_LENGTH)
    sup_user = models.ForeignKey(to=User, on_delete=models.CASCADE, null=True, related_name="sup_user")
    sup_group = models.ForeignKey(to=Group, on_delete=models.CASCADE, null=True)

    def serialize(self):
        return {
            "sysmsg_id": self.sysmsg_id,
            "sysop_id": self.sysop.sysop_id,
            "target_user_id": self.target_user.user_id,
            "sysmsg_type": self.sysmsg_type,
            "message": self.message,
            "create_time": self.create_time,
            "update_time": self.update_time,
            "can_operate": self.can_operate,
            "result": self.result,
            "sup_user_id": (None if self.sup_user is None else self.sup_user.user_id),
            "sup_group_id": (None if self.sup_group is None else self.sup_group.group_id),
        }

    def __str__(self) -> str:
        return f"{self.target_user.user_name} got a system message {self.message} and {'can' if self.can_operate else 'cannot'} operate it"

class CustomStorage(FileSystemStorage):
    def __init__(self, location=None, base_url=None):
        location = settings.BASE_DIR
        super().__init__(location, base_url)

def get_file_path(instance, filename):
    return f"database/msg/{instance.msg.msg_id}/{filename}"

class File(models.Model):
    msg = models.ForeignKey(to=Message, on_delete=models.CASCADE)
    name = models.CharField(max_length=MAX_CHAR_LENGTH)
    file = models.FileField(upload_to=get_file_path, storage=CustomStorage())
    upload_time = models.FloatField(default=utils_time.get_timestamp)

class Userdelmsg(models.Model):
    user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    msg = models.ForeignKey(to=Message, on_delete=models.CASCADE)
