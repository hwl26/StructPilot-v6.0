"""Desk pet (mascot) component for StructPilot.

Renders an interactive, animated companion. Uses st.markdown for HTML/CSS
and components.html for JS. JS communicates back to Python via a hidden
st.text_input (setting its value + simulating Enter keypress).

Key fix: Previous version cached JS in window.__spPetLoaded which prevented
re-initialization on Streamlit reruns. This version uses parent.window.__spPetCleanup
to properly clean up old observers/listeners/timers before binding new ones.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components


def render_desk_pet(
    pet_type: str,
    pet_svg: str,
    ctx_msgs: List[str],
    pet_msgs: List[str],
    body_msgs: List[str],
    tail_msgs: List[str],
    quick_qs: List[str],
    theme: Dict[str, str],
    is_dark: bool,
    pet_mood: str = "idle",
    pet_size: int = 64,
) -> Any:
    """Render the desk pet. Returns action data from hidden text input."""
    # --- Hidden text input for JS -> Python communication ---
    _action = st.text_input(
        "pet_action",
        key="_pet_action",
        label_visibility="collapsed",
        placeholder="",
    )
    st.markdown(
        '<style>'
        'div[data-testid="stTextInput"]:has(input[aria-label="pet_action"]){'
        "position:fixed!important;left:-9999px!important;top:-9999px!important;"
        "width:1px!important;height:1px!important;overflow:hidden!important;opacity:0!important;"
        "}"
        "</style>",
        unsafe_allow_html=True,
    )

    shadow_alpha = "0.25" if is_dark else "0.12"
    panel_shadow_alpha = "0.3" if is_dark else "0.15"
    t = theme  # shorthand

    # =======================================================================
    # CSS
    # =======================================================================
    pet_css = f"""<style>
.sp-pet {{
    position: fixed !important;
    right: 16px; bottom: 16px;
    z-index: 99999;
    user-select: none;
    touch-action: none;
    transition: transform 0.2s ease;
    pointer-events: auto;
}}
.sp-pet:hover .sp-pet-body {{
    transform: scale(1.08);
    filter: drop-shadow(0 4px 12px rgba(0,0,0,0.18));
}}
.sp-pet.sp-dragging {{ cursor: grabbing !important; transition: none !important; }}
.sp-pet.sp-dragging .sp-pet-body {{
    animation: none !important;
    transform: scale(1.1);
    filter: drop-shadow(0 6px 16px rgba(0,0,0,0.25));
}}
.sp-pet-body {{
    width: {pet_size}px; height: {pet_size}px;
    cursor: grab;
    animation: spPetFloat 3s ease-in-out infinite;
    transition: transform 0.2s ease, filter 0.2s ease, width 0.3s ease, height 0.3s ease;
}}
.sp-pet-body:active {{ cursor: grabbing; }}
.sp-pet.sp-happy .sp-pet-body {{ animation: spPetJump 0.45s ease-in-out 3; }}
.sp-pet.sp-angry .sp-pet-body {{ animation: spPetShake 0.12s ease-in-out 8; }}
.sp-pet.sp-sleepy .sp-pet-body {{ animation: spPetDrowse 2.5s ease-in-out infinite; }}
.sp-pet.sp-sleepy .sp-pet-eye-pupil {{ animation: spPetSleep 2.5s ease-in-out infinite !important; }}
.sp-pet-cheek {{
    position: absolute; width: 18px; height: 10px;
    background: #fca5a5; border-radius: 50%;
    opacity: 0; pointer-events: none; filter: blur(2px);
    transition: opacity 0.3s ease;
}}
.sp-pet-cheek-l {{ left: 6px; top: 24px; }}
.sp-pet-cheek-r {{ right: 6px; top: 24px; }}
.sp-pet.sp-happy .sp-pet-cheek,
.sp-pet.sp-angry .sp-pet-cheek {{ opacity: 1; }}
.sp-pet-zzz {{
    position: absolute; top: 0px; right: 8px;
    pointer-events: none; font-size: 14px; font-weight: bold;
    color: #94a3b8; opacity: 0; transition: opacity 0.5s ease;
}}
.sp-pet.sp-sleepy .sp-pet-zzz {{ opacity: 1; animation: spPetZzz 2s ease-in-out infinite; }}
@keyframes spPetFloat {{ 0%,100% {{ transform: translateY(0px); }} 50% {{ transform: translateY(-8px); }} }}
.sp-pet-eye-pupil {{
    transition: transform 0.12s ease-out;
    animation: spPetBlink 4s ease-in-out infinite;
    transform-origin: center;
}}
@keyframes spPetBlink {{ 0%,46%,54%,100% {{ transform: scaleY(1); }} 50% {{ transform: scaleY(0.08); }} }}
@keyframes spPetJump {{
    0%,100% {{ transform: translateY(0) scale(1); }}
    30% {{ transform: translateY(-18px) scale(1.08); }}
    60% {{ transform: translateY(0) scale(0.95); }}
}}
@keyframes spPetShake {{
    0%,100% {{ transform: translateX(0) rotate(0); }}
    25% {{ transform: translateX(-5px) rotate(-3deg); }}
    75% {{ transform: translateX(5px) rotate(3deg); }}
}}
@keyframes spPetDrowse {{
    0%,100% {{ transform: translateY(0) rotate(0deg); }}
    50% {{ transform: translateY(3px) rotate(4deg); }}
}}
@keyframes spPetSleep {{ 0%,100% {{ transform: scaleY(0.05); }} }}
@keyframes spPetZzz {{
    0% {{ opacity: 0; transform: translateY(0) scale(0.8); }}
    50% {{ opacity: 1; transform: translateY(-10px) scale(1); }}
    100% {{ opacity: 0; transform: translateY(-20px) scale(1.3); }}
}}
.sp-pet.sp-happy .sp-pet-body {{ animation: spPetHappyJump 0.5s ease; }}
@keyframes spPetHappyJump {{
    0%,100% {{ transform: translateY(0) scale(1); }}
    30% {{ transform: translateY(-15px) scale(1.08); }}
    60% {{ transform: translateY(-5px) scale(1.03); }}
}}
.sp-pet.sp-wag .sp-pet-body {{ animation: spPetWiggle 0.35s ease-in-out 3; }}
@keyframes spPetWiggle {{
    0%,100% {{ transform: rotate(0deg); }}
    25% {{ transform: rotate(-6deg) translateX(-4px); }}
    75% {{ transform: rotate(6deg) translateX(4px); }}
}}
.sp-pet-bubble {{
    position: absolute; right: 90px; bottom: 58px;
    background: {t['sidebar']}; border: 1px solid {t['sidebar_border']};
    border-radius: 14px; padding: 10px 16px; font-size: 0.8rem;
    color: {t['text']}; white-space: nowrap;
    box-shadow: 0 6px 20px rgba(0,0,0,{shadow_alpha});
    opacity: 0; pointer-events: none;
    transition: opacity 0.3s ease, transform 0.3s ease;
    transform: translateY(6px) scale(0.95);
    max-width: 280px; white-space: normal; line-height: 1.5;
}}
.sp-pet-bubble::after {{
    content: ''; position: absolute; right: -7px; bottom: 18px;
    width: 0; height: 0;
    border-left: 7px solid {t['sidebar_border']};
    border-top: 6px solid transparent; border-bottom: 6px solid transparent;
}}
.sp-pet-bubble::before {{
    content: ''; position: absolute; right: -5px; bottom: 18px;
    width: 0; height: 0;
    border-left: 7px solid {t['sidebar']};
    border-top: 6px solid transparent; border-bottom: 6px solid transparent;
    z-index: 1;
}}
.sp-pet-bubble.sp-show {{ opacity: 1; transform: translateY(0) scale(1); }}

/* ===== Quick panel ===== */
.sp-pet-quick-panel {{
    position: absolute; right: 90px; bottom: 40px;
    background: {t['sidebar']}; border: 1px solid {t['sidebar_border']};
    border-radius: 14px; padding: 12px 14px;
    box-shadow: 0 8px 28px rgba(0,0,0,{panel_shadow_alpha});
    opacity: 0; pointer-events: none;
    transform: translateY(10px) scale(0.95);
    transition: opacity 0.25s ease, transform 0.25s ease;
    z-index: 9999; min-width: 220px; max-width: 280px;
}}
.sp-pet-quick-panel.sp-show {{ opacity: 1; pointer-events: auto; transform: translateY(0) scale(1); }}
.sp-pet-quick-panel-title {{
    font-size: 0.78rem; font-weight: 600; color: {t['text']};
    margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
}}
.sp-pet-quick-panel-close {{ margin-left: auto; cursor: pointer; opacity: 0.6; font-size: 0.9rem; padding: 0 4px; }}
.sp-pet-quick-panel-close:hover {{ opacity: 1; }}
.sp-pet-quick-item {{
    display: block; padding: 7px 10px; margin: 4px 0;
    background: {t['app']}; border: 1px solid {t['sidebar_border']};
    border-radius: 8px; font-size: 0.8rem; color: {t['text']};
    cursor: pointer; transition: all 0.15s ease; text-decoration: none; line-height: 1.4;
}}
.sp-pet-quick-item:hover {{
    background: {t['accent']}; color: #fff; border-color: {t['accent']}; transform: translateX(2px);
}}
.sp-pet-quick-panel::after {{
    content: ''; position: absolute; right: -7px; bottom: 20px;
    width: 0; height: 0;
    border-left: 7px solid {t['sidebar_border']};
    border-top: 6px solid transparent; border-bottom: 6px solid transparent;
}}
.sp-pet-quick-panel::before {{
    content: ''; position: absolute; right: -5px; bottom: 20px;
    width: 0; height: 0;
    border-left: 7px solid {t['sidebar']};
    border-top: 6px solid transparent; border-bottom: 6px solid transparent;
    z-index: 1;
}}

/* ===== Context menu (right-click) ===== */
.sp-pet-ctx-menu {{
    position: fixed; z-index: 100001;
    background: {t['sidebar']}; border: 1px solid {t['sidebar_border']};
    border-radius: 12px; padding: 6px;
    box-shadow: 0 8px 32px rgba(0,0,0,{panel_shadow_alpha});
    opacity: 0; pointer-events: none;
    transform: scale(0.92); transform-origin: top left;
    transition: opacity 0.18s ease, transform 0.18s ease;
    min-width: 180px; max-width: 220px;
}}
.sp-pet-ctx-menu.sp-show {{ opacity: 1; pointer-events: auto; transform: scale(1); }}
.sp-pet-ctx-header {{
    font-size: 0.68rem; font-weight: 600; color: {t['text']};
    padding: 4px 10px; opacity: 0.5; text-transform: uppercase; letter-spacing: 0.5px;
}}
.sp-pet-ctx-item {{
    padding: 7px 10px; margin: 2px 0; border-radius: 8px;
    font-size: 0.8rem; color: {t['text']};
    cursor: pointer; transition: background 0.12s ease;
    display: flex; align-items: center; gap: 6px;
}}
.sp-pet-ctx-item:hover {{ background: {t['accent']}; color: #fff; }}
.sp-pet-ctx-item.active {{ background: {t['accent']}22; color: {t['accent']}; font-weight: 600; }}
.sp-pet-ctx-separator {{ height: 1px; background: {t['sidebar_border']}; margin: 4px 8px; }}

/* ===== Pet-specific animations ===== */
.sp-pet.sp-wag .sp-pet-tail-group {{ animation: spPetWag 0.25s ease-in-out 5; }}
@keyframes spPetWag {{ 0%,100% {{ transform: rotate(0deg); }} 25% {{ transform: rotate(25deg); }} 75% {{ transform: rotate(-25deg); }} }}
.sp-pet[data-pet="penguin"].sp-happy .sp-pet-tail-group {{ animation: spPenguinWing 0.3s ease-in-out 4; }}
@keyframes spPenguinWing {{ 0%,100% {{ transform: rotate(0deg); }} 50% {{ transform: rotate(25deg) translateY(3px); }} }}
.sp-pet[data-pet="dog"].sp-happy .sp-pet-tail-group {{ animation: spDogTail 0.2s ease-in-out 6; }}
@keyframes spDogTail {{ 0%,100% {{ transform: rotate(0deg); }} 50% {{ transform: rotate(35deg); }} }}
.sp-pet[data-pet="robot"].sp-happy .sp-pet-tail-group {{ animation: spRobotAntenna 0.3s ease-in-out 5; }}
@keyframes spRobotAntenna {{ 0%,100% {{ transform: rotate(0deg); }} 25% {{ transform: rotate(-15deg); }} 75% {{ transform: rotate(15deg); }} }}
.sp-pet[data-pet="robot"].sp-happy .sp-pet-eye-pupil {{ animation: spRobotGlow 0.4s ease-in-out 4 !important; }}
@keyframes spRobotGlow {{ 0%,100% {{ opacity: 0.95; }} 50% {{ opacity: 1; filter: brightness(1.8) drop-shadow(0 0 6px #22d3ee); }} }}
.sp-pet[data-pet="dog"]:not(.sp-dragging):not(.sp-sleepy):hover .sp-pet-tail-group {{ animation: spDogTail 0.3s ease-in-out infinite; }}
.sp-pet[data-pet="penguin"] .sp-pet-cheek-l {{ left: 12px; top: 28px; }}
.sp-pet[data-pet="penguin"] .sp-pet-cheek-r {{ right: 12px; top: 28px; }}
.sp-pet[data-pet="dog"] .sp-pet-cheek-l {{ left: 10px; top: 30px; width:16px; height:9px; }}
.sp-pet[data-pet="dog"] .sp-pet-cheek-r {{ right: 10px; top: 30px; width:16px; height:9px; }}
.sp-pet[data-pet="robot"] .sp-pet-cheek {{ display: none; }}
.sp-pet[data-pet="robot"].sp-happy rect[fill="#fbbf24"] {{ animation: spRobotLight 0.3s ease-in-out 5; }}
@keyframes spRobotLight {{ 0%,100% {{ fill: #fbbf24; }} 50% {{ fill: #fef08a; filter: drop-shadow(0 0 4px #fbbf24); }} }}
.sp-pet[data-pet="rabbit"] .sp-pet-cheek-l {{ left: 10px; top: 36px; width: 14px; height: 8px; }}
.sp-pet[data-pet="rabbit"] .sp-pet-cheek-r {{ right: 10px; top: 36px; width: 14px; height: 8px; }}
.sp-pet[data-pet="rabbit"].sp-happy .sp-pet-tail-group {{ animation: spRabbitTail 0.2s ease-in-out 6; }}
@keyframes spRabbitTail {{ 0%,100% {{ transform: scale(1); }} 50% {{ transform: scale(1.3); }} }}
.sp-pet[data-pet="rabbit"]:not(.sp-dragging):not(.sp-sleepy):hover .sp-pet-tail-group {{ animation: spRabbitTail 0.5s ease-in-out infinite; }}

/* Cat-specific */
.sp-cat-ear-l, .sp-cat-ear-r {{ transform-origin: center bottom; transition: transform 0.15s ease; }}
.sp-pet[data-pet="cat"].sp-happy .sp-cat-ear-l {{ animation: spCatEarL 0.3s ease-in-out 5; }}
.sp-pet[data-pet="cat"].sp-happy .sp-cat-ear-r {{ animation: spCatEarR 0.3s ease-in-out 5; }}
@keyframes spCatEarL {{ 0%,100% {{ transform: rotate(0deg); }} 50% {{ transform: rotate(-12deg) translateY(-1px); }} }}
@keyframes spCatEarR {{ 0%,100% {{ transform: rotate(0deg); }} 50% {{ transform: rotate(12deg) translateY(-1px); }} }}
.sp-cat-whiskers-l, .sp-cat-whiskers-r {{ transition: transform 0.1s ease; }}
.sp-pet[data-pet="cat"]:hover .sp-cat-whiskers-l {{ animation: spCatWhiskL 2s ease-in-out infinite; }}
.sp-pet[data-pet="cat"]:hover .sp-cat-whiskers-r {{ animation: spCatWhiskR 2s ease-in-out infinite; }}
.sp-pet[data-pet="cat"].sp-happy .sp-cat-whiskers-l {{ animation: spCatWhiskL 0.25s ease-in-out 6; }}
.sp-pet[data-pet="cat"].sp-happy .sp-cat-whiskers-r {{ animation: spCatWhiskR 0.25s ease-in-out 6; }}
@keyframes spCatWhiskL {{ 0%,100% {{ transform: translateX(0); }} 50% {{ transform: translateX(-1.5px); }} }}
@keyframes spCatWhiskR {{ 0%,100% {{ transform: translateX(0); }} 50% {{ transform: translateX(1.5px); }} }}
.sp-pet[data-pet="cat"].sp-happy .sp-cat-pupil-l,
.sp-pet[data-pet="cat"].sp-happy .sp-cat-pupil-r {{ opacity: 0; transform: scaleY(0.08); }}
.sp-pet[data-pet="cat"].sp-happy .sp-cat-eye-closed-l,
.sp-pet[data-pet="cat"].sp-happy .sp-cat-eye-closed-r {{ opacity: 1 !important; }}
.sp-pet[data-pet="cat"].sp-sleepy .sp-cat-pupil-l,
.sp-pet[data-pet="cat"].sp-sleepy .sp-cat-pupil-r {{ animation: spCatSleepyEye 3s ease-in-out infinite !important; }}
@keyframes spCatSleepyEye {{ 0%,40%,60%,100% {{ transform: scaleY(1); opacity:1; }} 50% {{ transform: scaleY(0.1); opacity:0.5; }} }}
.sp-pet[data-pet="cat"].sp-happy .sp-cat-mouth {{ opacity: 0; }}
.sp-pet[data-pet="cat"].sp-happy .sp-cat-mouth-open {{ opacity: 1 !important; animation: spCatMeow 0.4s ease-in-out 3; }}
@keyframes spCatMeow {{ 0%,100% {{ transform: scaleY(1); }} 50% {{ transform: scaleY(1.4); }} }}
.sp-pet[data-pet="cat"].sp-purr .sp-pet-body {{ animation: spCatPurr 0.12s ease-in-out infinite; }}
@keyframes spCatPurr {{ 0%,100% {{ transform: translateX(0); }} 25% {{ transform: translateX(-0.8px); }} 75% {{ transform: translateX(0.8px); }} }}
.sp-pet[data-pet="cat"] .sp-cat-hearts {{ pointer-events: none; transition: opacity 0.3s; }}
.sp-pet[data-pet="cat"].sp-hearts .sp-cat-hearts {{ opacity: 1 !important; }}
.sp-cat-heart {{ opacity: 0; }}
.sp-pet[data-pet="cat"].sp-hearts .sp-cat-heart {{ animation: spCatHeartFloat 1.2s ease-out forwards; }}
.sp-pet[data-pet="cat"].sp-hearts .sp-cat-h1 {{ animation-delay: 0s; }}
.sp-pet[data-pet="cat"].sp-hearts .sp-cat-h2 {{ animation-delay: 0.15s; }}
.sp-pet[data-pet="cat"].sp-hearts .sp-cat-h3 {{ animation-delay: 0.3s; }}
@keyframes spCatHeartFloat {{
    0% {{ opacity: 0; transform: translateY(0) scale(0.3); }}
    20% {{ opacity: 1; transform: translateY(-5px) scale(1.1); }}
    100% {{ opacity: 0; transform: translateY(-35px) scale(0.6); }}
}}
.sp-pet[data-pet="cat"]:not(.sp-dragging):not(.sp-happy):not(.sp-angry):not(.sp-wag):hover .sp-pet-tail-group {{ animation: spCatTailSway 1.8s ease-in-out infinite; }}
@keyframes spCatTailSway {{ 0%,100% {{ transform: rotate(-5deg); }} 50% {{ transform: rotate(15deg); }} }}
.sp-pet[data-pet="cat"].sp-happy .sp-pet-tail-group {{ animation: spCatTailHappy 0.4s ease-in-out 5; }}
@keyframes spCatTailHappy {{ 0%,100% {{ transform: rotate(0deg); }} 50% {{ transform: rotate(-25deg) translateY(-3px); }} }}
.sp-pet[data-pet="cat"].sp-angry .sp-pet-tail-group {{ animation: spCatTailThrash 0.1s ease-in-out 10; }}
@keyframes spCatTailThrash {{ 0%,100% {{ transform: rotate(0deg); }} 25% {{ transform: rotate(18deg); }} 75% {{ transform: rotate(-18deg); }} }}
.sp-pet[data-pet="cat"].sp-wave .sp-cat-paw-l {{ animation: spCatPawWave 0.3s ease-in-out 3; transform-origin: 22px 56px; }}
@keyframes spCatPawWave {{ 0%,100% {{ transform: rotate(0deg) translateY(0); }} 50% {{ transform: rotate(-25deg) translateY(-4px); }} }}
.sp-pet[data-pet="cat"] .sp-pet-cheek-l {{ left: 10px; top: 34px; }}
.sp-pet[data-pet="cat"] .sp-pet-cheek-r {{ right: 10px; top: 34px; }}
.sp-pet[data-pet="cat"].sp-happy .sp-cat-forehead {{ animation: spCatStripeShimmer 0.5s ease-in-out 3; }}
@keyframes spCatStripeShimmer {{ 0%,100% {{ stroke: #cbd5e1; }} 50% {{ stroke: #fda4af; }} }}

/* Drag hint */
.sp-pet-drag-hint {{
    position: absolute; bottom: -4px; left: 50%; transform: translateX(-50%);
    font-size: 0.6rem; color: #cbd5e1; opacity: 0;
    transition: opacity 0.3s; white-space: nowrap; pointer-events: none;
}}
.sp-pet:hover .sp-pet-drag-hint {{ opacity: 1; }}
.sp-pet-hint-btn {{
    position: absolute; top: -8px; left: -8px;
    width: 24px; height: 24px; border-radius: 50%;
    background: {t['accent']}; color: #fff; font-size: 14px; font-weight: bold;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    z-index: 25; animation: sp-hint-bounce 1.2s ease-in-out infinite;
    transition: transform 0.2s;
}}
.sp-pet-hint-btn::after {{
    content: ''; position: absolute; bottom: -3px; right: 3px;
    width: 8px; height: 8px; background: {t['accent']};
    transform: rotate(45deg); border-radius: 1px;
}}
.sp-pet-hint-btn:hover {{ transform: scale(1.3) rotate(-5deg); }}
@keyframes sp-hint-bounce {{ 0%,100% {{ transform: translateY(0) scale(1); }} 50% {{ transform: translateY(-6px) scale(1.1); }} }}
</style>"""

    # =======================================================================
    # HTML
    # =======================================================================
    pet_html = f"""{pet_css}
<div class="sp-pet" id="spPet" data-pet="{pet_type}" data-mood="{pet_mood}" data-size="{pet_size}">
    <div class="sp-pet-bubble" id="spPetBubble"></div>
    <div class="sp-pet-quick-panel" id="spPetQuickPanel">
        <div class="sp-pet-quick-panel-title">
            <span>💬 快捷问题</span>
            <span class="sp-pet-quick-panel-close" id="spPetQuickClose">x</span>
        </div>
        <div id="spPetQuickItems"></div>
        <div style="font-size:11px;color:#94a3b8;margin-top:8px;padding-top:8px;border-top:1px solid #e2e8f0;text-align:center;">
            右键萌宠可打开设置菜单
        </div>
    </div>
    <div class="sp-pet-ctx-menu" id="spPetCtxMenu">
        <div class="sp-pet-ctx-header">切换形象</div>
        <div class="sp-pet-ctx-item" data-action="switch" data-pet="cat">🐱 科研小猫</div>
        <div class="sp-pet-ctx-item" data-action="switch" data-pet="penguin">🐧 冷冻企鹅</div>
        <div class="sp-pet-ctx-item" data-action="switch" data-pet="dog">🐶 实验小狗</div>
        <div class="sp-pet-ctx-item" data-action="switch" data-pet="rabbit">🐰 实验兔兔</div>
        <div class="sp-pet-ctx-item" data-action="switch" data-pet="robot">🤖 AI助手</div>
        <div class="sp-pet-ctx-separator"></div>
        <div class="sp-pet-ctx-header">尺寸</div>
        <div class="sp-pet-ctx-item" data-action="size" data-size="48">📏 小号</div>
        <div class="sp-pet-ctx-item" data-action="size" data-size="64">📐 中号</div>
        <div class="sp-pet-ctx-item" data-action="size" data-size="80">📊 大号</div>
        <div class="sp-pet-ctx-separator"></div>
        <div class="sp-pet-ctx-item" data-action="quick">💬 快捷提问</div>
        <div class="sp-pet-ctx-item" data-action="hide">👋 隐藏伙伴</div>
    </div>
    {pet_svg}
    <div class="sp-pet-cheek sp-pet-cheek-l"></div>
    <div class="sp-pet-cheek sp-pet-cheek-r"></div>
    <div class="sp-pet-zzz">z</div>
    <div class="sp-pet-drag-hint">拖动可移动 · 右键设置</div>
    <div class="sp-pet-hint-btn" id="spPetHintBtn" title="点我问问题">?</div>
</div>"""

    st.markdown(pet_html, unsafe_allow_html=True)

    # =======================================================================
    # JS (injected via components.html iframe, accesses parent.document)
    # =======================================================================
    config = json.dumps({
        "ctxMsgs": ctx_msgs,
        "petMsgs": pet_msgs,
        "bodyMsgs": body_msgs,
        "tailMsgs": tail_msgs,
        "quickQs": quick_qs,
        "petType": pet_type,
        "petMood": pet_mood,
        "petSize": pet_size,
    }, ensure_ascii=False)

    # JS is a raw string (NOT f-string) to avoid brace escaping issues.
    # Dynamic values are injected via __CONFIG__ placeholder.
    js_code = r"""
(function() {
    var doc = parent.document;
    var win = parent.window;

    // ===== CLEAN UP PREVIOUS INSTANCE =====
    // This is the KEY FIX: properly remove old observers, listeners, and timers
    // so that new Streamlit reruns can rebind fresh event handlers.
    if (win.__spPetCleanup) { try { win.__spPetCleanup(); } catch(e) {} }

    var CFG = __CONFIG__;
    var petType = CFG.petType;
    var petMood = CFG.petMood;
    var petSize = CFG.petSize || 64;
    var ctxMsgs = CFG.ctxMsgs;
    var petMsgs = CFG.petMsgs;
    var bodyMsgs = CFG.bodyMsgs;
    var tailMsgs = CFG.tailMsgs;
    var quickQuestions = CFG.quickQs;
    var petId = 'sp-pet-pos-' + petType;

    // State object — all handlers/timers/observer stored here for cleanup
    var S = {};

    // Cleanup function (will be called by the NEXT instance)
    win.__spPetCleanup = function() {
        if (S.observer) { try { S.observer.disconnect(); } catch(e) {} }
        if (S.idleTimer) clearTimeout(S.idleTimer);
        if (S.intervalTimer) clearInterval(S.intervalTimer);
        if (S.bubbleTimer) clearTimeout(S.bubbleTimer);
        if (S.moodTimer) clearTimeout(S.moodTimer);
        if (S.retryTimer) clearInterval(S.retryTimer);
        if (S.onMove) doc.removeEventListener('mousemove', S.onMove);
        if (S.onUp) doc.removeEventListener('mouseup', S.onUp);
        if (S.onTouchMove) doc.removeEventListener('touchmove', S.onTouchMove);
        if (S.onTouchEnd) doc.removeEventListener('touchend', S.onTouchEnd);
        if (S.onOutsideClick) doc.removeEventListener('click', S.onOutsideClick);
        // Clear __spBound on ALL spPet elements (old and new) so the fresh instance can rebind
        var pets = doc.querySelectorAll('#spPet');
        for (var i = 0; i < pets.length; i++) { delete pets[i].__spBound; }
    };

    function pick(a) { return a[Math.floor(Math.random() * a.length)]; }

    function initPet() {
        // Pick the LAST spPet in the DOM (newest after Streamlit rerun) to avoid stale element binding
        var pets = doc.querySelectorAll('#spPet');
        var pet = pets[pets.length - 1];
        if (!pet) return false;
        var bubble = pet.querySelector('#spPetBubble');
        if (!bubble) return false;
        // Remove any stale/duplicate pet containers left over from reruns
        for (var i = 0; i < pets.length - 1; i++) {
            if (pets[i] && pets[i].parentNode) pets[i].parentNode.removeChild(pets[i]);
        }
        if (pet.__spBound) return true;
        pet.__spBound = true;

        var isDragging = false, dragMoved = false;
        var startX, startY, origLeft, origTop;
        var headPetCount = 0, headPetTimer = null, clickTimer = null;
        var quickPanelOpen = false;

        // ===== Helpers =====
        function show(text, duration) {
            bubble.textContent = text;
            bubble.classList.add('sp-show');
            if (S.bubbleTimer) clearTimeout(S.bubbleTimer);
            S.bubbleTimer = setTimeout(function() { bubble.classList.remove('sp-show'); }, duration || 3500);
        }

        function setMood(cls, duration) {
            pet.classList.remove('sp-happy', 'sp-angry', 'sp-sleepy', 'sp-wag', 'sp-hearts', 'sp-purr', 'sp-wave');
            if (cls) pet.classList.add(cls);
            if (S.moodTimer) clearTimeout(S.moodTimer);
            if (duration && cls) S.moodTimer = setTimeout(function() { pet.classList.remove(cls); }, duration);
        }

        function resetIdle() {
            if (S.idleTimer) clearTimeout(S.idleTimer);
            pet.classList.remove('sp-sleepy');
            S.idleTimer = setTimeout(function() {
                setMood('sp-sleepy');
                show(pick(['zzz...', '好困...要打盹了...', '休眠中...轻点打扰~']), 2500);
            }, 45000);
        }

        // ===== JS -> Python communication via hidden text input =====
        function sendToPython(data) {
            var input = null;
            // First try: collapsed text input associated with label 'pet_action'
            var inputs = doc.querySelectorAll('input[type="text"]');
            for (var i = 0; i < inputs.length; i++) {
                if (inputs[i].getAttribute('aria-label') === 'pet_action') {
                    input = inputs[i]; break;
                }
            }
            if (!input) {
                // Fallback: any input with aria-label 'pet_action'
                var allInputs = doc.querySelectorAll('input');
                for (var j = 0; j < allInputs.length; j++) {
                    if (allInputs[j].getAttribute('aria-label') === 'pet_action') {
                        input = allInputs[j]; break;
                    }
                }
            }
            if (!input) return;
            var setter = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
            var value = JSON.stringify(data);
            setter.call(input, value);
            // Dispatch both input and change events so Streamlit reliably detects the update
            input.dispatchEvent(new win.Event('input', { bubbles: true }));
            input.dispatchEvent(new win.Event('change', { bubbles: true }));
            input.focus();
            input.dispatchEvent(new win.KeyboardEvent('keydown', {
                key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true
            }));
            input.dispatchEvent(new win.KeyboardEvent('keypress', {
                key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true
            }));
            input.dispatchEvent(new win.KeyboardEvent('keyup', {
                key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true
            }));
        }

        // ===== Context menu (right-click) =====
        var ctxMenu = pet.querySelector('#spPetCtxMenu');

        function showCtxMenu(x, y) {
            if (!ctxMenu) return;
            // Highlight current pet type
            var swItems = ctxMenu.querySelectorAll('[data-action="switch"]');
            for (var i = 0; i < swItems.length; i++) {
                if (swItems[i].getAttribute('data-pet') === petType) swItems[i].classList.add('active');
                else swItems[i].classList.remove('active');
            }
            // Highlight current size
            var sizeItems = ctxMenu.querySelectorAll('[data-action="size"]');
            var currentSize = parseInt(pet.getAttribute('data-size') || petSize);
            for (var j = 0; j < sizeItems.length; j++) {
                if (parseInt(sizeItems[j].getAttribute('data-size')) === currentSize) sizeItems[j].classList.add('active');
                else sizeItems[j].classList.remove('active');
            }
            // Position
            var menuW = 200, menuH = 340;
            var px = Math.min(x, win.innerWidth - menuW - 10);
            var py = Math.min(y, win.innerHeight - menuH - 10);
            ctxMenu.style.left = Math.max(10, px) + 'px';
            ctxMenu.style.top = Math.max(10, py) + 'px';
            ctxMenu.classList.add('sp-show');
        }

        function hideCtxMenu() {
            if (ctxMenu) ctxMenu.classList.remove('sp-show');
        }

        pet.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            e.stopPropagation();
            showCtxMenu(e.clientX, e.clientY);
            setMood('sp-wag', 1000);
            resetIdle();
        });

        S.onOutsideClick = function(e) {
            if (ctxMenu && ctxMenu.classList.contains('sp-show') && !ctxMenu.contains(e.target) && !pet.contains(e.target)) {
                hideCtxMenu();
            }
        };
        doc.addEventListener('click', S.onOutsideClick);

        if (ctxMenu) {
            var menuItems = ctxMenu.querySelectorAll('.sp-pet-ctx-item');
            for (var k = 0; k < menuItems.length; k++) {
                (function(item) {
                    item.onclick = function(e) {
                        e.stopPropagation();
                        e.preventDefault();
                        var action = item.getAttribute('data-action');
                        if (action === 'switch') {
                            var newType = item.getAttribute('data-pet');
                            sendToPython({ action: 'switch_pet', pet_type: newType });
                            setMood('sp-happy', 1500);
                            show('切换中...', 2000);
                        } else if (action === 'size') {
                            var size = parseInt(item.getAttribute('data-size'));
                            applySize(size);
                            sendToPython({ action: 'set_size', pet_size: size });
                            // Update active state
                            var sizeItems2 = ctxMenu.querySelectorAll('[data-action="size"]');
                            for (var m = 0; m < sizeItems2.length; m++) {
                                if (parseInt(sizeItems2[m].getAttribute('data-size')) === size) sizeItems2[m].classList.add('active');
                                else sizeItems2[m].classList.remove('active');
                            }
                            show('大小已调整～', 1500);
                        } else if (action === 'quick') {
                            toggleQuickPanel();
                        } else if (action === 'hide') {
                            sendToPython({ action: 'hide_pet' });
                        }
                        hideCtxMenu();
                    };
                })(menuItems[k]);
            }
        }

        // ===== Size control =====
        function applySize(size) {
            var body = pet.querySelector('.sp-pet-body');
            if (body) {
                body.style.width = size + 'px';
                body.style.height = size + 'px';
            }
            pet.setAttribute('data-size', size);
            try { localStorage.setItem('sp-pet-size', size.toString()); } catch(e) {}
        }

        // Apply configured size from Python as source of truth
        // (avoid reading localStorage first, otherwise settings selectbox changes are overridden)
        applySize(petSize);

        // ===== Quick panel =====
        var quickPanel = pet.querySelector('#spPetQuickPanel');
        var quickItems = pet.querySelector('#spPetQuickItems');

        function renderQuickItems() {
            if (!quickItems || !quickQuestions || !quickQuestions.length) return;
            quickItems.innerHTML = '';
            for (var i = 0; i < quickQuestions.length; i++) {
                (function(q) {
                    var div = doc.createElement('div');
                    div.className = 'sp-pet-quick-item';
                    div.textContent = q;
                    div.onclick = function(e) {
                        e.stopPropagation();
                        sendToPython({ action: 'quick_q', question: q });
                        setMood('sp-happy', 1500);
                        show('好的～这就帮你问！', 2000);
                        toggleQuickPanel(false);
                        resetIdle();
                    };
                    quickItems.appendChild(div);
                })(quickQuestions[i]);
            }
        }

        function toggleQuickPanel(force) {
            if (!quickPanel) return;
            var showIt = (typeof force === 'boolean') ? force : !quickPanelOpen;
            quickPanelOpen = showIt;
            if (showIt) { quickPanel.classList.add('sp-show'); setMood('sp-wag', 1200); }
            else { quickPanel.classList.remove('sp-show'); }
        }

        var hintBtn = pet.querySelector('#spPetHintBtn');
        if (hintBtn) {
            hintBtn.onclick = function(e) {
                e.stopPropagation();
                e.preventDefault();
                toggleQuickPanel();
                setMood('sp-happy', 1000);
                resetIdle();
            };
        }

        var quickClose = pet.querySelector('#spPetQuickClose');
        if (quickClose) {
            quickClose.onclick = function(e) { e.stopPropagation(); toggleQuickPanel(false); };
        }

        // Triple click to open quick panel
        var tripleCount = 0, tripleTimer = null;
        pet.addEventListener('click', function(e) {
            tripleCount++;
            if (tripleTimer) clearTimeout(tripleTimer);
            tripleTimer = setTimeout(function() { tripleCount = 0; }, 600);
            if (tripleCount >= 3) { tripleCount = 0; toggleQuickPanel(); }
        });

        // ===== Interaction (click areas) =====
        function distToRect(px, py, rect) {
            var cx = Math.max(rect.left, Math.min(px, rect.right));
            var cy = Math.max(rect.top, Math.min(py, rect.bottom));
            return Math.hypot(px - cx, py - cy);
        }

        function hitArea(e) {
            var r = pet.getBoundingClientRect();
            var y = e.clientY - r.top;
            var tailGroups = pet.querySelectorAll('.sp-pet-tail-group');
            var closestDist = Infinity;
            for (var i = 0; i < tailGroups.length; i++) {
                var d = distToRect(e.clientX, e.clientY, tailGroups[i].getBoundingClientRect());
                if (d < closestDist) closestDist = d;
            }
            if (closestDist < 22) return 'tail';
            if (y < r.height * 0.55) return 'head';
            if (y > r.height * 0.81) return 'tail';
            return 'body';
        }

        var specialMsgs = {
            "cat": ["喵呜～最爱你了！", "咕噜咕噜咕噜…超级幸福！", "在你身上踩奶踩奶！", "翻肚皮！要一直摸！", "喵——！你是我的主人！"],
            "penguin": ["咕噜咕噜～你是我最好的朋友！", "要不要一起去滑冰？", "企鹅抱抱！"],
            "dog": ["汪汪汪！最最最喜欢你！！", "舔舔舔～你是我的全世界！", "翻肚皮！要摸摸！"],
            "rabbit": ["蹦蹦～好开心呀！", "啃胡萝卜庆祝！", "软乎乎的兔兔抱抱！", "竖耳朵听你说！"],
            "robot": ["情感模块输出：最高级喜悦。", "系统提示：你是一个优秀的操作者。", "检测到幸福指数飙升！"]
        };

        function onDblClick(e) {
            if (dragMoved) return;
            var msgs = specialMsgs[petType] || specialMsgs.cat;
            setMood('sp-happy', 2000);
            if (petType === 'cat') {
                pet.classList.add('sp-hearts'); pet.classList.add('sp-purr');
                setTimeout(function() { pet.classList.remove('sp-hearts'); }, 1500);
                setTimeout(function() { pet.classList.remove('sp-purr'); }, 3000);
            }
            show(pick(msgs), 3500);
            resetIdle();
        }

        function onClick(e) {
            if (dragMoved) { dragMoved = false; return; }
            if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; onDblClick(e); return; }
            clickTimer = setTimeout(function() {
                clickTimer = null;
                if (dragMoved) { dragMoved = false; return; }
                var a = hitArea(e);
                if (a === 'head') {
                    setMood('sp-happy', 1500); show(pick(petMsgs), 3000);
                    if (petType === 'cat') {
                        headPetCount++;
                        if (headPetTimer) clearTimeout(headPetTimer);
                        headPetTimer = setTimeout(function() { headPetCount = 0; }, 3000);
                        if (headPetCount >= 3) {
                            pet.classList.add('sp-hearts'); pet.classList.add('sp-purr');
                            setTimeout(function() { pet.classList.remove('sp-hearts'); }, 1500);
                            setTimeout(function() { pet.classList.remove('sp-purr'); }, 3000);
                            headPetCount = 0;
                            bubble.classList.remove('sp-show');
                            setTimeout(function() {
                                show(pick(["咕噜咕噜咕噜！最爱你了喵！", "呼噜…完全被驯服了…", "喵呜～摸头杀！出爱心了！"]), 3000);
                            }, 400);
                        }
                    }
                } else if (a === 'tail') {
                    setMood('sp-angry', 1200); show(pick(tailMsgs), 3000); headPetCount = 0;
                } else {
                    setMood('sp-wag', 1200); show(pick(bodyMsgs), 3000);
                    if (petType === 'cat') { pet.classList.add('sp-wave'); setTimeout(function() { pet.classList.remove('sp-wave'); }, 1000); }
                }
                resetIdle();
            }, 250);
        }

        // ===== Drag (FIXED: proper event lifecycle) =====
        function onDown(e) {
            if (e.button !== undefined && e.button !== 0) return;
            // Don't start drag if clicking on context menu or quick panel
            if (e.target.closest && (e.target.closest('.sp-pet-ctx-menu') || e.target.closest('.sp-pet-quick-panel'))) return;
            isDragging = true; dragMoved = false;
            var r = pet.getBoundingClientRect();
            startX = e.clientX; startY = e.clientY; origLeft = r.left; origTop = r.top;
            pet.classList.add('sp-dragging');
            pet.style.right = 'auto'; pet.style.bottom = 'auto';
            pet.style.left = origLeft + 'px'; pet.style.top = origTop + 'px';
            if (e.preventDefault) e.preventDefault();
        }

        S.onMove = function(e) {
            if (isDragging) {
                var dx = e.clientX - startX, dy = e.clientY - startY;
                if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragMoved = true;
                var nl = origLeft + dx, nt = origTop + dy;
                var vw = win.innerWidth || doc.documentElement.clientWidth;
                var vh = win.innerHeight || doc.documentElement.clientHeight;
                var pw = pet.offsetWidth || 64, ph = pet.offsetHeight || 64;
                nl = Math.max(-pw / 2, Math.min(nl, vw - pw / 2));
                nt = Math.max(-ph / 2, Math.min(nt, vh - ph / 2));
                pet.style.left = nl + 'px'; pet.style.top = nt + 'px';
                return;
            }
            // Eye tracking
            var eyes = pet.querySelectorAll('.sp-pet-eye-pupil');
            if (eyes.length >= 2) {
                var pr = pet.getBoundingClientRect();
                var cx = pr.left + pr.width / 2, cy = pr.top + pr.height / 2;
                var ang = Math.atan2(e.clientY - cy, e.clientX - cx);
                var dist = Math.min(2, Math.hypot(e.clientX - cx, e.clientY - cy) / 100);
                var ox = Math.cos(ang) * dist, oy = Math.sin(ang) * dist * 0.6;
                for (var i = 0; i < eyes.length; i++) {
                    eyes[i].style.transform = 'translate(' + ox + 'px,' + oy + 'px)';
                }
            }
        };

        S.onUp = function(e) {
            if (!isDragging) return;
            isDragging = false;
            pet.classList.remove('sp-dragging');
            try { localStorage.setItem(petId, JSON.stringify({ left: pet.style.left, top: pet.style.top })); } catch(err) {}
            var ev = e;
            setTimeout(function() { if (!dragMoved) onClick(ev); }, 0);
        };

        // Use mousedown on pet, mousemove/mouseup on document
        pet.addEventListener('mousedown', onDown);
        doc.addEventListener('mousemove', S.onMove);
        doc.addEventListener('mouseup', S.onUp);

        // Touch support
        pet.addEventListener('touchstart', function(e) {
            if (e.target.closest && (e.target.closest('.sp-pet-ctx-menu') || e.target.closest('.sp-pet-quick-panel'))) return;
            var t = e.touches[0];
            onDown({ clientX: t.clientX, clientY: t.clientY, button: 0, preventDefault: function() {} });
        }, { passive: false });

        S.onTouchMove = function(e) {
            if (!isDragging) return;
            var t = e.touches[0];
            S.onMove({ clientX: t.clientX, clientY: t.clientY });
            e.preventDefault();
        };

        S.onTouchEnd = function(e) {
            if (!isDragging) return;
            var t = e.changedTouches[0];
            S.onUp({ clientX: t.clientX, clientY: t.clientY });
        };

        doc.addEventListener('touchmove', S.onTouchMove, { passive: false });
        doc.addEventListener('touchend', S.onTouchEnd);

        // ===== Load saved position =====
        try {
            var s = JSON.parse(localStorage.getItem(petId) || 'null');
            if (s && s.left && s.top) {
                pet.style.right = 'auto'; pet.style.bottom = 'auto';
                pet.style.left = s.left; pet.style.top = s.top;
            }
        } catch(err) {}

        // ===== Mood system =====
        function applyMood(mood) {
            pet.setAttribute('data-mood', mood);
            if (mood === 'done') {
                setMood('sp-happy', 3000);
                show(pick(['太棒了！全部完成！🎉', '辛苦啦！你是最棒的！', '完美收工！给你比心！']), 4000);
                triggerCelebration();
            } else if (mood === 'error') {
                setMood('sp-angry', 2000);
                show(pick(['遇到问题了？别慌，我帮你看看！', '点「报错」告诉我具体情况～', '别着急，我们一起解决！']), 3500);
            } else if (mood === 'working') {
                show(pick(ctxMsgs), 3500);
                setMood('sp-wag', 800);
            } else {
                // idle
                show(pick(ctxMsgs), 4000);
                setMood('sp-happy', 1200);
            }
        }

        function triggerCelebration() {
            var emojis = ['\u2764\ufe0f', '\ud83c\udf89', '\u2728', '\u2b50', '\ud83c\udf1f', '\ud83d\udcab'];
            for (var i = 0; i < 10; i++) {
                (function(idx) {
                    setTimeout(function() {
                        var el = doc.createElement('div');
                        el.textContent = emojis[idx % emojis.length];
                        el.style.cssText = 'position:fixed;font-size:24px;pointer-events:none;z-index:100000;opacity:0;transition:all 1.8s ease-out;';
                        var rect = pet.getBoundingClientRect();
                        el.style.left = (rect.left + rect.width / 2) + 'px';
                        el.style.top = rect.top + 'px';
                        doc.body.appendChild(el);
                        setTimeout(function() {
                            el.style.opacity = '1';
                            el.style.transform = 'translate(' + ((Math.random() - 0.5) * 250) + 'px, -' + (120 + Math.random() * 120) + 'px) scale(' + (0.5 + Math.random()) + ')';
                        }, 50);
                        setTimeout(function() { if (el.parentNode) el.remove(); }, 2200);
                    }, idx * 80);
                })(i);
            }
        }

        // ===== Initialize =====
        renderQuickItems();

        // Apply mood after short delay
        setTimeout(function() { applyMood(petMood); resetIdle(); }, 800);

        // Periodic messages
        S.intervalTimer = setInterval(function() {
            if (!bubble.classList.contains('sp-show') && !pet.classList.contains('sp-sleepy') && !quickPanelOpen) {
                show(pick(ctxMsgs), 3500);
                setMood('sp-wag', 800);
                resetIdle();
            }
        }, 20000);

        return true;
    }

    // ===== Try to init =====
    if (!initPet()) {
        S.observer = new MutationObserver(function() {
            if (initPet()) {
                S.observer.disconnect();
                S.observer = null;
            }
        });
        S.observer.observe(doc.body, { childList: true, subtree: true });

        var retries = 0;
        S.retryTimer = setInterval(function() {
            retries++;
            if (initPet() || retries > 15) clearInterval(S.retryTimer);
        }, 200);
    }
})();
""".replace("__CONFIG__", config)

    components.html(f"<script>{js_code}</script>", height=0, scrolling=False)

    # Return hidden text input value (for Python to read actions)
    return _action if _action else None


def handle_pet_quick_question(
    q: str,
    run_command: Any,
    response_profile: str = "teaching",
) -> None:
    """Submit a quick question from the desk pet as a chat message."""
    if not q or not q.strip():
        return
    q = q.strip()
    last_q = st.session_state.get("_pet_last_processed_q")
    if last_q and q == last_q:
        return
    st.session_state["_pet_last_processed_q"] = q
    run_command(
        q,
        [],
        input_metadata={"input_modality": "text", "source": "pet_quick_question"},
        response_profile=response_profile,
    )
    st.session_state._sp_scroll_target = "chat_bottom"
