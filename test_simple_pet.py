"""超级简单的桌宠测试页面"""
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="桌宠测试", layout="wide")

st.title("🐧 桌宠测试页面")

st.info("如果右下角看到一个 🐧 企鹅，说明桌宠组件工作正常。")

# 超级简化的桌宠HTML
html_code = """
<script>
(function() {
    // 删除旧的桌宠（如果存在）
    var oldPet = parent.document.getElementById('test-pet');
    if (oldPet) {
        oldPet.remove();
    }

    // 创建新桌宠
    var style = parent.document.createElement('style');
    style.textContent = `
        #test-pet {
            position: fixed;
            right: 20px;
            bottom: 100px;
            font-size: 64px;
            z-index: 99999;
            cursor: pointer;
            animation: float 2s ease-in-out infinite;
        }
        @keyframes float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-12px); }
        }
    `;
    parent.document.head.appendChild(style);

    var pet = parent.document.createElement('div');
    pet.id = 'test-pet';
    pet.textContent = '🐧';
    pet.title = '测试桌宠';
    parent.document.body.appendChild(pet);

    console.log('桌宠已渲染到 parent.document.body');
})();
</script>
"""

components.html(html_code, height=0, scrolling=False)

st.markdown("---")
st.markdown("### 测试步骤")
st.markdown("1. 查看右下角是否有 🐧")
st.markdown("2. 企鹅应该有上下漂浮的动画")
st.markdown("3. 刷新页面（F5），企鹅应该还在")

st.markdown("---")
st.markdown("### 调试信息")
st.code("""
// 在浏览器 Console 中运行以下代码检查：
var pet = document.getElementById('test-pet');
console.log('桌宠元素:', pet);
console.log('桌宠位置:', pet ? pet.getBoundingClientRect() : 'not found');
""", language="javascript")
