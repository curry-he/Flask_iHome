from werkzeug.routing import BaseConverter


class RegexConverter(BaseConverter):
    """自定义正则转换器"""
    def __init__(self, url_map, regex):
        super().__init__(url_map)
        self.regex = regex

