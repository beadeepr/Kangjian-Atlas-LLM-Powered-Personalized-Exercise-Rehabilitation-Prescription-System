# 后端自动化测试报告

- 测试时间：2026-06-26T01:35:08.165878+00:00
- 总用例数：16
- 通过：14
- 失败：2
- 状态：failed

## 用例明细

| 用例 | 状态 | 说明 |
|------|------|------|
| 健康检查 | passed | 通过 |
| 生产存储栈配置 | passed | 通过 |
| 用户注册与登录 | passed | 通过 |
| 患者档案 CRUD | passed | 通过 |
| 红旗症状处方拦截 | passed | 通过 |
| 处方生成与导出 | passed | 通过 |
| 训练打卡与趋势统计 | failed | 
Traceback (most recent call last):
  File "D:\project\KALPPERPS\Kangjian-Atlas-LLM-Powered-Personalized-Exercise-Rehabilitation-Prescription-System\backend\run_backend_tests.py", line 46, in record
    detail = fn() or "通过"
             ~~^^
  File "D:\project\KALPPERPS\Kangjian-Atlas-LLM-Powered-Personalized-Exercise-Rehabilitation-Prescription-System\backend\run_backend_tests.py", line 274, in training_flow
    assert response.json()["total_checkins"] >= 1
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
 |
| 实时动作纠正接口 | passed | 通过 |
| RTMPose流式推理接口 | passed | 通过 |
| 3D骨骼与AR叠加服务 | passed | 通过 |
| 语音纠错提示 | passed | 通过 |
| 医生协同与处方动态调整闭环 | passed | 通过 |
| 康复进度报告 | failed | 
Traceback (most recent call last):
  File "D:\project\KALPPERPS\Kangjian-Atlas-LLM-Powered-Personalized-Exercise-Rehabilitation-Prescription-System\backend\run_backend_tests.py", line 46, in record
    detail = fn() or "通过"
             ~~^^
  File "D:\project\KALPPERPS\Kangjian-Atlas-LLM-Powered-Personalized-Exercise-Rehabilitation-Prescription-System\backend\run_backend_tests.py", line 502, in progress_report_flow
    assert data["total_checkins"] >= 1
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
 |
| 知识科普与问答 | passed | 通过 |
| 后台管理统计与反馈 | passed | 通过 |
| 管理员知识库权限与维护 | passed | 通过 |

## 备注

覆盖健康检查、认证、患者档案、处方导出、训练打卡、管理员知识库维护等后端主流程。
