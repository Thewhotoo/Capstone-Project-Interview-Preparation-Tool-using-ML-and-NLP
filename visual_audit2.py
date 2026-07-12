"""Quick audit of quiz and interview screens only."""
import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        
        await page.goto("http://localhost:5000/")
        await page.wait_for_selector("#landing-container")
        
        # Quick quiz via testQuizDirectly
        await page.evaluate("testQuizDirectly()")
        await asyncio.sleep(5)
        
        # Quiz audit
        print("=== QUIZ SCREEN ===")
        quiz_scroll = await page.evaluate("""(() => {
            const el = document.getElementById('quiz-section');
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { display: s.display, width: r.width, height: r.height, 
                     maxHeight: s.getPropertyValue('max-height'), overflow: s.getPropertyValue('overflow-y'),
                     scrollH: el.scrollHeight, clientH: el.clientHeight };
        })()""")
        print(f"  Quiz section: {quiz_scroll['width']:.0f}x{quiz_scroll['height']:.0f}, maxH={quiz_scroll['maxHeight']}, overflow={quiz_scroll['overflow']}")
        print(f"  Scroll: scrollH={quiz_scroll['scrollH']}, clientH={quiz_scroll['clientH']}")
        
        # Header card
        hc = await page.evaluate("""(() => {
            const el = document.querySelector('.quiz-header-card');
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { position: s.position, top: s.top, zIndex: s.zIndex, width: r.width, height: r.height };
        })()""")
        print(f"  Header card: pos={hc['position']}, top={hc['top']}, z={hc['zIndex']}, {hc['width']:.0f}x{hc['height']:.0f}")
        
        # Question card widths
        cw = await page.evaluate("""(() => {
            return Array.from(document.querySelectorAll('.quiz-question-card')).slice(0,5).map(el => {
                const r = el.getBoundingClientRect();
                return r.width;
            });
        })()""")
        print(f"  Card widths (first 5): {[f'{w:.0f}' for w in cw]}")
        
        # Option text color contrast check
        oc = await page.evaluate("""(() => {
            const label = document.querySelector('.quiz-opt label');
            if (!label) return null;
            const s = getComputedStyle(label);
            return { color: s.color, fontSize: s.fontSize, cursor: s.cursor };
        })()""")
        if oc:
            print(f"  Option: color={oc['color']}, size={oc['fontSize']}, cursor={oc['cursor']}")
        
        # Badge colors
        bc = await page.evaluate("""(() => {
            const badges = {};
            document.querySelectorAll('.quiz-q-badge').forEach(el => {
                const text = el.textContent.trim();
                const s = getComputedStyle(el);
                if (!badges[text]) badges[text] = { color: s.color, bg: s.backgroundColor };
            });
            return badges;
        })""")
        for d, c in bc.items():
            print(f"  Badge '{d}': color={c['color']}, bg={c['bg'][:30]}")
        
        # Submit button
        sb = await page.evaluate("""(() => {
            const btn = document.querySelector('#quiz-questions-container .start-btn');
            if (!btn) return null;
            const s = getComputedStyle(btn);
            const r = btn.getBoundingClientRect();
            return { width: r.width, height: r.height, bg: s.backgroundColor, radius: s.borderRadius };
        })()""")
        if sb:
            print(f"  Submit: {sb['width']:.0f}x{sb['height']:.0f}, bg={sb['bg']}, radius={sb['radius']}")
        
        # Answer quiz and go to subject selection
        cards = await page.query_selector_all(".quiz-question-card")
        for i in range(len(cards)):
            r = await page.query_selector(f'input[name="q{i}"][value="1"]')
            if r: await r.click()
            else:
                r = await page.query_selector(f'input[name="q{i}"][value="0"]')
                if r: await r.click()
        await asyncio.sleep(0.5)
        submit = await page.query_selector("#quiz-questions-container .start-btn")
        if submit: await submit.click()
        await asyncio.sleep(1)
        
        # Start interview
        await page.select_option("#subject-select", "CN")
        await page.select_option("#topic-select", "TCP")
        await page.click(".subject-start-btn")
        await asyncio.sleep(3)
        
        # Interview audit
        print("\n=== INTERVIEW CHAT ===")
        chat_hdr = await page.evaluate("""(() => {
            const el = document.getElementById('chat-header-title');
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { text: el.textContent, width: r.width, height: r.height, padding: s.padding };
        })()""")
        print(f"  Header: '{chat_hdr['text']}', {chat_hdr['width']:.0f}x{chat_hdr['height']:.0f}")
        
        # Messages area
        ma = await page.evaluate("""(() => {
            const el = document.getElementById('messages');
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { width: r.width, left: r.left, maxW: s.maxWidth, padding: s.padding, gap: s.gap };
        })()""")
        print(f"  Messages: {ma['width']:.0f}w at left={ma['left']:.0f}, maxW={ma['maxW']}, padding={ma['padding']}, gap={ma['gap']}")
        
        # Input area  
        ia = await page.evaluate("""(() => {
            const el = document.getElementById('input-area');
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { width: r.width, left: r.left, maxWidth: s.maxWidth, gap: s.gap, padding: s.padding, paddingBottom: s.paddingBottom };
        })()""")
        print(f"  Input area: {ia['width']:.0f}w at left={ia['left']:.0f}, maxW={ia['maxWidth']}, gap={ia['gap']}, padding={ia['padding']}")
        
        # Text input + buttons sizing
        ti = await page.evaluate("""(() => {
            const input = document.getElementById('user-input');
            const send = document.getElementById('send-btn');
            const mic = document.getElementById('mic-btn');
            const ir = input.getBoundingClientRect();
            const sr = send.getBoundingClientRect();
            const mr = mic.getBoundingClientRect();
            const is = getComputedStyle(input);
            const ss = getComputedStyle(send);
            const ms = getComputedStyle(mic);
            return { 
                inputW: ir.width, inputH: ir.height, inputGrow: is.flexGrow, inputRadius: is.borderRadius,
                sendW: sr.width, sendH: sr.height, sendRadius: ss.borderRadius, sendFontSize: ss.fontSize,
                micW: mr.width, micH: mr.height, micRadius: ms.borderRadius, micFontSize: ms.fontSize,
                inputBorder: is.border?.substring(0, 30), inputBg: is.backgroundColor
            };
        })()""")
        print(f"  Input: {ti['inputW']:.0f}x{ti['inputH']:.0f}, radius={ti['inputRadius']}, border={ti['inputBorder']}")
        print(f"  Send:  {ti['sendW']:.0f}x{ti['sendH']:.0f}, radius={ti['sendRadius']}, size={ti['sendFontSize']}")
        print(f"  Mic:   {ti['micW']:.0f}x{ti['micH']:.0f}, radius={ti['micRadius']}, size={ti['micFontSize']}")
        
        # Button height alignment
        if abs(ti['sendH'] - ti['micH']) > 2:
            print(f"  [ISSUE] Button height mismatch: send={ti['sendH']:.0f} vs mic={ti['micH']:.0f}")
        if abs(ti['inputH'] - ti['sendH']) > 6:
            print(f"  [ISSUE] Input/button height mismatch: input={ti['inputH']:.0f} vs send={ti['sendH']:.0f}")
        
        # Bot message bubble
        bm = await page.evaluate("""(() => {
            const el = document.querySelector('.bot-msg');
            if (!el) return null;
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { width: r.width, padding: s.padding, bg: s.backgroundColor, border: s.border?.substring(0, 40), radius: s.borderRadius, fontSize: s.fontSize, lineHeight: s.lineHeight };
        })()""")
        if bm:
            print(f"  Bot bubble: {bm['width']:.0f}w, padding={bm['padding']}, radius={bm['radius']}, size={bm['fontSize']}")
        
        # Avatar
        av = await page.evaluate("""(() => {
            const el = document.querySelector('.avatar');
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { w: r.width, h: r.height, bg: s.backgroundColor, border: s.border?.substring(0, 30), radius: s.borderRadius };
        })()""")
        print(f"  Avatar: {av['w']:.0f}x{av['h']:.0f}, bg={av['bg'][:30]}, radius={av['radius']}")
        
        # Msg wrapper alignment
        mw = await page.evaluate("""(() => {
            const el = document.querySelector('.bot-wrapper');
            if (!el) return null;
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { alignSelf: s.alignSelf, wrapperW: r.width, left: r.left, flexDirection: s.flexDirection };
        })()""")
        if mw:
            print(f"  Bot wrapper: align={mw['alignSelf']}, maxW={mw['wrapperW']:.0f}, left={mw['left']:.0f}")
        
        # Check message content width (should not exceed max-width)
        msg_content = await page.evaluate("""(() => {
            const el = document.querySelector('.bot-msg');
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return { width: r.width, right: r.right, fontSize: s.fontSize, lineHeight: s.lineHeight };
        })()""")
        if msg_content:
            print(f"  Bot msg content: {msg_content['width']:.0f}w, right={msg_content['right']:.0f}")
        
        await browser.close()

asyncio.run(main())
