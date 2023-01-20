from datetime import datetime
import json

from flask import g, request, jsonify, current_app, session
from . import api
from .. import db, constants, redis_restore
from ..models import User, Area, House, Facility, HouseImage, Order
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
    return resp_json, 200, {"Content-Type": "application/json"}


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


@api.route("/houses/index")
def get_house_index():
    """主页幻灯片获取房源基本信息，不需要登录也可以访问"""
    # 首先从缓存中获取房源数据，如果没有，再去数据库中查询，然后保存至缓存中
    try:
        ret = redis_restore.get("home_page_data")
    except Exception as e:
        current_app.logger.error(e)
        ret = None
    if ret:
        ret = ret.decode("utf-8")
        current_app.logger.info("hit house index info redis")
        return '{"errno":"0", "errmsg":"OK", "data":%s}' % ret, 200, {"Content-Type": "application/json"}
    else:
        try:
            # 查询数据库，返回订单量最大的最多5条数据
            houses = House.query.order_by(House.order_count.desc()).limit(constants.HOME_PAGE_MAX_HOUSES)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="获取数据失败")
        if not houses:
            return jsonify(errno=RET.NODATA, errmsg="查询无数据")

        houses_list = []
        for house in houses:
            # 如果房源主图还没有设置，那么就跳过，不予展示
            if not house.index_image_url:
                continue
            houses_list.append(house.to_basic_dict())

        print(houses_list)
        json_houses = json.dumps(houses_list)
        try:
            redis_restore.setex("home_page_data", constants.INDEX_PAGE_DATA_REDIS_EXPIRES, json_houses)
        except Exception as e:
            current_app.logger.error(e)
        return '{"errno":"0", "errmsg":"OK", "data":%s}' % json_houses, 200, {"Content-Type": "application/json"}


@api.route("/houses/<int:house_id>", methods=["GET"])
def get_house_detail(house_id):
    """显示房源详细信息"""
    # 如果查看的是房主本人，那么不予显示预定按钮。将user_id与房主id查询结果发给前端，让前端判断
    user_id = session.get("user_id", "-1")

    if not house_id:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    try:
        ret = redis_restore.get("house_info_%s" % house_id)
    except Exception as e:
        current_app.logger.error(e)
        ret = None
    if ret:
        current_app.logger.info("hit house info redis")
        ret = ret.decode("utf-8")
        return '{"errno":"0", "errmsg":"OK", "data":{"user_id":%s, "house":%s}}' % (user_id, ret), 200, {
            "Content-Type": "application/json"}

    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

    if not house:
        return jsonify(errno=RET.NODATA, errmsg="房源不存在")

    try:
        house_data = house.to_full_dict()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

    json_house = json.dumps(house_data)
    try:
        redis_restore.setex("house_info_%s" % house_id, constants.DETAIL_PAGE_DATA_REDIS_EXPIRES, json_house)
    except Exception as e:
        current_app.logger.error(e)
    resp = '{"errno":"0", "errmsg":"OK", "data":{"user_id":%s, "house":%s}}' % (user_id, json_house), 200, {
        "Content-Type": "application/json"}
    return resp


@api.route("/houses/search")
def get_house_list():
    start_date = request.args.get('sd', "")  # 开始时间
    end_date = request.args.get('ed', "")  # 结束时间
    area_id = request.args.get('aid', "")  # 区域编号
    sort_key = request.args.get('sk', 'new')  # 排序关键字
    page = request.args.get('p', "")  # 页数

    # 校验参数
    # 日期格式校验
    try:
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
        if start_date and end_date:
            assert start_date <= end_date
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="日期参数错误")

    # 区域编号校验
    if area_id:
        try:
            area = Area.query.get(area_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据库异常")
        if not area:
            return jsonify(errno=RET.NODATA, errmsg="区域不存在")

    # 页数校验
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    # 从redis中获取缓存数据
    redis_key = "house_%s_%s_%s_%s" % (start_date, end_date, area_id, sort_key)
    try:
        resp_json = redis_restore.hget(redis_key, page)
    except Exception as e:
        current_app.logger.error(e)
    if resp_json:
        current_app.logger.info("hit house list redis")
        return '{"errno":"0", "errmsg":"OK", "data":%s}' % resp_json, 200, {"Content-Type": "application/json"}

    # 过滤条件参数列表
    filter_params = []

    # 填充过滤参数
    # 时间条件
    conflict_orders = None

    try:
        if start_date and end_date:
            # 查询冲突的订单
            conflict_orders = Order.query.filter(Order.begin_date <= end_date, Order.end_date >= start_date).all()
        elif start_date:
            conflict_orders = Order.query.filter(Order.end_date >= start_date).all()
        elif end_date:
            conflict_orders = Order.query.filter(Order.begin_date <= end_date).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    if conflict_orders:
        # 取出所有冲突订单中的房屋编号
        conflict_house_ids = [order.house_id for order in conflict_orders]
        if conflict_house_ids:
            filter_params.append(House.id.notin_(conflict_house_ids))

    # 区域条件
    if area_id:
        try:
            filter_params.append(House.area_id == area_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="区域条件有误")

    # 查询数据库
    # 补充排序条件
    if sort_key == "booking":
        house_query = House.query.filter(*filter_params).order_by(House.order_count.desc())
    elif sort_key == "price-inc":
        house_query = House.query.filter(*filter_params).order_by(House.price.asc())
    elif sort_key == "price-des":
        house_query = House.query.filter(*filter_params).order_by(House.price.desc())
    else:
        house_query = House.query.filter(*filter_params).order_by(House.create_time.desc())

    try:
        # 处理分页
        page_obj = house_query.paginate(page=page, per_page=constants.HOUSE_LIST_PAGE_CAPACITY, error_out=False)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    # 获取分页数据
    page_li = page_obj.items
    houses = []
    for house in page_li:
        houses.append(house.to_basic_dict())

    # 获取总页数
    total_page = page_obj.pages

    resp_dict = dict(errno=RET.OK, errmsg="OK", data={"total_page": total_page, "houses": houses, "current_page": page})
    resp_json = json.dumps(resp_dict)

    if page <= total_page:
        # 设置缓存
        redis_key = "house_%s_%s_%s_%s" % (start_date, end_date, area_id, sort_key)
        try:
            # redis_restore.hset(redis_key, page, resp_json)
            # redis_restore.expire(redis_key, constants.HOUSES_LIST_PAGE_REDIS_CACHE_EXPIRES)
            # 使用pipeline管道技术，一次性执行多个语句
            pipeline = redis_restore.pipeline()
            pipeline.multi()
            pipeline.hset(redis_key, page, resp_json)
            pipeline.expire(redis_key, constants.HOUSES_LIST_PAGE_REDIS_CACHE_EXPIRES)
            pipeline.execute()
        except Exception as e:
            current_app.logger.error(e)

    # 返回数据
    return resp_json, 200, {"Content-Type": "application/json"}
