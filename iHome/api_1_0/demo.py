from . import api
from iHome import db
from flask import current_app
import logging


@api.route('/index')
def index():
    current_app.logger.error('error')
    current_app.logger.warn('warn')
    current_app.logger.info('info')
    current_app.logger.debug('debug')
    return 'index page'
