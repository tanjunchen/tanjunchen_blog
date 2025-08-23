---
layout:     post
title:      "NVIDIA GPU 系统诊断与运维排查手册：常用命令与一键脚本指南"
subtitle:   "全面掌握 GPU 系统诊断：从硬件到驱动的一站式排查指南"
description: "本文系统整理了在使用 NVIDIA GPU 及其他加速卡时常见的系统诊断工具与命令，覆盖硬件信息、操作系统状态、内核日志、网络互联（OFED/Fabric）、IPMI 管理以及 NVIDIA 专属监控工具（如 nvidia-smi、nvidia-bug-report.sh） 等关键维度，为 GPU 用户提供全面的系统诊断工具箱。"
author: "陈谭军"
date: 2024-10-26
published: true
tags:
    - GPU
    - NVIDIA
    - 大模型
categories:
    - TECHNOLOGY
showtoc: true
---

# GPU 常见排查工具与命令

## 查看系统信息

| 检查项             | 命令/方法                                                                 | 说明 |
|--------------------|--------------------------------------------------------------------------|------|
| 硬件厂商           | `dmidecode -t system` (提取 Manufacturer)                                | 获取系统制造商信息 |
| CPU 型号           | `awk -F': ' '/model name/{print $2; exit}' /proc/cpuinfo`               | 提取 CPU 型号名称 |
| 操作系统           | `awk -F'"' '/PRETTY_NAME/{print $2}' /etc/os-release`                   | 显示操作系统名称（如 Ubuntu 20.04） |
| 内核版本           | `uname -r`                                                               | 查看当前运行的内核版本 |
| OFED 版本          | `ofed_info -s`                                                           | 查看 InfiniBand OFED 驱动版本 |
| 主机 IP            | `hostname -I \| awk '{print $1}'`                                        | 获取主机第一个 IP 地址 |
| 内核日志           | `dmesg`                                                                  | 打印或控制内核环形缓冲区 |
| 系统日志           | `cat /var/log/messages`                                                  | 查看系统日志消息（常见于较老系统） |
| OS 信息            | `cat /etc/issue`<br>`uname -r`<br>`cat /etc/*-release`                   | 收集操作系统发行版、内核版本等详细信息 |
| Fabric 日志        | `cat /var/log/fabricmanager.log`                                         | 查看 NVIDIA Fabric Manager 日志 |
| 内核模块           | `lsmod`                                                                  | 显示当前已加载的内核模块 |
| PCI 设备           | `lspci -tv`<br>`lspci -vvd 10de:`<br>`lspci -vvv`<br>`lspci -xxxx`       | 以不同详细级别查看 PCI 设备信息（特别是 NVIDIA 设备） |
| CPU 信息           | `lscpu`<br>`cpupower frequency-info`                                     | 显示 CPU 架构、核心数、频率等信息 |
| Systemd 日志       | `journalctl --since "10 days ago"`<br>`journalctl \| head -n 15000`      | 查看 systemd 管理的日志（按时间或行数限制） |
| IPMI 信息          | `ipmitool fru list`<br>`ipmitool sdr list`<br>`ipmitool sel list`        | 列出 IPMI 的 FRU（硬件资产）、传感器数据和系统事件日志 |
| NVIDIA 驱动        | `ls /sys/class/video/*`<br>`modinfo $(modprobe -n nvidia)`<br>`rpm -qa \| grep fabric` | 查看 NVIDIA 驱动模块文件及相关软件包 |
| NVIDIA SMI         | `nvidia-smi`<br>`nvidia-smi -q`<br>`nvidia-smi topo -m`                  | 查看 GPU 状态、详细信息及拓扑结构 |
| GPU ECC            | `nvidia-smi -q \| grep -A 5 "ECC Errors\|Memory Location\|Remapped Rows"` | 提取 GPU 的 ECC 错误和内存重映射情况 |
| NVIDIA Bug 报告    | `nvidia-bug-report.sh`                                                   | 运行 NVIDIA 官方错误报告脚本，生成诊断压缩包 |

## GPU 显存占用

使用 python 打印 GPU 显存占用信息脚本如下所示：
```python
import torch
import subprocess
from pynvml import *

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(torch.cuda.get_device_properties(device))
result = subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print(result.stdout)

nvmlInit()
handle = nvmlDeviceGetHandleByIndex(0)
uuid = nvmlDeviceGetUUID(handle)
print(f"gpu uuid {uuid} ")
info = nvmlDeviceGetMemoryInfo(handle)
print(f"总显存: {info.total}")
print(f"已使用显存: {info.used}")
print(f"剩余显存: {info.free}")

bytes_in_gb = 1024 ** 3
desired_memory_gb = 5
desired_memory_bytes = desired_memory_gb * bytes_in_gb
float_size = 4
num_floats = desired_memory_bytes // float_size
try:
  tensor = torch.cuda.FloatTensor(num_floats)
  print(f"success {desired_memory_gb} GB")
except RuntimeError as e:
  print(f"fail: {e}")
  info = nvmlDeviceGetMemoryInfo(handle)
  print(f"总显存: {info.total}")
  print(f"已使用显存: {info.used}")
  print(f"剩余显存: {info.free}")
nvmlShutdown()
```

## 一键统计 gpu 信息

```bash
#!/bin/bash

DATE=`date +%Y%m%d_%H%M%S`
HOSTNAME=$(cat /etc/hostname |awk -F '[.]' '{print $1 "." $2}')
SN=$(dmidecode -t system|grep -i "Serial Number" |awk '{print $3}')
LOG_DIR=gpulog_sn${SN}_${HOSTNAME}_${DATE}
LOG_NAME=gpulog_sn${SN}_${HOSTNAME}_${DATE}

mkdir -p ${LOG_DIR}
dmesg > ${LOG_DIR}/dmesg.log
cat /var/log/messages > ${LOG_DIR}/messages.log
cat /etc/issue >> ${LOG_DIR}/os_info.log
uname -r >> ${LOG_DIR}/os_info.log
cat /etc/*release >> ${LOG_DIR}/os_info.log
cat /var/log/fabricmanager.log >> ${LOG_DIR}/fabric_manger.log 2>>/dev/null

lsmod >>${LOG_DIR}/lsmod.log
lspci -tv > ${LOG_DIR}/lspci_tv.log
lspci -vvd 10de: > ${LOG_DIR}/lspci_gpu_vv.log 
lspci -vvv > ${LOG_DIR}/lspci_vv.log 
lspci -xxxx > ${LOG_DIR}/lspci_xxxx.log 
lscpu   > ${LOG_DIR}/lscpu.log
cpupower frequency-info  > ${LOG_DIR}/cpupower_frequency.log  2>>/dev/null 

journalctl --since `date -d "10 days ago" "+%Y-%m-%d"` > ${LOG_DIR}/journalctl_before_10_days.log 2>>/dev/null
journalctl | head -n 15000 > ${LOG_DIR}/journalctl_head_15000.log  2>>/dev/null

ipmitool fru list > ${LOG_DIR}/ipmi_fru.log  2>>/dev/null
ipmitool sdr list > ${LOG_DIR}/ipmi_sdr.log  2>>/dev/null
ipmitool sel list > ${LOG_DIR}/ipmi_sel.log  2>>/dev/null
ls /lib/modules/`uname -r`/kernel/drivers/video/*  > ${LOG_DIR}/nvidia-driver.log  2>>/dev/null
modinfo  /lib/modules/`uname -r`/kernel/drivers/video/nvidia.ko  >> ${LOG_DIR}/nvidia-driver.log
rpm -qa |grep -i fabric >>${LOG_DIR}/nvidia_fabric-manger.log
nvidia-smi > ${LOG_DIR}/nvidia-smi.log 2>>/dev/null 
nvidia-smi -q > ${LOG_DIR}/nvidia-smi_query.log 2>>/dev/null  
nvidia-smi -q | grep -A 9 "ECC Errors"|awk '{print $1,$2,$3,$4,$5}' >>${LOG_DIR}/gpu_ecc.log 2>>/dev/null
nvidia-smi -q |grep -i Remapping >> ${LOG_DIR}/gpu_ecc.log  2>>/dev/null
nvidia-smi topo -m > ${LOG_DIR}/nvidia-smi_topo.log 2>>/dev/null
nvidia-bug-report.sh  --output-file ${LOG_DIR}/nvidia-bug-report-sn${SN}_${HOSTNAME}.log  2>>/dev/null
tar -zcvf ${LOG_NAME}.tar.gz ${LOG_DIR}
rm -rf ${LOG_DIR}
```

## 常见排查问题命令

1. 基础信息收集
* 命令 : date +%Y%m%d_%H%M%S
    * 功能接口 : 时间戳获取
    * 用途说明 : 获取当前时间用于日志命名

* 命令 : cat /etc/hostname
    * 功能接口 : 主机名获取
    * 用途说明 : 获取系统主机名

* 命令 : dmidecode -t system
    * 功能接口 : 系统序列号获取
    * 用途说明 : 获取硬件序列号用于标识设备

1. 系统日志收集
* 命令 : dmesg
    * 功能接口 : 内核日志导出
    * 用途说明 : 导出内核环形缓冲区日志

* 命令 : cat /var/log/messages
    * 功能接口 : 系统消息日志
    * 用途说明 : 导出系统级消息日志

* 命令 : journalctl --since
    * 功能接口 : systemd日志查询
    * 用途说明 : 获取指定时间范围内的系统日志

* 命令 : journalctl | head -n 15000
    * 功能接口 : 最新日志截取
    * 用途说明 : 获取最新的系统日志记录


1. 操作系统信息
* 命令 : cat /etc/issue
    * 功能接口 : 系统提示信息
    * 用途说明 : 获取登录前的系统提示信息

* 命令 : uname -r
    * 功能接口 : 内核版本查询
    * 用途说明 : 获取当前运行的内核版本

* 命令 : cat /etc/*release
    * 功能接口 : 发行版信息
    * 用途说明 : 获取Linux发行版本详细信息


1. 硬件信息收集
* 命令 : lspci -tv
    * 功能接口 : PCI设备树状显示
    * 用途说明 : 以树状结构显示PCI设备连接关系

* 命令 : lspci -vvd 10de:
    * 功能接口 : NVIDIA GPU详细信息
    * 用途说明 : 显示NVIDIA GPU设备的详细配置

* 命令 : lspci -vvv
    * 功能接口 : PCI设备详细信息
    * 用途说明 : 显示所有PCI设备的详细信息

* 命令 : lspci -xxxx
    * 功能接口 : PCI配置空间
    * 用途说明 : 显示PCI设备的完整配置空间内容

* 命令 : lscpu
    * 功能接口 : CPU架构信息
    * 用途说明 : 显示CPU架构、核心数等信息

* 命令 : cpupower frequency-info
    * 功能接口 : CPU频率信息
    * 用途说明 : 显示CPU频率调节相关信息


1. 内核模块信息
* 命令 : lsmod
    * 功能接口 : 已加载模块列表
    * 用途说明 : 列出当前已加载的内核模块

* 命令 : ls /lib/modules/uname -r/kernel/drivers/video/*
    * 功能接口 : 视频驱动模块列表
    * 用途说明 : 列出视频驱动目录下的内核模块

* 命令 : modinfo /lib/modules/uname -r/kernel/drivers/video/nvidia.ko
    * 功能接口 : 驱动模块信息
    * 用途说明 : 显示NVIDIA驱动模块的详细信息


1. IPMI管理信息
* 命令 : ipmitool fru list
    * 功能接口 : FRU信息查询
    * 用途说明 : 获取固件/硬件可更换单元信息

* 命令 : ipmitool sdr list
    * 功能接口 : 传感器数据
    * 用途说明 : 获取系统传感器数据记录

* 命令 : ipmitool sel list
    * 功能接口 : 系统事件日志
    * 用途说明 : 获取系统事件日志记录


1. NVIDIA GPU 状态监控
* 命令 : nvidia-smi
    * 功能接口 : GPU基本状态
    * 用途说明 : 显示GPU温度、使用率、显存等基本信息

* 命令 : nvidia-smi -q
    * 功能接口 : GPU详细查询
    * 用途说明 : 显示GPU的详细状态信息

* 命令 : nvidia-smi -q | grep -A 9 "ECC Errors"
    * 功能接口 : ECC错误信息
    * 用途说明 : 提取GPU ECC内存错误信息

* 命令 : nvidia-smi -q | grep -i Remapping
    * 功能接口 : 内存重映射信息
    * 用途说明 : 获取GPU内存重映射相关信息

* 命令 : nvidia-smi topo -m
    * 功能接口 : GPU拓扑结构
    * 用途说明 : 显示GPU之间的连接拓扑关系

* 命令 : nvidia-bug-report.sh
    * 功能接口 : 官方诊断报告
    * 用途说明 : 运行NVIDIA官方诊断脚本生成完整报告

1. 软件包与服务信息
* 命令 : rpm -qa | grep -i fabric
    * 功能接口 : Fabric Manager 检查
    * 用途说明 : 检查是否安装NVIDIA Fabric Manager【机器有 NVLink 就需要开启】

* 命令 : cat /var/log/fabricmanager.log
    * 功能接口 : Fabric Manager日志
    * 用途说明 : 收集Fabric Manager服务日志

