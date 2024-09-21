---
layout:     post
title:      "Kubernetes CoreDNS 核心原理和源码解析"
subtitle:   ""
description: ""
author: "陈谭军"
date: 2024-01-07
published: true
tags:
    - Kubernetes
    - DNS
    - CoreDNS
categories:
    - TECHNOLOGY
showtoc: true
---

# K8S 中的 DNS 解析原理

![](/images/2024-01-09-kubernetes-coredns/1.png)

示例如下所示：
```bash
➜  tanjunchen_blog (main) kubectl  exec -it nginx-0 bash                                                                                                           ✱
kubectl exec [POD] [COMMAND] is DEPRECATED and will be removed in a future version. Use kubectl exec [POD] -- [COMMAND] instead.
root@nginx-0:/# cat /etc/resolv.conf
search default.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.22.0.10
options ndots:5
root@nginx-0:/# exit
exit
➜  tanjunchen_blog (main) kubectl  -n kube-system get svc kube-dns                                                                                                 ✱
NAME       TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)                  AGE
kube-dns   ClusterIP   10.22.0.10   <none>        53/UDP,53/TCP,9153/TCP   113d
```

# K8S DNS SPEC

CoreDNS 类似于 containerd 和 CRI，calico/cilium 和 CNI 之间的关系，CoreDNS 是对 [K8S DNS SPEC](https://github.com/kubernetes/dns/blob/master/docs/specification.md) 的一个实现，从 kubernetes v1.11 起，CoreDNS 已经取代 kube-dns 成为默认的 DNS 方案. 

# K8S SEPC 简要版本

这里列举 k8s 集群中常见的 DNS 查询，如下所示：

* Schema Version Record
* Service ClusterIP IPV4 Record
* Service ClusterIP IPV6 Record
* 根据 ClusterIP 反查 Service Name
* Headless Service Record

## Schema Version Record

```bash
* Question Example:
  * dns-version.cluster.local. IN TXT
* Answer Example:
  * dns-version.cluster.local. 28800 IN TXT "1.1.0"
```

## Service ClusterIP IPV4 Record

```bash
* Question Example:
  * kubernetes.default.svc.cluster.local. IN A
* Answer Example:
  * kubernetes.default.svc.cluster.local. 4 IN A 10.3.0.1
```

## Service ClusterIP IPV6 Record

```bash
* Question Example:
  * kubernetes.default.svc.cluster.local. IN AAAA
* Answer Example:
  * kubernetes.default.svc.cluster.local. 4 IN AAAA 2001:db8::1
```

## 根据 ClusterIP 反查 Service Name

假设 kubernetes 服务的 ClusterIP 是 10.3.0.1，注意这里查询请求 ip 地址为逆序. 

```bash
* Question Example:
  * 1.0.3.10.in-addr.arpa. IN PTR
* Answer Example:
  * 1.0.3.10.in-addr.arpa. 14 IN PTR kubernetes.default.svc.cluster.local.
```

## Headless Service Record

```bash
* Question Example:
  * headless.default.svc.cluster.local. IN A
* Answer Example:
  * headless.default.svc.cluster.local. 4 IN A 10.3.0.1
  * headless.default.svc.cluster.local. 4 IN A 10.3.0.2
  * headless.default.svc.cluster.local. 4 IN A 10.3.0.3
```

# CoreDNS 配置文件解析

格式如下：
```bash
[SCHEME://]ZONE [[SCHEME://]ZONE]...[:PORT]{[PLUGIN]...}
```

* SCHEME是可选的，默认值为dns://，也可以指定为tls://，grpc://或者https://
* ZONE是可选的，指定了此dnsserver可以服务的域名前缀，如果不指定，则默认为root，表示可以接收所有的dns请求
* PORT是选项的，指定了监听端口号，默认为53，如果这里指定了端口号，则不能通过参数-dns.port覆盖
* 一块上面格式的配置表示一个dnsserver，称为serverblock，可以配置多个serverblock表示多个dnsserver

下面通过一个例子说明，如下配置文件指定了4个serverblock，即4个dnsserver，第一个监听端口5300，后面三个监听同一个端口53，每个dnsserver指定了特定的插件. 
```bash
coredns.io:5300 {
    file /etc/coredns/zones/coredns.io.db
}

example.io:53 {
    log    
    errors
    file /etc/coredns/zones/example.io.db
}

example.net:53 {
    file /etc/coredns/zones/example.net.db
}

.:53 {
    kubernetes
    errors
    log
    health
}
```

# 快速开始

源码编译

```bash
$ git clone https://github.com/coredns/coredns
$ cd coredns
$ git checkout -b  v1.9.4 v1.9.4
$ make
```

coredns 默认会监听在 53 端口，没有配置 Corefile 的话，默认会加载 whoami 和 log 两个 plugin. 请求 `dig www.example.com` 如下所示：

```bash
(base) [root@instance-crwsvl7m-2 ~]#  dig www.example.com

; <<>> DiG 9.11.4-P2-RedHat-9.11.4-26.P2.el7 <<>> www.example.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY，status: NOERROR，id: 40514
;; flags: qr rd ra ad; QUERY: 1，ANSWER: 1，AUTHORITY: 0，ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0，flags:; udp: 1280
;; QUESTION SECTION:
;www.example.com.               IN      A

;; ANSWER SECTION:
www.example.com.        384     IN      A       93.184.215.14

;; Query time: 0 msec
;; SERVER: 106.12.199.25#53(106.12.199.25)
;; WHEN: Fri Sep 20 19:46:44 CST 2024
;; MSG SIZE  rcvd: 60
```

请求我们本地起的 coredns 进程 dig www.example.com，返回 client ip，即 whoami 插件的作用：

```bash
(base) [root@instance-crwsvl7m-2 ~]#  dig @127.0.0.1 -p53  www.example.com

; <<>> DiG 9.11.4-P2-RedHat-9.11.4-26.P2.el7 <<>> @127.0.0.1 -p53 www.example.com
; (1 server found)
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY，status: NOERROR，id: 26257
;; flags: qr aa rd; QUERY: 1，ANSWER: 0，AUTHORITY: 0，ADDITIONAL: 3
;; WARNING: recursion requested but not available

;; OPT PSEUDOSECTION:
; EDNS: version: 0，flags:; udp: 4096
;; QUESTION SECTION:
;www.example.com.               IN      A

;; ADDITIONAL SECTION:
www.example.com.        0       IN      A       127.0.0.1
_udp.www.example.com.   0       IN      SRV     0 0 50368 .

;; Query time: 0 msec
;; SERVER: 127.0.0.1#53(127.0.0.1)
;; WHEN: Fri Sep 20 19:43:56 CST 2024
;; MSG SIZE  rcvd: 114
```

coredns 日志也可以看到对应请求
```bash
(base) [root@instance-crwsvl7m-2 coredns]# ./coredns 
.:53
CoreDNS-1.9.4
linux/amd64，go1.20.12，1f0a41a
[INFO] 127.0.0.1:50368 - 26257 "A IN www.example.com. udp 44 false 4096" NOERROR qr,aa,rd 103 0.000157803s
```

# CoreDNS 源码解析

基于 tag v1.9.4，分析核心流程相关代码，如下所示：

## 插件定义

```bash
type (
	// Plugin is a middle layer which represents the traditional
	// idea of plugin: it chains one Handler to the next by being
	// passed the next Handler in the chain.
	Plugin func(Handler) Handler
	
	Handler interface {
		ServeDNS(context.Context，dns.ResponseWriter，*dns.Msg) (int，error)
		Name() string
	}
...
)
```

核心接口 ServeDNS，参数说明：

* context.Context，上下文信息
* dns.ResponseWriter，代表客户端连接，可以回写查询结果
* *dns.Msg，dns请求消息体

## 插件注册

以 kubernetes 为例，在 init() 内注册 setup 方法，然后使用 AddPlugin() 方法，将插件加入插件链. 

```bash
const pluginName = "kubernetes"

var log = clog.NewWithPlugin(pluginName)

func init() { plugin.Register(pluginName，setup) }

func setup(c *caddy.Controller) error {
...
	dnsserver.GetConfig(c).AddPlugin(func(next plugin.Handler) plugin.Handler {
		k.Next = next
		return k
	})
...
}
```

## CoreDNS 主要流程

main 函数：

* 解析 Corefile 配置文件
* 启动 server

```bash
func Run() {
    ...
	// Get Corefile input
	corefile，err := caddy.LoadCaddyfile(serverType)
	if err != nil {
		mustLogFatal(err)
	}
	fmt.Printf("DEBUG: Corefile is:\n%s"，string(corefile.Body()))

	// Start your engines
	instance，err := caddy.Start(corefile)
	if err != nil {
		mustLogFatal(err)
	}
    ...
}
```

Start 函数最终会调用 NewServer，新建 coredns server. coredns 在创建 Server 时，会遍历已注册的 plugin 来构建 pluginChain 调用链. 

```bash
// NewServer returns a new CoreDNS server and compiles all plugins in to it. By default CH class
// queries are blocked unless queries from enableChaos are loaded.
func NewServer(addr string，group []*Config) (*Server，error) {
	s := &Server{
		Addr:         addr,
		zones:        make(map[string]*Config),
		graceTimeout: 5 * time.Second,
		tsigSecret:   make(map[string]string),
	}
...
	for _，site := range group {
...
		// compile custom plugin for everything
		var stack plugin.Handler
		for i := len(site.Plugin) - 1; i >= 0; i-- {
			stack = site.Plugin[i](stack)

			// register the *handler* also
			site.registerHandler(stack)
...
		}
		site.pluginChain = stack
	}
...
	return s，nil
}
```

启动 udp/tcp 的监听，读取 dns 请求报文，处理 dns 请求。

* Serve 处理 TCP 请求
* ServePacket 处理 UDP 请求
  * ServePacket 会启动启动 dns server，并启动 udp server ;
  * ActivateAndServe 会根据配置来启动 tcp 和 udp 服务 ;
  * serveUDP 读取 dns 请求报文，然后开一个协程去调用 serveUDPPacket ;
  * serveUDPPacket 内部会实例化 writer 写对象，然后调用 serveDNS 处理请求.

```bash
// Serve starts the server with an existing listener. It blocks until the server stops.
// This implements caddy.TCPServer interface.
func (s *Server) Serve(l net.Listener) error {
	s.m.Lock()
	s.server[tcp] = &dns.Server{Listener: l，Net: "tcp"，Handler: dns.HandlerFunc(func(w dns.ResponseWriter，r *dns.Msg) {
		ctx := context.WithValue(context.Background()，Key{}，s)
		ctx = context.WithValue(ctx，LoopKey{}，0)
		s.ServeDNS(ctx，w，r)
	})，TsigSecret: s.tsigSecret}
	s.m.Unlock()

	return s.server[tcp].ActivateAndServe()
}
```

```bash
// ServePacket starts the server with an existing packetconn. It blocks until the server stops.
// This implements caddy.UDPServer interface.
func (s *Server) ServePacket(p net.PacketConn) error {
	s.m.Lock()
	s.server[udp] = &dns.Server{PacketConn: p，Net: "udp"，Handler: dns.HandlerFunc(func(w dns.ResponseWriter，r *dns.Msg) {
		ctx := context.WithValue(context.Background()，Key{}，s)
		ctx = context.WithValue(ctx，LoopKey{}，0)
		s.ServeDNS(ctx，w，r)
	})，TsigSecret: s.tsigSecret}
	s.m.Unlock()

	return s.server[udp].ActivateAndServe()
}
```

```bash
...
func (srv *Server) ActivateAndServe() error {
    ...
    if srv.PacketConn != nil {
        ...
        return srv.serveUDP(srv.PacketConn)
    }
    if srv.Listener != nil {
        ...
        return srv.serveTCP(srv.Listener)
    }
    return &Error{err: "bad listeners"}
}
```

```bash
...
func (srv *Server) serveUDP(l net.PacketConn) error {
	...
	for srv.isStarted() {
        ...
		if isUDP {
			m，sUDP，err = reader.ReadUDP(lUDP，rtimeout)
		} else {
			m，sPC，err = readerPC.ReadPacketConn(l，rtimeout)
		}
        ...
		go srv.serveUDPPacket(&wg，m，l，sUDP，sPC)
	}

	return nil
}
...
```

```bash
func (srv *Server) serveUDPPacket(wg *sync.WaitGroup，m []byte，u net.PacketConn，udpSession *SessionUDP，pcSession net.Addr) {
	w := &response{tsigProvider: srv.tsigProvider()，udp: u，udpSession: udpSession，pcSession: pcSession}
	if srv.DecorateWriter != nil {
		w.writer = srv.DecorateWriter(w)
	} else {
		w.writer = w
	}

	srv.serveDNS(m，w)
	wg.Done()
}
```

根据请求的 zone，遍历执行 pluginChain 插件链的所有 Plugin 插件，依次执行 plugin.ServeDNS 方法. 

```bash
func (s *Server) ServeDNS(ctx context.Context，w dns.ResponseWriter，r *dns.Msg) {
    ...
	// Wrap the response writer in a ScrubWriter so we automatically make the reply fit in the client's buffer.
	w = request.NewScrubWriter(r，w)

	q := strings.ToLower(r.Question[0].Name)
	var (
		off       int
		end       bool
		dshandler *Config
	)

	for {
		if h，ok := s.zones[q[off:]]; ok {
			if h.pluginChain == nil { // zone defined，but has not got any plugins
				errorAndMetricsFunc(s.Addr，w，r，dns.RcodeRefused)
				return
			}
			if r.Question[0].Qtype != dns.TypeDS {
				rcode，_ := h.pluginChain.ServeDNS(ctx，w，r)
				if !plugin.ClientWrite(rcode) {
					errorFunc(s.Addr，w，r，rcode)
				}
				return
			}
			// The type is DS，keep the handler，but keep on searching as maybe we are serving
			// the parent as well and the DS should be routed to it - this will probably *misroute* DS
			// queries to a possibly grand parent，but there is no way for us to know at this point
			// if there is an actual delegation from grandparent -> parent -> zone.
			// In all fairness: direct DS queries should not be needed.
			dshandler = h
		}
		off，end = dns.NextLabel(q，off)
		if end {
			break
		}
	}
    ...
	// Wildcard match，if we have found nothing try the root zone as a last resort.
	if h，ok := s.zones["."]; ok && h.pluginChain != nil {
		rcode，_ := h.pluginChain.ServeDNS(ctx，w，r)
		if !plugin.ClientWrite(rcode) {
			errorFunc(s.Addr，w，r，rcode)
		}
		return
	}

	// Still here? Error out with REFUSED.
	errorAndMetricsFunc(s.Addr，w，r，dns.RcodeRefused)
}
```

这里 `.` 代表的是 root zone，即其他 zone 都没匹配到，并配置了 root zone，则匹配到 root zone，进行处理，示例 Corefile 如下：

```bash
example.org:1053 {
    file /var/lib/coredns/example.org.signed
    transfer {
        to * 2001:500:8f::53
    }
    errors
    log
}
```

```bash
. {
    any
    forward . 8.8.8.8:53
    errors
    log
}
```

CoreDNS 的架构和核心流程总结如下：

![](/images/2024-01-09-kubernetes-coredns/2.png)

## kubernetes plugin 主要逻辑

插件配置：

```yaml
apiVersion: v1
data:
  Corefile: |-
    .:53 {
        errors
        health {
            lameduck 10s
        }
        ready
        log
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
            ttl 30
        }
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
kind: ConfigMap
```

插件加载主要功能如下所示：

* 解析 k8s 配置
* 实例化 kubeclient 并实例化 dns controller 控制器
* 把插件注册到 plugin 链

```bash
func setup(c *caddy.Controller) error {
	// Do not call klog.InitFlags(nil) here.  It will cause reload to panic.
	klog.SetLogger(logr.New(&loggerAdapter{log}))

	k，err := kubernetesParse(c)
	if err != nil {
		return plugin.Error(pluginName，err)
	}

	onStart，onShut，err := k.InitKubeCache(context.Background())
	if err != nil {
		return plugin.Error(pluginName，err)
	}
	if onStart != nil {
		c.OnStartup(onStart)
	}
	if onShut != nil {
		c.OnShutdown(onShut)
	}

	dnsserver.GetConfig(c).AddPlugin(func(next plugin.Handler) plugin.Handler {
		k.Next = next
		return k
	})

	// get locally bound addresses
	c.OnStartup(func() error {
		k.localIPs = boundIPs(c)
		return nil
	})

	return nil
}
```

```bash
func (k *Kubernetes) InitKubeCache(ctx context.Context) (onStart func() error，onShut func() error，err error) {
	config，err := k.getClientConfig()
	if err != nil {
		return nil，nil，err
	}

	kubeClient，err := kubernetes.NewForConfig(config)
    ...
	k.APIConn = newdnsController(ctx，kubeClient，k.opts)
    ...
}
```

dnsController 控制器逻辑，实例化 dnsControl 对象，同时实例化各个资源的 informer 对象，在实例化 informer 时传入自定义的 eventHandler 回调方法 和 indexer 索引方法.

```bash
func newdnsController(ctx context.Context，kubeClient kubernetes.Interface，opts dnsControlOpts) *dnsControl {
	dns := dnsControl{
		client:            kubeClient,
		selector:          opts.selector,
		namespaceSelector: opts.namespaceSelector,
		stopCh:            make(chan struct{}),
		zones:             opts.zones,
		endpointNameMode:  opts.endpointNameMode,
	}

	dns.svcLister，dns.svcController = object.NewIndexerInformer(
		&cache.ListWatch{
			ListFunc:  serviceListFunc(ctx，dns.client，api.NamespaceAll，dns.selector),
			WatchFunc: serviceWatchFunc(ctx，dns.client，api.NamespaceAll，dns.selector),
		},
		&api.Service{},
		cache.ResourceEventHandlerFuncs{AddFunc: dns.Add，UpdateFunc: dns.Update，DeleteFunc: dns.Delete},
		cache.Indexers{svcNameNamespaceIndex: svcNameNamespaceIndexFunc，svcIPIndex: svcIPIndexFunc，svcExtIPIndex: svcExtIPIndexFunc},
		object.DefaultProcessor(object.ToService，nil),
	)

	if opts.initPodCache {
		dns.podLister，dns.podController = object.NewIndexerInformer(
			&cache.ListWatch{
				ListFunc:  podListFunc(ctx，dns.client，api.NamespaceAll，dns.selector),
				WatchFunc: podWatchFunc(ctx，dns.client，api.NamespaceAll，dns.selector),
			},
			&api.Pod{},
			cache.ResourceEventHandlerFuncs{AddFunc: dns.Add，UpdateFunc: dns.Update，DeleteFunc: dns.Delete},
			cache.Indexers{podIPIndex: podIPIndexFunc},
			object.DefaultProcessor(object.ToPod，nil),
		)
	}

	if opts.initEndpointsCache {
		dns.epLock.Lock()
		dns.epLister，dns.epController = object.NewIndexerInformer(
			&cache.ListWatch{
				ListFunc:  endpointSliceListFunc(ctx，dns.client，api.NamespaceAll，dns.selector),
				WatchFunc: endpointSliceWatchFunc(ctx，dns.client，api.NamespaceAll，dns.selector),
			},
			&discovery.EndpointSlice{},
			cache.ResourceEventHandlerFuncs{AddFunc: dns.Add，UpdateFunc: dns.Update，DeleteFunc: dns.Delete},
			cache.Indexers{epNameNamespaceIndex: epNameNamespaceIndexFunc，epIPIndex: epIPIndexFunc},
			object.DefaultProcessor(object.EndpointSliceToEndpoints，dns.EndpointSliceLatencyRecorder()),
		)
		dns.epLock.Unlock()
	}

	dns.nsLister，dns.nsController = object.NewIndexerInformer(
		&cache.ListWatch{
			ListFunc:  namespaceListFunc(ctx，dns.client，dns.namespaceSelector),
			WatchFunc: namespaceWatchFunc(ctx，dns.client，dns.namespaceSelector),
		},
		&api.Namespace{},
		cache.ResourceEventHandlerFuncs{},
		cache.Indexers{},
		object.DefaultProcessor(object.ToNamespace，nil),
	)

	return &dns
}
```

* 为什么需要监听 service 资源 ? 
  * 用户在 pod 内直接使用 service_name 获取到 cluster ip
* 为什么需要监听 pod 资源 ? 
  * 用户可以直接通过 podname 进行解析
* 为什么需要监听 endpoints 资源 ? 
  * 如果 service 有配置 clusterNone，也就是 headless 类型，则需要使用到 endpoints 的地址
  * headless 服务的场景
    * 应用自己进行负载均衡
    * 应用需要连接到所有 pod
* 为什么需要监听 namespace 资源 ? 
  * 需要判断请求域名的 namespace 段是否可用

kubernetes 插件如何处理 dns 请求? kubernetes 插件也实现了 ServeDNS 方法，该逻辑通过请求的 Qtype 查询类型，调用不同方法来解析域名. 

```bash
// ServeDNS implements the plugin.Handler interface.
func (k Kubernetes) ServeDNS(ctx context.Context，w dns.ResponseWriter，r *dns.Msg) (int，error) {
	state := request.Request{W: w，Req: r}
    ...
	switch state.QType() {
	case dns.TypeA:
		records，truncated，err = plugin.A(ctx，&k，zone，state，nil，plugin.Options{})
	case dns.TypeAAAA:
		records，truncated，err = plugin.AAAA(ctx，&k，zone，state，nil，plugin.Options{})
	case dns.TypeTXT:
		records，truncated，err = plugin.TXT(ctx，&k，zone，state，nil，plugin.Options{})
	case dns.TypeCNAME:
		records，err = plugin.CNAME(ctx，&k，zone，state，plugin.Options{})
	case dns.TypePTR:
		records，err = plugin.PTR(ctx，&k，zone，state，plugin.Options{})
	case dns.TypeMX:
		records，extra，err = plugin.MX(ctx，&k，zone，state，plugin.Options{})
	case dns.TypeSRV:
		records，extra，err = plugin.SRV(ctx，&k，zone，state，plugin.Options{})
	case dns.TypeSOA:
		if qname == zone {
			records，err = plugin.SOA(ctx，&k，zone，state，plugin.Options{})
		}
	case dns.TypeAXFR，dns.TypeIXFR:
		return dns.RcodeRefused，nil
	case dns.TypeNS:
		if state.Name() == zone {
			records，extra，err = plugin.NS(ctx，&k，zone，state，plugin.Options{})
			break
		}
		fallthrough
	default:
		// Do a fake A lookup，so we can distinguish between NODATA and NXDOMAIN
		fake := state.NewWithQuestion(state.QName()，dns.TypeA)
		fake.Zone = state.Zone
		_，_，err = plugin.A(ctx，&k，zone，fake，nil，plugin.Options{})
	}
    ...
	m := new(dns.Msg)
	m.SetReply(r)
	m.Truncated = truncated
	m.Authoritative = true
	m.Answer = append(m.Answer，records...)
	m.Extra = append(m.Extra，extra...)
	w.WriteMsg(m)
	return dns.RcodeSuccess，nil
}
```

plugin.A，plugin.Txt，plugin.CNAME 等都会调用到 Services() 方法，以 CNAME 为例. 
```bash
func CNAME(ctx context.Context，b ServiceBackend，zone string，state request.Request，opt Options) (records []dns.RR，err error) {
	services，err := b.Services(ctx，state，true，opt)
	if err != nil {
		return nil，err
	}

	if len(services) > 0 {
		serv := services[0]
		if ip := net.ParseIP(serv.Host); ip == nil {
			records = append(records，serv.NewCNAME(state.QName()，serv.Host))
		}
	}
	return records，nil
}
```

Services() 最终调用 Records() 方法，会从域名的特征判断请求域名是 pod 还是 svc. Pod 走 findPods 查询方法，其他情况都走 findServices 方法。

```bash
func (k *Kubernetes) Services(ctx context.Context，state request.Request，exact bool，opt plugin.Options) (svcs []msg.Service，err error) {
    ...
	s，e := k.Records(ctx，state，false)
    ...
	internal := []msg.Service{}
	for _，svc := range s {
		if t，_ := svc.HostType(); t != dns.TypeCNAME {
			internal = append(internal，svc)
		}
	}

	return internal，e
}
```

```bash
func (k *Kubernetes) Records(ctx context.Context，state request.Request，exact bool) ([]msg.Service，error) {
	r，e := parseRequest(state.Name()，state.Zone)
    ...
	if r.podOrSvc == Pod {
		pods，err := k.findPods(r，state.Zone)
		return pods，err
	}

	services，err := k.findServices(r，state.Zone)
	return services，err
}
```

findServices：

* 如果 service 是 headless 类型，则返回 service endoptins 地址
* 如果 service 类型是 ClusterIP，则返回 clusterIP 这个 vip
* 如果 service 有绑定 ExternalName，则需要返回 CNAME 记录
```bash
func (k *Kubernetes) findServices(r recordRequest，zone string) (services []msg.Service，err error) {
	if !k.namespaceExposed(r.namespace) {
		return nil，errNoItems
	}
    ...
	idx := object.ServiceKey(r.service，r.namespace)
	serviceList = k.APIConn.SvcIndex(idx)
	endpointsListFunc = func() []*object.Endpoints { return k.APIConn.EpIndex(idx) }

	zonePath := msg.Path(zone，coredns)
	for _，svc := range serviceList {
        ...
		// External service
		if svc.Type == api.ServiceTypeExternalName {
			s := msg.Service{Key: strings.Join([]string{zonePath，Svc，svc.Namespace，svc.Name}，"/")，Host: svc.ExternalName，TTL: k.ttl}
			if t，_ := s.HostType(); t == dns.TypeCNAME {
				s.Key = strings.Join([]string{zonePath，Svc，svc.Namespace，svc.Name}，"/")
				services = append(services，s)

				err = nil
			}
			continue
		}

		// Endpoint query or headless service
		if svc.Headless() || r.endpoint != "" {
            ...
			for _，ep := range endpointsList {
                ...
				for _，eps := range ep.Subsets {
					for _，addr := range eps.Addresses {
                        ...
						for _，p := range eps.Ports {
                            ...
							services = append(services，s)
						}
					}
				}
			}
			continue
		}

		// ClusterIP service
		for _，p := range svc.Ports {
            ...
			for _，ip := range svc.ClusterIPs {
				s := msg.Service{Host: ip，Port: int(p.Port)，TTL: k.ttl}
				s.Key = strings.Join([]string{zonePath，Svc，svc.Namespace，svc.Name}，"/")
				services = append(services，s)
			}
		}
	}
	return services，err
}
```

findPods()：

* 处理 podname 的域名解析的方法，其内部调用 dnsController 里的 podLister.ByIndex 来获取 pod
* podLister 内部维护了 indexer 索引和 store 存储，查询条件是格式化过的 podname
```bash
func (k *Kubernetes) findPods(r recordRequest，zone string) (pods []msg.Service，err error) {
    ...
	for _，p := range k.APIConn.PodIndex(ip) {
		// check for matching ip and namespace
		if ip == p.PodIP && match(namespace，p.Namespace) {
			s := msg.Service{Key: strings.Join([]string{zonePath，Pod，namespace，podname}，"/")，Host: ip，TTL: k.ttl}
			pods = append(pods，s)

			err = nil
		}
	}
	return pods，err
}
```

# 总结

coredns 众多功能都是使用 plugin 插件来实现的，包括 cache 和 log 等功能. kubernetes dns 解析也是通过 plugin 实现的. kubernetes plugin 的源码和原理，相比其他 k8s 组件来说好理解的多，简化流程如下：

* coredns 启动时初始化 kubernetes 插件，并装载注册插件
* 插件 kubernetes 中有个 dnscontroller 控制器，它会实例化 service/pods/endpoints/ns 等资源的 informer 并发起监听. 当这些资源发生变更时，会修改 informer 关联的 indexer 索引存储对象
* 当 coredns 有查询请求到来时，尝试从 indexer 获取对象，然后返回组装的 dns 数据
  * 域名为 pod 特征
  * 从 podIndexer 中获取 podIP
  * 当查询的 service 为 externalName 时，则返回 CNAME 记录
  * 当查询的 service 为 ClusterNone or headless 时，则返回 service 对应的 endpoints 地址
  * 当查询的 service 为 ClusterIP 时，则返回 service 的 clusterIP

kubernetes 插件核心处理流程如下所示：

![](/images/2024-01-09-kubernetes-coredns/3.png)

# 参考资料

* https://github.com/coredns/deployment/blob/master/kubernetes/CoreDNS-k8s_version.md
* https://coredns.io/plugins/kubernetes/
* https://github.com/kubernetes/dns/blob/master/docs/specification.md
* https://github.com/coredns/coredns/issues/5495
* https://github.com/coredns/coredns/pull/5191
