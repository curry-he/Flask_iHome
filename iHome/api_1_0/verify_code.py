import random
from flask import make_response, current_app, jsonify, request
from . import api
from iHome.utils import captcha
from ..libs.yuntongxun.sms import CCP
from ..utils.captcha.captcha import captcha
from iHome import redis_restore, constants
from ..utils.response_code import RET
from iHome.models import User
from iHome.tasks.task_sms import send_sms

@api.route('/image_codes/<image_code_id>')
def get_image_code(image_code_id):
    """提供图片验证码"""
    # 接收参数
    # 校验参数
    # 业务逻辑处理
    # 生成验证码图片
    captcha.generate_captcha()
    # 名字，真实文本，图片数据
    name, text, image_data = captcha.generate_captcha()
    # 将验证码真实值和编号保存到redis中, 设置有效期
    try:
        redis_restore.setex('image_code_%s' % image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='save image code id failed')
    # 返回验证码图片
    resp = make_response(image_data)
    resp.headers['Content-Type'] = 'image/jpg'
    return resp


# @api.route("/sms_codes/<re(r'1[34578]\d{9}'):mobile>", methods=['GET', 'POST'])
# def get_sms_code(mobile):
#     """获取短信验证码"""
#     image_code = request.args.get("image_code")
#     image_code_id = request.args.get("image_code_id")
#     # 校验参数
#     if not all([image_code, image_code_id]):
#         return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')
#     # 从redis中取出真实的图片验证码，进行对比
#     try:
#         real_image_code = redis_restore.get("image_code_%s" % image_code_id)
#         print(real_image_code)
#         real_image_code = real_image_code.decode("utf-8")
#         print(real_image_code)
#     except Exception as E:
#         current_app.logger.error(E)
#         return jsonify(errno=RET.DBERR, errmsg="redis数据库异常")
#     # 判断图片验证码是否过期
#     if not real_image_code:
#         # 表示图片验证码没有或者过期
#         return jsonify(errno=RET.NODATA, errmsg="图片验证码失效")
#
#     # 删除redis中图片验证码，防止用户使用同一个图片验证码验证多次
#     try:
#         redis_restore.delete("image_code_%s" % image_code_id)
#     except Exception as E:
#         current_app.logger.error(E)
#
#     # 与用户填写的值进行对比
#     if real_image_code.lower() != image_code.lower():
#         return jsonify(errno=RET.DATAERR, errmsg="图片验证码错误")
#
#     # 判断这个手机号有没有发送短信的记录，有则认为发送频繁
#     try:
#         send_flag = redis_restore.get("sms_code_%s" % mobile)
#     except Exception as E:
#         current_app.logger.error(E)
#     else:
#         if send_flag is not None:
#             return jsonify(errno=RET.REQERR, errmsg="请求过于频繁，请60s后重试")
#
#     # 判断手机号是否注册过，如果否则发送短信，并保存真实的短信验证码
#     try:
#         user = User.query.filter_by(phone_num=mobile).first()
#     except Exception as E:
#         current_app.logger.error(E)
#     else:
#         if user is not None:
#             return jsonify(errno=RET.DATAEXIST, errmsg="手机号已存在")
#     # 生成短信验证码
#     sms_code = "%6d" % random.randint(0, 999999)
#     # 将短信验证码保存在redis中
#     try:
#         redis_restore.setex("sms_code_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
#         # 保存发送给这个手机号的记录，防止用户在60s内再次发送短信(value值随便设置)
#         redis_restore.setex("send_sms_code_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)
#     except Exception as E:
#         current_app.logger.error(E)
#         return jsonify(errno=RET.DBERR, errmsg="保存短信验证码异常")
#     # 发送短信
#     try:
#         ccp = CCP()
#         result = ccp.sendTemplateSMS(mobile, [sms_code, int(constants.SMS_CODE_REDIS_EXPIRES) / 60], 1)
#     except Exception as E:
#         current_app.logger.error(E)
#         return jsonify(errno=RET.THIRDERR, errmsg="发送异常")
#     if result:
#         # 发送成功
#         return jsonify(errno=RET.OK, errmsg="发送成功")
#     else:
#         return jsonify(errno=RET.THIRDERR, errmsg="发送失败")


@api.route("/sms_codes/<re(r'1[34578]\d{9}'):mobile>", methods=['GET', 'POST'])
def get_sms_code(mobile):
    """获取短信验证码"""
    image_code = request.args.get("image_code")
    image_code_id = request.args.get("image_code_id")
    # 校验参数
    if not all([image_code, image_code_id]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')
    # 从redis中取出真实的图片验证码，进行对比
    try:
        real_image_code = redis_restore.get("image_code_%s" % image_code_id)
        print(real_image_code)
        real_image_code = real_image_code.decode("utf-8")
        print(real_image_code)
    except Exception as E:
        current_app.logger.error(E)
        return jsonify(errno=RET.DBERR, errmsg="redis数据库异常")
    # 判断图片验证码是否过期
    if not real_image_code:
        # 表示图片验证码没有或者过期
        return jsonify(errno=RET.NODATA, errmsg="图片验证码失效")

    # 删除redis中图片验证码，防止用户使用同一个图片验证码验证多次
    try:
        redis_restore.delete("image_code_%s" % image_code_id)
    except Exception as E:
        current_app.logger.error(E)

    # 与用户填写的值进行对比
    if real_image_code.lower() != image_code.lower():
        return jsonify(errno=RET.DATAERR, errmsg="图片验证码错误")

    # 判断这个手机号有没有发送短信的记录，有则认为发送频繁
    try:
        send_flag = redis_restore.get("sms_code_%s" % mobile)
    except Exception as E:
        current_app.logger.error(E)
    else:
        if send_flag is not None:
            return jsonify(errno=RET.REQERR, errmsg="请求过于频繁，请60s后重试")

    # 判断手机号是否注册过，如果否则发送短信，并保存真实的短信验证码
    try:
        user = User.query.filter_by(phone_num=mobile).first()
    except Exception as E:
        current_app.logger.error(E)
    else:
        if user is not None:
            return jsonify(errno=RET.DATAEXIST, errmsg="手机号已存在")
    # 生成短信验证码
    sms_code = "%6d" % random.randint(0, 999999)
    # 将短信验证码保存在redis中
    try:
        redis_restore.setex("sms_code_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        # 保存发送给这个手机号的记录，防止用户在60s内再次发送短信(value值随便设置)
        redis_restore.setex("send_sms_code_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)
    except Exception as E:
        current_app.logger.error(E)
        return jsonify(errno=RET.DBERR, errmsg="保存短信验证码异常")
    # 发送短信
    send_sms.delay(mobile, [sms_code, int(constants.SMS_CODE_REDIS_EXPIRES) / 60], 1)

    return jsonify(errno=RET.OK, errmsg="发送成功")
