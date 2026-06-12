# 前端 UI 文档

## 项目名称
康健图谱 — 基于大模型的个性化运动康复处方生成系统

## 1. 目标

为康复患者与医生提供清晰、简洁、易用的前端界面，支持问诊输入、处方展示、摄像头姿态检测与反馈。

## 2. 页面结构

### 2.1 首页（示例）

- 标题：`康健图谱（示例前端）`
- 问诊表单区
  - 输入框：主诉 `symptoms`
  - 按钮：生成处方 `submit`
  - 显示区：处方结果 `result`
- 摄像头区
  - 视频显示：`video`
  - 隐藏画布：`canvas`
  - 按钮：启动摄像头 `startCam`
  - 按钮：发送帧 `sendFrame`
  - 文本反馈：`feedback`

### 2.2 后续页面建议

- 登录/注册页面
- 患者首页：查看历史处方、康复进度
- 医生首页：患者管理、方案审核
- 知识库管理：动作列表、提示词编辑
- 设置页面：API地址、用户资料、系统配置

## 3. 样式规范

### 3.1 基础样式

- 字体：Segoe UI, Roboto, Helvetica Neue, Arial
- 页面间距：`padding: 16px`
- 版块边框：`border: 1px solid #eee`
- 圆角：`border-radius: 6px`
- 标题颜色：`#1a73e8`

### 3.2 颜色方案（推荐）

- 主色：`#1a73e8`
- 辅助色：`#34a853`、`#fbbc05`
- 背景：`#ffffff`
- 边框：`#eeeeee`
- 文本：`#202124`

### 3.3 按钮与交互

- 按钮间距：`margin-right: 8px`
- 按钮悬停：加深颜色、轻微阴影
- 文本区域：宽度 100%、高度 80px
- 表单标签：块级显示，便于移动端操作

## 4. UI 组件设计

### 4.1 问诊表单组件

功能：输入症状，提交并展示处方结果。

字段：
- `主诉`：多行文本输入
- `生成处方`：提交按钮
- `处方结果`：只读展示区域

交互流程：
1. 用户输入症状
2. 点击生成处方
3. 发起 API 请求
4. 展示返回结果

### 4.2 摄像头姿态检测组件

功能：启动摄像头、获取当前帧、发送后端纠正请求

元素：
- 视频预览
- 发送帧按钮
- 实时反馈文本显示

### 4.3 反馈展示组件

功能：呈现后端返回的康复处方或姿态纠正建议

要求：
- 文本格式清晰
- 关键提示强调（如安全注意事项）
- 支持复制、打印或下载

## 5. 前端交互流程

### 5.1 生成处方流程

1. 用户输入主诉
2. 点击`生成处方`
3. 前端构造请求体并调用 `/api/generate_prescription`
4. 后端返回 `PrescriptionResponse`
5. 前端展示 `summary` 和 `actions`

### 5.2 摄像头校准流程

1. 用户点击`启动摄像头`
2. 浏览器授权并显示视频
3. 用户点击`发送帧`
4. 前端采集图像并调用 `/api/correct_pose`
5. 展示 `feedback`

## 6. UI 扩展建议

- 增加表单校验：症状不能为空、年龄为数字
- 增加手机端适配：响应式布局、按钮自适应宽度
- 增加患者历史记录卡片
- 增加医生审核与修改入口
- 增加主题切换（浅色/深色）

## 7. 页面示例结构

```html
<section id="form">
  <h2>问诊表单</h2>
  <label>主诉<textarea id="symptoms"></textarea></label>
  <button id="submit">生成处方</button>
  <pre id="result"></pre>
</section>

<section id="camera">
  <h2>摄像头实时（示例）</h2>
  <video id="video" autoplay playsinline width="480" height="360"></video>
  <canvas id="canvas" width="480" height="360" style="display:none"></canvas>
  <div id="feedback"></div>
  <button id="startCam">启动摄像头</button>
  <button id="sendFrame">发送帧进行纠正（示例）</button>
</section>
```

## 8. 结语

当前 UI 为 MVP 原型，重点保证最小可用功能。后续可根据用户反馈迭代为完整康复管理平台界面。