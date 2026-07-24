"""Boss直聘聊天页面操作 — 读取消息、发送消息、检测简历附件.

操作 Boss 直聘招聘者端的聊天界面：
- 左侧: 候选人聊天列表
- 右侧: 当前对话窗口
- 消息中可能包含简历附件
"""
import asyncio
import logging
import os
from browser import BossBrowser
from config import BOSS_CHAT_URL, BOSS_BASE_URL
import config as _config

log = logging.getLogger("boss-chat-scraper")


# JS: 提取左侧聊天列表
EXTRACT_CHAT_LIST_JS = """() => {
    const results = [];
    // Boss直聘聊天列表项的选择器（多策略适配）
    const selectors = [
        '.user-list li',
        '.chat-list li',
        '.friend-list li',
        '[class*="friend"] li',
        '[class*="chat-item"]',
        '.main-message-list li',
        '#user-list li',
        'ul.user-list > li'
    ];

    let items = [];
    for (const sel of selectors) {
        items = document.querySelectorAll(sel);
        if (items.length > 0) break;
    }

    for (let item of items) {
        const text = (item.innerText || '').trim();
        if (!text) continue;

        const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
        const name = lines[0] || '未知';

        // 尝试提取候选人信息
        let lastMsg = '';
        let time = '';
        let unread = 0;
        let jobTitle = '';

        for (let line of lines) {
            if (line.match(/^\\d{1,2}:\\d{2}/) || line.match(/^(昨天|前天|今天|\\d+天前)/)) {
                time = line;
            } else if (line.match(/\\d+/) && line.length <= 3) {
                unread = parseInt(line);
            } else if (line.length > 10 && !lastMsg) {
                lastMsg = line;
            }
        }

        // 提取职位信息
        const jobEl = item.querySelector('[class*="job"], [class*="position"], .name-text');
        if (jobEl) jobTitle = jobEl.innerText.trim();

        // 提取候选人ID（加密ID）
        const idEl = item.querySelector('[data-id], [data-uid], [data-geekid]');
        const geekId = idEl ? idEl.getAttribute('data-id') || idEl.getAttribute('data-uid') || idEl.getAttribute('data-geekid') || '' : '';

        results.push({
            name,
            last_message: lastMsg,
            time,
            unread_count: unread,
            job_title: jobTitle,
            geek_id: geekId,
            full_text: text.slice(0, 300),
            element_index: Array.from(items).indexOf(item)
        });
    }
    return results;
}"""


# JS: 提取当前对话窗口的消息
EXTRACT_MESSAGES_JS = """() => {
    const results = [];
    // 消息容器的多种选择器
    const msgSelectors = [
        '.message-content > div',
        '.chat-content .message',
        '.msg-item',
        '[class*="message-item"]',
        '[class*="msg-item"]',
        '.chat-message-list > div',
        '#message-list > div',
        '.im-message-item',
        'div[class*="bubble"]'
    ];

    let msgs = [];
    for (const sel of msgSelectors) {
        msgs = document.querySelectorAll(sel);
        if (msgs.length > 0) break;
    }

    for (let msg of msgs) {
        const text = (msg.innerText || '').trim();
        if (!text) continue;

        // 判断消息方向（自己发 vs 对方发）
        const classStr = msg.className || '';
        const parentClass = msg.parentElement?.className || '';
        const isSelf = classStr.includes('self') || classStr.includes('right') ||
                       classStr.includes('me') || classStr.includes('mine') ||
                       parentClass.includes('self') || parentClass.includes('right') ||
                       parentClass.includes('me') || parentClass.includes('mine');

        // 检测是否有附件/简历
        const hasAttachment = !!msg.querySelector(
            '[class*="file"], [class*="attach"], [class*="resume"], ' +
            'a[href*=".pdf"], a[href*=".doc"], a[href*=".docx"], ' +
            '[class*="card-file"], [class*="file-card"]'
        );

        // 提取附件信息
        let attachment = null;
        if (hasAttachment) {
            const fileEl = msg.querySelector(
                '[class*="file"], [class*="attach"], [class*="resume"], ' +
                'a[href*=".pdf"], a[href*=".doc"], [class*="card-file"]'
            );
            if (fileEl) {
                attachment = {
                    text: fileEl.innerText?.trim() || '',
                    href: fileEl.href || fileEl.getAttribute('data-url') || '',
                    tag: fileEl.tagName
                };
            }
        }

        // 提取时间戳
        const timeEl = msg.querySelector('[class*="time"], .message-time');
        const timestamp = timeEl ? timeEl.innerText.trim() : '';

        results.push({
            text: text.slice(0, 500),
            is_self: isSelf,
            has_attachment: hasAttachment,
            attachment: attachment,
            timestamp: timestamp
        });
    }
    return results;
}"""


# JS: 检测候选人信息卡片（对话窗口顶部）— 增强版提取职位信息
EXTRACT_CANDIDATE_INFO_JS = """() => {
    // === 策略1: 从对话头部信息栏提取 ===
    const headerSelectors = [
        '.user-info', '.geek-info', '.friend-info',
        '[class*="user-info"]', '[class*="geek-info"]',
        '.chat-header', '.message-header',
        '[class*="chat-info"]', '[class*="conversation-header"]'
    ];

    let headerInfo = null;
    for (const sel of headerSelectors) {
        const el = document.querySelector(sel);
        if (el) {
            const text = el.innerText || '';
            const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
            headerInfo = {
                source: 'header',
                full_text: text.slice(0, 800),
                name: lines[0] || '',
                info_lines: lines.slice(1, 8),
            };
            break;
        }
    }

    // === 策略2: 从左侧聊天列表当前选中项提取职位 ===
    let chatItemJob = '';
    const activeSelectors = [
        '.user-list li.active', '.user-list li.current',
        '.chat-list li.active', '.friend-list li.active',
        '[class*="friend"] li.active', '[class*="chat-item"].active',
        '.user-list li[class*="select"]', '.chat-list li[class*="select"]',
    ];

    for (const sel of activeSelectors) {
        const activeItem = document.querySelector(sel);
        if (activeItem) {
            const itemText = activeItem.innerText || '';
            const lines = itemText.split('\\n').map(l => l.trim()).filter(l => l);

            // 提取职位：通常在名字后面的行
            for (let i = 1; i < Math.min(lines.length, 5); i++) {
                const line = lines[i];
                // 跳过时间和未读数
                if (line.match(/^\\d{1,2}:\\d{2}/) || line.match(/^(昨天|前天|今天|\\d+天前)/)) continue;
                if (line.match(/^\\d+$/) && line.length <= 3) continue;
                // 跳过最后消息（通常较长）
                if (line.length > 20) continue;
                // 这可能就是职位
                if (line.length >= 2 && line.length <= 20) {
                    chatItemJob = line;
                    break;
                }
            }

            // 也尝试从子元素提取
            const jobEls = activeItem.querySelectorAll(
                '[class*="job"], [class*="position"], [class*="title"], .name-text, [class*="expect"]'
            );
            for (const jobEl of jobEls) {
                const jt = jobEl.innerText?.trim() || '';
                if (jt && jt.length >= 2 && jt.length <= 30) {
                    chatItemJob = jt;
                    break;
                }
            }
            break;
        }
    }

    // === 策略3: 从页面其他位置提取"投递职位"信息 ===
    let appliedJob = '';
    const appliedSelectors = [
        '[class*="job-name"]', '[class*="position-name"]',
        '[class*="apply-job"]', '[class*="deliver-job"]',
        '[class*="expect-job"]', '.job-label',
    ];
    for (const sel of appliedSelectors) {
        const el = document.querySelector(sel);
        if (el) {
            const jt = el.innerText?.trim() || '';
            if (jt && jt.length >= 2) {
                appliedJob = jt;
                break;
            }
        }
    }

    // 合并结果
    const result = headerInfo || {source: 'none', full_text: '', name: '', info_lines: []};
    result.chat_item_job = chatItemJob;
    result.applied_job = appliedJob;

    // 从 info_lines 中尝试解析职位
    if (!chatItemJob && !appliedJob && result.info_lines.length > 0) {
        for (const line of result.info_lines) {
            // 常见的职位标记
            if (line.includes('职位') || line.includes('应聘') ||
                line.includes('投递') || line.includes('期望')) {
                const clean = line.replace(/[职位应聘投递期望：:]/g, '').trim();
                if (clean.length >= 2 && clean.length <= 30) {
                    result.applied_job = clean;
                    break;
                }
            }
        }
    }

    return result;
}"""


class ChatScraper:
    """操作 Boss 直聘聊天页面."""

    def __init__(self, browser: BossBrowser):
        self.browser = browser

    async def navigate_to_chat(self) -> dict:
        """导航到 Boss 直聘聊天页面."""
        p = self.browser.page

        # 检查当前是否已在聊天页面
        current_url = p.url
        if "/web/boss/chat" in current_url or "/web/chat" in current_url:
            return {"status": "success", "message": "已在聊天页面"}

        # 尝试直接导航到聊天页
        try:
            await p.goto(BOSS_CHAT_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # 检查是否被重定向到旧版页面
            page_text = await p.evaluate("document.body.innerText || ''")
            if "停止维护" in page_text or "自动跳转" in page_text:
                # 等待跳转完成
                await asyncio.sleep(4)
                # 尝试新版聊天URL
                await p.goto(f"{BOSS_BASE_URL}/web/boss/chat", wait_until="domcontentloaded")
                await asyncio.sleep(3)
        except Exception as e:
            log.warning(f"导航聊天页失败: {e}")

        # 尝试通过点击导航菜单进入
        try:
            chat_menu = await p.query_selector(
                'a[href*="chat"], [class*="message"] a, .nav-chat, '
                'li[class*="chat"], a[class*="chat"]'
            )
            if chat_menu:
                await chat_menu.click()
                await asyncio.sleep(3)
        except Exception:
            pass

        # 验证是否成功进入聊天页面
        verify = await self._verify_chat_page()
        if verify:
            return {"status": "success", "message": "已进入聊天页面"}

        return {"status": "warning", "message": "请手动确认已进入Boss直聘聊天页面"}

    async def _verify_chat_page(self) -> bool:
        """验证是否在聊天页面."""
        try:
            p = self.browser.page
            # 检查是否有聊天列表元素
            for sel in ['.user-list li', '.chat-list li', '.friend-list li',
                        '[class*="friend"] li', '.main-message-list li']:
                el = await p.query_selector(sel)
                if el:
                    return True
            return False
        except Exception:
            return False

    async def get_chat_list(self) -> list[dict]:
        """读取左侧聊天列表（所有正在沟通的候选人）."""
        p = self.browser.page
        await self.browser.random_delay()

        # 尝试在主页面提取
        chat_list = await p.evaluate(EXTRACT_CHAT_LIST_JS)
        if chat_list:
            return chat_list

        # 尝试在iframe中提取
        frames = p.frames
        for frame in frames:
            try:
                chat_list = await frame.evaluate(EXTRACT_CHAT_LIST_JS)
                if chat_list:
                    return chat_list
            except Exception:
                continue

        return [{"error": "未找到聊天列表，请确认已进入聊天页面"}]

    async def select_chat_by_index(self, index: int) -> dict:
        """点击聊天列表中第 N 个候选人，进入对话."""
        p = self.browser.page

        # 在主页面尝试点击
        clicked = await p.evaluate(f"""() => {{
            const selectors = [
                '.user-list li', '.chat-list li', '.friend-list li',
                '[class*="friend"] li', '.main-message-list li', 'ul.user-list > li'
            ];
            for (const sel of selectors) {{
                const items = document.querySelectorAll(sel);
                if (items.length > {index}) {{
                    items[{index}].click();
                    return true;
                }}
            }}
            return false;
        }}""")

        if not clicked:
            # 尝试在iframe中点击
            for frame in p.frames:
                try:
                    clicked = await frame.evaluate(f"""() => {{
                        const selectors = [
                            '.user-list li', '.chat-list li', '.friend-list li',
                            '[class*="friend"] li', '.main-message-list li'
                        ];
                        for (const sel of selectors) {{
                            const items = document.querySelectorAll(sel);
                            if (items.length > {index}) {{
                                items[{index}].click();
                                return true;
                            }}
                        }}
                        return false;
                    }}""")
                    if clicked:
                        break
                except Exception:
                    continue

        if not clicked:
            return {"error": f"无法点击第 {index} 个聊天项"}

        await asyncio.sleep(2)
        await self.browser.random_delay()
        return {"status": "success", "message": f"已选择第 {index} 个聊天"}

    async def get_current_messages(self) -> list[dict]:
        """读取当前对话窗口的消息."""
        p = self.browser.page
        await self.browser.random_delay()

        # 尝试在主页面提取
        messages = await p.evaluate(EXTRACT_MESSAGES_JS)
        if messages:
            return messages

        # 尝试在iframe中提取
        for frame in p.frames:
            try:
                messages = await frame.evaluate(EXTRACT_MESSAGES_JS)
                if messages:
                    return messages
            except Exception:
                continue

        return [{"error": "未找到消息，请确认已选择一个对话"}]

    async def get_candidate_info(self, auto_match_job: bool = True) -> dict:
        """获取当前对话候选人的信息，自动识别投递职位并匹配岗位配置.

        Args:
            auto_match_job: 是否自动根据候选人投递职位匹配岗位配置
        Returns:
            包含候选人信息和岗位匹配结果的 dict
        """
        p = self.browser.page

        # 主页面尝试
        info = await p.evaluate(EXTRACT_CANDIDATE_INFO_JS)
        if not info:
            # iframe尝试
            for frame in p.frames:
                try:
                    info = await frame.evaluate(EXTRACT_CANDIDATE_INFO_JS)
                    if info:
                        break
                except Exception:
                    continue

        if not info:
            return {"error": "未找到候选人信息"}

        # 自动匹配岗位
        if auto_match_job:
            job_title = (
                info.get("applied_job", "")
                or info.get("chat_item_job", "")
                or ""
            )

            # 如果还没拿到职位，尝试从 full_text 或 info_lines 中解析
            if not job_title:
                full_text = info.get("full_text", "")
                match_result = _config.match_job_by_keywords(full_text)
                if match_result:
                    info["job_match"] = match_result
                    info["auto_job_title"] = match_result.get("title", "")
                    log.info(f"从文本关键词匹配岗位: {match_result.get('title')} "
                             f"(置信度: {match_result.get('confidence')})")
            else:
                # 用职位名称精确匹配
                match_result = _config.match_job_for_candidate(job_title)
                if match_result:
                    info["job_match"] = match_result
                    info["auto_job_title"] = match_result.get("title", "")
                    log.info(f"候选人投递职位 '{job_title}' → 匹配岗位: "
                             f"{match_result.get('title')} "
                             f"(置信度: {match_result.get('confidence')}, "
                             f"匹配分: {match_result.get('match_score')})")
                else:
                    log.warning(f"候选人投递职位 '{job_title}' 未匹配到任何岗位配置")

        return info

    async def send_message(self, message: str) -> dict:
        """在当前对话中发送消息."""
        p = self.browser.page

        # 查找输入框（多种选择器）
        input_selectors = [
            'textarea[class*="message"]',
            'textarea[class*="chat"]',
            'textarea[class*="input"]',
            'div[contenteditable="true"]',
            'textarea',
            '#message-input',
            '[class*="input-area"] textarea',
            '[class*="chat-input"] textarea',
        ]

        input_el = None

        # 主页面查找
        for sel in input_selectors:
            input_el = await p.query_selector(sel)
            if input_el:
                break

        # iframe查找
        target_frame = None
        if not input_el:
            for frame in p.frames:
                for sel in input_selectors:
                    try:
                        input_el = await frame.query_selector(sel)
                        if input_el:
                            target_frame = frame
                            break
                    except Exception:
                        continue
                if input_el:
                    break

        if not input_el:
            return {"error": "未找到消息输入框"}

        # 输入消息
        try:
            await input_el.click()
            await asyncio.sleep(0.3)

            # 对于 contenteditable 和 textarea 使用不同策略
            tag = await input_el.evaluate("el => el.tagName")
            if tag == "TEXTAREA":
                await input_el.fill(message)
            else:
                # contenteditable div
                await input_el.evaluate(f"el => {{ el.innerText = {repr(message)}; }}")

            await asyncio.sleep(0.5)

            # 查找发送按钮
            send_selectors = [
                'button[class*="send"]',
                'a[class*="send"]',
                '[class*="send-btn"]',
                '[class*="submit"]',
                'button:has-text("发送")',
                'a:has-text("发送")',
            ]

            send_btn = None
            search_scope = target_frame if target_frame else p
            for sel in send_selectors:
                try:
                    send_btn = await search_scope.query_selector(sel)
                    if send_btn:
                        break
                except Exception:
                    continue

            if send_btn:
                await send_btn.click()
            else:
                # 没有发送按钮，尝试按回车
                await input_el.press("Enter")

            await asyncio.sleep(1)
            return {"status": "success", "message": f"已发送消息: {message[:50]}..."}

        except Exception as e:
            return {"error": f"发送消息失败: {str(e)}"}

    async def request_resume(self, custom_message: str = "") -> dict:
        """向当前对话的候选人索要简历."""
        if not custom_message:
            custom_message = _config.PROFILE.get("messages", {}).get(
                "request_resume",
                "您好！您的经历很匹配我们的岗位，方便发一份完整简历给我吗？PDF或Word格式都可以，谢谢！"
            )
        return await self.send_message(custom_message)

    async def check_resume_received(self) -> dict:
        """检查当前对话中是否收到了简历附件."""
        messages = await self.get_current_messages()

        resume_messages = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("has_attachment"):
                attachment = msg.get("attachment", {})
                resume_messages.append({
                    "text": msg.get("text", ""),
                    "attachment_text": attachment.get("text", ""),
                    "attachment_url": attachment.get("href", ""),
                    "is_self": msg.get("is_self", False),
                    "timestamp": msg.get("timestamp", ""),
                })

        if resume_messages:
            return {
                "has_resume": True,
                "count": len(resume_messages),
                "resumes": resume_messages,
            }
        return {"has_resume": False, "message": "当前对话未检测到简历附件"}

    async def scroll_chat_list(self, direction: str = "down") -> dict:
        """滚动聊天列表，加载更多对话."""
        p = self.browser.page

        for frame in [p] + p.frames:
            try:
                if direction == "down":
                    await frame.evaluate(
                        "document.querySelector('.user-list, .chat-list, .friend-list')"
                        "?.scrollTo(0, document.body.scrollHeight)"
                    )
                else:
                    await frame.evaluate(
                        "document.querySelector('.user-list, .chat-list, .friend-list')"
                        "?.scrollTo(0, 0)"
                    )
                await asyncio.sleep(2)
                return {"status": "success"}
            except Exception:
                continue
        return {"status": "warning", "message": "未找到可滚动的聊天列表"}
