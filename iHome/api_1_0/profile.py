from flask import g, request, jsonify, current_app, session
from . import api
from .. import db, constants
from ..models import User
from ..utils.commons import login_required
from ..utils.image_storage import storage
from ..utils.response_code import RET


@api.route('/users/avatar', methods=['POST'])
@login_required
def set_user_avatar():
    """设置用户头像"""
    # 获取用户id
    user_id = g.user_id
    # 获取图片
    image_file = request.files.get('avatar')

    if image_file is None:
        return jsonify(errno=RET.PARAMERR, errmsg='未上传图片')

    # 读取图片数据
    image_data = image_file.read()

    # 调用七牛云上传图片
    try:
        file_name = storage(image_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg='上传图片失败')

    # 保存图片名到数据库
    try:
        User.query.filter_by(id=user_id).update({'avatar_url': file_name})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存图片信息失败')

    # 保存成功返回
    return jsonify(errno=RET.OK, errmsg='保存成功', data={'avatar_url': constants.QINIU_URL_DOMAIN + file_name})


@api.route('/users/name', methods=['PUT'])
@login_required
def set_user_name():
    """设置用户名"""
    # 获取用户id
    user_id = g.user_id
    # 获取用户名
    req_dict = request.get_json()
    user_name = req_dict.get('user_name')

    if not user_name:
        return jsonify(errno=RET.PARAMERR, errmsg="用户名不能为空")
    if len(user_name) >= 32:
        return jsonify(errno=RET.PARAMERR, errmsg="用户名过长")

    # 保存用户名到数据库
    try:
        User.query.filter_by(id=user_id).update({'name': user_name})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存用户名失败')

    # 保存成功返回
    session["name"] = user_name
    return jsonify(errno=RET.OK, errmsg='保存成功', data={'user_name': user_name})


@api.route('/users', methods=['GET'])
@login_required
def get_user_profile():
    """获取用户信息"""
    # 获取用户id
    user_id = g.user_id

    # 查询用户信息
    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户信息失败')
    if user is None:
        return jsonify(errno=RET.NODATA, errmsg='用户不存在')
    # 返回用户信息
    return jsonify(errno=RET.OK, errmsg='OK', data=user.to_dict())


@api.route('/users/auth', methods=['POST'])
@login_required
def set_user_auth():
    """实名认证"""
    # 获取用户id
    user_id = g.user_id
    # 获取参数
    req_dict = request.get_json()
    real_name = req_dict.get('real_name')
    id_card = req_dict.get('id_card')

    # 校验参数
    if not all([real_name, id_card]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')

    # 保存用户实名信息到数据库
    try:
        User.query.filter_by(id=user_id, real_name=None, id_card=None).update(
            {'real_name': real_name, 'id_card': id_card})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存用户实名信息失败')

    # 返回实名信息
    return jsonify(errno=RET.OK, errmsg='OK', data={'real_name': real_name, 'id_card': id_card})


@api.route('/users/auth', methods=['GET'])
@login_required
def get_user_auth():
    """获取用户信息"""
    # 获取用户id
    user_id = g.user_id

    # 查询用户信息
    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='获取实名认证信息失败')
    if user is None:
        return jsonify(errno=RET.NODATA, errmsg='用户不存在')
    # 返回用户信息
    return jsonify(errno=RET.OK, errmsg='OK', data=user.to_auth_dict())
