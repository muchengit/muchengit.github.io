"""配置管理 — Boss直聘 HR 助手.

支持多岗位配置：在 jobs/ 目录下放置多个岗位的 YAML 配置文件，
通过环境变量 BOSS_JOB 或 switch_job() 函数切换当前岗位。
"""
import os
import yaml
import glob

# BOSS 直聘
BOSS_BASE_URL = "https://www.zhipin.com"
BOSS_CHAT_URL = "https://www.zhipin.com/web/boss/chat"

# 项目根目录
BASE_DIR = os.path.dirname(__file__)

# Cookie 持久化
COOKIES_DIR = os.path.join(BASE_DIR, "cookies")
COOKIES_FILE = os.path.join(COOKIES_DIR, "boss_cookies.json")

# 简历下载目录
RESUME_DIR = os.path.join(BASE_DIR, "resumes")
# 筛选后的优质简历目录
SHORTLISTED_DIR = os.path.join(BASE_DIR, "resumes", "shortlisted")

# 候选人数据库
CANDIDATE_DB_FILE = os.path.join(BASE_DIR, "candidates_db.json")

# 浏览器配置
BROWSER_HEADLESS = False
MIN_DELAY = 2.0
MAX_DELAY = 5.0

# 简历评分阈值
SCORE_THRESHOLD = 95

# 岗位配置目录
JOBS_DIR = os.path.join(BASE_DIR, "jobs")
# 兼容：旧版单文件配置
LEGACY_PROFILE_FILE = os.path.join(BASE_DIR, "job_profile.yaml")
# 当前激活的岗位配置文件路径（由 switch_job 设置）
_ACTIVE_JOB_FILE = None


def list_jobs() -> list[dict]:
    """列出所有可用的岗位配置.

    Returns:
        [{key, filename, title, city, experience}, ...]
    """
    jobs = []
    if not os.path.exists(JOBS_DIR):
        return jobs

    yaml_files = sorted(glob.glob(os.path.join(JOBS_DIR, "*.yaml")))
    for fpath in yaml_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            job_info = data.get("job", {})
            jobs.append({
                "key": os.path.splitext(os.path.basename(fpath))[0],
                "filename": os.path.basename(fpath),
                "path": fpath,
                "title": job_info.get("title", "未命名"),
                "city": job_info.get("city", ""),
                "experience": job_info.get("experience", ""),
            })
        except Exception:
            continue

    return jobs


def get_active_job_file() -> str:
    """获取当前激活的岗位配置文件路径."""
    global _ACTIVE_JOB_FILE
    if _ACTIVE_JOB_FILE and os.path.exists(_ACTIVE_JOB_FILE):
        return _ACTIVE_JOB_FILE

    # 优先级：环境变量 > jobs目录第一个 > 旧版job_profile.yaml
    env_job = os.getenv("BOSS_JOB", "")
    if env_job:
        # 支持传入文件名或key
        candidate = env_job if os.path.isabs(env_job) else os.path.join(JOBS_DIR, env_job)
        if not candidate.endswith(".yaml"):
            candidate += ".yaml"
        if os.path.exists(candidate):
            _ACTIVE_JOB_FILE = candidate
            return candidate

    # jobs 目录第一个
    jobs = list_jobs()
    if jobs:
        _ACTIVE_JOB_FILE = jobs[0]["path"]
        return _ACTIVE_JOB_FILE

    # 旧版兼容
    if os.path.exists(LEGACY_PROFILE_FILE):
        _ACTIVE_JOB_FILE = LEGACY_PROFILE_FILE
        return LEGACY_PROFILE_FILE

    return ""


def switch_job(job_key: str) -> dict:
    """切换当前激活的岗位.

    Args:
        job_key: 岗位文件的key（不含扩展名）或完整文件名
    Returns:
        切换结果，包含岗位信息
    """
    global _ACTIVE_JOB_FILE

    # 标准化 key
    if job_key.endswith(".yaml"):
        job_key = job_key[:-5]

    # 在 jobs 目录查找
    candidate = os.path.join(JOBS_DIR, f"{job_key}.yaml")
    if os.path.exists(candidate):
        _ACTIVE_JOB_FILE = candidate
        # 重新加载配置
        _reload_profile()
        return {"status": "success", "job_file": candidate, "profile": PROFILE}

    # 尝试按标题模糊匹配
    jobs = list_jobs()
    for job in jobs:
        if job_key.lower() in job["title"].lower() or job_key.lower() in job["key"].lower():
            _ACTIVE_JOB_FILE = job["path"]
            _reload_profile()
            return {"status": "success", "job_file": job["path"], "profile": PROFILE}

    return {"status": "error", "message": f"未找到岗位配置: {job_key}"}


def _reload_profile():
    """重新加载 PROFILE（切换岗位后调用）."""
    global PROFILE
    PROFILE = load_profile()


def load_profile(job_key: str = "") -> dict:
    """从 YAML 配置文件加载岗位要求.

    Args:
        job_key: 岗位key。为空时使用当前激活的岗位。
    """
    if job_key:
        candidate = os.path.join(JOBS_DIR, f"{job_key}.yaml")
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}

    job_file = get_active_job_file()
    if job_file and os.path.exists(job_file):
        with open(job_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def match_job_for_candidate(candidate_job_title: str) -> dict:
    """根据候选人投递的职位名称，自动匹配最合适的岗位配置.

    匹配策略：
    1. 精确匹配岗位标题
    2. 关键词交叉匹配（候选人职位包含配置岗位标题词，或反之）
    3. 取匹配度最高的

    Args:
        candidate_job_title: 候选人投递/应聘的职位名称
            （从Boss聊天列表的"职位"字段或对话头部信息获取）
    Returns:
        {"job_key": str, "title": str, "confidence": str, "profile": dict}
        如果无法匹配，返回 None。
    """
    if not candidate_job_title:
        return None

    jobs = list_jobs()
    if not jobs:
        return None

    title_lower = candidate_job_title.lower().strip()
    best_match = None
    best_score = 0

    for job in jobs:
        job_title_lower = job["title"].lower()

        # 计算匹配分
        score = 0

        # 策略1: 精确匹配（含子串）
        if title_lower == job_title_lower:
            score = 100
        elif title_lower in job_title_lower or job_title_lower in title_lower:
            score = 80
        else:
            # 策略2: 关键词交叉匹配
            # 把岗位名拆成关键词，检查交叉覆盖率
            job_words = set(job_title_lower.replace("/", " ").replace("-", " ").split())
            cand_words = set(title_lower.replace("/", " ").replace("-", " ").split())

            # 移除太短的通用词
            common_noise = {"的", "工程师", "设计师", "开发", "助理", "经理",
                            "师", "员", "初级", "中级", "高级"}
            job_words -= common_noise
            cand_words -= common_noise

            if job_words and cand_words:
                overlap = job_words & cand_words
                if overlap:
                    # 基于覆盖率评分
                    precision = len(overlap) / len(job_words)
                    recall = len(overlap) / len(cand_words)
                    score = int(50 * precision + 30 * recall + 20 * min(precision, recall))

        # 额外加分：候选职位包含配置岗位的核心词
        core_keywords = _extract_core_keywords(job_title_lower)
        for kw in core_keywords:
            if kw in title_lower:
                score = max(score, 60)

        if score > best_score:
            best_score = score
            best_match = job

    if best_match and best_score >= 30:
        confidence = "高" if best_score >= 80 else "中" if best_score >= 50 else "低"
        profile = load_profile(best_match["key"])
        return {
            "job_key": best_match["key"],
            "title": best_match["title"],
            "city": best_match["city"],
            "confidence": confidence,
            "match_score": best_score,
            "profile": profile,
        }

    return None


def _extract_core_keywords(title: str) -> list[str]:
    """从岗位标题提取核心关键词用于模糊匹配."""
    # 预定义的核心词映射
    keyword_map = {
        "ui/ue美工设计师": ["ui", "ue", "美工", "视觉", "界面"],
        "大数据开发工程师": ["大数据", "数据", "etl", "数仓", "离线"],
        "常规运维工程师": ["运维", "应用运维", "系统运维"],
        "oa系统开发工程师": ["oa", "办公自动化", "oa开发"],
        "核心业务系统开发工程师": ["核心", "业务系统", "高级开发", "架构"],
    }

    for key, keywords in keyword_map.items():
        if key in title:
            return keywords

    # 通用提取：取2字以上非噪声词
    noise = {"的", "工程", "设计", "开发", "系统", "应用", "类"}
    words = [w for w in title.replace("/", " ").split() if len(w) >= 2 and w not in noise]
    return words[:3]


def match_job_by_keywords(text: str) -> dict:
    """从一段文本（候选人信息/消息）中智能识别职位并匹配.

    当无法直接获取职位标题时，从候选人信息文本中搜索
    职位相关关键词来推断。

    Args:
        text: 候选人信息文本（来自 chat 列表或对话头部）
    Returns:
        同 match_job_for_candidate
    """
    if not text:
        return None

    text_lower = text.lower()

    # 按优先级搜索职位关键词
    job_hints = [
        ("UI/UE美工设计师", ["ui设计", "ue设计", "美工设计", "视觉设计", "界面设计",
                               "交互设计", "平面设计", "角色设计", "ip设计"]),
        ("大数据开发工程师", ["大数据", "数据开发", "数据工程师", "数仓", "etl",
                               "数据建模", "hive", "spark", "离线开发"]),
        ("常规运维工程师", ["运维", "应用运维", "系统运维", "devops", "运维工程师",
                             "故障处理", "监控运维"]),
        ("OA系统开发工程师", ["oa", "办公自动化", "泛微", "用友", "工作流开发",
                               "协同开发", "流程开发"]),
        ("核心业务系统开发工程师", ["核心开发", "高级开发", "架构师", "技术专家",
                                     "系统架构", "高级工程师", "java高级"]),
    ]

    best_title = None
    for title, keywords in job_hints:
        for kw in keywords:
            if kw in text_lower:
                best_title = title
                break
        if best_title:
            break

    if best_title:
        return match_job_for_candidate(best_title)

    return None


# 初始加载
PROFILE = load_profile()
