from django.db.models import Q

from im.models import User, Group, Groupmember, Message, Systemmsg, Userdelmsg

from utils.utils_websocket import send_msg, online
from utils.utils_sysmsg import extract_sysmsg


def login_fetch(user: User):
    ret = []
    update_list = []
    for gm in Groupmember.objects.filter(member_user=user):
        delids = Userdelmsg.objects.filter(user=user, msg__group=gm.group).values("msg__msg_id")
        qset = Message.objects.filter(group=gm.group, msg_id__gt=gm.ack_msg_id).exclude(msg_id__in=delids)
        max_read = -1
        for msg in qset:
            data = msg.serialize()
            ret.append({
                "type": "message",
                "content": data,
            })
            max_read = max(max_read, data["msg_id"])
        
        if max_read != -1:
            gm.sent_msg_id = max_read
            update_list.append(gm)
    
    Groupmember.objects.bulk_update(update_list, fields=["sent_msg_id"])
    
    max_read = -1
    for msg in Systemmsg.objects.filter(Q(target_user=user) & (Q(sysmsg_id__gt=user.read_sysmsg_id) | Q(can_operate=True))):
        ret.append(extract_sysmsg(msg))
        max_read = max(max_read, msg.sysmsg_id)
    
    if max_read != -1:
        user.read_sysmsg_id = max_read
        user.save(update_fields=["read_sysmsg_id"])
    
    send_msg(user.user_name, ret)


def push_message(gm: Groupmember, new_msg: Message) -> bool:
    """
    Try sending message that id == new_msg id or > sent_msg_id to user.

    :param gm: group-member relation
    :param new_msg: generated message, may be not in database
    :returns: user online or not
    """
    new_msg_id = new_msg.msg_id
    user = gm.member_user
    group = gm.group
    if online(user.user_name):
        msgs = [{
            "type": "message",
            "content": msg.serialize(),
        } for msg in Message.objects.filter(group=group, msg_id__gt=gm.sent_msg_id)]
        if new_msg_id not in set(msg["content"]["msg_id"] for msg in msgs):
            msgs.append({
                "type": "message",
                "content": new_msg.serialize(),
            })
        send_msg(user.user_name, msgs)
        gm.sent_msg_id = max(new_msg_id, gm.sent_msg_id)
        return True
    
    return False


def push_sysmsg(user: User, new_sysmsg_id: int) -> bool:
    """
    Try sending system message to user.

    :param user: target user
    :param new_sysmsg_id: id of the generated system message
    :returns: user online or not
    """
    if online(user.user_name):
        lost_new = True
        ret = []
        for msg in Systemmsg.objects.filter(target_user=user, sysmsg_id__gt=user.read_sysmsg_id):
            ret.append(extract_sysmsg(msg))
            if msg.sysmsg_id == new_sysmsg_id:
                lost_new = False
        
        if lost_new:
            msg = Systemmsg.objects.filter(sysmsg_id=new_sysmsg_id).first()
            ret.append(extract_sysmsg(msg))
        
        send_msg(user.user_name, ret)
        user.read_sysmsg_id = new_sysmsg_id
        return True

    return False


def on_message(user_name: str, content: dict):
    keys = set(content.keys())
    assert keys == {"group_id", "msg_type", "msg_body"} \
        or keys == {"group_id", "msg_type", "msg_body", "reply_msg_id"}, "Incorrect json format for message.content"

    user = User.objects.filter(user_name=user_name).first()
    assert user is not None, f"user {user_name} does not exist"
    
    group_id = content["group_id"]
    group = Group.objects.filter(group_id=group_id).first()
    assert group is not None, f"group with id {group_id} does not exist"

    gm_1 = Groupmember.objects.filter(group=group, member_user=user).first()
    assert gm_1 is not None, f"user {user_name} is not in group {group.group_id}"

    reply_msg_id = content.get("reply_msg_id")
    assert reply_msg_id is None or isinstance(reply_msg_id, int) , "invalid type of reply_msg_id"
    if reply_msg_id is not None:
        reply_msg = Message.objects.filter(msg_id=reply_msg_id).first()
        assert reply_msg is not None, "reply message does not exist"
        assert reply_msg.group == group, "reply message is not in the group"
        assert reply_msg.msg_type != "recall", "reply message is recalled"

    msg = Message.objects.create(
        sender=user,
        group=group,
        msg_type=content["msg_type"],
        msg_body=content["msg_body"],
        reply_msg_id=reply_msg_id,
    )

    update_list = []
    for member in Groupmember.objects.filter(group=group):
        if push_message(member, msg):
            update_list.append(member)
    
    Groupmember.objects.bulk_update(update_list, fields=["sent_msg_id"])
