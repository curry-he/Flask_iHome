from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import redis
from flask_session import Session
from flask_wtf import CSRFProtect
from config import config_map
import logging
from logging.handlers import RotatingFileHandler

# 数据库
db = SQLAlchemy()

# 创建redis连接对象
redis_restore = None

# 设置日志的记录等级
logging.basicConfig(level=logging.DEBUG)  # 调试debug级
# 创建日志记录器，指明日志保存的路径，每个日志文件的最大大小，保存的日志文件个数上限
file_log_handler = RotatingFileHandler("logs/log", maxBytes=1024 * 1024 * 100, backupCount=10)
# 创建日志记录的格式 日志等级 输入日志信息的文件名 行数 日志信息
formatter = logging.Formatter('%(levelname)s %(filename)s:%(lineno)d %(message)s')
# 为刚创建的日志记录器设置日志记录格式
file_log_handler.setFormatter(formatter)
# 为全局的日志工具对象（flask app使用的）添加日志记录器
logging.getLogger().addHandler(file_log_handler)


# 工厂模式
def create_app(config_name):
    app = Flask(__name__)
    config_class = config_map.get(config_name)
    app.config.from_object(config_class)
    # 初始化数据库
    db.init_app(app)
    # 初始化redis
    global redis_restore
    redis_restore = redis.StrictRedis(host=config_class.REDIS_HOST, port=config_class.REDIS_PORT)
    # 利用flask_session,将session保存到redis中
    session = Session(app)
    # 为flask补充csrf防护
    CSRFProtect(app)
    # 注册蓝图
    from iHome import api_1_0
    app.register_blueprint(api_1_0.api, url_prefix='/api/v1.0')
    return app
