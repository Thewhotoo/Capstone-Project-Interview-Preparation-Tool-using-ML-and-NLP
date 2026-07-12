"""Programmatic Visual QA - Extract computed styles, positions, overflow, alignment from every screen."""
import asyncio
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

async def js(page, code):
    return await page.evaluate(code)

async def audit_landing(page):
    print("\n" + "="*60)
    print("SCREEN 1: LANDING PAGE")
    print("="*60)
    issues = []
    
    await page.goto("http://localhost:5000/")
    await page.wait_for_selector("#landing-container")
    await asyncio.sleep(0.5)
    
    # 1. Check landing container centering and dimensions
    landing = await js(page, """(() => {
        const el = document.getElementById('landing-container');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return {
            display: s.display, width: r.width, height: r.height,
            left: r.left, top: r.top, right: r.right, bottom: r.bottom,
            maxWidth: s.maxWidth, margin: s.margin, textAlign: s.textAlign,
            padding: s.padding
        };
    })()""")
    vw = await js(page, "window.innerWidth")
    vh = await js(page, "window.innerHeight")
    print(f"  Viewport: {vw}x{vh}")
    print(f"  Landing container: {landing['width']:.0f}x{landing['height']:.0f} at ({landing['left']:.0f}, {landing['top']:.0f})")
    print(f"  Centered: left={landing['left']:.0f}, expected_center={(vw-landing['width'])/2:.0f}")
    
    center_offset = abs(landing['left'] - (vw - landing['width']) / 2)
    if center_offset > 5:
        issues.append(f"Landing container not horizontally centered (offset: {center_offset:.0f}px)")
    
    # 2. Check vertical centering
    vertical_center = abs(landing['top'] - (vh - landing['height']) / 2)
    print(f"  Vertical center offset: {vertical_center:.0f}px")
    if vertical_center > 50:
        issues.append(f"Landing container not vertically centered (offset: {vertical_center:.0f}px)")
    
    # 3. Title typography
    title = await js(page, """(() => {
        const el = document.querySelector('.landing-title');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { fontSize: s.fontSize, fontWeight: s.fontWeight, color: s.color, 
                 fontFamily: s.fontFamily, lineHeight: s.lineHeight, marginBottom: s.marginBottom,
                 width: r.width, height: r.height };
    })()""")
    print(f"  Title: {title['fontSize']}, weight={title['fontWeight']}, color={title['color']}, mb={title['marginBottom']}")
    
    # 4. Subtitle
    sub = await js(page, """(() => {
        const el = document.querySelector('.landing-sub');
        const s = getComputedStyle(el);
        return { fontSize: s.fontSize, color: s.color, marginBottom: s.marginBottom };
    })()""")
    print(f"  Subtitle: {sub['fontSize']}, color={sub['color']}, mb={sub['marginBottom']}")
    
    # 5. File input styling
    file_input = await js(page, """(() => {
        const el = document.getElementById('resume-file');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { display: s.display, width: r.width, height: r.height, padding: s.padding,
                 border: s.border, borderRadius: s.borderRadius, background: s.backgroundColor,
                 color: s.color, cursor: s.cursor };
    })()""")
    print(f"  File input: {file_input['width']:.0f}x{file_input['height']:.0f}, border={file_input['border'][:30]}, cursor={file_input['cursor']}")
    
    # 6. Start button
    btn = await js(page, """(() => {
        const el = document.querySelector('.start-btn');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { display: s.display, width: r.width, height: r.height, padding: s.padding,
                 background: s.backgroundColor, color: s.color, borderRadius: s.borderRadius,
                 fontSize: s.fontSize, fontWeight: s.fontWeight, cursor: s.cursor, marginTop: s.marginTop };
    })()""")
    print(f"  Start button: {btn['width']:.0f}x{btn['height']:.0f}, bg={btn['background']}, color={btn['color']}, radius={btn['borderRadius']}")
    
    # 7. Check overall spacing between elements
    elements = await js(page, """(() => {
        const els = document.querySelectorAll('#landing-container > *');
        return Array.from(els).map(el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return { tag: el.tagName + '.' + el.className.split(' ')[0], top: r.top, bottom: r.bottom, height: r.height, display: s.display, mb: s.marginBottom };
        });
    })()""")
    print("  Element layout:")
    prev_bottom = 0
    for e in elements:
        if e['display'] == 'none':
            continue
        gap = e['top'] - prev_bottom
        print(f"    {e['tag']}: top={e['top']:.0f}, h={e['height']:.0f}, gap_above={gap:.0f}px, mb={e['mb']}")
        prev_bottom = e['bottom']
    
    # 8. Check for overflow
    overflow = await js(page, """(() => {
        const body = document.body;
        return {
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            scrollHeight: document.documentElement.scrollHeight,
            clientHeight: document.documentElement.clientHeight,
            bodyOverflow: getComputedStyle(body).overflow
        };
    })()""")
    print(f"  Body overflow: scrollW={overflow['scrollWidth']}, clientW={overflow['clientWidth']}, scrollH={overflow['scrollHeight']}, bodyOverflow={overflow['bodyOverflow']}")
    if overflow['scrollWidth'] > overflow['clientWidth'] + 5:
        issues.append(f"Horizontal overflow: scrollWidth({overflow['scrollWidth']}) > clientWidth({overflow['clientWidth']})")
    
    # 9. Check hidden sections are actually hidden
    hidden_sections = await js(page, """(() => {
        const sections = ['resume-analysis', 'quiz-section', 'subject-selection-section', 'chat-container', 'dashboard-container'];
        return sections.map(id => {
            const el = document.getElementById(id);
            if (!el) return { id, exists: false };
            const s = getComputedStyle(el);
            return { id, display: s.display, visibility: s.visibility };
        });
    })()""")
    for s in hidden_sections:
        if s.get('display') != 'none' and s.get('exists') != False:
            issues.append(f"Section #{s['id']} should be hidden but display={s['display']}")
    
    # 10. Check button alignment consistency
    buttons = await js(page, """(() => {
        return Array.from(document.querySelectorAll('#landing-container button')).map(el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return { text: el.textContent.trim().substring(0, 25), width: r.width, left: r.left, borderRadius: s.borderRadius, fontSize: s.fontSize };
        });
    })()""")
    if len(buttons) >= 2:
        widths = [b['width'] for b in buttons]
        lefts = [b['left'] for b in buttons]
        print(f"  Button widths: {[f'{w:.0f}' for w in widths]}")
        print(f"  Button lefts: {[f'{l:.0f}' for l in lefts]}")
        if max(widths) - min(widths) > 2:
            issues.append(f"Button widths not consistent: {[f'{w:.0f}' for w in widths]}")
    
    # 11. Check spacing between form-group label and input
    form_spacing = await js(page, """(() => {
        const label = document.querySelector('.form-group label');
        const input = document.querySelector('#resume-file');
        if (!label || !input) return null;
        const lr = label.getBoundingClientRect();
        const ir = input.getBoundingClientRect();
        return { labelBottom: lr.bottom, inputTop: ir.top, gap: ir.top - lr.bottom, labelMB: getComputedStyle(label).marginBottom };
    })()""")
    if form_spacing:
        print(f"  Label-to-input gap: {form_spacing['gap']:.0f}px (label mb: {form_spacing['labelMB']})")
    
    return issues

async def audit_resume_analysis(page):
    print("\n" + "="*60)
    print("SCREEN 2: RESUME ANALYSIS DASHBOARD")
    print("="*60)
    issues = []
    
    # Check section is visible
    visible = await js(page, """(() => {
        const el = document.getElementById('resume-analysis');
        const s = getComputedStyle(el);
        return { display: s.display, visibility: s.visibility };
    })()""")
    print(f"  Resume analysis visible: display={visible['display']}")
    
    # Check header layout (avatar + name + badges)
    header = await js(page, """(() => {
        const el = document.querySelector('.ra-header');
        const s = getComputedStyle(el);
        return { display: s.display, gap: s.gap, alignItems: s.alignItems, marginBottom: s.marginBottom, width: el.getBoundingClientRect().width };
    })()""")
    print(f"  Header: display={header['display']}, gap={header['gap']}, align={header['alignItems']}")
    
    # Avatar
    avatar = await js(page, """(() => {
        const el = document.querySelector('.ra-avatar');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, height: r.height, borderRadius: s.borderRadius, fontSize: s.fontSize, bg: s.backgroundColor };
    })()""")
    print(f"  Avatar: {avatar['width']:.0f}x{avatar['height']:.0f}, radius={avatar['borderRadius']}, bg={avatar['bg'][:30]}")
    
    # Name
    name = await js(page, """(() => {
        const el = document.getElementById('ra-name');
        const s = getComputedStyle(el);
        return { fontSize: s.fontSize, fontWeight: s.fontWeight, color: s.color };
    })()""")
    print(f"  Name: {name['fontSize']}, weight={name['fontWeight']}, color={name['color']}")
    
    # Domain badge
    domain_badge = await js(page, """(() => {
        const el = document.querySelector('.ra-domain-badge');
        const s = getComputedStyle(el);
        return { bg: s.backgroundColor, color: s.color, border: s.border, padding: s.padding, borderRadius: s.borderRadius, fontSize: s.fontSize };
    })()""")
    print(f"  Domain badge: bg={domain_badge['bg'][:30]}, color={domain_badge['color']}")
    
    # Grid layout
    grid = await js(page, """(() => {
        const el = document.querySelector('.ra-grid');
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { display: s.display, gridTemplateColumns: s.gridTemplateColumns, gap: s.gap, width: r.width, height: r.height };
    })()""")
    if grid:
        print(f"  Grid: display={grid['display']}, cols={grid['gridTemplateColumns']}, gap={grid['gap']}, {grid['width']:.0f}x{grid['height']:.0f}")
    
    # Stats grid
    stats = await js(page, """(() => {
        const els = document.querySelectorAll('.ra-stat');
        return Array.from(els).map(el => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { val: el.querySelector('.ra-stat-val')?.textContent, lbl: el.querySelector('.ra-stat-lbl')?.textContent,
                     width: r.width, height: r.height, padding: s.padding, bg: s.backgroundColor };
        });
    })()""")
    for st in stats:
        print(f"  Stat: {st['val']} ({st['lbl']}) - {st['width']:.0f}x{st['height']:.0f}, bg={st['bg'][:30]}")
    
    # Confidence bar
    conf = await js(page, """(() => {
        const track = document.querySelector('.ra-conf-track');
        const fill = document.querySelector('.ra-conf-fill');
        const pct = document.querySelector('.ra-conf-pct');
        if (!track) return null;
        const ts = getComputedStyle(track);
        const fs = fill ? getComputedStyle(fill) : null;
        return { trackH: ts.height, trackBg: ts.backgroundColor, trackRadius: ts.borderRadius,
                 fillW: fs?.width, fillBg: fs?.background?.substring(0, 40),
                 pctText: pct?.textContent };
    })()""")
    if conf:
        print(f"  Confidence bar: trackH={conf['trackH']}, fillW={conf['fillW']}, pct={conf['pctText']}")
    
    # Skills container
    skills = await js(page, """(() => {
        const container = document.querySelector('#ra-skills-container');
        if (!container) return null;
        const s = getComputedStyle(container);
        const r = container.getBoundingClientRect();
        const chips = container.querySelectorAll('.skill-chip');
        const groups = container.querySelectorAll('.skills-group');
        return { height: r.height, maxHeight: s.getPropertyValue('max-height'), overflow: s.getPropertyValue('overflow-y'), chipCount: chips.length, groupCount: groups.length };
    })()""")
    if skills:
        print(f"  Skills container: h={skills['height']:.0f}, maxHeight={skills.get('maxHeight')}, overflow={skills.get('overflow')}, chips={skills['chipCount']}, groups={skills['groupCount']}")
    
    # CTA button
    cta = await js(page, """(() => {
        const el = document.querySelector('.ra-cta');
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, height: r.height, bg: s.background?.substring(0, 50), color: s.color, 
                 borderRadius: s.borderRadius, fontSize: s.fontSize, fontWeight: s.fontWeight, cursor: s.cursor };
    })()""")
    if cta:
        print(f"  CTA button: {cta['width']:.0f}x{cta['height']:.0f}, bg={cta['bg']}, radius={cta['borderRadius']}")
    
    # Check alignment: left column vs right column heights
    cols = await js(page, """(() => {
        const left = document.querySelector('.ra-col-left');
        const right = document.querySelector('.ra-col-right');
        if (!left || !right) return null;
        const lr = left.getBoundingClientRect();
        const rr = right.getBoundingClientRect();
        return { leftH: lr.height, rightH: rr.height, leftW: lr.width, rightW: rr.width, leftTop: lr.top, rightTop: rr.top };
    })()""")
    if cols:
        print(f"  Columns: left={cols['leftW']:.0f}x{cols['leftH']:.0f}, right={cols['rightW']:.0f}x{cols['rightH']:.0f}")
        if abs(cols['leftTop'] - cols['rightTop']) > 10:
            issues.append(f"Columns not top-aligned: left top={cols['leftTop']:.0f}, right top={cols['rightTop']:.0f}")
        if abs(cols['leftH'] - cols['rightH']) > 50:
            issues.append(f"Columns height mismatch: left={cols['leftH']:.0f}, right={cols['rightH']:.0f}")
    
    # Check for overflow in the analysis section
    analysis_overflow = await js(page, """(() => {
        const el = document.getElementById('resume-analysis');
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { width: r.width, right: r.right, parentWidth: el.parentElement?.getBoundingClientRect().width };
    })()""")
    if analysis_overflow:
        if analysis_overflow['right'] > analysis_overflow['parentWidth'] + 5:
            issues.append(f"Resume analysis overflows parent: right={analysis_overflow['right']:.0f} > parent_w={analysis_overflow['parentWidth']:.0f}")
    
    return issues

async def audit_quiz(page):
    print("\n" + "="*60)
    print("SCREEN 3: DOMAIN QUIZ")
    print("="*60)
    issues = []
    
    # Check quiz section
    quiz_visible = await js(page, """(() => {
        const el = document.getElementById('quiz-section');
        const s = getComputedStyle(el);
        return { display: s.display, maxHeight: s.maxHeight, overflow: s.overflowY, width: el.getBoundingClientRect().width };
    })()""")
    print(f"  Quiz section: display={quiz_visible['display']}, maxH={quiz_visible['maxHeight']}, overflow={quiz_visible['overflowY']}")
    
    # Check sticky header card
    header_card = await js(page, """(() => {
        const el = document.querySelector('.quiz-header-card');
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { position: s.position, top: s.top, zIndex: s.zIndex, padding: s.padding, bg: s.backgroundColor,
                 width: r.width, height: r.height };
    })()""")
    if header_card:
        print(f"  Header card: pos={header_card['position']}, top={header_card['top']}, z={header_card['zIndex']}, {header_card['width']:.0f}x{header_card['height']:.0f}")
    
    # Check progress bar
    progress = await js(page, """(() => {
        const track = document.querySelector('.quiz-progress-track');
        const bar = document.getElementById('quiz-progress-bar');
        if (!track || !bar) return null;
        const ts = getComputedStyle(track);
        const bs = getComputedStyle(bar);
        return { trackH: ts.height, trackBg: ts.backgroundColor, trackRadius: ts.borderRadius,
                 barH: bs.height, barBg: bs.backgroundColor, barW: bs.width };
    })()""")
    if progress:
        print(f"  Progress: trackH={progress['trackH']}, barH={progress['barH']}, barBg={progress['barBg']}")
    
    # Check question card consistency
    cards = await js(page, """(() => {
        const els = document.querySelectorAll('.quiz-question-card');
        return Array.from(els).slice(0, 3).map(el => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { width: r.width, padding: s.padding, bg: s.backgroundColor, border: s.border?.substring(0, 40), borderRadius: s.borderRadius };
        });
    })()""")
    if cards:
        widths = [c['width'] for c in cards]
        print(f"  Question card widths: {[f'{w:.0f}' for w in widths]}")
        if max(widths) - min(widths) > 2:
            issues.append(f"Question card widths inconsistent: {[f'{w:.0f}' for w in widths]}")
    
    # Check option styling
    opts = await js(page, """(() => {
        const labels = document.querySelectorAll('.quiz-opt label');
        if (!labels.length) return null;
        const first = labels[0];
        const s = getComputedStyle(first);
        const r = first.getBoundingClientRect();
        return { color: s.color, fontSize: s.fontSize, cursor: s.cursor, height: r.height, display: s.display, alignItems: s.alignItems };
    })()""")
    if opts:
        print(f"  Option label: color={opts['color']}, fontSize={opts['fontSize']}, cursor={opts['cursor']}, h={opts['height']:.0f}")
    
    # Check difficulty badges
    badges = await js(page, """(() => {
        const els = document.querySelectorAll('.quiz-q-badge');
        const types = {};
        els.forEach(el => {
            const text = el.textContent.trim();
            const s = getComputedStyle(el);
            if (!types[text]) types[text] = { color: s.color, bg: s.backgroundColor, border: s.border?.substring(0, 40) };
        });
        return { total: els.length, types };
    })()""")
    print(f"  Badges: {badges['total']} total")
    for diff, style in badges['types'].items():
        print(f"    {diff}: color={style['color']}, bg={style['bg'][:30]}")
    
    # Check submit button
    submit = await js(page, """(() => {
        const btns = document.querySelectorAll('#quiz-questions-container .start-btn');
        if (!btns.length) return null;
        const el = btns[btns.length - 1];
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, height: r.height, bg: s.backgroundColor, color: s.color, borderRadius: s.borderRadius, marginTop: s.marginTop, cursor: s.cursor };
    })()""")
    if submit:
        print(f"  Submit button: {submit['width']:.0f}x{submit['height']:.0f}, bg={submit['bg']}, radius={submit['borderRadius']}")
    
    # Check if quiz scrolls properly
    quiz_scroll = await js(page, """(() => {
        const el = document.getElementById('quiz-section');
        return { scrollH: el.scrollHeight, clientH: el.clientHeight, scrollT: el.scrollTop };
    })()""")
    print(f"  Quiz scroll: scrollH={quiz_scroll['scrollH']}, clientH={quiz_scroll['clientH']}, scrollTop={quiz_scroll['scrollT']}")
    
    return issues

async def audit_subject_selection(page):
    print("\n" + "="*60)
    print("SCREEN 4: SUBJECT SELECTION")
    print("="*60)
    issues = []
    
    # Check section visibility
    visible = await js(page, """(() => {
        const el = document.getElementById('subject-selection-section');
        const s = getComputedStyle(el);
        return { display: s.display, marginTop: s.marginTop };
    })()""")
    print(f"  Subject section: display={visible['display']}, marginTop={visible['marginTop']}")
    
    # Check quiz result message (the green/passed div)
    result_msg = await js(page, """(() => {
        const section = document.getElementById('subject-selection-section');
        const firstChild = section?.firstElementChild;
        if (!firstChild) return null;
        const s = getComputedStyle(firstChild);
        return { text: firstChild.textContent?.substring(0, 80), color: s.color, bg: s.backgroundColor, 
                 padding: s.padding, borderRadius: s.borderRadius, mb: s.marginBottom };
    })()""")
    if result_msg:
        print(f"  Quiz result: '{result_msg['text']}', color={result_msg['color']}, mb={result_msg['mb']}")
    
    # Check select dropdowns
    selects = await js(page, """(() => {
        return ['subject-select', 'topic-select'].map(id => {
            const el = document.getElementById(id);
            if (!el) return null;
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { id, width: r.width, height: r.height, padding: s.padding, bg: s.backgroundColor, 
                     border: s.border?.substring(0, 40), borderRadius: s.borderRadius, color: s.color,
                     fontSize: s.fontSize };
        });
    })()""")
    for sel in selects:
        if sel:
            print(f"  {sel['id']}: {sel['width']:.0f}x{sel['height']:.0f}, padding={sel['padding']}, border={sel['border'][:30]}, radius={sel['borderRadius']}")
    
    # Check start button
    start_btn = await js(page, """(() => {
        const el = document.querySelector('.subject-start-btn');
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, height: r.height, bg: s.background?.substring(0, 50), color: s.color, borderRadius: s.borderRadius, fontSize: s.fontSize, fontWeight: s.fontWeight };
    })()""")
    if start_btn:
        print(f"  Start button: {start_btn['width']:.0f}x{start_btn['height']:.0f}, bg={start_btn['bg']}, radius={start_btn['borderRadius']}")
    
    # Check if form-groups have consistent spacing
    form_groups = await js(page, """(() => {
        return Array.from(document.querySelectorAll('#subject-selection-section .form-group')).map(el => {
            const s = getComputedStyle(el);
            return { mb: s.marginBottom, labelFontSize: getComputedStyle(el.querySelector('label')).fontSize };
        });
    })()""")
    for fg in form_groups:
        print(f"  Form group: mb={fg['mb']}, labelSize={fg['labelFontSize']}")
    
    # Check if the quiz result div overlaps with content
    result_divs = await js(page, """(() => {
        const section = document.getElementById('subject-selection-section');
        return Array.from(section.children).map(el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return { tag: el.tagName + '.' + (el.className || '').split(' ')[0], top: r.top, height: r.height, display: s.display, text: el.textContent?.substring(0, 40) };
        });
    })()""")
    print("  Section children:")
    for d in result_divs:
        if d['display'] != 'none':
            print(f"    {d['tag']}: top={d['top']:.0f}, h={d['height']:.0f}, text='{d['text']}'")
    
    return issues

async def audit_interview(page):
    print("\n" + "="*60)
    print("SCREEN 5: INTERVIEW CHAT")
    print("="*60)
    issues = []
    
    # Check chat container layout
    chat = await js(page, """(() => {
        const el = document.getElementById('chat-container');
        const s = getComputedStyle(el);
        return { display: s.display, flexDirection: s.flexDirection, width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height };
    })()""")
    print(f"  Chat container: display={chat['display']}, dir={chat['flexDirection']}, {chat['width']:.0f}x{chat['height']:.0f}")
    
    # Check chat header
    header = await js(page, """(() => {
        const el = document.getElementById('chat-header-title');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { text: el.textContent, width: r.width, height: r.height, padding: s.padding, bg: s.backgroundColor, 
                 color: s.color, fontSize: s.fontSize, letterSpacing: s.letterSpacing, textTransform: s.textTransform,
                 position: s.position, zIndex: s.zIndex, borderBottom: s.borderBottom };
    })()""")
    print(f"  Header: '{header['text']}', {header['width']:.0f}x{header['height']:.0f}, bg={header['bg'][:30]}, color={header['color']}")
    
    # Check messages area
    messages = await js(page, """(() => {
        const el = document.getElementById('messages');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, maxWidth: s.maxWidth, padding: s.padding, gap: s.gap, overflowY: s.overflowY, flexGrow: s.flexGrow };
    })()""")
    print(f"  Messages: {messages['width']:.0f}w, maxW={messages['maxWidth']}, padding={messages['padding']}, gap={messages['gap']}")
    
    # Check message bubbles
    msg_bubbles = await js(page, """(() => {
        const bots = document.querySelectorAll('.bot-msg');
        const users = document.querySelectorAll('.user-msg');
        return { botCount: bots.length, userCount: users.length,
                 botBg: bots.length ? getComputedStyle(bots[0]).backgroundColor : null,
                 botBorder: bots.length ? getComputedStyle(bots[0]).border?.substring(0, 40) : null,
                 botRadius: bots.length ? getComputedStyle(bots[0]).borderRadius : null };
    })()""")
    print(f"  Messages: bot={msg_bubbles['botCount']}, user={msg_bubbles['userCount']}")
    if msg_bubbles['botBg']:
        print(f"    Bot bubble: bg={msg_bubbles['botBorder']}, radius={msg_bubbles['botRadius']}")
    
    # Check avatar
    avatar = await js(page, """(() => {
        const el = document.querySelector('.avatar');
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, height: r.height, bg: s.backgroundColor, border: s.border?.substring(0, 30), borderRadius: s.borderRadius, fontSize: s.fontSize };
    })()""")
    if avatar:
        print(f"  Avatar: {avatar['width']:.0f}x{avatar['height']:.0f}, bg={avatar['bg'][:30]}, radius={avatar['borderRadius']}")
    
    # Check message wrapper alignment
    wrappers = await js(page, """(() => {
        return Array.from(document.querySelectorAll('.msg-wrapper')).slice(0, 3).map(el => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { align: s.alignSelf, maxWidth: r.width, flexDirection: s.flexDirection };
        });
    })()""")
    for w in wrappers:
        print(f"  Wrapper: align={w['align']}, maxW={w['width']:.0f}")
    
    # Check input area
    input_area = await js(page, """(() => {
        const el = document.getElementById('input-area');
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, maxWidth: s.maxWidth, display: s.display, gap: s.gap, padding: s.padding, paddingBottom: s.paddingBottom };
    })()""")
    if input_area:
        print(f"  Input area: {input_area['width']:.0f}w, maxW={input_area['maxWidth']}, gap={input_area['gap']}, pb={input_area['paddingBottom']}")
    
    # Check text input
    text_input = await js(page, """(() => {
        const el = document.getElementById('user-input');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, height: r.height, padding: s.padding, bg: s.backgroundColor, border: s.border?.substring(0, 40), 
                 borderRadius: s.borderRadius, color: s.color, fontSize: s.fontSize, flexGrow: s.flexGrow };
    })()""")
    print(f"  Text input: {text_input['width']:.0f}x{text_input['height']:.0f}, padding={text_input['padding']}, radius={text_input['borderRadius']}")
    
    # Check send button
    send_btn = await js(page, """(() => {
        const el = document.getElementById('send-btn');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, height: r.height, padding: s.padding, bg: s.backgroundColor, border: s.border?.substring(0, 40), 
                 borderRadius: s.borderRadius, color: s.color, fontSize: s.fontSize, fontWeight: s.fontWeight };
    })()""")
    print(f"  Send button: {send_btn['width']:.0f}x{send_btn['height']:.0f}, bg={send_btn['bg'][:30]}, radius={send_btn['borderRadius']}")
    
    # Check mic button
    mic_btn = await js(page, """(() => {
        const el = document.getElementById('mic-btn');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { width: r.width, height: r.height, padding: s.padding, bg: s.backgroundColor, border: s.border?.substring(0, 40), 
                 borderRadius: s.borderRadius, color: s.color, fontSize: s.fontSize };
    })()""")
    print(f"  Mic button: {mic_btn['width']:.0f}x{mic_btn['height']:.0f}")
    
    # Check button height consistency (send vs mic)
    if send_btn and mic_btn:
        if abs(send_btn['height'] - mic_btn['height']) > 4:
            issues.append(f"Send/Mic button height mismatch: send={send_btn['height']:.0f}, mic={mic_btn['height']:.0f}")
    
    # Check eval card styling (if visible)
    eval_card = await js(page, """(() => {
        const el = document.querySelector('.eval-card');
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { bg: s.backgroundColor, backdropFilter: s.backdropFilter, border: s.border?.substring(0, 40), 
                 borderRadius: s.borderRadius, padding: s.padding, width: r.width };
    })()""")
    if eval_card:
        print(f"  Eval card: bg={eval_card['bg'][:30]}, radius={eval_card['borderRadius']}, w={eval_card['width']:.0f}")
    
    return issues

async def audit_dashboard(page):
    print("\n" + "="*60)
    print("SCREEN 6: FINAL DASHBOARD")
    print("="*60)
    issues = []
    
    # Check dashboard container
    dash = await js(page, """(() => {
        const el = document.getElementById('dashboard-container');
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { display: s.display, width: r.width, maxWidth: s.maxWidth, height: r.height, padding: s.padding, overflowY: s.overflowY };
    })()""")
    print(f"  Dashboard: display={dash['display']}, {dash['width']:.0f}x{dash['height']:.0f}, maxW={dash['maxWidth']}, overflow={dash['overflowY']}")
    
    # Check header
    header = await js(page, """(() => {
        const el = document.querySelector('.dashboard-header');
        if (!el) return null;
        const s = getComputedStyle(el);
        return { fontSize: s.fontSize, fontWeight: s.fontWeight, color: s.color, marginBottom: s.marginBottom, letterSpacing: s.letterSpacing };
    })()""")
    if header:
        print(f"  Header: {header['fontSize']}, weight={header['fontWeight']}, color={header['color']}, mb={header['marginBottom']}")
    
    # Check stats grid
    stats_grid = await js(page, """(() => {
        const el = document.querySelector('.stats-grid');
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { display: s.display, gridTemplateColumns: s.gridTemplateColumns, gap: s.gap, width: r.width, marginBottom: s.marginBottom };
    })()""")
    if stats_grid:
        print(f"  Stats grid: cols={stats_grid['gridTemplateColumns']}, gap={stats_grid['gap']}, mb={stats_grid['marginBottom']}")
    
    # Check stat boxes
    stat_boxes = await js(page, """(() => {
        return Array.from(document.querySelectorAll('.stat-box')).map(el => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { padding: s.padding, bg: s.backgroundColor, border: s.border?.substring(0, 40), borderRadius: s.borderRadius, 
                     width: r.width, height: r.height };
        });
    })()""")
    for sb in stat_boxes:
        print(f"  Stat box: {sb['width']:.0f}x{sb['height']:.0f}, padding={sb['padding']}, radius={sb['borderRadius']}")
    
    # Check stat value styling
    stat_vals = await js(page, """(() => {
        return Array.from(document.querySelectorAll('.stat-value')).map(el => {
            const s = getComputedStyle(el);
            return { text: el.textContent.trim(), fontSize: s.fontSize, fontWeight: s.fontWeight, color: s.color, fontFamily: s.fontFamily };
        });
    })()""")
    for sv in stat_vals:
        print(f"  Stat value: '{sv['text']}', {sv['fontSize']}, weight={sv['fontWeight']}, color={sv['color']}")
    
    # Check skill bars
    skill_bars = await js(page, """(() => {
        return Array.from(document.querySelectorAll('.skill-bar-container')).map(el => {
            const bg = el.querySelector('.skill-bar-bg');
            const fill = el.querySelector('.skill-bar-fill');
            const header = el.querySelector('.skill-header');
            return { 
                label: header?.textContent?.trim()?.substring(0, 40),
                bgH: bg ? getComputedStyle(bg).height : null,
                bgRadius: bg ? getComputedStyle(bg).borderRadius : null,
                fillW: fill ? getComputedStyle(fill).width : null,
                fillBg: fill ? getComputedStyle(fill).background?.substring(0, 40) : null,
                fillRadius: fill ? getComputedStyle(fill).borderRadius : null
            };
        });
    })()""")
    for sb in skill_bars:
        print(f"  Skill: '{sb['label']}', fillW={sb['fillW']}, fillBg={sb['fillBg']}")
    
    # Check history cards
    hist_cards = await js(page, """(() => {
        return Array.from(document.querySelectorAll('.history-card')).slice(0, 2).map(el => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return { padding: s.padding, bg: s.backgroundColor, border: s.border?.substring(0, 40), borderRadius: s.borderRadius, 
                     width: r.width, height: r.height };
        });
    })()""")
    for hc in hist_cards:
        print(f"  History card: {hc['width']:.0f}x{hc['height']:.0f}, padding={hc['padding']}, radius={hc['borderRadius']}")
    
    # Check history card header (flex layout)
    hist_header = await js(page, """(() => {
        const el = document.querySelector('.history-card-header');
        if (!el) return null;
        const s = getComputedStyle(el);
        return { display: s.display, justifyContent: s.justifyContent, fontSize: s.fontSize, color: s.color, marginBottom: s.marginBottom };
    })()""")
    if hist_header:
        print(f"  History header: display={hist_header['display']}, justify={hist_header['justifyContent']}, fontSize={hist_header['fontSize']}")
    
    # Check retry button
    retry = await js(page, """(() => {
        const el = document.querySelector('.retry-btn');
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { text: el.textContent.trim(), width: r.width, height: r.height, bg: s.backgroundColor, color: s.color, 
                 borderRadius: s.borderRadius, fontSize: s.fontSize, marginTop: s.marginTop, cursor: s.cursor, alignSelf: s.alignSelf };
    })()""")
    if retry:
        print(f"  Retry button: '{retry['text']}', {retry['width']:.0f}x{retry['height']:.0f}, bg={retry['bg']}, mt={retry['marginTop']}")
    
    # Check section title
    section_titles = await js(page, """(() => {
        return Array.from(document.querySelectorAll('.section-title')).map(el => {
            const s = getComputedStyle(el);
            return { text: el.textContent.trim(), fontWeight: s.fontWeight, fontSize: s.fontSize, color: s.color, marginBottom: s.marginBottom, letterSpacing: s.letterSpacing };
        });
    })()""")
    for st in section_titles:
        print(f"  Section title: '{st['text']}', {st['fontSize']}, weight={st['fontWeight']}, color={st['color']}, mb={st['marginBottom']}")
    
    # Check for overflow in dashboard
    dash_overflow = await js(page, """(() => {
        const el = document.getElementById('dashboard-container');
        return { scrollH: el.scrollHeight, clientH: el.clientHeight, overflows: el.scrollHeight > el.clientHeight };
    })()""")
    print(f"  Dashboard scroll: scrollH={dash_overflow['scrollH']}, clientH={dash_overflow['clientH']}, overflows={dash_overflow['overflows']}")
    
    return issues

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        
        all_issues = {}
        
        try:
            # SCREEN 1: Landing
            issues = await audit_landing(page)
            all_issues['landing'] = issues
        except Exception as e:
            print(f"  [ERROR in landing audit: {e}]")
            all_issues['landing'] = [str(e)]
        
        try:
            # SCREEN 2: Upload + Analysis
            resume_path = r"C:\Users\mayur\capstone\test_resume.txt"
            await page.set_input_files("#resume-file", resume_path)
            await page.click(".start-btn")
            await page.wait_for_selector("#resume-analysis >> visible=true", timeout=120000)
            await asyncio.sleep(1)
            issues = await audit_resume_analysis(page)
            all_issues['analysis'] = issues
        except Exception as e:
            print(f"  [ERROR in analysis audit: {e}]")
            all_issues['analysis'] = [str(e)]
        
        try:
            # SCREEN 3: Quiz
            await page.click(".ra-cta")
            await page.wait_for_selector("#quiz-section >> visible=true", timeout=30000)
            await asyncio.sleep(1)
            issues = await audit_quiz(page)
            all_issues['quiz'] = issues
        except Exception as e:
            print(f"  [ERROR in quiz audit: {e}]")
            all_issues['quiz'] = [str(e)]
        
        try:
            # Answer all quiz questions
            quiz_cards = await page.query_selector_all(".quiz-question-card")
            for i in range(len(quiz_cards)):
                radio = await page.query_selector(f'input[name="q{i}"][value="1"]')
                if radio:
                    await radio.click()
                else:
                    radio = await page.query_selector(f'input[name="q{i}"][value="0"]')
                    if radio:
                        await radio.click()
            await asyncio.sleep(0.5)
            submit = await page.query_selector("#quiz-questions-container .start-btn")
            if submit:
                await submit.click()
            await asyncio.sleep(1)
        except Exception as e:
            print(f"  [ERROR answering quiz: {e}]")
        
        try:
            # SCREEN 4: Subject Selection
            issues = await audit_subject_selection(page)
            all_issues['subject_selection'] = issues
        except Exception as e:
            print(f"  [ERROR in subject selection audit: {e}]")
            all_issues['subject_selection'] = [str(e)]
        
        try:
            await page.select_option("#subject-select", "CN")
            await page.select_option("#topic-select", "TCP")
            
            # SCREEN 5: Interview
            await page.click(".subject-start-btn")
            await asyncio.sleep(3)
            issues = await audit_interview(page)
            all_issues['interview'] = issues
        except Exception as e:
            print(f"  [ERROR in interview audit: {e}]")
            all_issues['interview'] = [str(e)]
        
        try:
            # Answer questions to get to dashboard
            for q in range(5):
                await asyncio.sleep(3)
                await page.fill("#user-input", "TCP is a connection-oriented protocol that provides reliable data transfer using sequence numbers and acknowledgments")
                await page.click("#send-btn")
                await asyncio.sleep(2)
                await page.fill("#user-input", "SYN")
                await page.click("#send-btn")
                await asyncio.sleep(5)
        except Exception as e:
            print(f"  [ERROR answering questions: {e}]")
        
        try:
            # SCREEN 6: Dashboard
            await asyncio.sleep(3)
            issues = await audit_dashboard(page)
            all_issues['dashboard'] = issues
        except Exception as e:
            print(f"  [ERROR in dashboard audit: {e}]")
            all_issues['dashboard'] = [str(e)]
        
        await browser.close()
        
        # SUMMARY
        print("\n" + "="*60)
        print("ALL VISUAL ISSUES FOUND")
        print("="*60)
        total = 0
        for screen, screen_issues in all_issues.items():
            if screen_issues:
                print(f"\n  [{screen.upper()}]")
                for issue in screen_issues:
                    print(f"    - {issue}")
                    total += 1
        if total == 0:
            print("  No issues found!")
        else:
            print(f"\n  Total issues: {total}")

asyncio.run(main())
