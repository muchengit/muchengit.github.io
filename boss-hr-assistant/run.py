"""一键运行脚本 — 不需要配置 MCP，直接 Python 运行.

使用方法:
    python run.py              # 交互式菜单
    python run.py login        # 仅登录
    python run.py chat         # 查看聊天列表
    python run.py pipeline     # 一键完整流程
    python run.py score        # 仅评分筛选
"""
import asyncio
import sys
import os
import logging

# 确保能找到项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("boss-hr-runner")


async def interactive_menu():
    """交互式菜单."""
    from browser import BossBrowser
    from chat_scraper import ChatScraper
    from resume_downloader import ResumeDownloader
    from file_manager import FileManager
    from resume_evaluator import ResumeEvaluator
    import config

    browser = BossBrowser()
    await browser.launch()

    # 显示当前岗位
    active_job = config.get_active_job_file()
    active_title = config.PROFILE.get("job", {}).get("title", "未配置") if config.PROFILE else "未配置"
    active_city = config.PROFILE.get("job", {}).get("city", "") if config.PROFILE else ""

    print("\n" + "=" * 50)
    print("  Boss直聘 HR 助手")
    print(f"  当前岗位: {active_title} ({active_city})")
    print("=" * 50)

    while True:
        print("\n请选择操作:")
        print("  j. 切换岗位")
        print("  1. 检查登录状态")
        print("  2. 查看聊天列表")
        print("  3. 选择对话并查看消息")
        print("  4. 向当前对话索要简历")
        print("  5. 下载当前对话的简历")
        print("  6. 批量索要简历（向多个候选人）")
        print("  7. 批量下载简历")
        print("  8. 评分筛选已下载的简历")
        print("  9. 查看优质简历列表")
        print("  0. 一键完整流程")
        print("  q. 退出")

        choice = input("\n请输入选项: ").strip().lower()

        if choice == "q":
            break
        elif choice == "j":
            # 列出所有岗位并选择
            jobs = config.list_jobs()
            if not jobs:
                print("未找到岗位配置文件")
                continue
            print("\n可用岗位:")
            for i, job in enumerate(jobs):
                mark = " *当前" if job["path"] == active_job else ""
                print(f"  [{i}] {job['title']} ({job['city']}, {job['experience']}){mark}")
            idx_input = input("请输入岗位编号: ").strip()
            try:
                idx = int(idx_input)
                if 0 <= idx < len(jobs):
                    result = config.switch_job(jobs[idx]["key"])
                    if result.get("status") == "success":
                        # 重新初始化评估器以加载新配置
                        _evaluator = ResumeEvaluator()
                        _file_manager = FileManager()
                        active_job = jobs[idx]["path"]
                        active_title = jobs[idx]["title"]
                        active_city = jobs[idx]["city"]
                        print(f"已切换到: {active_title} ({active_city})")
                    else:
                        print(f"切换失败: {result}")
            except ValueError:
                print("无效输入")

        elif choice == "1":
            logged_in = await browser.is_logged_in()
            if not logged_in:
                print("未登录，正在打开登录页面...")
                result = await browser.login()
                print(result)
            else:
                print("已登录!")

        elif choice == "2":
            scraper = ChatScraper(browser)
            await scraper.navigate_to_chat()
            chat_list = await scraper.get_chat_list()
            print(f"\n找到 {len(chat_list)} 个对话:")
            for i, chat in enumerate(chat_list):
                if isinstance(chat, dict) and "error" not in chat:
                    name = chat.get("name", "未知")
                    last_msg = chat.get("last_message", "")[:30]
                    time = chat.get("time", "")
                    unread = chat.get("unread_count", 0)
                    print(f"  [{i}] {name} | {last_msg} | {time} | 未读:{unread}")

        elif choice == "3":
            scraper = ChatScraper(browser)
            idx = int(input("请输入对话索引: "))
            await scraper.select_chat_by_index(idx)
            messages = await scraper.get_current_messages()
            print(f"\n共 {len(messages)} 条消息:")
            for msg in messages:
                if isinstance(msg, dict) and "error" not in msg:
                    sender = "我" if msg.get("is_self") else "对方"
                    text = msg.get("text", "")[:80]
                    has_file = " [附件]" if msg.get("has_attachment") else ""
                    print(f"  [{sender}] {text}{has_file}")

        elif choice == "4":
            scraper = ChatScraper(browser)
            result = await scraper.request_resume()
            print(result)

        elif choice == "5":
            downloader = ResumeDownloader(browser)
            result = await downloader.download_resume_from_chat()
            print(result)

        elif choice == "6":
            count = int(input("处理多少个对话? (默认10): ") or "10")
            from server import boss_hr_batch_request_resume
            # 重新初始化全局实例
            import server
            server._browser = browser
            result = await server.boss_hr_batch_request_resume(count=count)
            print(f"\n发送: {result.get('sent', 0)}, 跳过: {result.get('skipped', 0)}")

        elif choice == "7":
            count = int(input("处理多少个对话? (默认20): ") or "20")
            downloader = ResumeDownloader(browser)
            result = await downloader.batch_download_from_chat_list(max_count=count)
            print(f"\n下载: {result.get('resumes_downloaded', 0)} 份简历")

        elif choice == "8":
            fm = FileManager()
            result = fm.process_downloaded_resumes()
            print(f"\n总计: {result.get('total', 0)} 份简历")
            print(f"通过筛选(≥95分): {result.get('shortlisted', 0)} 份")
            print(f"报告: {result.get('report', '')}")

        elif choice == "9":
            from config import SHORTLISTED_DIR
            if os.path.exists(SHORTLISTED_DIR):
                files = [f for f in os.listdir(SHORTLISTED_DIR)
                         if f.endswith((".pdf", ".doc", ".docx"))]
                print(f"\n优质简历 ({len(files)} 份):")
                for f in sorted(files):
                    print(f"  - {f}")
            else:
                print("暂无优质简历")

        elif choice == "0":
            print("\n=== 开始一键完整流程 ===")
            import server
            server._browser = browser
            result = await server.boss_hr_pipeline(max_chats=15)
            print(f"\n流程完成!")
            print(f"优质简历: {result.get('results', {}).get('shortlisted', {}).get('count', 0)} 份")

    await browser.close()
    print("\n已退出，再见!")


async def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "login":
            from browser import BossBrowser
            browser = BossBrowser()
            await browser.launch()
            if await browser.is_logged_in():
                print("已登录!")
            else:
                result = await browser.login()
                print(result)
            await browser.close()

        elif cmd == "chat":
            from browser import BossBrowser
            from chat_scraper import ChatScraper
            browser = BossBrowser()
            await browser.launch()
            scraper = ChatScraper(browser)
            await scraper.navigate_to_chat()
            chat_list = await scraper.get_chat_list()
            for i, chat in enumerate(chat_list):
                if isinstance(chat, dict) and "error" not in chat:
                    print(f"[{i}] {chat.get('name', '')} | {chat.get('last_message', '')[:40]}")
            await browser.close()

        elif cmd == "pipeline":
            import server
            await server.boss_hr_pipeline(max_chats=15)

        elif cmd == "score":
            from file_manager import FileManager
            fm = FileManager()
            result = fm.process_downloaded_resumes()
            print(f"总计: {result.get('total', 0)}, 通过: {result.get('shortlisted', 0)}")
            print(f"报告: {result.get('report', '')}")

        else:
            print(f"未知命令: {cmd}")
            print("可用命令: login, chat, pipeline, score")
    else:
        await interactive_menu()


if __name__ == "__main__":
    asyncio.run(main())
