from datetime import datetime
import json
from flask import g, request, jsonify, current_app, session
from . import api
from .. import db, constants, redis_restore
from ..models import User, Area, House, Facility, HouseImage, Order
from ..utils.commons import login_required
from ..utils.image_storage import storage
from ..utils.response_code import RET


@api.route('/orders', methods=['POST'])
@login_required
def save_order():
    """保存订单信息"""
    # 获取参数
    user_id = g.user_id
    order_data = request.get_json()
    if not order_data:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    house_id = order_data.get('house_id')
    start_date_str = order_data.get('start_date')
    end_date_str = order_data.get('end_date')
    # 校验参数
    if not all([house_id, start_date_str, end_date_str]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')
    # 处理日期
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        assert start_date <= end_date
        days = (end_date - start_date).days + 1
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg='日期参数有误')
    # 查询房屋信息
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')
    if not house:
        return jsonify(errno=RET.NODATA, errmsg='房屋不存在')
    # 判断房屋是否是当前用户的
    if house.user_id == user_id:
        return jsonify(errno=RET.ROLEERR, errmsg='不能预订自己的房屋')
    # 查询用户预定的房屋是否在时间冲突
    try:
        count = Order.query.filter(Order.house_id == house_id, Order.begin_date <= end_date,
                                   Order.end_date >= start_date).count()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')
    if count > 0:
        return jsonify(errno=RET.DATAERR, errmsg='房屋已被预定')
    # 计算总金额
    amount = days * house.price
    # 保存订单数据
    order = Order(
        user_id=user_id,
        house_id=house_id,
        begin_date=start_date,
        end_date=end_date,
        days=days,
        house_price=house.price,
        amount=amount
    )

    try:
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存订单数据失败')
    # 返回结果
    return jsonify(errno=RET.OK, errmsg='OK', data={'order_id': order.id})


@api.route('/user/orders', methods=['GET'])
@login_required
def get_user_orders():
    """获取用户订单信息"""
    # 获取参数
    user_id = g.user_id
    role = request.args.get('role', '')
    # 校验参数
    if role not in ('custom', 'landlord'):
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    # 查询订单数据
    try:
        if role == 'landlord':
            # 房东
            houses = House.query.filter(House.user_id == user_id).all()
            houses_ids = [house.id for house in houses]
            orders = Order.query.filter(Order.house_id.in_(houses_ids)).order_by(Order.create_time.desc()).all()
        else:
            # 客户
            orders = Order.query.filter(Order.user_id == user_id).order_by(Order.create_time.desc()).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')
    # 将订单数据转换成字典数据
    orders_dict_list = []
    if orders:
        for order in orders:
            orders_dict_list.append(order.to_dict())
    # 返回结果
    return jsonify(errno=RET.OK, errmsg='OK', data={'orders': orders_dict_list})


@api.route('/orders/<int:order_id>/status', methods=['PUT'])
@login_required
def accept_reject_order(order_id):
    """接单、拒单"""
    # 获取参数
    user_id = g.user_id
    req_data = request.get_json()
    if not req_data:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    action = req_data.get('action')
    # 校验参数
    if action not in ('accept', 'reject'):
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    # 查询订单信息
    try:
        order = Order.query.filter(Order.id == order_id, Order.status == 'WAIT_ACCEPT').first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')
    if not order:
        return jsonify(errno=RET.NODATA, errmsg='订单数据有误')
    # 接单、拒单
    if action == 'accept':
        # 接单
        order.status = 'WAIT_PAYMENT'
    elif action == 'reject':
        # 拒单
        reason = req_data.get('reason')
        if not reason:
            return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
        order.status = 'REJECTED'
        order.comment = reason
    # 保存订单信息
    try:
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存订单信息失败')
    # 返回结果
    return jsonify(errno=RET.OK, errmsg='OK')


@api.route('/orders/<int:order_id>/comment', methods=['PUT'])
@login_required
def save_order_comment(order_id):
    """保存订单评论信息"""
    # 获取参数
    user_id = g.user_id
    req_data = request.get_json()
    if not req_data:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    comment = req_data.get('comment')
    # 校验参数
    if not comment:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    # 查询订单信息
    try:
        order = Order.query.filter(Order.id == order_id, Order.user_id == user_id,
                                   Order.status == 'WAIT_COMMENT').first()
        house = order.house
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')
    if not order:
        return jsonify(errno=RET.NODATA, errmsg='订单数据有误')
    # 保存订单评论信息
    order.comment = comment
    order.status = 'COMPLETE'
    house.order_count += 1
    # 保存订单信息
    try:
        db.session.add(order)
        db.session.add(house)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存评论信息失败')
    try:
        redis_restore.delete('house_info_%s' % order.house_id)
    except Exception as e:
        current_app.logger.error(e)
    # 返回结果
    return jsonify(errno=RET.OK, errmsg='OK')
