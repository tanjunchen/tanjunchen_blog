---
layout:     post
title:      "istio-system 命名空间下的 envoyfilter 有什么作用？"
subtitle:   ""
description: "Istio 在自己的定制版本 Envoy 中，加入了 stats-filter 插件，用于计算 Istio 指标。可参见 https://github.com/istio/proxy/blob/release-1.14/extensions/stats/plugin.cc"
author: "陈谭军"
date: 2022-11-01
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

Istio 在自己的定制版本 Envoy 中，加入了 stats-filter 插件，用于计算 Istio 指标。可参见[stats-plugin.cc](https://github.com/istio/proxy/blob/release-1.14/extensions/stats/plugin.cc)。Istio 安装时默认会在 istio-system 命名空间下部署 `stats-filter-1.xx、tcp-stats-filter-1.xx` 等 envoyfilter 文件，如下图所示：
![](/images/2022-11-01-istio-envoyfilter/1.png)

# 介绍

Envoyfilter 是 Istio 自定义的 CRD，用于配置 Envoy 的过滤器，EnvoyFilter 配置文件如下所示：
![](/images/2022-11-01-istio-envoyfilter/2.png)

* EnvoyFilter 重要组成部分
  * 使用 workloadSelector 指定要配置的 Envoy 实例
    * 省略该字段，意味着将配置到同一个名称空间下的所有 Envoy 实例
    * 若 EnvoyFilter 定义在了根命名空间，且省略了该字段，则意味着配置到网格中所有名称空间中的 Envoy 实例
  * 由 configPatches 给出配置补丁
  * 补丁排序
    * 多个补丁间存在依赖关系时，其应用次序举足轻重
    * EnvoyFilter API 内置了两种应用顺序
      * 根命名空间下的 EnvoyFilter 将先于命名空间下的 EnvoyFilter 资源
      * 补丁集中的多个补丁以它们定义的顺序完成打补丁操作
    * 也可以为 EnvoyFilter 使用 priority 字段定义其优先级，可用的取值范围是 0 至 2^32-1
      * 负数优先级，表示将于 default EnvoyFilter 之前应用
* 补丁及其位置
  * applyTo 指定补丁在 Envoy 配置文件中要应用到的位置（配置段）
  * match 指定补丁在 Envoy 配置文件中相应的位置上要应用到的具体配置对象（Listener、RouteConfiguration 或 Cluster）
  * 补丁的内容及相应的操作则由 patch 字段定义

# 验证

按照 istio 官网安装 istio 集群，安装 Prometheus 监控，部署应用，进行流量测试访问。查看 Prometheus 监控 Metrics 指标，istio_requests_total 有值，如下所示：
![](/images/2022-11-01-istio-envoyfilter/3.png)

删除 istio-system 命名空间下的 `stats-filter-1.x、tcp-stats-filter-1.x` envoyfilter，重新测试，如下所示：
![](/images/2022-11-01-istio-envoyfilter/4.png)

## 结论

istio-system 下默认的 envoyfilter 跟指标息息相关，如果删除，所有跟指标相关的事项会有功能缺失。在 Istio 中，istio-system 命名空间下的 EnvoyFilter 主要用于配置 Envoy 代理的行为。EnvoyFilter 允许你对进出网格的流量进行细粒度的控制和修改，从而实现各种功能，如流量路由、安全策略、故障注入、监控指标收集等。
