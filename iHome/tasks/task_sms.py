from celery import Celery
from iHome.libs.yuntongxun.sms import CCP

# 创建celery对象
celery_app = Celery('tasks_sms', broker='redis://localhost:6379/10')


# 定义任务函数
@celery_app.task
def send_sms(to, datas, temp_id):
    """发送短信异步任务"""
    ccp = CCP()
    ccp.sendTemplateSMS(to, datas, temp_id)
