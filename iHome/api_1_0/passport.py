import re
from . import api
from flask import request, jsonify, current_app, session
from ..utils.response_code import RET
from iHome import redis_restore, db, constants
from iHome.models import User
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash


@api.route('/users', methods=['POST'])
def register():
    """用户注册"""
    # 获取参数
    req_dict = request.get_json()
    mobile = req_dict.get('mobile')
    sms_code = req_dict.get('sms_code')
    password = req_dict.get('password')
    password2 = req_dict.get('password2')
    # 校验参数
    if not all([mobile, sms_code, password]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')

    # 判断手机号格式
    if not re.match(r'1[34578]\d{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg='手机号格式错误')
    if password != password2:
        return jsonify(errno=RET.PARAMERR, errmsg='两次密码不一致')

    # 业务逻辑处理
    # 从redis中取出短信验证码
    try:
        real_sms_code = redis_restore.get('sms_code_%s' % mobile)
        real_sms_code = real_sms_code.decode("utf-8")
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询短信验证码异常')

    # 判断短信验证码是否过期
    if real_sms_code is None:
        return jsonify(errno=RET.NODATA, errmsg='短信验证码过期')

    # 删除redis中的短信验证码，防止用户使用同一个短信验证码验证多次
    try:
        redis_restore.delete('sms_code_%s' % mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='删除短信验证码异常')

    # 判断用户填写的短信验证码是否正确
    if real_sms_code != sms_code:
        return jsonify(errno=RET.DATAERR, errmsg='短信验证码错误')

    # # 判断手机号是否注册
    # try:
    #     user = User.query.filter_by(mobile=mobile).first()
    # except Exception as e:
    #     current_app.logger.error(e)
    #     return jsonify(errno=RET.DBERR, errmsg='查询用户数据异常')
    # else:
    #     if user is not None:
    #         return jsonify(errno=RET.DATAEXIST, errmsg='手机号已注册')

    # 保存用户的注册数据到数据库中
    user = User(name=mobile, mobile=mobile)
    # 对密码进行加密处理
    user.password_hash = password
    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError as e:
        # 手机号出现重复值，即手机号已注册
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='手机号已注册')
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存用户数据异常')

    # 保存登录状态到session中
    session['name'] = mobile
    session['mobile'] = mobile
    session['user_id'] = user.id

    # 返回结果
    return jsonify(errno=RET.OK, errmsg='注册成功')


@api.route('/sessions', methods=['POST'])
def login():
    """用户登录"""
    # 获取参数
    req_dict = request.get_json()
    mobile = req_dict.get('mobile')
    password = req_dict.get('password')

    # 校验参数
    if not all([mobile, password]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')

    # 判断手机号格式
    if not re.match(r'1[34578]\d{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg='手机号格式错误')

    # 判断错误次数是否超过限制，如果超过限制，则返回
    # redis记录： "access_nums_请求的ip": 次数
    user_ip = request.remote_addr  # 用户的ip
    try:
        access_nums = redis_restore.get("access_nums_%s" % user_ip)
    except Exception as e:
        current_app.logger.error(e)
    else:
        if access_nums is not None and int(access_nums) >= constants.LOGIN_ERROR_MAX_TIMES:
            return jsonify(errno=RET.REQERR, errmsg='错误次数过多，请稍后重试')

    # 业务逻辑处理
    # 从数据库中查询用户的数据
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='获取用户信息失败')

    # 判断用户的密码是否正确
    if user is None or not user.check_password(password):
        # 记录用户登录错误次数
        try:
            redis_restore.incr("access_nums_%s" % user_ip)
            redis_restore.expire("access_nums_%s" % user_ip, constants.LOGIN_ERROR_FORBID_TIME)
        except Exception as e:
            current_app.logger.error(e)

        return jsonify(errno=RET.DATAERR, errmsg='用户名或密码错误')

    # 保存用户的登录状态
    session['name'] = user.name
    session['mobile'] = user.mobile
    session['user_id'] = user.id

    # 返回结果
    return jsonify(errno=RET.OK, errmsg='登录成功')


@api.route('/session', methods=['GET'])
def check_login():
    """检查登录状态"""
    # 尝试从session中获取用户的名字
    name = session.get('name')

    # 如果session中数据name名字存在，则表示用户已登录，否则未登录
    if name is not None:
        return jsonify(errno=RET.OK, errmsg='true', data={'name': name})
    else:
        return jsonify(errno=RET.SESSIONERR, errmsg='false')


@api.route('/session', methods=['DELETE'])
def logout():
    """退出登录"""
    # 清除session数据
    session.clear()

    return jsonify(errno=RET.OK, errmsg='OK')
