"""Visual QA - Screenshots of every screen in the user flow."""
import asyncio
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

SCREENSHOT_DIR = r"C:\Users\mayur\capstone\qa_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

async def screenshot(page, name):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    await page.screenshot(path=path, full_page=True)
    print(f"  [OK] {name}.png saved")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        
        # ─── SCREEN 1: Landing Page ───
        print("\n=== SCREEN 1: Landing Page ===")
        await page.goto("http://localhost:5000/")
        await page.wait_for_selector("#landing-container")
        await screenshot(page, "01_landing_page")
        
        # Check for visual issues on landing
        title = await page.text_content(".landing-title")
        subtitle = await page.text_content(".landing-sub")
        print(f"  Title: '{title}'")
        print(f"  Subtitle: '{subtitle}'")
        
        # Check file input visibility
        file_input = await page.query_selector("#resume-file")
        is_visible = await file_input.is_visible()
        print(f"  File input visible: {is_visible}")
        
        # Check button text
        start_btn = await page.text_content(".start-btn")
        print(f"  Start button text: '{start_btn}'")
        
        # ─── SCREEN 2: Upload Resume ───
        print("\n=== SCREEN 2: Upload Resume ===")
        resume_path = r"C:\Users\mayur\capstone\test_resume.txt"
        await page.set_input_files("#resume-file", resume_path)
        await screenshot(page, "02_resume_selected")
        
        # Click Start Quiz
        await page.click(".start-btn")
        await page.wait_for_selector("#loading-overlay.active", timeout=5000)
        await screenshot(page, "02b_loading_analyzing")
        
        # Wait for analysis to complete
        await page.wait_for_selector("#resume-analysis >> visible=true", timeout=120000)
        await asyncio.sleep(1)  # Let animations finish
        await screenshot(page, "03_resume_analysis")
        
        # ─── SCREEN 3: Resume Analysis Dashboard ───
        print("\n=== SCREEN 3: Resume Analysis Dashboard ===")
        
        # Check all analysis elements
        name_text = await page.text_content("#ra-name")
        domain_text = await page.text_content("#ra-domain")
        conf_text = await page.text_content("#ra-conf-pct")
        skills_count = await page.text_content("#ra-skills-count")
        exp_text = await page.text_content("#ra-exp")
        projects_text = await page.text_content("#ra-projects")
        edu_text = await page.text_content("#ra-edu")
        
        print(f"  Name: {name_text}")
        print(f"  Domain: {domain_text}")
        print(f"  Confidence: {conf_text}")
        print(f"  Skills count: {skills_count}")
        print(f"  Experience: {exp_text}")
        print(f"  Projects: {projects_text}")
        print(f"  Education: {edu_text}")
        
        # Check skills chips rendered
        skill_chips = await page.query_selector_all(".skill-chip")
        print(f"  Skill chips rendered: {len(skill_chips)}")
        
        # Check CTA button
        cta_text = await page.text_content(".ra-cta")
        print(f"  CTA text: '{cta_text.strip()}'")
        
        # ─── SCREEN 4: Quiz ───
        print("\n=== SCREEN 4: Quiz ===")
        await page.click(".ra-cta")
        await page.wait_for_selector("#quiz-section >> visible=true", timeout=30000)
        await asyncio.sleep(1)
        await screenshot(page, "04_quiz")
        
        # Check quiz structure
        quiz_cards = await page.query_selector_all(".quiz-question-card")
        print(f"  Quiz cards rendered: {len(quiz_cards)}")
        
        # Check progress bar
        quiz_total = await page.text_content("#quiz-total")
        quiz_progress = await page.text_content("#quiz-progress")
        print(f"  Quiz total: {quiz_total}, Progress: {quiz_progress}")
        
        # Check if questions have options
        first_options = await page.query_selector_all('.quiz-question-card:first-child .quiz-opt')
        print(f"  First question options: {len(first_options)}")
        
        # Check difficulty badges
        badges = await page.query_selector_all(".quiz-q-badge")
        badge_texts = []
        for b in badges[:5]:
            badge_texts.append(await b.text_content())
        print(f"  Difficulty badges (first 5): {badge_texts}")
        
        # Scroll quiz to see all questions
        await page.evaluate("document.getElementById('quiz-section').scrollTop = 10000")
        await screenshot(page, "04b_quiz_bottom")
        
        # Check submit button
        submit_btns = await page.query_selector_all(".start-btn")
        if submit_btns:
            last_btn = submit_btns[-1]
            btn_text = await last_btn.text_content()
            print(f"  Submit button: '{btn_text.strip()}'")
        
        # Answer all questions (select option 1 for all - the most common correct answer)
        for i in range(len(quiz_cards)):
            radio = await page.query_selector(f'input[name="q{i}"][value="1"]')
            if radio:
                await radio.click()
            else:
                radio = await page.query_selector(f'input[name="q{i}"][value="0"]')
                if radio:
                    await radio.click()
        
        await asyncio.sleep(0.5)
        await screenshot(page, "04c_quiz_answered")
        
        # Submit quiz
        submit_btn = await page.query_selector("#quiz-questions-container .start-btn")
        if submit_btn:
            await submit_btn.click()
        await asyncio.sleep(1)
        
        # ─── SCREEN 5: Subject Selection ───
        print("\n=== SCREEN 5: Subject Selection ===")
        await page.wait_for_selector("#subject-selection-section >> visible=true", timeout=10000)
        await screenshot(page, "05_subject_selection")
        
        # Check dropdowns
        subject_options = await page.query_selector_all("#subject-select option")
        topic_options = await page.query_selector_all("#topic-select option")
        print(f"  Subject options: {len(subject_options)}")
        print(f"  Topic options: {len(topic_options)}")
        
        # Check quiz result message
        subject_section = await page.query_selector("#subject-selection-section")
        result_text = await subject_section.inner_text()
        if "Passed" in result_text or "Completed" in result_text:
            print(f"  Quiz result: PRESENT")
        else:
            print(f"  Quiz result: MISSING")
        
        # Select CN and a topic, then start interview
        await page.select_option("#subject-select", "CN")
        await page.select_option("#topic-select", "TCP")
        await screenshot(page, "05b_subject_selected")
        
        # ─── SCREEN 6: Interview Chat ───
        print("\n=== SCREEN 6: Interview Chat ===")
        await page.click(".subject-start-btn")
        await asyncio.sleep(1)
        
        # Wait for chat container
        await page.wait_for_selector("#chat-container >> visible=true", timeout=10000)
        await asyncio.sleep(2)  # Wait for first question to load
        await screenshot(page, "06_interview_chat")
        
        # Check chat header
        header_text = await page.text_content("#chat-header-title")
        print(f"  Chat header: '{header_text}'")
        
        # Check messages
        messages = await page.query_selector_all(".msg-wrapper")
        print(f"  Messages rendered: {len(messages)}")
        
        # Check input area
        input_visible = await page.is_visible("#user-input")
        send_visible = await page.is_visible("#send-btn")
        mic_visible = await page.is_visible("#mic-btn")
        print(f"  Input visible: {input_visible}, Send visible: {send_visible}, Mic visible: {mic_visible}")
        
        # Type an answer
        await page.fill("#user-input", "TCP is a connection-oriented reliable transport protocol that uses a three-way handshake to establish connections between client and server")
        await screenshot(page, "06b_answer_typed")
        
        # Submit answer
        await page.click("#send-btn")
        await asyncio.sleep(2)  # Wait for fill-mask prompt
        await screenshot(page, "06c_fill_mask_prompt")
        
        # Type fill mask answer
        await page.fill("#user-input", "SYN")
        await page.click("#send-btn")
        await asyncio.sleep(3)  # Wait for evaluation
        await screenshot(page, "06d_evaluation_result")
        
        # Wait for next question to load
        await asyncio.sleep(5)
        await screenshot(page, "06e_next_question")
        
        # Scroll to see all messages
        await page.evaluate("document.getElementById('messages').scrollTop = 10000")
        await screenshot(page, "06f_chat_scrolled")
        
        # ─── SCREEN 7: Dashboard (after enough questions) ───
        print("\n=== SCREEN 7: Final Dashboard ===")
        # Answer 4 more questions quickly to reach the limit
        for q_num in range(4):
            # Wait for question
            await asyncio.sleep(5)
            await page.fill("#user-input", "This is a test answer about the topic covering key concepts and definitions")
            await page.click("#send-btn")
            await asyncio.sleep(2)
            await page.fill("#user-input", "answer")
            await page.click("#send-btn")
            await asyncio.sleep(5)
            print(f"  Answered question {q_num + 2}")
        
        # Wait for dashboard to appear
        await asyncio.sleep(5)
        await screenshot(page, "07_dashboard")
        
        # Check dashboard content
        dashboard_visible = await page.is_visible("#dashboard-container")
        print(f"  Dashboard visible: {dashboard_visible}")
        
        if dashboard_visible:
            stats = await page.query_selector_all(".stat-box")
            print(f"  Stat boxes: {len(stats)}")
            
            history_cards = await page.query_selector_all(".history-card")
            print(f"  History cards: {len(history_cards)}")
            
            skill_bars = await page.query_selector_all(".skill-bar-container")
            print(f"  Skill bars: {len(skill_bars)}")
            
            retry_btn = await page.query_selector(".retry-btn")
            if retry_btn:
                retry_text = await retry_btn.text_content()
                print(f"  Retry button: '{retry_text.strip()}'")
            
            await page.evaluate("document.getElementById('dashboard-container').scrollTop = 10000")
            await screenshot(page, "07b_dashboard_bottom")
        
        # ─── SCREEN 8: Reset / New Session ───
        print("\n=== SCREEN 8: Reset ===")
        retry_btn = await page.query_selector(".retry-btn")
        if retry_btn:
            await retry_btn.click()
            await asyncio.sleep(1)
            await screenshot(page, "08_reset_landing")
            
            # Verify we're back at landing
            landing_visible = await page.is_visible("#landing-container")
            print(f"  Back to landing: {landing_visible}")
        
        # ─── TEST: Direct Quiz (no resume) ───
        print("\n=== TEST: Direct Quiz Button ===")
        test_btn = await page.query_selector("button[onclick='testQuizDirectly()']")
        if test_btn:
            await test_btn.click()
            await asyncio.sleep(5)
            await screenshot(page, "09_direct_quiz")
        
        await browser.close()
        print("\n=== ALL SCREENSHOTS COMPLETE ===")

asyncio.run(main())
