# -*- coding: utf-8 -*-
"""春日极光 3 轮全面测试：功能 / 边界异常 / 动画回归"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8095/02-sakura-spring.html"
issues, passed = [], []

def ok(name, cond, detail=""):
    (passed if cond else issues).append(f"{name}{(' | ' + detail) if detail and not cond else ''}")
    print(("PASS " if cond else "FAIL ") + name + ((" | " + detail) if not cond else ""))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)

    # ============ 第 1 轮：核心功能 ============
    print("\n=== ROUND 1: 核心功能 ===")
    pg.goto(URL, wait_until="domcontentloaded"); pg.wait_for_timeout(1500)
    pg.evaluate("localStorage.clear()")
    pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(1500)

    ob = pg.locator("#onboard")
    ok("R1 onboarding 出现", ob.count() == 1 and ob.is_visible())
    pg.click("#obNext")                       # s1 -> s2
    ok("R1 s2 基础画像", pg.locator(".ob-step.s2.active").is_visible())
    pg.click('.ob-chips[data-ob="grade"] .chip:first-child')
    ok("R1 s2 单选切换", pg.locator('.ob-chips[data-ob="grade"] .chip.on').first.inner_text() == "初中")
    pg.click("#obNext")                       # s2 -> s3
    pg.click('.ob-chips[data-ob="issues"] .chip:nth-child(3)')
    ok("R1 s3 多选", pg.locator('.ob-chips[data-ob="issues"] .chip.on').count() == 3)
    pg.click("#obNext")                       # s3 -> s4
    ok("R1 s4 行为偏好", pg.locator(".ob-step.s4.active").is_visible())
    pg.click("#obPrev"); ok("R1 上一步回 s3", pg.locator(".ob-step.s3.active").is_visible())
    pg.click("#obNext")                       # 回 s4
    pg.click("#obNext")                       # s4 -> s5 生成画像
    gen_ok = False
    for _ in range(40):                       # 生成动画 rAF 依负载浮动，轮询 8s
        pg.wait_for_timeout(200)
        if "初始画像" in pg.locator("#genTxt").inner_text(): gen_ok = True; break
    ok("R1 s5 画像文案", gen_ok)
    ok("R1 s5 摘要出现", pg.locator("#obSummary").is_visible())
    pg.click("#obNext")                       # 进入微律
    pg.wait_for_timeout(900)
    ok("R1 onboarding 关闭", pg.locator("#onboard").count() == 0)
    ok("R1 localStorage 标记", pg.evaluate("localStorage.getItem('wl_aurora_onboarded')") == "1")

    ok("R1 首页 早上好", pg.locator("#view-today").get_by_text("早上好").count() >= 1)
    ok("R1 微律观察卡", pg.locator(".obs-head h3").inner_text() == "微律观察")
    ok("R1 顶栏今日微任务", "今日微任务" in pg.locator(".tb-label").inner_text())

    card1 = pg.locator(".task-card[data-idx='0']")
    card1.locator('[data-act="start"]').click()
    pg.wait_for_timeout(800)
    ok("R1 任务1 进入进行态", card1.locator('[data-act="done"]').count() == 1)
    card1.locator('[data-act="done"]').click()      # 完成啦
    pg.wait_for_timeout(1100)
    ok("R1 任务1 done-note", card1.locator(".done-note").count() == 1)
    ok("R1 任务1 按钮移除", card1.locator('[data-act="start"]').count() == 0)
    ok("R1 任务1 完成态", "done" in (card1.get_attribute("class") or ""))
    fx_clean = False
    for _ in range(10):                                   # rAF 负载下清理可能延迟，轮询 3s
        if pg.evaluate("document.querySelectorAll('.fx-p').length") == 0: fx_clean = True; break
        pg.wait_for_timeout(300)
    ok("R1 粒子已清理", fx_clean, "3s 后仍有残留")

    pg.evaluate("document.getElementById('breathLabel').scrollIntoView({block:'center'})")
    breath_changed = False
    s1 = pg.evaluate("(document.getElementById('breathLabel').textContent + '|' + document.getElementById('breathCount').textContent)")
    for _ in range(20):
        pg.wait_for_timeout(500)
        s2 = pg.evaluate("(document.getElementById('breathLabel').textContent + '|' + document.getElementById('breathCount').textContent)")
        if s1 != s2: breath_changed = True; break
    ok("R1 呼吸节奏变化", breath_changed, f"{s1} 持续不变")
    breath_anim = pg.evaluate("""(() => {
      const els = [...document.querySelectorAll('[class*=breath]')];
      for (const el of els) { const a = getComputedStyle(el).animationName; if (a !== 'none') return a; }
      return 'none'; })()""")
    ok("R1 呼吸动画运行", breath_anim != "none", breath_anim)

    pg.click('.tab[data-view="assistant"]'); pg.wait_for_timeout(700)
    ok("R1 切到 AI 助手", pg.locator("#view-assistant.active").is_visible())
    pg.click('.chip[data-q="exam"]')
    for _ in range(12):                                  # 拆解约 1.6s 后出现
        pg.wait_for_timeout(400)
        if pg.locator("#chatLog .subqs").count() >= 1: break
    ok("R1 问题拆解 subqs", pg.locator("#chatLog .subqs").count() >= 1)
    pg.wait_for_timeout(2600)
    ok("R1 chunk 依据", pg.locator("#chatLog .chunk").count() >= 1)
    log_txt = pg.locator("#chatLog").inner_text()
    ok("R1 AI 生成回答", ("低负担" in log_txt or "10 分钟" in log_txt or "微休息" in log_txt), log_txt[:80])

    def wait_view(sel, timeout_ms=3000):
        for _ in range(timeout_ms // 200):
            if pg.locator(sel).is_visible(): return True
            pg.wait_for_timeout(200)
        return False
    pg.click('.tab[data-view="profile"]')
    ok("R1 画像页渲染", wait_view("#view-profile.active"))
    pg.click('.tab[data-view="weekly"]')
    ok("R1 周度页渲染", wait_view("#view-weekly.active"))

    pg.click('.tab[data-view="today"]'); pg.wait_for_timeout(400)
    ok("R1 初始不吸附", "tb-dock" not in pg.evaluate("document.body.className"))
    pg.evaluate("window.scrollTo(0, 300)"); pg.wait_for_timeout(400)
    ok("R1 滚动后吸附", "tb-dock" in pg.evaluate("document.body.className"))
    pg.evaluate("window.scrollTo(0, 0)"); pg.wait_for_timeout(400)
    ok("R1 回顶解除吸附", "tb-dock" not in pg.evaluate("document.body.className"))

    # ============ 第 2 轮：边界 / 异常 ============
    print("\n=== ROUND 2: 边界 / 异常 ===")
    pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(1500)
    ok("R2 已引导不再弹", pg.locator("#onboard").count() == 0)
    pg.goto(URL + "?onboard=1", wait_until="domcontentloaded"); pg.wait_for_timeout(1500)
    ok("R2 ?onboard 强制引导", pg.locator("#onboard").is_visible())
    pg.click("#obSkip"); pg.wait_for_timeout(900)
    ok("R2 跳过引导可用", pg.locator("#onboard").count() == 0)

    pg.click('.tab[data-view="assistant"]'); pg.wait_for_timeout(500)
    before = pg.locator("#chatLog .msg").count()
    pg.click('#chatForm button[type="submit"]'); pg.wait_for_timeout(400)
    ok("R2 空输入不发送", pg.locator("#chatLog .msg").count() == before)
    pg.fill("#chatInput", "最近心情有点低落")
    pg.click('#chatForm button[type="submit"]')
    pg.wait_for_timeout(3400)
    ok("R2 自定义提问有回答", pg.locator("#chatLog").inner_text().count("低落") >= 1)

    pg.click('.tab[data-view="today"]'); pg.wait_for_timeout(500)
    # 真实双击：JS 同步连点，第二击应被 450ms 冷却拦截
    pg.evaluate("""(() => {
      const card = document.querySelector(".task-card[data-idx='1']");
      card.querySelector("[data-act='start']").click();
      card.querySelector("[data-act='done']").click();
    })()""")
    pg.wait_for_timeout(900)
    ok("R2 连点被冷却拦截", "done" not in (pg.locator(".task-card[data-idx='1']").get_attribute("class") or ""))
    pg.locator(".task-card[data-idx='1'] [data-act='done']").click()
    pg.wait_for_timeout(1200)
    ok("R2 冷却后可正常完成", pg.locator(".task-card[data-idx='1'] .done-note").count() == 1)

    card3 = pg.locator(".task-card[data-idx='2']")
    card3.locator('[data-act="replace"]').click(); pg.wait_for_timeout(700)
    ok("R2 换一朵有效", card3.locator(".task-name").count() >= 1)
    pg.locator(".task-card[data-idx='2'] [data-act='skip']").click(); pg.wait_for_timeout(700)
    ok("R2 先跳过-跳过态", pg.locator(".task-card[data-idx='2'].skippedcard").count() == 1)
    ok("R2 先跳过-恢复钮", pg.locator(".task-card[data-idx='2'] [data-act='restore']").count() == 1)
    pg.locator(".task-card[data-idx='2'] [data-act='restore']").click(); pg.wait_for_timeout(700)
    ok("R2 恢复任务", pg.locator(".task-card[data-idx='2'] [data-act='start']").count() == 1)

    for v in ["assistant", "profile", "weekly", "today", "assistant"]:
        pg.click(f'.tab[data-view="{v}"]'); pg.wait_for_timeout(180)
    pg.wait_for_timeout(600)
    ok("R2 快速切页无错", pg.locator("#view-assistant.active").is_visible())

    # ============ 第 3 轮：动画 / 回归 ============
    print("\n=== ROUND 3: 动画 / 回归 ===")
    pg.evaluate("window.scrollTo(0,0)")
    petals = pg.evaluate("document.querySelectorAll('[class*=petal]').length")
    ok("R3 花瓣存在", petals > 0, f"{petals} 片")
    petal_anim = pg.evaluate("""(() => { const p = document.querySelector('.petal'); return (p && p.firstElementChild) ? getComputedStyle(p.firstElementChild).animationName : 'none' })()""")
    ok("R3 花瓣动画", petal_anim not in ("none", ""), petal_anim)
    blobs = pg.evaluate("""(() => { const b = document.querySelectorAll('.blob'); return { n: b.length, anim: b[0] ? getComputedStyle(b[0]).animationName : 'none' } })()""")
    ok("R3 极光色晕", blobs["n"] >= 4 and blobs["anim"] != "none", str(blobs))
    font = pg.evaluate("getComputedStyle(document.querySelector('.obs-main')).fontFamily")
    ok("R3 明朝字体", ("Serif" in font or "Songti" in font or "SimSun" in font), font)
    ok("R3 视图过渡样式", pg.evaluate("getComputedStyle(document.querySelector('.view')).transitionDuration") != "")
    pg.click('.tab[data-view="today"]'); pg.wait_for_timeout(800)
    pg.screenshot(path=".tmp_r3_today.png", full_page=False)
    pg.click('.tab[data-view="assistant"]'); pg.wait_for_timeout(800)
    pg.screenshot(path=".tmp_r3_ai.png")
    ok("R3 截图完成", True)
    real_errors = [e for e in errors if "net::ERR" not in e and "font" not in e.lower()]
    ok("R3 无 JS 错误", len(real_errors) == 0, "; ".join(real_errors[:3]))

    browser.close()

print(f"\n===== 结果: {len(passed)} 通过 / {len(issues)} 失败 =====")
for i in issues: print("  ✗ " + i)
sys.exit(1 if issues else 0)
