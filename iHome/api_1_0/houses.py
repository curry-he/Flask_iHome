import json

from flask import g, request, jsonify, current_app
from . import api
from .. import db, constants, redis_restore
from ..models import User, Area, House, Facility, HouseImage
from ..utils.commons import login_required
from ..utils.image_storage import storage
from ..utils.response_code import RET


@api.route('/areas', methods=['GET'])
def get_area_info():
    """获取城区信息"""
    # 尝试从redis中读取数据
    try:
        resp_json = redis_restore.get("area_info")
    except Exception as e:
        current_app.loggeer.error(e)
    else:
        if resp_json:
            return resp_json, 200, {"Content-Type": "application/json", "charset": "utf-8"}

    # 获取城区信息
    try:
        area_li = Area.query.all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    # 将对象列表转换为字典列表
    area_dict_li = []
    for area in area_li:
        area_dict_li.append(area.to_dict())

    # 将数据保存到redis中
    # 将数据转换为json字符串
    resp_dict = dict(errno=RET.OK, errmsg="OK", data=area_dict_li)
    resp_json = json.dumps(resp_dict)

    try:
        redis_restore.setex("area_info", constants.AREA_INFO_REDIS_CACHE_EXPIRES, resp_json)
    except Exception as e:
        current_app.logger.error(e)
    # 返回应答
    return resp_json, 200, {"ContentType": "application/json"}


@api.route("/houses", methods=["GET"])
@login_required
def get_passcard():
    """判断用户是否进行过实名认证，是否可以发布新房源"""
    user_id = g.user_id
    try:
        user = User.query.filter_by(id=user_id).first()
        real_name = user.real_name
        id_card = user.id_card
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="mysql数据库错误")
    if real_name and id_card:
        return jsonify(errno=RET.OK, errmsg="OK")


@api.route('/houses/info', methods=['POST'])
@login_required
def save_house_info():
    """保存房源信息"""
    # 获取参数
    house_dict = request.get_json()
    title = house_dict.get('title')  # 房屋标题
    price = house_dict.get('price')  # 房屋单价
    area_id = house_dict.get('area_id')  # 归属地的区域编号
    address = house_dict.get('address')  # 地址
    room_count = house_dict.get('room_count')  # 房间数目
    acreage = house_dict.get('acreage')  # 房屋面积
    unit = house_dict.get('unit')  # 房屋单元，如几室几厅
    capacity = house_dict.get('capacity')  # 房屋容纳的人数
    beds = house_dict.get('beds')  # 房屋床铺的配置
    deposit = house_dict.get('deposit')  # 房屋押金
    min_days = house_dict.get('min_days')  # 最少入住天数
    max_days = house_dict.get('max_days')  # 最多入住天数  - 可选项

    # 校验参数
    if not all([title, price, area_id, address, room_count, acreage, unit, capacity, beds, deposit, min_days]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不完整")
    # 保存房屋的基本信息数据
    try:
        price = int(float(price) * 100)  # 单位为分
        deposit = int(float(deposit) * 100)  # 单位为分
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    # 判断城区id是否存在
    try:
        area = Area.query.get(area_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")
    if area is None:
        return jsonify(errno=RET.NODATA, errmsg="城区信息错误")

    # 保存房屋信息
    house = House(
        user_id=g.user_id,
        area_id=area_id,
        title=title,
        price=price,
        address=address,
        room_count=room_count,
        acreage=acreage,
        unit=unit,
        capacity=capacity,
        beds=beds,
        deposit=deposit,
        min_days=min_days,
        max_days=max_days

    )
    db.session.add(house)

    # 处理房屋设施信息
    facility_ids = house_dict.get('facility')
    if facility_ids:
        try:
            # 查询出所有的设施信息
            facilities = Facility.query.filter(Facility.id.in_(facility_ids)).all()
            # 保存设施信息
            house.facilities = facilities
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据库异常")

        if facilities:
            house.facilities = facilities

    try:
        db.session.add(house)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据异常")

    # 返回应答，房屋的编号
    return jsonify(errno=RET.OK, errmsg="OK", data={"house_id": house.id})


@api.route('/houses/image', methods=['POST'])
@login_required
def save_house_image():
    """保存房屋的图片"""
    # 获取参数
    house_image = request.files.get('house_image').read()
    house_id = request.form.get('house_id')
    # 校验参数
    if not all([house_image, house_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不完整")
    # 判断房屋编号是否存在
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")
    if house is None:
        return jsonify(errno=RET.NODATA, errmsg="房屋不存在")
    # 保存房屋图片到七牛云
    try:
        key = storage(house_image)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传房屋图片失败")
    # 保存房屋图片信息
    house_image = HouseImage(house_id=house_id, url=key)
    db.session.add(house_image)

    # 处理房屋的主图片
    if not house.index_image_url:
        house.index_image_url = key
        db.session.add(house)

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存房屋图片信息失败")
    # 拼接图片的完整路径
    image_url = constants.QINIU_URL_DOMAIN + key
    # 返回应答
    return jsonify(errno=RET.OK, errmsg="OK", data={"image_url": image_url})


@api.route("/user/houses", methods=["GET"])
@login_required
def get_user_house():
    """获取信息页用户发布过的房源信息"""
    user_id = g.user_id

    try:
        # 这样可以同时判断用户id是否存在
        user = User.query.get(user_id)
        houses = user.houses
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="获取数据失败")
    houses_list = []
    if houses:
        for house in houses:
            houses_list.append(house.to_basic_dict())
    return jsonify(errno=RET.OK, errmsg="OK", data={"houses": houses_list})








