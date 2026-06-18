# 动作图示与示范视频素材指南

将图片放入 `frontend/assets/actions/{动作ID}.png`，将 B 站链接填入 `frontend/config.js` 对应动作的 `videoUrl`。
文件名对照表见 `actions/README.md`。

```javascript
videoUrl: "https://www.bilibili.com/video/BVxxxxxxxx",
videoHint: "B站搜索：...",  // videoUrl 为空时显示
```

## 素材来源建议（请自行筛选，注意版权与医学准确性）

| 类型 | 推荐来源 | 说明 |
|------|----------|------|
| 示意图 | 手绘（Figma / Excalidraw / PPT 导出 SVG） | 实训答辩最稳妥，可标注关键角度 |
| 示意图 | 开源医学插图（如 OpenStax、Wikimedia Commons） | 需注明出处，选 CC 协议素材 |
| 示意图 | 医院康复科宣教册扫描（需授权） | 仅作课程演示时向老师确认 |
| 短视频 | B 站康复科普账号 | 搜索「动作名 + 康复 / 物理治疗」 |
| 短视频 | YouTube（需翻墙，答辩慎用） | 可找 McKenzie、Bob & Brad 等频道作参考 |

**不建议**：直接爬取商业网站图片、未授权的医院宣传册、来源不明的短视频。

---

## 17 个知识库动作 + 1 个算法扩展动作

### 颈部

| ID | 名称 | 示意图建议 | B 站搜索关键词 | 优先替换 |
|----|------|------------|--------------|----------|
| `neck_chin_tuck` | 下巴回收训练 | 侧面剪影，标下巴水平后移 | `下巴回收训练 颈椎` `Chin Tuck 中文` | ⭐ 高 |
| `neck_side_bend` | 颈部侧屈拉伸 | 正面/侧面，标耳朵靠肩方向 | `颈部侧屈拉伸 颈椎病` | ⭐ 高 |
| `chin_tuck` | 收下巴训练 | 侧面，标「后脑勺贴衣领」 | `收下巴 颈深屈肌` `头前伸纠正` | ⭐ 高 |

### 肩背部

| ID | 名称 | 示意图建议 | B 站搜索关键词 | 优先替换 |
|----|------|------------|--------------|----------|
| `scapular_retraction` | 肩胛后缩训练 | 背面，箭头示肩胛向脊柱夹紧 | `肩胛后缩 圆肩` `Scapular Retraction` | ⭐ 高 |
| `thoracic_extension` | 胸椎伸展训练 | 坐姿侧面，区分胸椎与腰椎 | `胸椎伸展 坐姿挺胸` | 中 |
| `shoulder_pendulum` | 肩关节钟摆运动 | 体前屈，手臂下垂摆动轨迹 | `肩关节钟摆 肩周炎` `Codman 钟摆` | 中 |
| `shoulder_external_rotation` | 肩外旋弹力带训练 | 正面，肘贴身体、前臂外旋 | `肩外旋 弹力带 肩袖` | 中 |

### 腰部 / 核心

| ID | 名称 | 示意图建议 | B 站搜索关键词 | 优先替换 |
|----|------|------------|--------------|----------|
| `cat_cow` | 猫牛式脊柱松动 | 四点跪位拱背/塌腰两帧 | `猫牛式 腰痛` `Cat Cow 中文` | ⭐ 高 |
| `pelvic_tilt` | 骨盆后倾训练 | 仰卧侧面，腰椎贴地 | `骨盆后倾 腰背贴地` | 中 |
| `bird_dog` | 鸟狗式核心训练 | 俯视角，对侧手脚伸展 | `鸟狗式 Bird Dog` | 中 |
| `dead_bug` | 死虫式核心训练 | 仰卧，对侧手脚下放 | `死虫式 Dead Bug 腰痛` | 中 |
| `glute_bridge` | 臀桥训练 | 侧面，肩髋膝一线 | `臀桥 臀肌激活` `Glute Bridge 中文` | ⭐ 高 |
| `mckenzie_press_up` | 麦肯基俯卧撑 | 俯卧撑起，骨盆贴地 | `麦肯基疗法 俯卧撑` `McKenzie 腰椎` | 中 |

### 膝 / 踝

| ID | 名称 | 示意图建议 | B 站搜索关键词 | 优先替换 |
|----|------|------------|--------------|----------|
| `wall_squat` | 靠墙静蹲 | 侧面，膝不过脚尖 | `靠墙静蹲 膝痛康复` | ⭐ 高 |
| `straight_leg_raise` | 直腿抬高训练 | 仰卧抬腿约 30° | `直腿抬高 SLR 康复` | 中 |
| `quad_set` | 股四头肌等长收缩 | 膝下毛巾、大腿绷紧特写 | `股四头肌等长收缩 膝术后` | 中 |
| `calf_stretch` | 小腿后侧拉伸 | 弓步拉墙，后脚跟着地 | `小腿拉伸 跟腱` `腓肠肌拉伸` | 中 |
| `ankle_pump` | 踝泵运动 | 足背伸/跖屈对比两帧 | `踝泵运动 血栓预防` | 低 |

---

## 答辩前最低工作量建议（5–8 个高频动作）

优先替换示意图 + 填入 `videoUrl`：

1. `neck_side_bend` — 颈椎病处方最常见  
2. `chin_tuck` 或 `neck_chin_tuck` — 与上条二选一或都做  
3. `wall_squat` — 跟练演示效果好  
4. `scapular_retraction` — 久坐肩颈场景  
5. `cat_cow` — 腰痛场景  
6. `glute_bridge` — 腰痛 / 臀肌无力  
7. `glute_bridge` / `straight_leg_raise` — 膝关节场景二选一  
8. `calf_stretch` 或 `ankle_pump` — 踝部场景  

## 重新生成占位图

已移除自动生成的火柴人占位图。请自行上传真实示意图。

## 与知识库对齐说明

- `ACTION_CATALOG` 的 `id`、`name`、`description`、`contraindications`、`sets`、`reps`、`frequency` 已与 `knowledge/actions.json` 对齐。  
- `mckenzie_press_up` 为后端算法扩展动作，不在知识库 JSON 中，但处方 API 可能返回。  
- `chin_tuck` 与 `neck_chin_tuck` 在知识库中为两个条目；跟练算法统一走 `neck_chin_tuck`（见 `CATALOG_TO_BACKEND_ACTION_ID`）。
