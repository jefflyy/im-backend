from channels.generic.websocket import JsonWebsocketConsumer
from channels.exceptions import StopConsumer
import sys

from im.models import User
from .views import login_fetch, on_message
from utils.utils_jwt import auth_jwt_token
from utils.utils_websocket import login_user, clear_reg


class ChatConsumer(JsonWebsocketConsumer):

    def log_error(self, msg):
        self.send_json([{"type": "error", "content": msg}])

    def connect(self):
        try:
            user_name = self.scope['path'].split('/')[-1]
            assert len(user_name) > 0, "Invalid [user_name]"

            jwt_token = self.scope['query_string'].decode('utf-8')
            assert auth_jwt_token(jwt_token) == user_name, "Invalid [jwt_token]"

            user = User.objects.filter(user_name=user_name).first()
            assert user is not None, "no such user"
            login_user(user_name, jwt_token, self)
            self.user_name = user_name
            self.jwt_token = jwt_token
            self.accept()
            login_fetch(user)
        except AssertionError:
            self.user_name = None
            self.jwt_token = None
            self.close()

    def disconnect(self, close_code):
        clear_reg(self.user_name, self.jwt_token)
        print(f"websocket disconnected with close code {close_code}", file=sys.stderr)
        raise StopConsumer

    def receive_json(self, json):
        try:
            assert set(json.keys()) == {"type", "content"}, "Invalid json format"
            assert json["type"] in {"message"}, "Invalid message [type]"
            msg_type = json["type"]
            if msg_type == "message":
                return on_message(self.user_name, json["content"])
        except AssertionError as e:
            self.log_error(str(e))
