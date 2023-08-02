---
layout:     post
title:      "istio 1.8.0 支持 VM 虚拟机验证"
subtitle:   ""
description: "Istio 集群通过 workloadentry 将虚拟机中的服务集成到网格中，从而使虚拟机中的服务可以享受 Mesh 的红利。"
author: "陈谭军"
date: 2020-11-30
published: true
tags:
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

# 环境

* K8s 版本：1.17.2
* Istio 版本：1.8.0
* CentOS 版本：8.0（要求Glibc大于等于 2.18）

查看机器的 glibc 版本：
```bash
ldd --version
ldd (GNU libc) 2.18
Copyright (C) 2013 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
Written by Roland McGrath and Ulrich Drepper.
```

# 常见问题

1. Libc 版本过低，虚拟机启动 envoy 进程会报错。
```
/usr/local/bin/envoy: /lib64/libc.so.6: version `GLIBC_2.18' not found (required by /usr/local/bin/envoy) 
```
2. 确认 k8s 是够支持 TokenRequest，具体详情参见 [configure-third-party-service-account-tokens](https://istio.io/latest/docs/ops/best-practices/security/#configure-third-party-service-account-tokens)。如果不支持，在生成 sa 时报错，*could not create a token under service account %s in namespace %s: %v*。
```bash
kubectl get --raw /api/v1 | jq '.resources[] | select(.name | index("serviceaccounts/token"))'
{
  "name": "serviceaccounts/token",
  "singularName": "",
  "namespaced": true,
  "group": "authentication.k8s.io",
  "version": "v1",
  "kind": "TokenRequest",
  "verbs": [
    "create"
  ]
}
```

# 步骤

**搭建 k8s 集群**

我本地 k8s 环境是 kubeadm 搭建的，需要支持 *TokenRequest*。开启上述特性，案例参考如下所示：
```
/etc/kubernetes/manifests/kube-apiserver.yaml 添加以下文件：
- --service-account-api-audiences=api,istio-ca
- --service-account-issuer=kubernetes.default.svc
- --service-account-signing-key-file=/etc/kubernetes/pki/sa.key
```

![](/images/2020-11-30-istio-support-vm/1.png)

**设置环境变量**

```bash
vm.env
#VM_APP: 该虚拟机将运行的服务名称
#VM_NAMESPACE: 服务命名空间名称
#WORK_DIR：工作目录
#SERVICE_ACCOUNT 用于该虚拟机的k8s serviceaccount名称
export VM_APP=test
export VM_NAMESPACE=test
export WORK_DIR=./test
export SERVICE_ACCOUNT=test
#在虚拟机上使 vm.env 环境变量生效。
```

**创建目录**

```bash
mkdir -p "${WORK_DIR}"
```

**安装 Istio 集群**

```bash
istioctl install
```

**生成虚拟机配置**

```bash
# 生成东西向网关
samples/multicluster/gen-eastwest-gateway.sh --single-cluster | istioctl install -y -f -
# 配置路由
kubectl apply -f samples/multicluster/expose-istiod.yaml
# 变更服务类型 更改 istio-system 下服务的类型为 NodePort
# 创建命名空间、sa、workloadentry
kubectl create namespace "${VM_NAMESPACE}"
kubectl create serviceaccount "${SERVICE_ACCOUNT}" -n "${VM_NAMESPACE}"
istioctl x workload group create --name "${VM_APP}" --namespace "${VM_NAMESPACE}" --labels app="${VM_APP}" --serviceAccount "${SERVICE_ACCOUNT}" > workloadgroup.yaml
# 生成cluster.env、istio-token、mesh.yaml、root-cert.pem、hosts等虚拟机需要使用的文件，注意在 cluster.env 文件中添加 ISTIO_PILOT_PORT='32600' 32600是 gw 15012 对应的端口。
istioctl x workload entry configure -f workloadgroup.yaml -o "${WORK_DIR}"
```
![](/images/2020-11-30-istio-support-vm/2.png)

![](/images/2020-11-30-istio-support-vm/3.png)


**在虚拟机上安装 Istio 进程**

```bash
# 将 "${WORK_DIR}" 目录下的所有的文件拷贝到虚拟机 test 目录下
sudo mkdir -p /etc/certs
sudo cp test/root-cert.pem /etc/certs/root-cert.pem
# 复制 token
sudo  mkdir -p /var/run/secrets/tokens
sudo cp test/istio-token /var/run/secrets/tokens/istio-token
# 服务 rpm 包
curl -LO https://storage.googleapis.com/istio-release/releases/1.8.1/rpm/istio-sidecar.rpm
sudo rpm -i istio-sidecar.rpm
# 复制 envoy 加载的环境变量
sudo cp test/cluster.env /var/lib/istio/envoy/cluster.env
# 复制 mesh 模板 yaml 文件
sudo cp test/mesh.yaml /etc/istio/config/mesh
# 增加域名解析 /etc/hosts
10.20.11.190 istiod.istio-system.svc 其中 10.20.11.190 是 istiod 所在节点的 IP 地址
# 增加用户组
sudo mkdir -p /etc/istio/proxy
sudo chown -R istio-proxy /var/lib/istio /etc/certs /etc/istio/proxy /etc/istio/config /var/run/secrets /etc/certs/root-cert.pem
```

**启用 istio 进程**

```bash
sudo systemctl start istio
```

**查看启动日志**

```bash
tail -f /var/log/istio/istio.log
```
![](/images/2020-11-30-istio-support-vm/4.png)

**虚拟机开启一个 HTTP 服务**

```bash
python -m SimpleHTTPServer 8080
```

**添加虚拟机服务到 mesh 中**

```yaml
cat <<EOF | kubectl -n <vm-namespace> apply -f -
apiVersion: v1
kind: Service
metadata:
  name: cloud-vm
  labels:
    app: cloud-vm
spec:
  ports:
  - port: 8080
    name: http-vm
    targetPort: 8080
  selector:
    app: cloud-vm
EOF
```
```yaml
cat <<EOF | kubectl -n <vm-namespace> apply -f -
apiVersion: networking.istio.io/v1beta1
kind: WorkloadEntry
metadata:
  name: "cloud-vm"
  namespace: "<vm-namespace>"
spec:
  address: "${VM_IP}"
  labels:
    app: cloud-vm
  serviceAccount: "<service-account>"
EOF
#VM_IP 表示虚拟机的IP 地址
```

**在 Istio 集群中部署 sleep 服务**

```bash
kubectl label ns test istio-injection=enabled
```
![](/images/2020-11-30-istio-support-vm/5.png)

**通过 sleep 服务访问虚拟机上的 http 服务验证 k8s -> vm 是否正确**

```bash
kubectl exec -it sleep-f8cbf5b76-hhll2  -n test -c sleep -- curl cloud-vm.${VM_NAMESPACE}.svc.cluster.local:8080
```
![](/images/2020-11-30-istio-support-vm/6.png)

虚拟机 istio 进程的日志
![](/images/2020-11-30-istio-support-vm/7.png)

http 服务的日志
![](/images/2020-11-30-istio-support-vm/8.png)

sleep 服务的日志
![](/images/2020-11-30-istio-support-vm/9.png)

Istio 集群中的服务成功访问虚拟机上的 http 服务。

# 总结

Istio 集群通过 workloadentry 将虚拟机中的服务集成到网格中，从而使虚拟机中的服务可以享受 Mesh 的红利。

# 附录

1. https://github.com/istio/istio/issues/30020

