import queue

class ProxyPool:
    def __init__(self, proxies):
        self.proxy_queue = queue.Queue()
        for proxy in proxies:
            self.proxy_queue.put(proxy)

    def get_proxy(self):
        """获取一个可用代理"""
        if not self.proxy_queue.empty():
            return self.proxy_queue.get()
        else:
            print("无可用代理")
            return None

    def put_proxy(self, proxy):
        """将代理重新放回队列"""
        self.proxy_queue.put(proxy)

    def remove_proxy(self, proxy):
        """移除不可用代理"""
        with self.proxy_queue.mutex:
            self.proxy_queue.queue = queue.deque([p for p in self.proxy_queue.queue if p != proxy])

        # 初始化代理池


