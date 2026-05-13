#!/usr/bin/env python
# -*- coding:utf-8 -*-
import argparse
import os
import re
import sys
import urllib
import json
import socket
import urllib.request
import urllib.parse
import urllib.error
# 设置超时
import time

timeout = 5
socket.setdefaulttimeout(timeout)


class Crawler:
    # 睡眠时长
    __time_sleep = 0.1
    __amount = 0
    __start_amount = 0
    __counter = 0
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:23.0) Gecko/20100101 Firefox/23.0', 'Cookie': ''}
    __per_page = 30

    # 获取图片url内容等
    # t 下载图片时间间隔
    def __init__(self, t=0.1):
        self.time_sleep = t

    # 获取后缀名
    @staticmethod
    def get_suffix(name):
        m = re.search(r'\.[^\.]*$', name)
        if m and m.group(0) and len(m.group(0)) <= 5:
            return m.group(0)
        else:
            return '.jpeg'

    @staticmethod
    def handle_baidu_cookie(original_cookie, cookies):
        """
        :param string original_cookie:
        :param list cookies:
        :return string:
        """
        if not cookies:
            return original_cookie
        result = original_cookie
        for cookie in cookies:
            result += cookie.split(';')[0] + ';'
        result.rstrip(';')
        return result

    # 保存图片
    def save_image(self, rsp_data, word):
        output_dir = './output/' + word
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        # 判断名字是否重复，获取图片长度
        self.__counter = len(os.listdir(output_dir)) + 1
        for image_info in rsp_data['data']:
            try:
                if 'replaceUrl' not in image_info or len(image_info['replaceUrl']) < 1:
                    continue
                obj_url = image_info['replaceUrl'][0]['ObjUrl']

                # 过滤抖音链接
                if 'douyinpic.com' in obj_url or 'douyin.com' in obj_url:
                    continue

                # 直接使用原图URL，不走百度下载接口
                time.sleep(self.time_sleep)
                suffix = self.get_suffix(obj_url)

                # 使用更完整的请求头
                req = urllib.request.Request(obj_url)
                req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                req.add_header('Referer', 'https://image.baidu.com/')
                req.add_header('Accept', 'image/webp,image/apng,image/*,*/*;q=0.8')
                req.add_header('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8')

                # 保存图片
                filepath = './output/%s/%s' % (word, str(self.__counter) + str(suffix))

                response = urllib.request.urlopen(req, timeout=10)
                with open(filepath, 'wb') as f:
                    f.write(response.read())

                if os.path.getsize(filepath) < 5000:  # 小于5KB认为是无效文件
                    print("下载到了空文件，跳过!")
                    os.unlink(filepath)
                    continue
            except urllib.error.HTTPError as urllib_err:
                print(f"HTTP错误 {urllib_err.code}: {obj_url}")
                continue
            except socket.timeout:
                print("下载超时，跳过")
                continue
            except Exception as err:
                print(f"下载失败: {err}")
                continue
            else:
                print("成功下载第" + str(self.__counter) + "张图片")
                self.__counter += 1
        return

    # 开始获取
    def get_images(self, word):
        search = urllib.parse.quote(word)
        # pn int 图片数
        pn = self.__start_amount
        while pn < self.__amount:
            url = 'https://image.baidu.com/search/acjson?tn=resultjson_com&ipn=rj&ct=201326592&is=&fp=result&queryWord=%s&cl=2&lm=-1&ie=utf-8&oe=utf-8&adpicid=&st=-1&z=&ic=&hd=&latest=&copyright=&word=%s&s=&se=&tab=&width=&height=&face=0&istype=2&qc=&nc=1&fr=&expermode=&force=&pn=%s&rn=%d&gsm=1e&1594447993172=' % (search, search, str(pn), self.__per_page)
            # 设置header防403
            try:
                time.sleep(self.time_sleep)
                req = urllib.request.Request(url=url, headers=self.headers)
                page = urllib.request.urlopen(req)
                self.headers['Cookie'] = self.handle_baidu_cookie(self.headers['Cookie'], page.info().get_all('Set-Cookie'))
                rsp = page.read()
                page.close()
            except UnicodeDecodeError as e:
                print(e)
                print('-----UnicodeDecodeErrorurl:', url)
            except urllib.error.URLError as e:
                print(e)
                print("-----urlErrorurl:", url)
            except socket.timeout as e:
                print(e)
                print("-----socket timout:", url)
            else:
                # 解析json
                rsp_data = json.loads(rsp, strict=False)
                if 'data' not in rsp_data:
                    print("触发了反爬机制，自动重试！")
                else:
                    self.save_image(rsp_data, word)
                    # 读取下一页
                    print("下载下一页")
                    pn += self.__per_page
        print("下载任务结束")
        return

    def start(self, word, total_page=1, start_page=1, per_page=30):
        """
        爬虫入口
        :param word: 抓取的关键词
        :param total_page: 需要抓取数据页数 总抓取图片数量为 页数 x per_page
        :param start_page:起始页码
        :param per_page: 每页数量
        :return:
        """
        self.__per_page = per_page
        self.__start_amount = (start_page - 1) * self.__per_page
        self.__amount = total_page * self.__per_page + self.__start_amount
        self.get_images(word)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser()
        parser.add_argument("-w", "--word", type=str, help="抓取关键词", required=True)
        parser.add_argument("-tp", "--total_page", type=int, help="需要抓取的总页数", required=True)
        parser.add_argument("-sp", "--start_page", type=int, help="起始页数", required=True)
        parser.add_argument("-pp", "--per_page", type=int, help="每页大小", choices=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100], default=30, nargs='?')
        parser.add_argument("-d", "--delay", type=float, help="抓取延时（间隔）", default=0.05)
        args = parser.parse_args()

        crawler = Crawler(args.delay)
        crawler.start(args.word, args.total_page, args.start_page, args.per_page) 
    else:
        # 如果不指定参数，那么程序会按照下面进行执行
        crawler = Crawler(0.05)  # 抓取延迟为 0.05

        crawler.start('猫咪', 10, 2, 30)  
