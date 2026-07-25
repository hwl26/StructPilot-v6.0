"""简化的桌宠组件 - 纯CSS实现，无需复杂的JavaScript"""
import streamlit as st
import streamlit.components.v1 as components


def render_simple_desk_pet(
    pet_type: str = "penguin",
    pet_size: int = 64,
    pet_mood: str = "idle",
) -> None:
    """渲染简化版桌宠（纯CSS动画，持久化）。

    Parameters
    ----------
    pet_type : str
        桌宠类型（penguin/cat/dog/robot/rabbit）
    pet_size : int
        桌宠大小（像素）
    pet_mood : str
        桌宠心情（idle/happy/working/done/error）
    """
    # 根据类型选择emoji
    pet_emojis = {
        "penguin": "🐧",
        "cat": "🐱",
        "dog": "🐶",
        "robot": "🤖",
        "rabbit": "🐰",
    }
    emoji = pet_emojis.get(pet_type, "🐧")

    # 根据心情选择动画
    animations = {
        "idle": "float",
        "happy": "bounce",
        "working": "wiggle",
        "done": "celebrate",
        "error": "shake",
    }
    animation = animations.get(pet_mood, "float")

    # 使用 components.html 持久化渲染
    html_code = f"""
<style>
.sp-simple-pet {{
    position: fixed;
    right: 20px;
    bottom: 100px;
    width: {pet_size}px;
    height: {pet_size}px;
    font-size: {pet_size}px;
    z-index: 99999;
    cursor: pointer;
    user-select: none;
    animation: {animation} 2s ease-in-out infinite;
    transition: transform 0.2s ease;
    filter: drop-shadow(0 2px 8px rgba(0,0,0,0.15));
}}

.sp-simple-pet:hover {{
    transform: scale(1.15);
    filter: drop-shadow(0 4px 12px rgba(0,0,0,0.25));
}}

/* 动画定义 */
@keyframes float {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-12px); }}
}}

@keyframes bounce {{
    0%, 100% {{ transform: translateY(0); }}
    25% {{ transform: translateY(-20px); }}
    50% {{ transform: translateY(0); }}
    75% {{ transform: translateY(-10px); }}
}}

@keyframes wiggle {{
    0%, 100% {{ transform: rotate(0deg); }}
    25% {{ transform: rotate(-8deg); }}
    75% {{ transform: rotate(8deg); }}
}}

@keyframes celebrate {{
    0%, 100% {{ transform: scale(1) rotate(0deg); }}
    25% {{ transform: scale(1.2) rotate(-10deg); }}
    50% {{ transform: scale(1) rotate(0deg); }}
    75% {{ transform: scale(1.2) rotate(10deg); }}
}}

@keyframes shake {{
    0%, 100% {{ transform: translateX(0); }}
    10%, 30%, 50%, 70%, 90% {{ transform: translateX(-5px); }}
    20%, 40%, 60%, 80% {{ transform: translateX(5px); }}
}}

/* 气泡提示 */
.sp-pet-tooltip {{
    position: fixed;
    right: {pet_size + 30}px;
    bottom: {100 + pet_size // 2}px;
    background: rgba(0, 0, 0, 0.75);
    color: white;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 12px;
    z-index: 99998;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease;
    white-space: nowrap;
}}

.sp-simple-pet:hover + .sp-pet-tooltip {{
    opacity: 1;
}}
</style>

<script>
(function() {{
    // 检查是否已经存在桌宠
    var existingPet = parent.document.getElementById('sp-simple-pet-container');
    if (existingPet) {{
        // 如果已存在，只更新动画类
        var pet = existingPet.querySelector('.sp-simple-pet');
        if (pet) {{
            pet.className = 'sp-simple-pet';
            pet.style.animation = '{animation} 2s ease-in-out infinite';
        }}
        return;
    }}

    // 创建桌宠容器
    var container = parent.document.createElement('div');
    container.id = 'sp-simple-pet-container';
    container.innerHTML = '<div class="sp-simple-pet" title="你的科研小伙伴 ✨">{emoji}</div><div class="sp-pet-tooltip">陪你做实验 🧪</div>';

    // 添加到 body
    parent.document.body.appendChild(container);

    // 添加样式
    var style = parent.document.createElement('style');
    style.textContent = `{html_code.split('</style>')[0].split('<style>')[1]}`;
    parent.document.head.appendChild(style);
}})();
</script>
"""

    # 使用 height=0 避免占用空间
    components.html(html_code, height=0, scrolling=False)


def update_pet_mood(
    completed_count: int,
    total_count: int,
    has_errors: bool,
    session_started: bool
) -> str:
    """根据流程状态自动更新桌宠心情。

    Returns
    -------
    str
        心情标识（idle/happy/working/done/error）
    """
    if not session_started:
        return "idle"
    elif has_errors:
        return "error"
    elif completed_count >= total_count:
        return "done"
    elif completed_count > 0:
        return "working"
    else:
        return "idle"
