import random
from scrapy.downloadermiddlewares.useragent import UserAgentMiddleware

class RotateUserAgentMiddleware(UserAgentMiddleware):
    def __init__(self, user_agent_list):
        self.user_agent_list = user_agent_list
        super().__init__()

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.getlist("USER_AGENT_LIST"))

    def process_request(self, request, spider):
        ua = random.choice(self.user_agent_list)
        request.headers[b"User-Agent"] = ua.encode()
        return None