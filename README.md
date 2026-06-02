# Mental Health Monitor

基于摄像头画面和视觉语言模型（VLM）的心理健康实时监测系统。通过分析面部表情、姿态、眼神等非语言信号，输出 13 个心理维度的评分和个性化疏导建议。

## 架构

```
摄像头 → Camera(camera.py) → Analyzer(analyzer.py) → vLLM API → Guidance(guidance.py) → Web UI
                              ↑                                              ↓
                         采集线程                                   建议生成 + 日志
```

- **camera.py**: 摄像头采集线程，10fps 捕获 + 人脸引导椭圆叠加
- **analyzer.py**: 调用 vLLM (Qwen3-VL-8B) 进行多帧视觉分析
- **guidance.py**: 13 维心理建议体系，覆盖低/中/高三档
- **web_app.py**: Flask 仪表盘，SSE 实时推送分析结果
- **logger.py**: JSONL 会话日志

## 13 个心理维度

| 维度 | 说明 |
|------|------|
| stress | 压力 — 皱眉、牙关紧咬、肩膀高耸 |
| fatigue | 疲劳 — 眼皮下垂、目光无神、打哈欠 |
| anxiety | 焦虑 — 坐立不安、眼神游移 |
| sadness | 悲伤 — 嘴角下拉、沮丧表情 |
| irritation | 易怒 — 表情烦躁、不耐烦 |
| focus | 专注力 — 目光是否稳定 |
| posture_tension | 姿态紧张 — 肩膀僵硬、身体蜷缩 |
| depression | 抑郁倾向 — 表情淡漠、缺乏生气 |
| emotional_stability | 情绪稳定性 — 表情波动 |
| eye_contact | 眼神接触 — 是否回避镜头 |
| sleep_deficit_signs | 睡眠不足 — 黑眼圈、目光涣散 |
| psychomotor_retardation | 精神运动迟缓 — 动作缓慢 |
| positive_affect_blunting | 积极情感钝化 — 缺乏积极表情 |
| **overall_distress** | 综合异常程度 |

## 快速开始

### 1. 启动 vLLM 服务器

需要一台 >= 24GB 显存的 GPU。

```powershell
.\start_vllm.ps1
```

或手动：

```bash
vllm serve Qwen/Qwen3-VL-8B-Instruct \
    --port 8000 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 16384 \
    --dtype bfloat16 \
    --enforce-eager \
    --trust-remote-code
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 修改配置

编辑 `config.py`，将 `vllm_api_url` 指向你的 vLLM 服务器地址：

```python
vllm_api_url: str = "http://localhost:8000/v1"
```

### 4. 启动

```bash
python web_app.py
```

浏览器打开 `http://localhost:5000`，点击"开始采集分析"。

## 工作原理

1. 摄像头采集 15 秒视频帧（5fps，共约 75 帧）
2. 自动裁剪面部区域，均匀采样 24 帧送模型
3. Qwen3-VL-8B 分析帧序列，输出 13 维 JSON 评分
4. 系统根据评分生成分级疏导建议（低/中/高三档）
5. 结果通过 SSE 实时推送到 Web 仪表盘

## 技术栈

- Python 3.11+
- OpenCV（摄像头采集 + 人脸检测）
- Flask + SSE（Web 仪表盘）
- Qwen3-VL-8B / vLLM（视觉语言模型推理）
- NumPy / Pillow（图像处理）

## 许可证

MIT
