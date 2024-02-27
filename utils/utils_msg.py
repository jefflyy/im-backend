import json

from im.models import Groupmember, Message, Userdelmsg, File


RECALL_TIME_LIMIT = 2 * 60 # 2 minutes

def get_latest_msg(gm: Groupmember):
    delids = Userdelmsg.objects.filter(user=gm.member_user, msg__group=gm.group).values("msg__msg_id")
    qset = Message.objects.filter(group=gm.group, msg_id__lte=gm.ack_msg_id).exclude(msg_id__in=delids)
    if not qset.exists():
        return None
    else:
        return qset.latest("msg_id").serialize()

def get_file_set(msg: Message):
    if msg is None:
        return set()
    if msg.msg_type in {"text", "recall"}:
        return set()
    if msg.msg_type == "forward":
        file = File.objects.filter(msg=msg, name="files.json").first()
        if file is None:
            return set()
        with file.file.open("r") as f:
            return set(json.loads(f.read()))
    else:
        # single file
        return {msg.msg_id}
