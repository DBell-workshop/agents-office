# 一期 API 清单：导购培训与跨平台比价

## 1. 设计原则

- 所有接口都面向能力，不绑定具体页面
- 长耗时任务采用异步任务模型
- 关键结果返回 `trace_id` 以支持审计
- 所有写操作默认记录操作者身份
- 对不确定结果显式返回 `confidence` 和 `issue_flags`

## 2. 通用约定

### 2.1 认证

- 后台接口：Bearer Token
- 内部服务：Service Token 或 mTLS

### 2.2 通用响应

```json
{
  "trace_id": "trc_123",
  "request_id": "req_123",
  "data": {},
  "error": null
}
```

### 2.3 异步任务响应

```json
{
  "trace_id": "trc_123",
  "request_id": "req_123",
  "data": {
    "task_id": "task_123",
    "status": "pending"
  },
  "error": null
}
```

### 2.4 错误码建议

| 错误码 | 含义 |
| --- | --- |
| `INVALID_ARGUMENT` | 参数错误 |
| `UNAUTHORIZED` | 未认证或无权限 |
| `NOT_FOUND` | 资源不存在 |
| `CONFLICT` | 版本冲突或状态冲突 |
| `UPSTREAM_FAILURE` | 外部依赖失败 |
| `COLLECTION_FAILED` | 页面采集失败 |
| `NORMALIZATION_FAILED` | 字段标准化失败 |
| `EVALUATION_FAILED` | 评分失败 |

## 3. 导购培训接口

### 3.1 创建课程

`POST /api/v1/training/courses`

请求体：

```json
{
  "product_id": "prod_001",
  "objective": "新品首销导购训练",
  "required_points": [
    "核心卖点 1",
    "核心卖点 2"
  ],
  "target_audience": "门店导购"
}
```

返回：

```json
{
  "trace_id": "trc_001",
  "request_id": "req_001",
  "data": {
    "course_id": "course_001",
    "status": "draft"
  },
  "error": null
}
```

### 3.2 生成训练内容

`POST /api/v1/training/courses/{course_id}:generate-content`

请求体：

```json
{
  "script_style": "natural",
  "scene": "门店首推",
  "language": "zh-CN"
}
```

返回：

```json
{
  "trace_id": "trc_002",
  "request_id": "req_002",
  "data": {
    "task_id": "task_gen_001",
    "status": "pending"
  },
  "error": null
}
```

### 3.3 获取训练内容任务结果

`GET /api/v1/training/content-tasks/{task_id}`

返回要点：

- 训练卡文本
- 话术稿
- 模拟问答
- evidence_refs
- content_version

### 3.4 生成示范语音

`POST /api/v1/training/contents/{content_id}:synthesize-audio`

请求体：

```json
{
  "voice": "female_warm",
  "speed": 1.0
}
```

返回：

```json
{
  "trace_id": "trc_003",
  "request_id": "req_003",
  "data": {
    "audio_id": "audio_001",
    "audio_url": "https://example.com/audio_001.mp3",
    "duration_ms": 68400
  },
  "error": null
}
```

### 3.5 提交导购练习

`POST /api/v1/training/attempts`

请求体：

```json
{
  "course_id": "course_001",
  "user_id": "user_001",
  "audio_url": "https://example.com/attempt_001.m4a"
}
```

返回：

```json
{
  "trace_id": "trc_004",
  "request_id": "req_004",
  "data": {
    "attempt_id": "attempt_001",
    "status": "submitted"
  },
  "error": null
}
```

### 3.6 发起练习点评

`POST /api/v1/training/attempts/{attempt_id}:evaluate`

请求体：

```json
{
  "rubric_version": "v1"
}
```

返回：

```json
{
  "trace_id": "trc_005",
  "request_id": "req_005",
  "data": {
    "task_id": "task_eval_001",
    "status": "pending"
  },
  "error": null
}
```

### 3.7 获取点评报告

`GET /api/v1/training/evaluation-tasks/{task_id}`

返回要点：

```json
{
  "trace_id": "trc_006",
  "request_id": "req_006",
  "data": {
    "report_id": "report_001",
    "attempt_id": "attempt_001",
    "transcript": "...",
    "scores": {
      "accuracy": 82,
      "coverage": 75,
      "fluency": 68,
      "naturalness": 80,
      "compliance": 90
    },
    "issues": [
      {
        "type": "fact_error",
        "timestamp_ms": 22100,
        "content": "将 12 期免息讲成了 24 期免息",
        "evidence_ref": "prod_doc_12"
      }
    ],
    "suggestions": [
      "先介绍核心卖点，再说明优惠权益"
    ],
    "rubric_version": "v1"
  },
  "error": null
}
```

### 3.8 店长复核

`POST /api/v1/training/reports/{report_id}:review`

请求体：

```json
{
  "reviewer_id": "manager_001",
  "review_decision": "needs_retry",
  "comment": "卖点顺序还可以更聚焦"
}
```

## 4. 跨平台比价接口

### 4.1 创建比价任务

`POST /api/v1/comparison/tasks`

请求体：

```json
{
  "source_product_id": "prod_001",
  "targets": [
    {
      "platform": "jd",
      "url": "https://item.jd.com/xxx"
    },
    {
      "platform": "taobao",
      "url": "https://detail.tmall.com/xxx"
    }
  ]
}
```

返回：

```json
{
  "trace_id": "trc_101",
  "request_id": "req_101",
  "data": {
    "task_id": "cmp_001",
    "status": "pending"
  },
  "error": null
}
```

### 4.2 采集页面

`POST /api/v1/comparison/tasks/{task_id}:collect`

说明：

- 该接口由工作流调用
- 内部由 `OpenClaw Collector Adapter` 实现

请求体：

```json
{
  "template_version": "jd_v1"
}
```

返回：

```json
{
  "trace_id": "trc_102",
  "request_id": "req_102",
  "data": {
    "collection_job_id": "job_001",
    "status": "pending"
  },
  "error": null
}
```

### 4.3 获取采集结果

`GET /api/v1/comparison/collections/{collection_job_id}`

返回要点：

```json
{
  "trace_id": "trc_103",
  "request_id": "req_103",
  "data": {
    "collection_job_id": "job_001",
    "platform": "jd",
    "status": "succeeded",
    "raw_fields": {
      "price_text": "到手价 2999",
      "coupon_text": "领券减 200"
    },
    "snapshot_id": "snap_001",
    "screenshot_urls": [
      "https://example.com/s1.png"
    ]
  },
  "error": null
}
```

### 4.4 标准化平台字段

`POST /api/v1/comparison/tasks/{task_id}:normalize`

请求体：

```json
{
  "rule_version": "offer_v1"
}
```

返回字段建议：

- `base_price`
- `coupon_discount`
- `instant_discount`
- `gift_items`
- `membership_benefits`
- `installment_terms`
- `trade_in_benefits`
- `final_price`
- `issue_flags`
- `confidence`

### 4.5 生成对比报告

`POST /api/v1/comparison/tasks/{task_id}:analyze`

返回：

```json
{
  "trace_id": "trc_104",
  "request_id": "req_104",
  "data": {
    "report_id": "cmp_report_001",
    "status": "ready"
  },
  "error": null
}
```

### 4.6 获取对比报告

`GET /api/v1/comparison/reports/{report_id}`

返回要点：

```json
{
  "trace_id": "trc_105",
  "request_id": "req_105",
  "data": {
    "report_id": "cmp_report_001",
    "comparable_type": "same_sku",
    "offers": [
      {
        "platform": "jd",
        "final_price": 2999,
        "gift_items": ["耳机"],
        "confidence": 0.92
      },
      {
        "platform": "taobao",
        "final_price": 3099,
        "gift_items": [],
        "confidence": 0.88
      }
    ],
    "deltas": [
      "京东到手价低 100 元",
      "京东有赠品，淘宝无赠品"
    ],
    "recommendations": [
      "若目标是短期转化，可优先关注赠品策略差异"
    ],
    "issue_flags": []
  },
  "error": null
}
```

### 4.7 运营复核

`POST /api/v1/comparison/reports/{report_id}:review`

请求体：

```json
{
  "reviewer_id": "ops_001",
  "decision": "accepted",
  "comment": "同款判断可信，可用于今日策略会"
}
```

## 5. 共用治理接口

### 5.1 获取审计记录

`GET /api/v1/audit/traces/{trace_id}`

返回内容建议：

- 请求发起人
- 工作流步骤
- 使用的模型与版本
- 使用的知识版本
- 采集模板版本
- 人工修订与复核记录

### 5.2 获取试点指标

`GET /api/v1/metrics/trials`

查询参数示例：

- `scenario=training`
- `scenario=comparison`
- `date_from=2026-03-01`
- `date_to=2026-03-10`

## 6. 内部服务接口建议

这些接口不一定直接暴露给前端，但建议作为服务边界存在：

- `POST /internal/v1/rag/query`
- `POST /internal/v1/tts/synthesize`
- `POST /internal/v1/asr/transcribe`
- `POST /internal/v1/scoring/evaluate`
- `POST /internal/v1/openclaw/collect`
- `POST /internal/v1/offers/normalize`
- `POST /internal/v1/risk/audit`

## 7. 幂等与重试

- 创建课程和创建比价任务支持 `Idempotency-Key`
- 采集任务和点评任务失败后支持有限次数重试
- 重试必须保留原始失败原因和最后一次结果

## 8. 安全要求

- 音频、截图、页面快照默认按敏感数据处理
- OpenClaw 登录会话不得明文暴露给业务侧
- 接口日志中避免记录用户原始敏感信息
- 所有复核接口必须记录操作者身份和时间
