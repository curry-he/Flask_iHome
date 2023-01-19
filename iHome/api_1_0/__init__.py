from flask import Blueprint


# 创建蓝图对象
api = Blueprint("api_1_0", __name__)

from . import demo, verify_code, passport, profile, houses, orders
