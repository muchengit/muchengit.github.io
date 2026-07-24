"""Boss直聘 HR 助手 MCP Server — 自动化简历筛选流程.

工作流程:
1. 读取 Boss 直聘聊天消息
2. 向候选人索要简历
3. 下载候选人发送的简历附件
4. 根据岗位要求给简历打分
5. 筛选95分以上简历并按固定格式命名

基于 boss-zhipin-mcp 项目架构改造。
"""
import sys
import os
import asyncio
import logging

from fastmcp import FastMCP

import browser as browser_mod
import chat_scraper as chat_mod
import resume_downloader as downloader_mod
import resume_evaluator as evaluator_mod
import file_manager as file_mod

from browser import BossBrowser
from chat_scraper import ChatScraper
from resume_downloader import ResumeDownloader
from resume_evaluator import ResumeEvaluator
from file_manager import FileManager
from config import (
    PROFILE, SCORE_THRESHOLD, RESUME_DIR, SHORTLISTED_DIR,
    list_jobs, switch_job as _switch_job, get_active_job_file,
    match_job_for_candidate, match_job_by_keywords,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
log = logging.getLogger("boss-hr-server")

mcp = FastMCP("boss-hr-assistant")

# 共享实例
_browser: BossBrowser | None = None
_scraper: ChatScraper | None = None
_downloader: ResumeDownloader | None = None
_evaluator = ResumeEvaluator()
_file_manager = FileManager()


# --- 浏览器/Scraper 辅助 ---
async def get_browser() -> BossBrowser:
    global _browser, _scraper, _downloader
    if _browser is None or not _browser.is_alive:
        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
        _browser = BossBrowser()
        await _browser.launch()
        _scraper = None
        _downloader = None
    return _browser


async def get_scraper() -> ChatScraper:
    global _scraper
    browser = await get_browser()
    if _scraper is None:
        _scraper = ChatScraper(browser)
    return _scraper


async def get_downloader() -> ResumeDownloader:
    global _downloader
    browser = await get_browser()
    if _downloader is None:
        _downloader = ResumeDownloader(browser)
    return _downloader


# ===================== MCP Tools =====================


@mcp.tool()
async def boss_hr_login() -> dict:
    """登录 Boss 直聘招聘者账号.

    首次使用需要在弹出的浏览器中手动完成登录（扫码或短信验证）。
    登录成功后 Cookie 会自动保存，后续无需重复登录。
    """
    browser = await get_browser()
    if await browser.is_logged_in():
        return {"status": "success", "message": "已登录，Cookie 有效"}
    return await browser.login()


@mcp.tool()
async def boss_hr_go_chat() -> dict:
    """导航到 Boss 直聘聊天页面.

    进入招聘者端的「沟通」/「消息」页面，准备读取聊天列表。
    """
    scraper = await get_scraper()
    return await scraper.navigate_to_chat()


@mcp.tool()
async def boss_hr_chat_list() -> list[dict]:
    """读取 Boss 直聘聊天列表.

    返回所有正在沟通的候选人列表，包括姓名、最后消息、时间、未读数等。
    """
    scraper = await get_scraper()
    return await scraper.get_chat_list()


@mcp.tool()
async def boss_hr_select_chat(index: int) -> dict:
    """选择聊天列表中的第 N 个候选人，进入对话.

    Args:
        index: 聊天列表索引（0-based，来自 boss_hr_chat_list 返回的 element_index）
    """
    scraper = await get_scraper()
    return await scraper.select_chat_by_index(index)


@mcp.tool()
async def boss_hr_messages() -> list[dict]:
    """读取当前对话的消息记录.

    返回当前选中对话的所有消息，包括消息文本、方向（自己/对方）、是否有附件等。
    """
    scraper = await get_scraper()
    return await scraper.get_current_messages()


@mcp.tool()
async def boss_hr_candidate_info() -> dict:
    """获取当前对话候选人的基本信息.

    返回候选人姓名、职位、经验等信息（从对话窗口头部提取）。
    """
    scraper = await get_scraper()
    return await scraper.get_candidate_info()


@mcp.tool()
async def boss_hr_send_message(message: str) -> dict:
    """在当前对话中发送消息.

    Args:
        message: 要发送的消息内容
    """
    scraper = await get_scraper()
    return await scraper.send_message(message)


@mcp.tool()
async def boss_hr_request_resume(custom_message: str = "") -> dict:
    """向当前对话的候选人索要简历.

    发送预设的索要简历消息（可在 job_profile.yaml 中配置模板）。

    Args:
        custom_message: 自定义消息内容（可选，不传则使用配置文件中的模板）
    """
    scraper = await get_scraper()
    return await scraper.request_resume(custom_message)


@mcp.tool()
async def boss_hr_check_resume() -> dict:
    """检查当前对话中是否收到了简历附件.

    扫描当前对话的消息，检测是否包含简历/文件附件。
    """
    scraper = await get_scraper()
    return await scraper.check_resume_received()


@mcp.tool()
async def boss_hr_download_resume(chat_index: int = -1) -> dict:
    """从当前或指定对话中下载简历附件.

    Args:
        chat_index: 聊天列表索引，-1 表示当前对话。指定后会先切换到该对话。
    """
    downloader = await get_downloader()
    return await downloader.download_resume_from_chat(chat_index)


@mcp.tool()
async def boss_hr_batch_request_resume(
    start_index: int = 0,
    count: int = 10,
    skip_has_resume: bool = True,
) -> dict:
    """批量向多个候选人索要简历.

    遍历聊天列表，向尚未发送过简历的候选人发送索要简历消息。

    Args:
        start_index: 从第几个聊天开始（0-based）
        count: 最多处理多少个对话
        skip_has_resume: 是否跳过已有简历的对话（默认True）
    """
    scraper = await get_scraper()
    chat_list = await scraper.get_chat_list()
    valid_chats = [c for c in chat_list if isinstance(c, dict) and "error" not in c]

    if not valid_chats:
        return {"error": "聊天列表为空"}

    end_index = min(start_index + count, len(valid_chats))
    results = []
    sent_count = 0
    skipped_count = 0

    for i in range(start_index, end_index):
        chat = valid_chats[i]
        name = chat.get("name", "未知")

        # 选择对话
        select_result = await scraper.select_chat_by_index(i)
        if "error" in select_result:
            results.append({"index": i, "name": name, "status": "error", "message": "选择对话失败"})
            continue

        # 检查是否已有简历
        if skip_has_resume:
            resume_check = await scraper.check_resume_received()
            if resume_check.get("has_resume"):
                skipped_count += 1
                results.append({"index": i, "name": name, "status": "skipped", "message": "已有简历"})
                continue

        # 发送索要简历消息
        send_result = await scraper.request_resume()
        if send_result.get("status") == "success":
            sent_count += 1
            results.append({"index": i, "name": name, "status": "sent"})
        else:
            results.append({"index": i, "name": name, "status": "failed", "message": send_result.get("error", "")})

        await asyncio.sleep(2)

    return {
        "status": "success",
        "total_processed": len(results),
        "sent": sent_count,
        "skipped": skipped_count,
        "failed": len(results) - sent_count - skipped_count,
        "details": results,
    }


@mcp.tool()
async def boss_hr_batch_download(max_count: int = 20) -> dict:
    """批量下载所有有简历附件的对话中的简历.

    遍历聊天列表，自动下载包含简历附件的对话中的简历文件。

    Args:
        max_count: 最多处理的对话数量，默认20
    """
    downloader = await get_downloader()
    return await downloader.batch_download_from_chat_list(max_count)


@mcp.tool()
async def boss_hr_score_and_filter(auto_match: bool = True) -> dict:
    """对已下载的简历进行评分和筛选（自动匹配岗位）.

    扫描 resumes 目录中的所有简历文件，自动根据候选人投递的职位
    匹配对应的岗位配置进行评分。如果匹配不到，则使用默认配置。
    筛选95分以上的简历，按固定格式重命名，并复制到 shortlisted 目录。

    Args:
        auto_match: 是否自动匹配岗位（默认True）
    """
    return _file_manager.process_downloaded_resumes(auto_match=auto_match)


@mcp.tool()
async def boss_hr_get_shortlisted() -> dict:
    """获取已筛选的优质简历列表（95分以上）.

    返回 shortlisted 目录中的所有优质简历文件列表。
    """
    if not os.path.exists(SHORTLISTED_DIR):
        return {"error": "优质简历目录不存在，请先执行评分筛选"}

    files = []
    for filename in sorted(os.listdir(SHORTLISTED_DIR)):
        if filename.endswith((".pdf", ".doc", ".docx")):
            file_path = os.path.join(SHORTLISTED_DIR, filename)
            files.append({
                "filename": filename,
                "path": file_path,
                "size": os.path.getsize(file_path),
            })

    # 也检查是否有筛选报告
    reports = [
        f for f in os.listdir(SHORTLISTED_DIR)
        if f.startswith("筛选报告") and f.endswith(".md")
    ]

    return {
        "status": "success",
        "count": len(files),
        "files": files,
        "reports": reports,
        "directory": SHORTLISTED_DIR,
    }


@mcp.tool()
async def boss_hr_score_resume(file_path: str, job_key: str = "") -> dict:
    """对单个简历文件进行评分（不重命名、不归档）.

    Args:
        file_path: 简历文件的完整路径
        job_key: 指定岗位key进行评分（可选，不传则自动匹配或使用默认配置）
    """
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    resume_text = _file_manager._extract_text_sync(file_path)
    if not resume_text:
        return {"error": "无法提取简历文本，可能是扫描版PDF或文件损坏"}

    name = _evaluator.extract_candidate_name(resume_text)
    experience = _evaluator.extract_experience_years(resume_text)
    education = _evaluator.extract_education(resume_text)

    # 自动匹配岗位（如果未指定 job_key）
    _profile = None
    if job_key:
        _profile = _config.load_profile(job_key)
    else:
        match = match_job_by_keywords(resume_text[:500])
        if match:
            _profile = match.get("profile")

    evaluation = _evaluator.evaluate(resume_text, profile=_profile)

    return {
        "file": os.path.basename(file_path),
        "name": name,
        "experience": experience,
        "education": education,
        "matched_job": evaluation.get("matched_job", ""),
        **evaluation,
    }


@mcp.tool()
async def boss_hr_pipeline(
    request_resumes: bool = True,
    download_resumes: bool = True,
    score_and_filter: bool = True,
    max_chats: int = 15,
    auto_match_jobs: bool = True,
) -> dict:
    """一键执行完整流程: 索要简历 → 下载简历 → 自动匹配岗位评分筛选.

    自动根据候选人投递的职位匹配对应的岗位配置进行评分，
    不需要手动切换岗位。

    Args:
        request_resumes: 是否执行索要简历步骤
        download_resumes: 是否执行下载简历步骤
        score_and_filter: 是否执行评分筛选步骤
        max_chats: 最多处理的对话数量
        auto_match_jobs: 是否自动根据候选人职位匹配岗位评分（默认True）
    """
    results = {}
    log.info("=== 开始执行完整招聘流程（自动岗位匹配）===")

    # 步骤0: 确保登录并进入聊天页面
    browser = await get_browser()
    if not await browser.is_logged_in():
        login_result = await browser.login()
        if login_result.get("status") != "success":
            return {"error": "登录失败，请手动登录后重试"}

    scraper = await get_scraper()
    await scraper.navigate_to_chat()

    # 获取聊天列表（用于后续候选人→职位映射）
    chat_list = await scraper.get_chat_list()
    valid_chats = [c for c in chat_list if isinstance(c, dict) and "error" not in c]
    results["chat_list_count"] = len(valid_chats)
    log.info(f"聊天列表共 {len(valid_chats)} 个对话")

    # 步骤1: 索要简历
    if request_resumes:
        log.info("步骤1: 批量索要简历")
        results["request_resumes"] = await boss_hr_batch_request_resume(
            start_index=0, count=max_chats, skip_has_resume=True
        )

    # 步骤2: 下载简历（等待候选人回复后执行）
    if download_resumes:
        log.info("步骤2: 批量下载简历")
        results["download_resumes"] = await boss_hr_batch_download(max_count=max_chats)

    # 步骤3: 评分筛选（自动匹配岗位）
    if score_and_filter:
        log.info("步骤3: 评分筛选简历（自动匹配岗位）")
        results["score_and_filter"] = _file_manager.process_downloaded_resumes(
            auto_match=auto_match_jobs,
            chat_list_info=valid_chats if auto_match_jobs else None,
        )

    # 步骤4: 获取优质简历列表
    log.info("步骤4: 获取优质简历列表")
    results["shortlisted"] = await boss_hr_get_shortlisted()

    log.info("=== 招聘流程完成 ===")
    return {
        "status": "success",
        "pipeline": "complete",
        "auto_match_jobs": auto_match_jobs,
        "steps_executed": [k for k, v in results.items() if isinstance(v, dict) and v.get("status") != "error"],
        "results": results,
    }


@mcp.tool()
async def boss_hr_reload() -> dict:
    """热重载代码，修改后无需重启 server."""
    import importlib
    modules_to_reload = [
        browser_mod, chat_mod, downloader_mod,
        evaluator_mod, file_mod
    ]
    for mod in modules_to_reload:
        importlib.reload(mod)

    global _browser, _scraper, _downloader, _evaluator, _file_manager
    _scraper = None
    _downloader = None
    _evaluator = ResumeEvaluator()
    _file_manager = FileManager()

    return {"status": "success", "message": "代码已热重载"}


@mcp.tool()
async def boss_hr_list_jobs() -> list[dict]:
    """列出所有可用的岗位配置.

    返回 jobs/ 目录下所有岗位的列表，包括岗位名称、城市、经验要求等。
    """
    jobs = list_jobs()
    active_file = get_active_job_file()
    for job in jobs:
        job["active"] = (job["path"] == active_file)
    return jobs


@mcp.tool()
async def boss_hr_switch_job(job_key: str) -> dict:
    """切换当前激活的岗位配置.

    切换后，后续的评分、索要简历消息模板、命名格式都会使用新岗位的配置。

    Args:
        job_key: 岗位key（如 "01_ui_ue_designer"）或岗位标题关键词（如 "UI" "大数据" "运维" "OA" "核心"）
    """
    global _evaluator, _file_manager
    result = _switch_job(job_key)
    if result.get("status") == "success":
        # 重新初始化评估器和文件管理器以加载新配置
        import importlib
        importlib.reload(evaluator_mod)
        importlib.reload(file_mod)
        _evaluator = evaluator_mod.ResumeEvaluator()
        _file_manager = file_mod.FileManager()
        result["current_job"] = PROFILE.get("job", {}).get("title", "")
        result["city"] = PROFILE.get("job", {}).get("city", "")
    return result


@mcp.tool()
async def boss_hr_status() -> dict:
    """查看当前状态: 浏览器连接、简历数量、配置信息等."""
    status = {
        "browser_connected": _browser is not None and _browser.is_alive if _browser else False,
        "score_threshold": SCORE_THRESHOLD,
        "resume_dir": RESUME_DIR,
        "shortlisted_dir": SHORTLISTED_DIR,
        "job_title": PROFILE.get("job", {}).get("title", "未配置"),
        "job_city": PROFILE.get("job", {}).get("city", "未配置"),
        "job_experience": PROFILE.get("job", {}).get("experience", "未配置"),
        "naming_format": PROFILE.get("naming", {}).get("format", "未配置"),
        "active_job_file": get_active_job_file(),
    }

    # 统计简历文件
    if os.path.exists(RESUME_DIR):
        resume_count = len([
            f for f in os.listdir(RESUME_DIR)
            if f.endswith((".pdf", ".doc", ".docx"))
        ])
        status["total_resumes"] = resume_count

    if os.path.exists(SHORTLISTED_DIR):
        shortlisted_count = len([
            f for f in os.listdir(SHORTLISTED_DIR)
            if f.endswith((".pdf", ".doc", ".docx"))
        ])
        status["shortlisted_count"] = shortlisted_count

    return status


# --- Server 入口 ---
if __name__ == "__main__":
    mcp.run()
