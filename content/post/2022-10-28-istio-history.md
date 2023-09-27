---
layout:     post
title:      "说道说道 Istio，重新扬帆加入 CNCF"
subtitle:   "Istio 发展历史与简介"
description: "2022年9月底，CNCF TOC（技术监督委员会，Technical Oversight Committee ）已经投票接受了 Istio 作为 CNCF 的孵化项目。Istio 扬帆加入 CNCF，具体细节可参见 Istio 扬帆加入 CNCF。"
author: "陈谭军"
date: 2022-10-28
published: true
tags:
    - istio
    - kubernetes
    - microservice
categories:
    - TECHNOLOGY
showtoc: true
---

# 序言

2022年9月底，CNCF TOC（技术监督委员会，Technical Oversight Committee ）已经投票接受了 Istio 作为 CNCF 的孵化项目。Istio 扬帆加入 CNCF，具体细节可参见 Istio 扬帆加入 CNCF。

# 介绍

Istio 是 2017 年 5 月 24 日开源的。至今(2022-10月)为止，Istio 已经开源5年多了，让我们一起来回顾一下 Istio 五年来的发展与探讨 Istio 服务网格的内功。主要网站是：[github](https://github.com/istio/istio)，[website](https://istio.io/)，架构如下所示：
![](/images/2022-10-28-istio-history/1.png)

1. 主要功能特性：Traffic management、Observability、Security、Extension 等主要部分。
1. 控制平面：服务发现、配置管理、证书管理。
1. 数据平面：负载均衡、HTTP/2、 gRPC 流量转发、TLS熔断、限流、健康检查、故障注入、Log、Metrics、Trace等主要流量治理功能。
1. 主要厂商：许多公司构建平台和服务来安装、管理和实施 Istio。如 Google Cloud、HuaWei、Tetrate 等28家，具体可参见[providers](https://istio.io/latest/about/ecosystem/#providers)。

# 开源历史

2017 年是 Kubernetes 结束容器编排之战的一年，Google 为了巩固在云原生领域的优势，弥补 Kubernetes 在服务间流量管理方面的劣势，趁势开源了 Istio。下面是截止目前为止(2022-10)，Istio 主要的版本发布记录，数据来源于 [istio 版本](https://istio.io/latest/news/)。

|日期|版本|主要功能|备注|
|---|---|---|---|
| 2017-05-24 | 0.1 | 发布开源，确定 envoy 作为 sidecar 代理| |
| 2017-10-10 | 0.2 | 支持多运行时环境，如虚拟机| |
| 2018-06-01 | 0.8 | 重构 API| |
| 2018-07-31 | 1.0 | 达到生产环境要求，Istio 团队大规模重组|重要里程碑 |
| 2019-03-19 | 1.1 | 达到企业级就绪，支持多集群 | |
| 2020-03-05 | 1.5 | 控制面 istiod 、支持 WASM 、增强 istioctl 易用性 | 重要里程碑 |
| 2020-11-19 | 1.8 | Istio Operator 安装与升级 istio、增强多集群功能、增强对虚拟机的支持、istioctl 易用性、正式废弃 Mixer 等 | 重要里程碑 |
| 2021-05-18 | 1.10 | 选择性服务发现、Istio Operator金丝雀升级、istio.io 网站美化、Sidecar 网络优化等 |  |
| 2022-02-11 | 1.13 | 新增 ProxyConfig CRD、Telemetry CRD 优化、其他等 |  |
| 2022-06-01 | 1.14 | 支持 Spire 运行时、支持 SNI 自动侦测、Telemetry 增强等 |  |
| 2022-08-31 | 1.15 | 支持 arm64、修复 istioctl 已知 bug、istio 进入 CNCF SandBox 进度同步等。 | 重要里程碑 |
|   ......   |  | 期待(Ambient Mesh、ebpf 等) |  |

2019 年 3 月 Istio 1.1 发布，而这距离 1.0 发布已经过去了近 9 个月，这已经远远超出一个开源项目的平均发布周期。此后 Istio 开始以每个季度一个版本的固定发版节奏，并在 2019 年成为了 GitHub 增长最快的十大项目中排名第 4 名！

## 里程碑

至今为止(2022-10)，Istio 开源社区的数据如下所示：
* 来自 15 家公司的 85 名主要维护人员
* 个人贡献者(Contributor)：>8.8k
* 拉取请求(Pull Request)：>25k
* Issues：>20k
* 版本(Release)：>260
* GitHub 星星(Stars)：>31.6k
* Slack 成员：>8.5k

代码贡献趋势：
![](/images/2022-10-28-istio-history/2.png)

# 学习 Istio

## 主要目录
```bash
chentanjun@tanjunchenMac~/opensource cloc istio
  4069 text files.
  3832 unique files.
  844 files ignored.

1 error:
Line count, exceeded timeout:  istio/pilot/pkg/networking/core/v1alpha3/gateway_simulation_test.go

github.com/AlDanial/cloc v 1.90  T=9.61 s (337.2 files/s, 59012.2 lines/s)
--------------------------------------------------------------------------------
Language                      files          blank        comment           code
--------------------------------------------------------------------------------
Go                             1654          36854          52558         317546
YAML                           1282           1304           3379         100735
JSON                             57            131              0          27819
CSS                               4              7             22           7368
Markdown                         75           1324              0           3596
Bourne Shell                     61            680           1405           2979
JavaScript                        5            605            229           1816
make                             18            288            405            943
Python                            6            179            206            568
Protocol Buffers                  5            338            555            530
SVG                               6              0             24            453
Dockerfile                       31            124            221            346
XML                               9             18             22            228
Java                              7             41            114            210
HTML                              3             21             58            182
Ruby                              2             33             45            128
Bourne Again Shell                4             30             75            105
INI                               1              4              0             42
Bazel                             2              9              1             41
Gradle                            4              8              0             41
C++                               1              7             14             17
C/C++ Header                      1              6             13             17
SQL                               1              2              0             11
diff                              1              0              8             10
--------------------------------------------------------------------------------
SUM:                           3240          42013          59354         465731
--------------------------------------------------------------------------------
```
以 istio tag 1.15.1 bf836f0be536b0adcef68f93c405994769e767cb commit 为例，截止目前为止，Istio 代码量达到 46 万+。
![](/images/2022-10-28-istio-history/3.png)
config：配置中心
![](/images/2022-10-28-istio-history/4.png)
serviceregistry：注册中心
![](/images/2022-10-28-istio-history/5.png)
1. model：istio 模型抽象层
1. networking：XDS 计算层
1. bootstrap：Pilot Server
1. xds：处理 xds 请求

## Istio CRD

![](/images/2022-10-28-istio-history/6.png)

## 重点模块

XDS 协议层参见 [go-control-plane](https://github.com/envoyproxy/go-control-plane)  

# 调试与答疑

## 控制平面

1. 获取 Pilot 中的 CRD 信息，curl -s 127.1:15014/debug/configz
1. 获取 Pilot 内部状态的指标，curl -s 127.1:15014/metrics

具体可参见：https://istio.io/latest/docs/ops/diagnostic-tools/proxy-cmd/ 、https://istio.io/latest/docs/ops/diagnostic-tools/

## 数据平面

1. 获取 Envoy 接收到的 configdump，curl -s 127.1:15000/config_dump
1. 获取 Envoy 接收到的实例状态信息，curl -s 127.1:15000/clusters ，数据有请求成功数，失败数，超时数，连接信息，健康状态等
1. 更改数据平面的日志级别，curl -s -X POST 127.1:15000/logging?level=trace

具体可参考：https://istio.io/latest/docs/ops/diagnostic-tools/proxy-cmd/、https://istio.io/latest/docs/ops/diagnostic-tools/

# 总结

主要介绍了 istio 的发展、开源历史、现状、以及主要的代码目录、调试技巧等内容。

# 参考资料

1. https://istio.io/
1. https://mp.weixin.qq.com/s/Xb4ekvMVIwUITruF4o-9kg
1. https://istio.io/latest/news/
