import requests
from urllib.parse import urlencode
from requests.exceptions import RequestException
import json
from bs4 import BeautifulSoup
import re
import pymongo
import os
from hashlib import md5
from multiprocessing import Pool

#链接mongodb
from config import *

#声明客户端链接
#开启多进程时,会多次请求mongodb,所以设置connect=False,避免警告
client=pymongo.MongoClient(MONGO_URL,connect=False)
db=client[MONGO_DB]   #声明库名称

def get_page_index(offset,keyword):
    #从网页获取里面的参数
    data={
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab': 1
    }
    #urlencode将字典参数转化为url请求参数
    url='https://www.toutiao.com/search_content/?'+urlencode(data)
    try:
        response=requests.get(url)
        if response.status_code==200:
            return response.text
        return None
    except RequestException:
        print("请求网页出错")
        return None

#获取网页后开始解析
def parse_page_index(html):
    data=json.loads(html) #将json字符串转换成json对象
    if data and 'data' in data.keys(): #判断是否在data的键里
        for item in data.get('data'):
            yield item.get('article_url')

#获取详情页
def get_page_detail(url):
    try:
        response=requests.get(url)
        if response.status_code==200:
            return response.text
        return None
    except RequestException:
        print("请求详情页出错")
        return None


#解析详情页
def parse_page_detail(html,url):
    soup=BeautifulSoup(html,'lxml')
    title=soup.select('title')[0].get_text() #get_text()获取文本
    print(title)
    image_pattern=re.compile('.*?quot;//(.*?)&quot;')
    results=re.findall(image_pattern,html)
    for image in results:
        download_image("https://"+image)
    return {
                'title':title,
                'image':results,
                'url':url
        }

#将数据保存到数据库中
def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):   #将数据插入到表中
        print('存储到MongoDB成功',result)
        return True
    return False

#测试请求图片是否出错下来并保存
def download_image(url):
    print('正在下载',url)
    try:
        response=requests.get(url)
        if response.status_code==200:
            save_image(response.content) #保存图片是用content,这样保存下来是二进制
            return response.text
        return None
    except RequestException:
        print('请求图片出错',url)
        return None


#将图片保存到本地
def save_image(content):
    #os.path.abspath('.');os.getcwd()---获取当前路径
    #os.path.abspath('..')---获取上一级路径
    #os.path.abspath('./')---下一级路径
    #路径/文件名.后缀名,这里用md5保存方式(若文件内容相同保存就不会重复)
    file_path='{0}/{1}.{2}'.format(os.path.abspath('./photo_2'),md5(content).hexdigest(),'jpg')
    if not os.path.exists(file_path):  #如果文件不存在
        with open(file_path,'wb') as f:
            f.write(content)
            f.close()


def main(offset):
    html=get_page_index(offset,KEYWORD)
    for url in parse_page_index(html):
        html=get_page_detail(url)
        #print(html)
        if html:
            result=parse_page_detail(html,url)
            #print(result)
            if result !=None:
                save_to_mongo(result)
            else:
                print("空数据无法存储")

if __name__ == '__main__':
    group = [x * 20 for x in range(GROUP_START,GROUP_END+1)]
    pool=Pool()
    pool.map(main,group)
