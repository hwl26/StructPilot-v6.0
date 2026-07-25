"""知识库管理工具 - 重置和领域适配

提供两个管理功能：
1. 从头开始：清除所有用户贡献的知识库内容，保留官方基础内容
2. 领域适配：将 StructPilot 抽象为通用框架，适配其他领域
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional


def reset_knowledge_base(backup: bool = True) -> Dict[str, any]:
    """重置知识库到初始状态（仅保留官方内容）。

    Parameters
    ----------
    backup : bool
        是否备份当前知识库

    Returns
    -------
    Dict
        操作结果：{"success": bool, "message": str, "stats": Dict}
    """
    kb_path = "runtime/knowledge_base/experiences.json"

    if not os.path.exists(kb_path):
        return {
            "success": False,
            "message": "知识库文件不存在",
            "stats": {}
        }

    # 加载当前知识库
    with open(kb_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    experiences = data.get("experiences", [])

    # 统计
    total_count = len(experiences)
    official_count = len([e for e in experiences if e.get("source") == "official"])
    user_count = total_count - official_count

    # 备份
    if backup and user_count > 0:
        backup_dir = "runtime/knowledge_base/backups"
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{backup_dir}/experiences_backup_{timestamp}.json"

        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # 仅保留官方内容
    official_experiences = [e for e in experiences if e.get("source") == "official"]

    data["experiences"] = official_experiences

    # 保存
    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {
        "success": True,
        "message": f"知识库已重置：删除 {user_count} 条用户贡献，保留 {official_count} 条官方内容",
        "stats": {
            "total_before": total_count,
            "official": official_count,
            "user_deleted": user_count,
            "backup_created": backup
        }
    }


def create_domain_template(
    domain_name: str,
    domain_name_en: str,
    description: str,
    steps: List[Dict[str, str]],
    software_list: List[str],
    output_dir: str = "runtime/domain_templates"
) -> Dict[str, any]:
    """创建领域适配模板。

    Parameters
    ----------
    domain_name : str
        领域名称（中文），如"冷冻电镜单颗粒分析"
    domain_name_en : str
        领域名称（英文），如"CryoEM-SPA"
    description : str
        领域描述
    steps : List[Dict]
        工作流步骤列表，每个步骤包含：
        - id: 步骤ID（如 cp_01）
        - name: 步骤名称
        - description: 步骤描述
    software_list : List[str]
        该领域常用软件列表
    output_dir : str
        输出目录

    Returns
    -------
    Dict
        生成的模板信息
    """
    os.makedirs(output_dir, exist_ok=True)

    # 创建领域模板
    template = {
        "domain": {
            "name": domain_name,
            "name_en": domain_name_en,
            "description": description,
            "created_at": datetime.now().isoformat()
        },
        "workflow": {
            "steps": steps
        },
        "software": software_list,
        "knowledge_base": {
            "experiences": [],
            "categories": [step["id"] for step in steps]
        },
        "forum": {
            "tags": [domain_name_en.lower()] + software_list,
            "categories": ["问题求助", "经验分享", "参数讨论", "软件使用"]
        },
        "ui_config": {
            "app_name": f"{domain_name}智能助手",
            "logo": f"🔬",  # 可自定义
            "welcome_message": f"欢迎使用 {domain_name} 智能助手！我可以帮助您完成整个工作流程。"
        }
    }

    # 保存模板
    template_path = f"{output_dir}/{domain_name_en.lower()}_template.json"
    with open(template_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    # 生成配置说明文档
    readme_path = f"{output_dir}/{domain_name_en.lower()}_README.md"
    readme_content = f"""# {domain_name} 领域适配模板

## 基本信息
- **领域名称：** {domain_name}
- **英文标识：** {domain_name_en}
- **描述：** {description}

## 工作流步骤

{chr(10).join([f"{i+1}. **{step['name']}** (`{step['id']}`) - {step['description']}" for i, step in enumerate(steps)])}

## 常用软件
{chr(10).join([f"- {sw}" for sw in software_list])}

## 使用方法

### 1. 复制模板
```bash
cp {template_path} runtime/active_domain_config.json
```

### 2. 修改配置
编辑 `runtime/active_domain_config.json`，根据实际需求调整：
- 工作流步骤
- 软件列表
- UI 配置

### 3. 重启应用
```bash
streamlit run main.py --server.domain {domain_name_en.lower()}
```

### 4. 初始化知识库
在应用中：
1. 登录管理员账号
2. 进入「设置」→「高级管理」
3. 点击「从头开始」清空知识库
4. 开始积累本领域的经验

## 自定义建议

### 调整工作流
根据本领域的实际流程，修改 `workflow.steps`：
```json
{{
  "id": "custom_01",
  "name": "自定义步骤名称",
  "description": "步骤描述"
}}
```

### 添加软件
在 `software` 数组中添加常用软件：
```json
"software": ["软件A", "软件B", "软件C"]
```

### 修改 UI
在 `ui_config` 中自定义：
```json
{{
  "app_name": "您的助手名称",
  "logo": "🔬",
  "welcome_message": "欢迎使用..."
}}
```

## 技术支持
如有问题，请参考主项目文档或联系开发团队。
"""

    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    return {
        "success": True,
        "domain": domain_name,
        "template_path": template_path,
        "readme_path": readme_path,
        "steps_count": len(steps),
        "software_count": len(software_list)
    }


# 预定义的领域模板
DOMAIN_TEMPLATES = {
    "cryoet": {
        "name": "冷冻电子断层扫描",
        "name_en": "CryoET",
        "description": "冷冻电子断层扫描（Cryo-Electron Tomography）工作流程管理",
        "steps": [
            {"id": "ct_01", "name": "数据采集", "description": "倾斜系列数据采集"},
            {"id": "ct_02", "name": "运动校正", "description": "帧对齐和剂量加权"},
            {"id": "ct_03", "name": "CTF估计", "description": "对比度传递函数估计"},
            {"id": "ct_04", "name": "层析重建", "description": "3D体积重建"},
            {"id": "ct_05", "name": "去卷积", "description": "CTF校正和去噪"},
            {"id": "ct_06", "name": "模板匹配", "description": "目标定位"},
            {"id": "ct_07", "name": "子断层平均", "description": "亚层析平均"},
            {"id": "ct_08", "name": "分类和精修", "description": "3D分类和精修"},
        ],
        "software": ["IMOD", "Etomo", "RELION", "Warp", "emClarity", "novaCTF"]
    },
    "proteomics": {
        "name": "蛋白质组学",
        "name_en": "Proteomics",
        "description": "基于质谱的蛋白质组学数据分析工作流程",
        "steps": [
            {"id": "pt_01", "name": "数据导入", "description": "原始质谱数据导入"},
            {"id": "pt_02", "name": "峰检测", "description": "MS/MS峰识别"},
            {"id": "pt_03", "name": "数据库搜索", "description": "肽段数据库匹配"},
            {"id": "pt_04", "name": "FDR控制", "description": "假阳性率控制"},
            {"id": "pt_05", "name": "蛋白推断", "description": "蛋白质鉴定"},
            {"id": "pt_06", "name": "定量分析", "description": "蛋白质定量"},
            {"id": "pt_07", "name": "统计分析", "description": "差异表达分析"},
            {"id": "pt_08", "name": "功能注释", "description": "GO/KEGG注释"},
        ],
        "software": ["MaxQuant", "ProteomeDiscoverer", "Mascot", "X!Tandem", "Perseus"]
    },
    "materials": {
        "name": "材料学电镜分析",
        "name_en": "Materials-EM",
        "description": "材料科学电子显微镜分析工作流程",
        "steps": [
            {"id": "mt_01", "name": "数据采集", "description": "TEM/SEM图像采集"},
            {"id": "mt_02", "name": "图像预处理", "description": "噪声去除和增强"},
            {"id": "mt_03", "name": "相位对比", "description": "相位对比分析"},
            {"id": "mt_04", "name": "晶体结构", "description": "电子衍射分析"},
            {"id": "mt_05", "name": "元素分析", "description": "EDS/EELS分析"},
            {"id": "mt_06", "name": "形貌表征", "description": "颗粒/晶粒分析"},
            {"id": "mt_07", "name": "缺陷分析", "description": "位错/孪晶分析"},
            {"id": "mt_08", "name": "数据可视化", "description": "3D重建和可视化"},
        ],
        "software": ["DigitalMicrograph", "ImageJ", "CrysTBox", "JEMS", "PyTEM"]
    },
    "art": {
        "name": "艺术品分析",
        "name_en": "Art-Analysis",
        "description": "艺术品科学分析和制作工艺研究工作流程",
        "steps": [
            {"id": "ar_01", "name": "图像采集", "description": "高分辨率图像获取"},
            {"id": "ar_02", "name": "光谱分析", "description": "颜料成分分析"},
            {"id": "ar_03", "name": "层次分析", "description": "底层和覆盖层分析"},
            {"id": "ar_04", "name": "纹理分析", "description": "笔触和纹理特征"},
            {"id": "ar_05", "name": "年代鉴定", "description": "放射性碳定年"},
            {"id": "ar_06", "name": "修复建议", "description": "损伤评估和修复方案"},
            {"id": "ar_07", "name": "真伪鉴定", "description": "风格和材料一致性分析"},
            {"id": "ar_08", "name": "数字归档", "description": "3D建模和数字存档"},
        ],
        "software": ["ImageJ", "MATLAB", "Adobe Photoshop", "Agisoft Metashape", "QGIS"]
    }
}


def generate_all_domain_templates(output_dir: str = "runtime/domain_templates") -> List[Dict]:
    """生成所有预定义领域的模板。

    Returns
    -------
    List[Dict]
        所有生成的模板信息列表
    """
    results = []

    for domain_key, config in DOMAIN_TEMPLATES.items():
        result = create_domain_template(
            domain_name=config["name"],
            domain_name_en=config["name_en"],
            description=config["description"],
            steps=config["steps"],
            software_list=config["software"],
            output_dir=output_dir
        )
        results.append(result)

    return results
