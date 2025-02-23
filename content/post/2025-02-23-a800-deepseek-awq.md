---
layout:     post
title:      "A800 单机8卡体验 DeepSeek-R1-AWQ 量化满血版之旅"
subtitle:   "A800 单机8卡体验 DeepSeek-R1-AWQ 量化满血版之旅"
description: ""
author: "陈谭军"
date: 2025-02-23
published: true
tags:
    - AI
    - 大模型
    - DeepSeek
categories:
    - TECHNOLOGY
showtoc: true
---

# 硬件与系统环境要求

## 硬件配置

* GPU: 8× NVIDIA A800 80GB 
* 显存要求: 每卡80GB
* 系统内存: ≥32GB (用于交换空间)
* CPU：lscpu | grep "Model name"  值：Model name: Intel(R) Xeon(R) Platinum 8350C CPU @ 2.60GHz
* CPU架构：lscpu | grep Architecture 值：Architecture: x86_64
* MEM：free -g
* HDD/SDD lsblk

## 软件环境

* 操作系统（OS）: CentOS release 7.6 (Final)
* 内核： uname -a 5.10.0-1.0.0.41 #1 SMP Mon Nov 25 08:24:56 UTC 2024 x86_64 x86_64 x86_64 GNU/Linux
* 驱动版本: NVIDIA-SMI 535.183.06 Driver Version: 535.183.06  CUDA Version: 12.2
* Docker：docker version 20.10.5

# 获取模型与框架

## 下载量化版模型文件
 
方式一：
```bash
git clone 
https://huggingface.co/cognitivecomputations/DeepSeek-R1-AWQ
```

方式二：
```bash
pip install modelscope
from modelscope.hub.snapshot_download import snapshot_download
model_dir = snapshot_download('cognitivecomputations/DeepSeek-R1-awq', cache_dir='/root/model/modelscope')
print(f"Model downloaded to: {model_dir}")
```

cognitivecomputations/DeepSeek-R1-awq 大约 340G；

## 准备vLLM框架

准备测试镜像：vllm/vllm-openai:v0.7.2

# 运行模型

部署 vllm 服务，如下所示：

```bash
# 模型权重路径
export MODEL_PATH=/ssd1/deepseek/model

docker run -id --runtime nvidia --gpus all \
    --net=host \
    --ipc=host \
    --privileged \
    --entrypoint "" \
    --name=vllm-test \
    -v $MODEL_PATH:/workspace \
    -v /dev/shm:/dev/shm \
    -w /workspace \
    vllm/vllm-openai:v0.7.2 \
    /bin/bash
```

进入到 vllm 部署 DeepSeek-R1-awq  模型服务，如下所示：
```bash
docker exec -it vllm-test /bin/bash

export VLLM_HOST_IP=$(hostname -I | awk '{print $1}')
export HOST_IP=$VLLM_HOST_IP

python3 -m vllm.entrypoints.openai.api_server --host 0.0.0.0 --port 12345 --max-model-len 65536 --trust-remote-code --tensor-parallel-size 8 --quantization moe_wna16 --gpu-memory-utilization 0.90 --kv-cache-dtype fp8_e5m2 --calculate-kv-scales --served-model-name deepseek-reasoner --model /workspace/DeepSeek-R1-awq

# 守护进程
nohup python3 -m vllm.entrypoints.openai.api_server --host 0.0.0.0 --port 12345 --max-model-len 65536 --trust-remote-code --tensor-parallel-size 8 --quantization moe_wna16 --gpu-memory-utilization 0.90 --kv-cache-dtype fp8_e5m2 --calculate-kv-scales --served-model-name deepseek-reasoner --model /workspace/DeepSeek-R1-awq > out.file 2>&1 &
```

# 请求测试

另启动一个终端进入 DeepSeek-R1-awq  模型服务，发送 API 测试请求；
备注：stream 设置为 true，则是流式请求；

```bash
docker exec -it vllm-test bash

export IP=$(hostname -i):12345

curl --request POST \
  -H "Content-Type: application/json" \
  --url $IP/v1/chat/completions \
  --data '{
    "messages":[
      {"role":"user","content":"你好，给我推荐中国适合旅游的地方"}
    ],
    "stream": false,
    "model": "deepseek-reasoner"
  }'
```

返回结果：

```bash
root@a800-test01:/workspace# curl --request POST \
  -H "Content-Type: application/json" \
  --url $IP/v1/chat/completions \
  --data '{
    "messages":[
      {"role":"user","content":"你好，给我推荐中国适合旅游的地方"}
    ],
    "stream": false,
    "model": "deepseek-reasoner"
  }'
{"id":"chatcmpl-eb7377e79fbc48d899475c68497bb8ed","object":"chat.completion","created":1739715780,"model":"deepseek-reasoner","choices":[{"index":0,"message":{"role":"assistant","reasoning_content":null,"content":"<think>\n\n</think>\n\n中国拥有丰富多彩的旅游资源，不同地区各具特色。以下是几个适合旅游的推荐目的地：\n\n### 一、自然风光类\n1. **云南·香格里拉**  \n   - **亮点**：普达措国家公园、松赞林寺、梅里雪山  \n   - **特色**：高原草甸、藏族文化、雪山湖泊  \n\n2. **四川·九寨沟**  \n   - **亮点**：五彩池、诺日朗瀑布、长海  \n   - **特色**：世界自然遗产，以钙华池、彩林和清澈湖水闻名。\n\n3. **广西·桂林**  \n   - **亮点**：漓江、阳朔西街、龙脊梯田  \n   - **特色**：“山水甲天下”，喀斯特地貌与田园风光融合。\n\n4. **新疆·喀纳斯**  \n   - **亮点**：喀纳斯湖、禾木村、图瓦人村落  \n   - **特色**：神秘湖怪传说、秋季彩林、原始村落。\n\n---\n\n### 二、历史人文类\n1. **北京**  \n   - **亮点**：故宫、长城（推荐慕田峪、司马台）、颐和园  \n   - **特色**：明清皇家文化、胡同与四合院。\n\n2. **陕西·西安**  \n   - **亮点**：兵马俑、大雁塔、古城墙  \n   - **特色**：十三朝古都，丝路起点，美食（肉夹馍、羊肉泡馍）。\n\n3. **浙江·杭州**  \n   - **亮点**：西湖、灵隐寺、西溪湿地  \n   - **特色**：江南水乡，茶文化（龙井茶），南宋遗迹。\n\n4. **西藏·拉萨**  \n   - **亮点**：布达拉宫、大昭寺、八廓街  \n   - **特色**：藏传佛教圣地，高原风情。\n\n---\n\n### 三、小众深度游类\n1. **福建·泉州**  \n   - **亮点**：开元寺、蟳埔村、崇武古城  \n   - **特色**：海上丝绸之路起点，闽南文化融合（宗教、建筑、美食）。\n\n2. **贵州·肇兴侗寨**  \n   - **亮点**：侗族鼓楼、堂安梯田、侗族大歌  \n   - **特色**：原生态侗族村落，非遗文化体验。\n\n3. **甘肃·敦煌**  \n   - **亮点**：莫高窟、鸣沙山月牙泉、阳关遗址  \n   - **特色**：丝路明珠，壁画艺术与沙漠奇观。\n\n---\n\n### 四、季节限定类\n- **春季**（3-5月）：江西婺源（油菜花）、无锡鼋头渚（樱花）  \n- **冬季**（12-2月）：哈尔滨冰雪大世界、吉林长白山（滑雪、温泉）\n\n---\n\n### 旅行小贴士：\n1. **高原地区**（如西藏、香格里拉）需注意防高反，避免剧烈运动。  \n2. **热门景区**（如九寨沟、故宫）建议提前预约门票，错峰出行。  \n3. **饮食**：尝试当地特色时，适量为主（如云南菌子、藏餐酥油茶）。\n\n希望你能在旅途中感受到中国的自然之美与文化底蕴！如果有具体偏好（如徒步、美食、摄影），可以进一步为你定制路线哦~ 😊","tool_calls":[]},"logprobs":null,"finish_reason":"stop","stop_reason":null}],"usage":{"prompt_tokens":11,"total_tokens":742,"completion_tokens":731,"prompt_tokens_details":null},"prompt_logprobs":null}root@gajl-inf-sci-k8s-a800-hbxgn6-0587:/workspace# 
```

# 参考

1、[cognitivecomputations/DeepSeek-R1-AWQ](https://huggingface.co/cognitivecomputations/DeepSeek-R1-AWQ)
