import os

from alipay import AliPay
from flask import jsonify, current_app, request, g

from . import api
from .. import constants, db
from ..models import Order
from ..utils.commons import login_required
from ..utils.response_code import RET


@api.route('/orders/<int:order_id>/payment', methods=['POST'])
@login_required
def order_pay(order_id):
    """订单支付"""
    # 获取参数
    user_id = g.user_id
    # 校验参数
    if not order_id:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    # 查询订单信息
    try:
        order = Order.query.filter(Order.id == order_id, Order.user_id == user_id,
                                   Order.status == 'WAIT_PAYMENT').first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')
    if not order:
        return jsonify(errno=RET.NODATA, errmsg='订单数据有误')
    # 调用支付宝的sdk工具进行支付
    # 初始化
    alipay_client = AliPay(
        appid="2021000121699419",
        app_notify_url=None,  # 默认回调url
        app_private_key_string=open(os.path.join(os.path.dirname(__file__), "keys/app_private_key.pem")).read(),
        # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
        alipay_public_key_string=open(os.path.join(os.path.dirname(__file__), "keys/alipay_public_key.pem")).read(),
        sign_type="RSA2",  # RSA 或者 RSA2
        debug=True  # 默认False
    )
    # 调用支付接口
    order_string = alipay_client.api_alipay_trade_wap_pay(
        out_trade_no=order_id,  # 订单编号
        total_amount=str(order.amount / 100.0),  # 订单总金额
        subject=u"爱家租房 %s" % order_id,
        return_url="http://127.0.0.1:5000/paycompleted.html",
        notify_url=None  # 可选, 不填则使用默认notify url
    )

    # 构建支付宝的支付链接地址
    pay_url = constants.ALIPAY_URL_PREFIX + order_string

    # 返回应答
    return jsonify(errno=RET.OK, errmsg='OK', data={'pay_url': pay_url})


@api.route('/order/payment', methods=['PUT'])
def save_order_payment_result():
    """保存订单支付结果"""
    # 获取参数
    alipay_dict = request.form.to_dict()
    print(alipay_dict)
    # 对支付宝的数据进行分离，提取出sign
    signature = alipay_dict.pop('sign')

    # 创建支付宝sdk的工具对象
    alipay_client = AliPay(
        appid="2021000121699419",
        app_notify_url=None,  # 默认回调url
        app_private_key_string=open(os.path.join(os.path.dirname(__file__), "keys/app_private_key.pem")).read(),
        # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
        alipay_public_key_string=open(os.path.join(os.path.dirname(__file__), "keys/alipay_public_key.pem")).read(),
        sign_type="RSA2",  # RSA 或者 RSA2
        debug=True  # 默认False
    )

    # 校验这个重定向是否是alipay重定向过来的
    result = alipay_client.verify(alipay_dict, signature)
    if result:
        # 保存支付结果
        order_id = alipay_dict.get('out_trade_no')
        trade_no = alipay_dict.get('trade_no')  # 支付宝的交易号
        try:
            Order.query.filter(Order.id == order_id).update({'status': 'WAIT_COMMENT', 'trade_no': trade_no})
            # Order.query.filter(Order.id == order_id).update({'status': 'WAIT_COMMENT'})
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg='数据库异常')

    return jsonify(errno=RET.OK, errmsg='OK')