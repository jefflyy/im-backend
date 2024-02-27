
ws_reg = {}

# record websocket connection, using (user_name, jwt_token) as key
def login_user(user_name, jwt_token, ws):
    if user_name not in ws_reg:
        ws_reg[user_name] = {}
    ws_reg[user_name][jwt_token] = ws

# try sending message to all websocket connections of user_name
def send_msg(user_name, content):
    if user_name in ws_reg:
        err_jwts = []
        for jwt, ws in ws_reg[user_name].items():
            try:
                ws.send_json(content)
            except:
                err_jwts.append(jwt)
        for jwt in err_jwts:
            try:
                ws_reg[user_name].pop(jwt).close()
            except:
                pass

# remove websocket connection from registry
def clear_reg(user_name, jwt_token):
    if (user_name in ws_reg) and (jwt_token in ws_reg[user_name]):
        ws = ws_reg[user_name].pop(jwt_token)
        if not ws_reg[user_name]:
            ws_reg.pop(user_name)
        return ws
    return None

# close websocket connection
def logout_user(user_name, jwt_token):
    ws = clear_reg(user_name, jwt_token)
    if ws:
        ws.close()

# check if user_name is online, i.e. has a websocket connection with any jwt_token
def online(user_name):
    return (user_name in ws_reg) and (ws_reg[user_name] is not None)
