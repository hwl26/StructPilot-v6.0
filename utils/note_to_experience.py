"""笔记润色：把口语化的实验笔记整理成结构化技术经验。

复用 utils.perf_cache 中缓存的 LLMAgent 单例，未配置 API Key 时返回空字符串，
由调用方提示用户检查 LLM 配置。
"""

from __future__ import annotations

_STYLE_HINTS = {
    "standard": "保持与原文相当的篇幅，把口语表达改写为清晰的技术描述。",
    "detailed": "补全省略的操作前提和判断依据，可适度扩写，但不得虚构原文没有的数值。",
    "concise": "只保留关键步骤、参数与结论，删去铺垫和重复表述。",
}


def polish_note(content: str, style: str = "standard", include_code: bool = True) -> str:
    """润色单条笔记。

    Parameters
    ----------
    content : str
        原始笔记正文。
    style : str
        ``standard`` / ``detailed`` / ``concise``。
    include_code : bool
        为 True 时保留命令、路径、参数的代码块格式。

    Returns
    -------
    str
        润色后的 Markdown 文本；LLM 未启用或调用失败时返回空字符串。
    """
    text = (content or "").strip()
    if not text:
        return ""

    from utils.perf_cache import get_cached_llm_agent

    llm = get_cached_llm_agent()
    if not getattr(llm, "enabled", False):
        return ""

    code_hint = (
        "命令、文件路径、参数名与数值用 `行内代码` 或代码块包裹。"
        if include_code
        else "不要使用代码块，全部用普通段落和列表表达。"
    )

    instruction = (
        "你在整理一条冷冻电镜实验笔记，把它改写为可供课题组其他成员复用的技术经验。\n\n"
        "要求：\n"
        f"- {_STYLE_HINTS.get(style, _STYLE_HINTS['standard'])}\n"
        f"- {code_hint}\n"
        "- 用 Markdown 小标题分段（如：背景 / 操作 / 结果 / 注意事项），没有对应内容的标题直接省略。\n"
        "- 只允许使用原文提供的信息；原文没写的参数值、结论一律不要补。\n"
        "- 直接输出润色后的正文，不要加任何前言或说明。"
    )

    try:
        polished = llm.rewrite(
            user_text=instruction,
            rule_reply=text,
            response_profile="teaching",
        )
    except Exception:
        return ""

    polished = (polished or "").strip()
    # rewrite() 在降级时会原样返回 rule_reply，此时视为未润色
    if not polished or polished == text:
        return ""
    return polished
