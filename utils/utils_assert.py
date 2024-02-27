from django.test import TestCase


def assertSingleSysmsg(self: TestCase, ret, sysmsg_type, message, can_operate, result, sup_user_id=None, sup_group_id=None):
    self.assertIsInstance(ret, list)
    self.assertEqual(len(ret), 1)
    self.assertIsInstance(ret[0], dict)
    self.assertSetEqual(set(ret[0].keys()), {"type", "content"})
    self.assertEqual(ret[0]["type"], "sysmsg")
    content: dict = ret[0]["content"]
    self.assertIsInstance(content, dict)
    self.assertSetEqual(set(content.keys()), {"sysmsg_id", "sysmsg_type", "message", "create_time", "update_time", "can_operate", "result", "sup_user_id", "sup_group_id"})
    self.assertEqual(content["sysmsg_type"], sysmsg_type)
    self.assertEqual(content["message"], message)
    self.assertEqual(content["can_operate"], can_operate)
    self.assertEqual(content["result"], result)
    self.assertEqual(content["sup_user_id"], sup_user_id)
    self.assertEqual(content["sup_group_id"], sup_group_id)

def assertSingleMessage(self: TestCase, ret, sender_id, group_id, msg_type, msg_body, reply_msg_id=None):
    self.assertIsInstance(ret, list)
    self.assertEqual(len(ret), 1)
    self.assertIsInstance(ret[0], dict)
    self.assertSetEqual(set(ret[0].keys()), {"type", "content"})
    self.assertEqual(ret[0]["type"], "message")
    content: dict = ret[0]["content"]
    self.assertIsInstance(content, dict)
    self.assertSetEqual(set(content.keys()), {"msg_id", "sender_id", "group_id", "msg_type", "msg_body", "create_time", "reply_msg_id"})
    self.assertEqual(content["sender_id"], sender_id)
    self.assertEqual(content["group_id"], group_id)
    self.assertEqual(content["msg_type"], msg_type)
    self.assertEqual(content["msg_body"], msg_body)
    self.assertEqual(content["reply_msg_id"], reply_msg_id)
