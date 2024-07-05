---
layout:     post
title:      "Sidecar 在 Istio 大规模场景下性能测试"
subtitle:   "Istio Sidecar Scope 性能测试"
description: "Istio XDS 全量下发在大规模场景下存在性能问题
* Istio 全量下发配置会导致数据面/控制面出现性能瓶颈；
* 全量下发造成数据面 Envoy 配置庞大，Envoy 内存使用率较大；"
author: "陈谭军"
date: 2024-03-09
published: true
tags:
    - kubernetes
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

# 背景

Istio XDS 全量下发在大规模场景下存在性能问题。
* Istio 全量下发配置会导致数据面/控制面出现性能瓶颈；
* 全量下发造成数据面 Envoy 配置庞大，Envoy 内存使用率较大；

# 测试目标

主要目标是测试在评估（Sidecar）按需下发后 Istio 控制平面与数据平面性能（数据平面的 Envoy 内存占用与控制平面的推送时延）。

# 性能测试

## 集群信息

```bash
Kubernetes 版本：v1.26.9
istio 版本：1.16.5 
```

测试工作负载如下所示：
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sleep
---
apiVersion: v1
kind: Service
metadata:
  name: sleep
  labels:
    app: sleep
    service: sleep
spec:
  ports:
  - port: 80
    name: http
  selector:
    app: sleep
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sleep
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sleep
  template:
    metadata:
      labels:
        app: sleep
    spec:
      terminationGracePeriodSeconds: 0
      serviceAccountName: sleep
      containers:
      - name: sleep
        image: docker.io/kennethreitz/httpbin:latest
        command: ["/bin/sleep", "infinity"]
        imagePullPolicy: IfNotPresent
        volumeMounts:
        - mountPath: /etc/sleep/tls
          name: secret-volume
      volumes:
      - name: secret-volume
        secret:
          secretName: sleep-secret
          optional: true
apiVersion: v1
kind: ServiceAccount
metadata:
  name: httpbin
---
apiVersion: v1
kind: Service
metadata:
  name: httpbin
  labels:
    app: httpbin
    service: httpbin
spec:
  ports:
  - name: http
    port: 8000
    targetPort: 80
  selector:
    app: httpbin
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: httpbin
spec:
  replicas: 1
  selector:
    matchLabels:
      app: httpbin
      version: v1
  template:
    metadata:
      labels:
        app: httpbin
        version: v1
    spec:
      serviceAccountName: httpbin
      containers:
      - image: docker.io/kennethreitz/httpbin:latest
        imagePullPolicy: IfNotPresent
        name: httpbin
        ports:
        - containerPort: 80
```

测试条件：
* 在10个命名空间，每个命名空间下5个Pod（4httpbin、1sleep），总共50注入Sidecar的Pod；
* istio-system 命名空间下部署 1000 个 service entry；
* istio-proxy  limits：CPU 2c，Memory：1024Mi，requests：CPU：100m，128Mi；
* Istiod limits：CPU 4c，Memory：8Gi，requests：CPU 4c，Memory：8Gi；

## 安装 istio 集群

```bash
istioctl install -f iop.yaml
```

```yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
metadata:
  name: iop-istio
  namespace: istio-system
spec:
  tag: 1.16.5
  namespace: istio-system
  meshConfig:
    accessLogFile: /dev/stdout
    defaultConfig:
      holdApplicationUntilProxyStarts: true
      proxyMetadata:
      # 开启智能 DNS
        ISTIO_META_DNS_CAPTURE: "true"
        ISTIO_META_DNS_AUTO_ALLOCATE: "true"
      # 支持多协议
      proxyStatsMatcher:
        inclusionPrefixes:
        - thrift
        - dubbo
        - kafka
        - meta_protocol
        inclusionRegexps:
        - .*dubbo.*
        - .*thrift.*
        - .*kafka.*
        - .*zookeeper.*
        - .*meta_protocol.*
  values:
    global:
      meshID: test
      istioNamespace: istio-system
      network: gz
    sidecarInjectorWebhook:
      rewriteAppHTTPProbe: false
  components:
    ingressGateways:
      - name: istio-ingressgateway
        enabled: false
```

## 创建 namespace 与工作负载

```bash
#!/bin/bash

for i in {1..10}
do
	namespace="test-$i"
	kubectl create namespace $namespace || true
	kubectl -n $namespace apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sleep
---
apiVersion: v1
kind: Service
metadata:
  name: sleep
  labels:
    app: sleep
    service: sleep
spec:
  ports:
  - port: 80
    name: http
  selector:
    app: sleep
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sleep
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sleep
  template:
    metadata:
      labels:
        app: sleep
    spec:
      terminationGracePeriodSeconds: 0
      serviceAccountName: sleep
      containers:
      - name: sleep
        image: docker.io/kennethreitz/httpbin:latest
        command: ["/bin/sleep", "infinity"]
        imagePullPolicy: IfNotPresent
        volumeMounts:
        - mountPath: /etc/sleep/tls
          name: secret-volume
      volumes:
      - name: secret-volume
        secret:
          secretName: sleep-secret
          optional: true
EOF

	for j in {1..4}
	do
		kubectl -n $namespace apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: httpbin
---
apiVersion: v1
kind: Service
metadata:
  name: httpbin
  labels:
    app: httpbin
    service: httpbin
spec:
  ports:
  - name: http
    port: 8000
    targetPort: 80
  selector:
    app: httpbin
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: httpbin-$namespace-$j
spec:
  replicas: 1
  selector:
    matchLabels:
      app: httpbin
      version: v1
  template:
    metadata:
      labels:
        app: httpbin
        version: v1
    spec:
      serviceAccountName: httpbin
      containers:
      - image: docker.io/kennethreitz/httpbin:latest
        imagePullPolicy: IfNotPresent
        name: httpbin
        ports:
        - containerPort: 80
EOF
	done
done
```

![](/images/2024-03-09-istio-sidecar-performance-test/1.png)

![](/images/2024-03-09-istio-sidecar-performance-test/2.png)

![](/images/2024-03-09-istio-sidecar-performance-test/3.png)

## 创建 1000 个 ServiceEntry

```bash
#!/bin/bash

for i in {1..1000}
do
  entry_name="httpbin-entry-$i"
  namespace="istio-system"
kubectl -n $namespace apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: ServiceEntry
metadata:
  name: $entry_name
  namespace: $namespace
spec:
  hosts:
  - httpbin.org
  ports:
  - number: 80
    name: http
    protocol: HTTP
  resolution: DNS
EOF

done
```

![](/images/2024-03-09-istio-sidecar-performance-test/4.png)

## 未使用 Sidecar

```bash
#查看namespace下pod的运行情况
kubectl -n test-1 get pod  | grep sleep 
sleep-69cdf8667d-p2v7l              2/2     Running   0          15h

#执行以下命令，下载httpbin-0应用所在Pod的Sidecar，保存至本地。
kubectl -n test-1 exec -it sleep-69cdf8667d-p2v7l -c istio-proxy -- curl localhost:15000/config_dump > se.json

#执行以下命令，查看Sidecar配置文件的大小。
du -sh se_configdump.json
880K	se_configdump.json
```

## 使用 Sidecar

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Sidecar
metadata:
  name: default
  namespace: test-1
spec:
  egress:
  - hosts:
    - "test-1/*"
    - "istio-system/*"
```

```bash
kubectl -n test-1 exec -it sleep-69cdf8667d-ld5n4  -c istio-proxy -- curl localhost:15000/config_dump > with_sidecar_se_configdump.json

du -sh with_sidecar_se_configdump.json
580K	with_sidecar_se_configdump.json
```

Istio Sidecar 不加 istio-system 命令空间。

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Sidecar
metadata:
  name: default
  namespace: test-1
spec:
  egress:
  - hosts:
    - "test-1/*"
```

```bash
➜  istio-1.16.5 du -sh with_sidecar_se_configdump_no_istio_system.json
196K	with_sidecar_se_configdump_no_istio_system.json
```

## 在 test-1 下创建 Pod，查看控制面推送时延

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nginx:1.17.3
          ports:
            - containerPort: 80
```

存在 Sidecar（带有 istio-system） 的情况下：
```bash
2024-04-25T05:33:36.971926Z	info	ads	EDS: PUSH request for node:nginx-84bfdb5dc4-sd554.test-1 resources:6 size:1.6kB empty:0 cached:6/6
2024-04-25T05:33:36.979920Z	info	ads	LDS: PUSH request for node:nginx-84bfdb5dc4-sd554.test-1 resources:8 size:41.0kB
2024-04-25T05:33:36.979958Z	info	ads	NDS: PUSH request for node:nginx-84bfdb5dc4-sd554.test-1 resources:1 size:292B
2024-04-25T05:33:37.022978Z	info	ads	RDS: PUSH request for node:nginx-84bfdb5dc4-sd554.test-1 resources:4 size:2.6kB cached:4/4
2024-04-25T05:33:37.677824Z	info	ads	CDS: PUSH for node:nginx-84bfdb5dc4-sd554.test-1 resources:10 size:67.1kB cached:7/7
2024-04-25T05:33:37.677958Z	info	ads	EDS: PUSH for node:nginx-84bfdb5dc4-sd554.test-1 resources:6 size:1.6kB empty:0 cached:6/6
2024-04-25T05:33:37.679227Z	info	ads	LDS: PUSH for node:nginx-84bfdb5dc4-sd554.test-1 resources:8 size:41.0kB
2024-04-25T05:33:37.679673Z	info	ads	RDS: PUSH for node:nginx-84bfdb5dc4-sd554.test-1 resources:4 size:2.6kB cached:4/4
2024-04-25T05:33:37.679737Z	info	ads	NDS: PUSH for node:nginx-84bfdb5dc4-sd554.test-1 resources:1 size:292B
```

不存在 Sidecar（带有 istio-system） 的情况下：
```bash
2024-04-25T05:41:11.461208Z	info	Sidecar injection request for test-1/nginx-84bfdb5dc4-***** (actual name not yet known)
2024-04-25T05:41:12.397619Z	info	ads	ADS: new connection for node:nginx-84bfdb5dc4-gjr74.test-1-257
2024-04-25T05:41:12.400264Z	info	ads	CDS: PUSH request for node:nginx-84bfdb5dc4-gjr74.test-1 resources:35 size:91.9kB cached:1006/1031
2024-04-25T05:41:12.522927Z	info	ads	EDS: PUSH request for node:nginx-84bfdb5dc4-gjr74.test-1 resources:31 size:11.1kB empty:1 cached:6/31
2024-04-25T05:41:12.736528Z	info	ads	LDS: PUSH request for node:nginx-84bfdb5dc4-gjr74.test-1 resources:15 size:68.4kB
2024-04-25T05:41:12.736940Z	info	ads	NDS: PUSH request for node:nginx-84bfdb5dc4-gjr74.test-1 resources:1 size:2.3kB
2024-04-25T05:41:12.767528Z	info	ads	RDS: PUSH request for node:nginx-84bfdb5dc4-gjr74.test-1 resources:8 size:13.4kB cached:8/8
2024-04-25T05:41:13.264996Z	info	ads	CDS: PUSH for node:nginx-84bfdb5dc4-gjr74.test-1 resources:35 size:91.9kB cached:1006/1031
2024-04-25T05:41:13.265818Z	info	ads	EDS: PUSH for node:nginx-84bfdb5dc4-gjr74.test-1 resources:31 size:11.1kB empty:1 cached:6/31
2024-04-25T05:41:13.267125Z	info	ads	LDS: PUSH for node:nginx-84bfdb5dc4-gjr74.test-1 resources:15 size:68.4kB
2024-04-25T05:41:13.267757Z	info	ads	RDS: PUSH for node:nginx-84bfdb5dc4-gjr74.test-1 resources:8 size:13.4kB cached:8/8
2024-04-25T05:41:13.268017Z	info	ads	NDS: PUSH for node:nginx-84bfdb5dc4-gjr74.test-1 resources:1 size:2.3kB
```

## 测试结论

以下为使用Sidecar资源优化前后的效果对比。

| 规模 | 类型  | 配置 | 使用 Sidecar | 未使用 Sidecar |
| --- | --- | --- | --- | --- |
| 50 Pod | 1000 SE | Sidecar配置大小 | 580K | 880K |
| 50 Pod | 1000 SE | 控制平面配置推送时间 | 0.7s | 1.8s |

结论：在 istio-system 命名空间下部署 1000 个 service entry；50个注入Sidecar的Pod；Istiod 资源4c8Gi（request 与 limis 相等）情况下测试数据：
* Sidecar配置大小从880K降到580K，下降34%，随着Sidecar规模增加，下降的效果越明显；
* 控制平面配置推送时间从1.8s降到0.7s，下降61.1%，随着Sidecar规模增加，下降的效果越明显；

# 参考

1. [effects-of-sidecar-recommendation-on-configuration-push-optimization](https://help.aliyun.com/zh/asm/user-guide/effects-of-sidecar-recommendation-on-configuration-push-optimization?spm=a2c4g.11186623.0.0.6b1b6a46LET3Bd)
