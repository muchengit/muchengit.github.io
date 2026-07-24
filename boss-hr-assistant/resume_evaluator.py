"""简历评分模块 — 根据岗位要求对简历进行多维度评分.

评分逻辑：
- 基础分 50 分
- 硬性要求: 满足加分，不满足扣分
- 加分项: 匹配关键词加分
- 减分项: 匹配风险关键词扣分
- 最终分数限制在 0-100
"""
import logging
import re
import config as _config

log = logging.getLogger("boss-resume-evaluator")


class ResumeEvaluator:
    """根据 YAML 配置的评分标准评估简历.

    支持两种用法:
    1. 自动模式: evaluator.evaluate(text) — 使用当前激活的岗位配置
    2. 指定岗位: evaluator.evaluate(text, job_key="05_core_system_developer")
       或 evaluator.evaluate(text, profile={...})
    """

    def __init__(self):
        pass

    def evaluate(self, resume_text: str, candidate_info: dict = None,
                 job_key: str = "", profile: dict = None) -> dict:
        """评估简历文本，返回评分和详细分析.

        Args:
            resume_text: 简历全文文本
            candidate_info: 候选人基本信息（可选）
            job_key: 指定岗位key，自动加载对应配置（可选）
            profile: 直接传入岗位配置dict（可选，优先级最高）
        Returns:
            {
                score: 0-100,
                level: "优秀" | "良好" | "一般" | "不合格",
                passed: bool,
                matched_job: str,  # 匹配到的岗位名称
                details: [...],
                strengths: [...],
                weaknesses: [...],
                summary: str
            }
        """
        if not resume_text:
            return self._empty_result()

        # 确定使用哪套评分配置
        _profile = profile or (None if not job_key else _config.load_profile(job_key))
        scoring = (_profile or _config.PROFILE).get("scoring", {})
        job_cfg = (_profile or _config.PROFILE).get("job", {})
        matched_job_title = job_cfg.get("title", "")

        text_lower = resume_text.lower()
        score = 50  # 基础分
        details = []
        strengths = []
        weaknesses = []

        # 1. 评估硬性要求
        must_have = scoring.get("must_have", [])
        for item in must_have:
            name = item.get("name", "")
            keywords = item.get("keywords", [])
            weight = item.get("weight", 10)
            required = item.get("required", False)
            description = item.get("description", "")

            matched, matched_keywords = self._match_keywords(text_lower, keywords)

            if matched:
                score += weight
                strengths.append(f"{name}: 匹配到 {', '.join(matched_keywords)}")
                details.append({
                    "category": "硬性要求",
                    "name": name,
                    "matched": True,
                    "weight": weight,
                    "matched_keywords": matched_keywords,
                })
            else:
                if required:
                    score -= weight  # 硬性要求不满足扣分
                    weaknesses.append(f"{name}: 未匹配（{description}）")
                else:
                    score -= weight // 2
                details.append({
                    "category": "硬性要求",
                    "name": name,
                    "matched": False,
                    "weight": -weight if required else -weight // 2,
                    "description": description,
                })

        # 2. 评估加分项
        nice_to_have = scoring.get("nice_to_have", [])
        for item in nice_to_have:
            name = item.get("name", "")
            keywords = item.get("keywords", [])
            weight = item.get("weight", 5)
            description = item.get("description", "")

            matched, matched_keywords = self._match_keywords(text_lower, keywords)

            if matched:
                score += weight
                strengths.append(f"{name}: 匹配到 {', '.join(matched_keywords)}")
                details.append({
                    "category": "加分项",
                    "name": name,
                    "matched": True,
                    "weight": weight,
                    "matched_keywords": matched_keywords,
                })
            else:
                details.append({
                    "category": "加分项",
                    "name": name,
                    "matched": False,
                    "weight": 0,
                    "description": description,
                })

        # 3. 评估减分项
        negative = scoring.get("negative", [])
        for item in negative:
            name = item.get("name", "")
            keywords = item.get("keywords", [])
            weight = item.get("weight", -10)
            description = item.get("description", "")

            matched, matched_keywords = self._match_keywords(text_lower, keywords)

            if matched:
                score += weight  # weight 是负数
                weaknesses.append(f"{name}: 匹配到 {', '.join(matched_keywords)}（{description}）")
                details.append({
                    "category": "减分项",
                    "name": name,
                    "matched": True,
                    "weight": weight,
                    "matched_keywords": matched_keywords,
                })

        # 限制分数范围
        score = max(0, min(100, score))

        # 判断等级
        if score >= 95:
            level = "优秀"
        elif score >= 80:
            level = "良好"
        elif score >= 60:
            level = "一般"
        else:
            level = "不合格"

        # 生成摘要
        summary_parts = [
            f"总分 {score}/100（{level}）",
            f"硬性要求匹配 {sum(1 for d in details if d['category']=='硬性要求' and d['matched'])}/{len(must_have)}",
            f"加分项匹配 {sum(1 for d in details if d['category']=='加分项' and d['matched'])}/{len(nice_to_have)}",
        ]
        if weaknesses:
            summary_parts.append(f"风险点 {len(weaknesses)} 个")

        return {
            "score": score,
            "level": level,
            "passed": score >= 95,
            "matched_job": matched_job_title,
            "details": details,
            "strengths": strengths or ["无明显亮点"],
            "weaknesses": weaknesses or ["无明显风险"],
            "summary": "；".join(summary_parts),
        }

    def _match_keywords(self, text: str, keywords: list[str]) -> tuple[bool, list[str]]:
        """检查文本中是否包含关键词（不区分大小写）."""
        matched = []
        for kw in keywords:
            if kw.lower() in text:
                matched.append(kw)
        return len(matched) > 0, matched

    def _empty_result(self) -> dict:
        """空简历的默认结果."""
        return {
            "score": 0,
            "level": "不合格",
            "passed": False,
            "details": [],
            "strengths": [],
            "weaknesses": ["简历内容为空，无法评估"],
            "summary": "简历内容为空",
        }

    def extract_candidate_name(self, resume_text: str) -> str:
        """从简历文本中提取候选人姓名."""
        if not resume_text:
            return "未知"

        lines = resume_text.strip().split("\n")

        # 策略1: 第一行通常是姓名
        first_line = lines[0].strip() if lines else ""
        if first_line and len(first_line) <= 10 and not any(
            c in first_line for c in "@#￥%……&*（）"
        ):
            # 清理可能的标题前缀
            name = re.sub(r'(简历|个人简历|RESUME|CV)', '', first_line, flags=re.IGNORECASE).strip()
            if name and len(name) >= 2:
                return name

        # 策略2: 查找"姓名："模式
        for line in lines[:10]:
            match = re.search(r'姓名[：:]\s*(\S+)', line)
            if match:
                return match.group(1).strip()

        # 策略3: 查找"Name:"模式
        for line in lines[:10]:
            match = re.search(r'Name[：:]\s*(\S+)', line, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "未知"

    def extract_experience_years(self, resume_text: str) -> str:
        """从简历中提取工作年限."""
        if not resume_text:
            return "未知"

        # 匹配 "X年经验" "X年工作经验" 等模式
        patterns = [
            r'(\d+)\s*年\s*(?:工作)?经验',
            r'工作年限[：:]\s*(\d+年)',
            r'(\d+)\s*years?\s*(?:of)?\s*experience',
        ]

        for pattern in patterns:
            match = re.search(pattern, resume_text, re.IGNORECASE)
            if match:
                return match.group(1) + "年" if match.group(1).isdigit() else match.group(1)

        return "未知"

    def extract_education(self, resume_text: str) -> str:
        """从简历中提取最高学历."""
        if not resume_text:
            return "未知"

        education_levels = ["博士", "硕士", "研究生", "本科", "学士", "大专", "专科", "高中"]
        text_lower = resume_text.lower()

        for edu in education_levels:
            if edu in resume_text:
                return edu

        return "未知"
