from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import redis
from flask_session import Session
from flask_wtf import CSRFProtect
app = Flask(__name__)


class Config(object):
    DEBUG = True
    SECRET_KEY = 'hhz19991026'

    # 数据库
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:mysql@127.0.0.1:3306/iHome'
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    # redis
    REDIS_HOST = '127.0.0.1'
    REDIS_PORT = 6379

    # session
    SESSION_TYPE = 'redis'
    SESSION_REDIS = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)
    SESSION_USE_SIGNER = True
    PERMANENT_SESSION_LIFETIME = 60*60*24


# 使用配置
app.config.from_object(Config)

# 数据库
db = SQLAlchemy(app)

# 创建redis连接对象
redis_restore = redis.StrictRedis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)

# 利用flask_session,将session保存到redis中
session = Session(app)

# 为flask补充csrf防护
CSRFProtect(app)


@app.route('/index')
def index():
    return 'index page'


if __name__ == '__main__':
    app.run()
    with app.app_context():
        db.drop_all()
        db.create_all()
