import functools
from flask import session, jsonify, g
from werkzeug.routing import BaseConverter
from iHome.utils.response_code import RET


class RegexConverter(BaseConverter):
    """自定义正则转换器"""

    def __init__(self, url_map, regex):
        super().__init__(url_map)
        self.regex = regex


# 自定义登录验证装饰器
def login_required(view_func):
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is not None:
            # 用户已登录
            g.user_id = user_id
            return view_func(*args, **kwargs)
        else:
            # 用户未登录
            return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    return wrapper
