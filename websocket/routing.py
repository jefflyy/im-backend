from django.urls import path

from websocket.consumers import ChatConsumer

websocket_urlpatterns = [
    path('ws/chat/<str:user_name>', ChatConsumer.as_asgi()),
]
