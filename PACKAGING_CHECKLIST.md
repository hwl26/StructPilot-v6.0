# StructPilot v5.1 提交文件清单

**版本**: v5.1 优化版  
**提交日期**: 2026-01-15  
**打包日期**: 待执行 `prepare_final_submission.bat`

---

## 📁 必须包含的文件和目录

### 1. 核心源代码 ✅
```
StructPilot_v5.1/
├── main.py                          # 主程序入口（5015 行）
├── version.py                       # 版本信息
├── requirements.txt                 # Python 依赖包列表
├── requirements-dev.txt             # 开发依赖（可选）
├── start.bat                        # Windows 启动脚本
└── __init__.py                      # 包初始化文件
```

### 2. 代理模块 ✅
```
agents/
├── __init__.py
├── llm_agent.py                     # LLM 接口代理（支持 OpenAI/Anthropic/Gemini）
├── expert_agent.py                  # 专家问答代理
├── navigator_agent.py               # 流程导航代理
├── sop_agent.py                     # SOP 推理代理
├── memory_agent.py                  # 会话持久化代理（SQLite）
└── smart_qa_engine.py               # 智能问答引擎（6项优化核心）
```

### 3. 图状态管理 ✅
```
graph/
├── __init__.py
├── app.py                          # LangGraph 应用主逻辑（对话上下文优化）
└── state.py                        # 状态定义（PipelineState/Message）
```

### 4. UI 组件 ✅
```
ui/
├── __init__.py
└── components/
    ├── __init__.py
    ├── answer_cards.py             # 回答卡片渲染（概念问答修复）
    ├── stage_workspace.py          # 检查点工作区（质控/SOP/参数/截图优化）
    ├── image_gallery.py            # 图片画廊组件
    ├── parameter_panel.py          # 参数面板组件
    └── paste_image.py              # 截图粘贴组件
```

### 5. 知识库 ✅
```
knowledge_base/
├── flows/
│   ├── pipeline_checkpoints.json   # 14步流程定义
│   └── cryosparc_jobs.json         # cryoSPARC 作业定义
├── rules/
│   ├── tier2_rules.json            # Tier 2 规则库
│   └── response_profiles.json      # 回答风格定义
├── faults/
│   └── fault_trouble.json          # 故障排查知识
├── terminology/
│   └── glossary.json               # 术语词典
├── relion_stage_cards.json         # RELION 阶段卡片（cp_05 质控更新）
├── cryosparc_stage_cards.json      # cryoSPARC 阶段卡片
├── knowledge_index.json            # 知识库索引
├── metadata_index.json             # 元数据索引
├── importer.py                     # 知识导入工具
└── document_ingest.py              # 文档摄取工具
```

### 6. 实验室参数数据 ✅
```
../Batch3_0702_实验室真实SOP/
└── lab_parameters_master.csv       # 实验室参数主表（SOP tab 读取）
```
**注意**: 打包时需要确保这个文件被包含或复制到项目根目录

### 7. 配置文件 ✅
```
config/
├── __init__.py
└── settings.py                     # 配置管理
```

### 8. 文档 ✅
```
├── README.md                       # 项目说明（快速开始）
├── OPTIMIZATION_SUMMARY.md         # 优化总结（本次6项优化）
├── SUBMISSION_NOTES.md             # 提交说明（团队信息待填写）
├── SUBMISSION_GUIDE.md             # 提交指南（3种方案）
├── CHANGELOG_V5.1.md               # 版本更新日志
├── PROJECT_REPORT.md               # 项目技术报告
└── DELIVERY_AND_USER_GUIDE_V5.1.md # 交付和用户指南
```

### 9. 运行时目录结构 ✅
```
runtime/                            # 运行时数据（清空但保留目录）
├── logs/                           # 日志目录
└── cache/                          # 缓存目录

memory/                             # 会话持久化（清空但保留目录）
└── .gitkeep
```

### 10. 测试用例（可选） ✅
```
tests/
├── __init__.py
└── test_*.py                       # 单元测试

eval_cases/                         # 评估用例
└── *.json
```

---

## 🗑️ 必须排除的文件

### 自动清理（脚本会处理）
- `__pycache__/` - Python 缓存目录
- `*.pyc` - Python 字节码文件
- `*.pyo` - Python 优化字节码
- `runtime/logs/*.log` - 运行日志
- `runtime/cache/*` - 缓存文件
- `memory/*.sqlite3-journal` - SQLite 日志
- `.pytest_cache/` - Pytest 缓存
- `htmlcov/` - 测试覆盖率报告
- `.coverage` - 覆盖率数据

### 手动检查（可能含敏感信息）
- `.env` - 环境变量文件（如含 API Key 需删除）
- `config/*.key` - 密钥文件
- `memory/*.sqlite3` - 会话数据库（可选，包含用户数据）

### 可选排除（不影响运行）
- `.git/` - Git 仓库（如果使用 Git 方式提交则保留）
- `.vscode/` - VSCode 配置
- `.idea/` - PyCharm 配置
- `*.zip` - 旧版本压缩包
- `修复实施记录.md` - 内部开发记录
- `软件体验评估与诊断报告.md` - 内部评估文档

---

## 📊 预期文件大小

| 类别 | 预估大小 |
|------|---------|
| 源代码 | ~2 MB |
| 知识库 | ~5 MB |
| 文档 | ~500 KB |
| 依赖（不含） | ~50 MB |
| **总计（压缩前）** | **~8 MB** |
| **压缩包大小** | **~3-5 MB** |

---

## 🚀 打包步骤（推荐）

### 方式 1：使用自动脚本（推荐）

1. **双击运行打包脚本**:
   ```
   prepare_final_submission.bat
   ```

2. **脚本会自动**:
   - ✅ 清理 Python 缓存
   - ✅ 清理运行时数据
   - ✅ 清理测试输出
   - ✅ 检查敏感文件
   - ✅ 创建压缩包（带时间戳）

3. **输出文件**:
   ```
   StructPilot_v5.1_Final_Submission_YYYYMMDD_HHMMSS.zip
   ```

4. **验证压缩包**:
   - 解压到临时目录
   - 检查文件完整性
   - 测试能否正常启动

### 方式 2：手动打包

1. **清理临时文件**:
   ```bash
   # 删除 __pycache__
   find . -type d -name "__pycache__" -exec rm -rf {} +
   
   # 删除 .pyc 文件
   find . -name "*.pyc" -delete
   ```

2. **删除敏感文件**:
   - 检查并删除 `.env`（如有 API Key）
   - 清空 `runtime/logs/`
   - 清空 `memory/`（可选）

3. **创建压缩包**:
   - 右键 `StructPilot_v5.1` 文件夹
   - 选择"发送到" → "压缩文件夹"
   - 重命名为 `StructPilot_v5.1_Final_Submission.zip`

---

## ✅ 提交前检查清单

### 基本检查
- [ ] 压缩包大小合理（< 20 MB）
- [ ] 包含所有必须文件（源码 + 知识库 + 文档）
- [ ] 已删除 Python 缓存（`__pycache__/`）
- [ ] 已删除敏感信息（`.env`、API Key）
- [ ] README.md 清晰完整
- [ ] requirements.txt 完整

### 文档完整性
- [ ] OPTIMIZATION_SUMMARY.md 已生成
- [ ] SUBMISSION_NOTES.md 团队信息已填写
- [ ] CHANGELOG_V5.1.md 已更新
- [ ] 所有文档无占位文本

### 功能验证
- [ ] 解压后可以正常启动（运行 start.bat）
- [ ] 14步流程导航正常
- [ ] 质控/SOP/参数/截图 tab 显示正常
- [ ] 智能问答功能正常（如配置 LLM）

### 优化验证
- [ ] 概念问答不显示 JSON 原始数据
- [ ] 图片上传不报 TypeError
- [ ] 沉淀经验表单正常
- [ ] 参数区显示实际推荐（非 `**—**`）
- [ ] 质控区无"课题组经验值"
- [ ] SOP/截图区图文排版正常

---

## 📧 提交方式选择

### 方式 A：邮件提交
- **附件**: `StructPilot_v5.1_Final_Submission.zip`
- **正文**: 见 `SUBMISSION_NOTES.md` 邮件模板
- **主题**: `[比赛名称] StructPilot v5.1 项目提交 - [团队名]`

### 方式 B：平台上传
- **文件**: `StructPilot_v5.1_Final_Submission.zip`
- **说明**: 复制 `SUBMISSION_NOTES.md` 内容

### 方式 C：Git 仓库
- **推送到**: GitHub/GitLab
- **创建**: Release 标签 `v5.1-final`
- **提供**: 仓库链接和访问权限

---

## 🎯 特别说明

### 1. 实验室参数文件位置
`lab_parameters_master.csv` 目前在上级目录，需要确保打包时包含：

**选项1**: 复制到项目根目录
```bash
copy ..\Batch3_0702_实验室真实SOP\lab_parameters_master.csv .
```

**选项2**: 确保评委解压后目录结构正确
```
StructPilot_v5.1/
Batch3_0702_实验室真实SOP/
  └── lab_parameters_master.csv
```

### 2. 知识库图片
如果知识库中有图片引用，确保图片文件也被包含：
- `knowledge_base/assets/`
- `assets/screenshots/`

### 3. 运行环境说明
在 README.md 中明确说明：
- Python 3.10+ 要求
- 依赖安装命令
- 首次启动步骤
- 常见问题排查

---

## 📝 最终确认

打包完成后，请确认：

1. **压缩包可以解压**
2. **README.md 可以打开并阅读**
3. **start.bat 可以运行**
4. **应用可以启动到浏览器**
5. **SUBMISSION_NOTES.md 团队信息已填写**
6. **文件大小在合理范围内**（建议 < 20 MB）

---

**准备好后，运行** `prepare_final_submission.bat` **开始打包！**
