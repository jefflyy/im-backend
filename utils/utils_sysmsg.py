from .utils_request import return_field

def extract_sysmsg(msg):
    return {
        "type": "sysmsg",
        "content": return_field(msg.serialize(), [
            "sysmsg_id",
            "sysmsg_type",
            "message",
            "create_time",
            "update_time",
            "can_operate",
            "result",
            "sup_user_id",
            "sup_group_id",
        ])
    }
