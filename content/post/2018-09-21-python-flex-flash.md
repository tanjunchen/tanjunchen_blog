---
layout:     post
title:      "Python 抓取 Flex (Flash) 技术数据传输"
subtitle:   ""
description: ""
author: "陈谭军"
date: 2018-09-21
published: true
tags:
    - python
categories:
    - TECHNOLOGY
showtoc: true
---

最近发现了一个网站中国农业信息网，他有个数据请求是以 amf 的方式请求数据，以前没有遇到过。所以网上了解一下，找到了python 中的第三方包 pyamf，能够成功获取到展示数据。

![](/images/2018-09-21-python-flex-flash/1.jpeg)

其实，用 flash 这种方式传输数据的网站已经很少了，基本上都怀抱 H5。所以，我们来了解下怎么获取基于 Flex 与 Flash 技术的数据抓取。工具 Pyamf 第三方包，Charles 抓包软件(Fiddler 不能抓取到我们需要的包) 分析是如何构造 API 请求的。 

![](/images/2018-09-21-python-flex-flash/2.jpeg)

我们点击时发现其中的数据请求方式与我们常见的网站不太一样，这是一种 amf 请求的方式。  
【百度百科】AMF(Action Message Format)是 Flash 与服务端通信的一种常见的二进制编码模式，其传输效率高，可以在HTTP 层面上传输。现在很多 Flash WebGame 都采用这样的消息格式。

![](/images/2018-09-21-python-flex-flash/3.jpeg)
通过 pyamf 的 api 与抓包的请求参数我们需要构造一个请求去请求获取数据。首先，我们看到包含了 body 的整个请求体在pyamf 是用 messaging 类来创建的，构造 flex.messaging.messages.RemotingMessage 消息：
```python
msg = messaging.RemotingMessage(messageId=str(uuid.uuid1()).upper(),
                                clientId=str(uuid.uuid1()).upper(),
                                operation='getHqSearchData',
                                destination='reportStatService',
                                timeToLive=0,
                                timestamp=0)
```
然后，注册实体类。
```python
class HqPara:
    def __init__(self):
        self.marketInfo =None
        self.breedInfoDl =None
        self.breedInfo =None
        self.province =None
# 注册自定义的Body参数类型，这样数据类型com.itown.kas.pfsc.report.po.HqPara就会在后面被一并发给服务端
# 否则服务端就可能返回参数不是预期的异常Client.Message.Deserialize.InvalidType
pyamf.register_class(HqPara, alias='com.itown.kas.pfsc.report.po.HqPara')
```
其次，注册 body，填入 body 需要的参数字段。第一个是查询参数，第二个是页数，第三个是控制每页显示的数量（默认每页只显示15条）但爬取的时候可以一下子设置成全部的数量构造请求数据。
```python
def get_request_data(page_num, total):
    msg.body = [HqPara(), str(page_num), str(total)]
    msg.headers['DSEndpoint'] =
None
    msg.headers['DSId'] =
str(uuid.uuid1()).upper()
    # 按AMF协议编码数据
    req = remoting.Request('null', body=(msg,))
    env = remoting.Envelope(amfVersion=pyamf.AMF3)
    env.bodies = [('/1', req)]
    data =
bytes(remoting.encode(env).read())
    return data
```
最后，定义请求的返回数据格式，获取我们需要的数据。

```python
# 返回一个请求的数据格式
def get_response(data):
    url =
'http://jgsb.agri.cn/messagebroker/amf'
    res = requests.post(url, data, headers={'Content-Type':
'application/x-amf'})
    return res.content
```
最终抓下来的数据如下：
![](/images/2018-09-21-python-flex-flash/5.jpeg)

数据返回格式 Charles 抓包如下：
![](/images/2018-09-21-python-flex-flash/4.jpeg)

难点：如何获取与构造 API 请求参，该请求方式较老，这方面的文档资料很少。
