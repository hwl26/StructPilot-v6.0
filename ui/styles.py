"""StructPilot UI styles: themes and CSS blocks extracted from main.py."""

from __future__ import annotations


THEMES = {
    "静谧蓝": {"app": "#f7f8fa", "sidebar": "#ffffff", "accent": "#3b82f6", "accent2": "#6366f1", "text": "#1e293b", "sidebar_text": "#475569", "sidebar_border": "#e2e8f0"},
    "墨竹绿": {"app": "#f7faf8", "sidebar": "#ffffff", "accent": "#059669", "accent2": "#0d9488", "text": "#1a2e22", "sidebar_text": "#475569", "sidebar_border": "#e2e8f0"},
    "雅致紫": {"app": "#f8f7fc", "sidebar": "#ffffff", "accent": "#7c3aed", "accent2": "#6366f1", "text": "#1e1b2e", "sidebar_text": "#475569", "sidebar_border": "#e2e8f0"},
    "深邃黑": {"app": "#0f172a", "sidebar": "#1e293b", "accent": "#38bdf8", "accent2": "#818cf8", "text": "#e2e8f0", "sidebar_text": "#94a3b8", "sidebar_border": "#334155"},
}



def build_global_styles(theme: dict, is_dark: bool, app_bg: str) -> str:
    """Build the global app CSS string from the active theme and background."""
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/icon?family=Material+Icons');
    :root {{
        color-scheme: {'dark' if is_dark else 'light'};
        --sp-accent: {theme['accent']};
        --sp-accent2: {theme['accent2']};
        --sp-text: {theme['text']};
        --sp-sidebar-text: {theme['sidebar_text']};
        --sp-sidebar-border: {theme['sidebar_border']};
    }}

    .material-icons, [data-testid="stIconMaterial"] {{
        font-family: 'Material Icons' !important;
        font-weight: 400 !important;
        font-style: normal !important;
        font-size: 24px !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-block !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        -webkit-font-feature-settings: 'liga' !important;
        -webkit-font-smoothing: antialiased !important;
    }}

    .stApp {{ {app_bg} }}

    /* ===== Fix code tag dark background ===== */
    code, pre {{
        background: transparent !important;
        color: inherit !important;
        border: none !important;
        padding: 0 !important;
    }}
    div[data-testid="stVerticalBlock"] code {{
        background: transparent !important;
    }}

    /* ===== Phase header ===== */
    .sp-phase-header {{
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: {theme['accent']};
        padding: 0.6rem 0.5rem 0.2rem 0.5rem;
        margin-top: 0.3rem;
        border-bottom: 1px solid {theme['sidebar_border']};
    }}

    /* ===== Progress stats ===== */
    .sp-progress-stats {{
        display: flex;
        justify-content: space-between;
        font-size: 0.72rem;
        padding: 0.3rem 0.5rem;
        margin-top: 0.2rem;
        color: {theme['sidebar_text']};
    }}
    .sp-progress-stats .sp-stat-passed {{ color: #22c55e; font-weight: 500; }}
    .sp-progress-stats .sp-stat-failed {{ color: #ef4444; font-weight: 500; }}
    .sp-progress-stats .sp-stat-skipped {{ color: #f59e0b; font-weight: 500; }}

    /* ===== Sidebar — ultra minimal ===== */
    section[data-testid="stSidebar"] {{
        background: {theme['sidebar']} !important;
        border-right: 1px solid {theme['sidebar_border']} !important;
        box-shadow: none !important;
        padding-top: 1rem !important;
    }}
    section[data-testid="stSidebar"] .block-container {{
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
    }}
    .sp-brand-block {{
        width: 100%;
        margin: 0 0 0.6rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid {theme['sidebar_border']};
    }}
    [data-testid="stSidebarUserContent"] .sp-brand-block ~ .sp-brand-block {{
        display: none !important;
    }}
    [data-testid="stSidebarUserContent"] [data-testid="stElementContainer"]:nth-child(n+2):has(.sp-brand-block) {{
        display: none !important;
    }}
    [data-testid="stSidebarUserContent"] [data-testid="stElementContainer"]:nth-child(n+3):has(.sp-mode-indicator) {{
        display: none !important;
    }}
    .sp-brand-bar {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 14px;
        width: 100%;
        min-height: 42px;
        padding: 0;
        margin: 0;
    }}
    .sp-brand-logo {{
        display: block;
        height: auto;
        max-height: 38px;
        max-width: 46%;
        object-fit: contain;
        opacity: 0.9;
    }}
    .sp-brand-logo-1 {{ width: 112px; transform: translateY(1px); }}
    .sp-brand-logo-2 {{ width: 106px; transform: translateY(1px); }}
    .sp-app-title {{
        color: {theme['text']};
        font-size: 1.08rem;
        font-weight: 700;
        line-height: 1.25;
        margin: 0 0 0.35rem 0;
    }}
    .sp-app-subtitle {{
        color: {theme['sidebar_text']};
        font-size: 0.82rem;
        line-height: 1.35;
        margin: 0 0 1.25rem 0;
        opacity: 0.78;
    }}
    @media (max-width: 760px) {{
        .sp-brand-block {{ margin-bottom: 0.5rem; padding-bottom: 0.4rem; }}
        .sp-brand-bar {{ gap: 10px; min-height: 38px; }}
        .sp-brand-logo {{ max-height: 34px; max-width: 46%; }}
        .sp-brand-logo-1 {{ width: 104px; }}
        .sp-brand-logo-2 {{ width: 98px; }}
    }}
    /* Sidebar headings — small, quiet labels */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2 {{
        color: {theme['text']} !important;
        font-weight: 600 !important;
        font-size: 1.05rem !important;
        letter-spacing: -0.01em;
        margin-bottom: 0.15rem !important;
    }}
    section[data-testid="stSidebar"] h3 {{
        color: {theme['sidebar_text']} !important;
        font-weight: 500 !important;
        font-size: 0.72rem !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-top: 1.2rem !important;
        margin-bottom: 0.4rem !important;
    }}
    section[data-testid="stSidebar"] .stMarkdown p {{
        color: {theme['sidebar_text']} !important;
        font-size: 0.82rem !important;
    }}
    section[data-testid="stSidebar"] .stCaption,
    section[data-testid="stSidebar"] small {{
        color: #94a3b8 !important;
        font-size: 0.72rem !important;
    }}
    section[data-testid="stSidebar"] hr {{
        border-color: {theme['sidebar_border']} !important;
        margin: 0.9rem 0 !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] > div > div {{
        background: transparent !important;
        border: 1px solid {theme['sidebar_border']} !important;
        color: {theme['text']} !important;
        border-radius: 6px !important;
        font-size: 0.84rem !important;
        min-height: 2rem !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] label {{
        color: {theme['sidebar_text']} !important;
        font-weight: 400 !important;
        font-size: 0.78rem !important;
    }}

    /* ===== Checkpoint nav buttons — text list, no borders ===== */
    section[data-testid="stSidebar"] .stButton button {{
        all: unset !important;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        box-sizing: border-box !important;
        text-align: left !important;
        padding: 0.3rem 0.5rem 0.3rem 0.6rem !important;
        font-size: 0.82rem !important;
        font-family: inherit !important;
        color: {theme['sidebar_text']} !important;
        border-left: 2px solid transparent !important;
        border-radius: 0 !important;
        background: transparent !important;
        cursor: pointer !important;
        transition: all 0.12s ease !important;
        line-height: 1.5 !important;
        min-height: unset !important;
        height: auto !important;
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        color: {theme['text']} !important;
        background: {('#334155' if is_dark else '#f1f5f9')} !important;
        border-radius: 0 4px 4px 0 !important;
    }}
    /* Current checkpoint — left accent bar + highlight */
    section[data-testid="stSidebar"] .stButton button[kind="primary"],
    section[data-testid="stSidebar"] .stButton button[data-testid="baseButton-primary"] {{
        color: {theme['text']} !important;
        font-weight: 600 !important;
        border-left: 2px solid {theme['accent']} !important;
        background: {theme['accent']}08 !important;
        border-radius: 0 4px 4px 0 !important;
    }}
    section[data-testid="stSidebar"] .stButton button[kind="primary"]:hover,
    section[data-testid="stSidebar"] .stButton button[data-testid="baseButton-primary"]:hover {{
        background: {theme['accent']}12 !important;
    }}
    /* Failed checkpoint — subtle red tint */
    section[data-testid="stSidebar"] .stButton button .fail-icon {{
        color: #ef4444 !important;
    }}

    /* Session management buttons — ghost, minimal */
    section[data-testid="stSidebar"] div[data-testid="stColumn"] .stButton button {{
        all: unset !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        box-sizing: border-box !important;
        padding: 0.3rem 0.5rem !important;
        font-size: 0.78rem !important;
        font-family: inherit !important;
        color: {theme['sidebar_text']} !important;
        border: 1px solid {theme['sidebar_border']} !important;
        border-radius: 6px !important;
        background: transparent !important;
        cursor: pointer !important;
        transition: all 0.12s ease !important;
        min-height: unset !important;
        height: auto !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stColumn"] .stButton button:hover {{
        border-color: {theme['accent']} !important;
        color: {theme['accent']} !important;
        background: {theme['accent']}06 !important;
    }}

    /* Progress bar — ultra slim */
    section[data-testid="stSidebar"] div[data-testid="stProgressBar"] {{
        background: {theme['sidebar_border']} !important;
        border-radius: 999px;
        height: 3px !important;
        overflow: hidden;
    }}
    section[data-testid="stSidebar"] div[data-testid="stProgressBar"] > div {{
        background: {theme['accent']} !important;
        border-radius: 999px;
        height: 3px !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stProgress"] {{
        font-size: 0.72rem !important;
        line-height: 1.2 !important;
        margin-bottom: 0.3rem !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stProgress"] p,
    section[data-testid="stSidebar"] div[data-testid="stProgress"] label {{
        font-size: 0.72rem !important;
        color: #94a3b8 !important;
        margin: 0 0 0.25rem 0 !important;
        line-height: 1.2 !important;
        padding: 0 !important;
    }}

    /* Metric cards — remove emojis, minimal text */
    section[data-testid="stSidebar"] div[data-testid="stMetric"] {{
        background: transparent;
        border: none;
        padding: 0.2rem 0 !important;
        text-align: center;
    }}
    section[data-testid="stSidebar"] div[data-testid="stMetric"] label {{
        display: none !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: {theme['sidebar_text']} !important;
        font-size: 0.75rem !important;
        font-weight: 500 !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stMetric"] div[data-testid="stMetricValue"] span {{
        color: #94a3b8 !important;
    }}

    /* Text inputs in sidebar — minimal */
    section[data-testid="stSidebar"] .stTextInput > div > div > input {{
        background: transparent !important;
        border: 1px solid {theme['sidebar_border']} !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
    }}
    section[data-testid="stSidebar"] .stTextInput label {{
        display: none !important;
    }}

    /* Text areas in sidebar — compact for notes */
    section[data-testid="stSidebar"] .stTextArea > div > div > textarea {{
        background: transparent !important;
        border: 1px solid {theme['sidebar_border']} !important;
        border-radius: 6px !important;
        font-size: 0.78rem !important;
        min-height: 40px !important;
        padding: 0.4rem 0.5rem !important;
        line-height: 1.4 !important;
    }}
    section[data-testid="stSidebar"] .stTextArea label {{
        display: none !important;
    }}

    /* Sidebar expanders */
    section[data-testid="stSidebar"] details {{
        border: none !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        background: transparent !important;
    }}
    section[data-testid="stSidebar"] details summary {{
        padding: 0.3rem 0.5rem !important;
        font-weight: 400 !important;
        font-size: 0.78rem !important;
        color: {theme['sidebar_text']} !important;
        border-radius: 6px !important;
    }}
    section[data-testid="stSidebar"] details summary:hover {{
        background: {('#334155' if is_dark else '#f8fafc')};
    }}
    section[data-testid="stSidebar"] details[open] summary {{
        border-bottom: none;
    }}

    /* ===== Main Content ===== */
    .main .block-container {{
        padding-top: 3.5rem !important;
        padding-bottom: 6rem !important;
        max-width: 860px !important;
        padding-left: 2.5rem !important;
        padding-right: 2.5rem !important;
    }}

    /* Tabs — underline minimal */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        background: transparent;
        padding: 0;
        border-radius: 0;
        border: none;
        border-bottom: 1px solid {theme['sidebar_border']};
        margin-bottom: 1.5rem;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px 8px 0 0 !important;
        padding: 0.65rem 1.25rem !important;
        font-weight: 500 !important;
        font-size: 1.05rem !important;
        color: {theme['sidebar_text']} !important;
        transition: all 0.18s ease;
        border-bottom: 2px solid transparent !important;
        background: transparent !important;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        color: {theme['text']} !important;
        background: rgba(255,255,255,0.45) !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background: rgba(255,255,255,0.85) !important;
        color: {theme['text']} !important;
        font-weight: 700 !important;
        border-bottom: 2px solid {theme['accent']} !important;
        box-shadow: 0 0 14px {theme['accent']}2e, 0 -2px 8px {theme['accent']}14 !important;
    }}

    /* Quick action buttons — ghost */
    div[data-testid="stHorizontalBlock"] .stButton button {{
        all: unset !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0.4rem 0.8rem !important;
        font-size: 0.84rem !important;
        font-family: inherit !important;
        color: {theme['sidebar_text']} !important;
        border: 1px solid {theme['sidebar_border']} !important;
        border-radius: 6px !important;
        background: transparent !important;
        cursor: pointer !important;
        transition: all 0.12s ease !important;
    }}
    div[data-testid="stHorizontalBlock"] .stButton button:hover {{
        border-color: {theme['accent']} !important;
        color: {theme['accent']} !important;
        background: {theme['accent']}06 !important;
    }}

    /* ===== Chat Messages — clean, no card borders ===== */
    div[data-testid="stChatMessage"] {{
        background: transparent !important;
        padding: 0.6rem 0 !important;
        gap: 0.6rem !important;
    }}
    div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] {{
        border-radius: 8px !important;
        padding: 0.7rem 1rem !important;
        line-height: 1.65 !important;
        box-shadow: none !important;
        font-size: 0.9rem;
        border: none !important;
    }}
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar-assistant"]) div[data-testid="stChatMessageContent"] {{
        background: transparent !important;
    }}
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar-user"]) div[data-testid="stChatMessageContent"] {{
        background: {theme['accent']}06 !important;
        border: 1px solid {theme['accent']}18 !important;
    }}
    @supports not (selector(:has(*))) {{
        div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] {{
            background: transparent !important;
            border: none !important;
        }}
    }}
    /* Chat avatars */
    div[data-testid="stChatMessage"] div[data-testid="stChatMessageAvatar"] {{
        width: 28px !important;
        height: 28px !important;
        font-size: 0.8rem !important;
    }}

    /* Chat input — minimal */
    div[data-testid="stChatInput"] {{
        background: {theme['sidebar']} !important;
        border-radius: 8px !important;
        border: 1px solid {theme['sidebar_border']} !important;
        box-shadow: none !important;
        padding: 0.2rem !important;
    }}
    div[data-testid="stChatInput"]:focus-within {{
        border-color: {theme['accent']} !important;
        box-shadow: 0 0 0 2px {theme['accent']}12;
    }}
    div[data-testid="stChatInput"] textarea {{
        font-size: 0.9rem !important;
        line-height: 1.5 !important;
    }}

    /* Dividers — lighter */
    hr {{
        border-color: {theme['sidebar_border']} !important;
        margin: 1rem 0 !important;
    }}

    /* Alert boxes — minimal */
    div[data-testid="stAlert"] {{
        border-radius: 8px !important;
        border: 1px solid {theme['sidebar_border']} !important;
        box-shadow: none !important;
        padding: 0.6rem 0.9rem !important;
    }}

    /* Expanders / details — minimal */
    details {{
        border-radius: 8px !important;
        border: 1px solid {theme['sidebar_border']} !important;
        box-shadow: none !important;
        overflow: hidden;
        background: {theme['sidebar']} !important;
    }}
    details summary {{
        padding: 0.5rem 0.9rem !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        border-radius: 8px !important;
        transition: background 0.12s;
        color: {theme['text']} !important;
    }}
    details summary:hover {{
        background: {('#334155' if is_dark else '#f8fafc')};
    }}
    details[open] summary {{
        border-bottom: 1px solid {theme['sidebar_border']};
        border-radius: 8px 8px 0 0 !important;
    }}
    /* Markdown inside expanders — compact */
    details .stMarkdown h1,
    details .stMarkdown h2 {{
        color: {theme['text']} !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        margin-top: 0.8rem !important;
        margin-bottom: 0.3rem !important;
        border-bottom: none !important;
    }}
    details .stMarkdown h3,
    details .stMarkdown h4 {{
        color: {theme['accent']} !important;
        font-size: 0.92rem !important;
        font-weight: 600 !important;
        margin-top: 0.6rem !important;
        margin-bottom: 0.2rem !important;
    }}
    details .stMarkdown p,
    details .stMarkdown li {{
        font-size: 0.87rem !important;
        line-height: 1.6 !important;
        color: {theme['sidebar_text']} !important;
        margin-bottom: 0.3rem !important;
    }}
    details .stMarkdown ul,
    details .stMarkdown ol {{
        margin-top: 0.15rem !important;
        margin-bottom: 0.3rem !important;
        padding-left: 1.1rem !important;
    }}
    details .stMarkdown code {{
        background: {('#334155' if is_dark else '#f1f5f9')} !important;
        color: {theme['text']} !important;
        padding: 0.08rem 0.3rem !important;
        border-radius: 3px !important;
        font-size: 0.82rem !important;
    }}
    details .stMarkdown pre {{
        background: {('#1e293b' if is_dark else '#f8fafc')} !important;
        border-radius: 6px !important;
        padding: 0.5rem 0.7rem !important;
        font-size: 0.82rem !important;
    }}
    details .stMarkdown strong {{
        color: {theme['text']} !important;
        font-weight: 600 !important;
    }}

    /* Buttons — general reset */
    .stButton button {{
        border-radius: 6px !important;
        font-weight: 500 !important;
        transition: all 0.12s ease !important;
    }}

    /* Form submit buttons */
    .stFormSubmitButton > button {{
        background: {theme['accent']} !important;
        color: white !important;
        border: none !important;
        font-weight: 500 !important;
        box-shadow: none !important;
        border-radius: 6px !important;
    }}
    .stFormSubmitButton > button:hover {{
        background: {theme['accent2']} !important;
    }}

    /* Inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {{
        border-radius: 6px !important;
        border: 1px solid {theme['sidebar_border']} !important;
        transition: all 0.12s !important;
        font-size: 0.87rem !important;
    }}
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {{
        border-color: {theme['accent']} !important;
        box-shadow: 0 0 0 2px {theme['accent']}12 !important;
    }}
    .stNumberInput > div > div > input {{
        border-radius: 6px !important;
    }}
    .stSelectbox > div > div {{
        border-radius: 6px !important;
    }}

    /* Success/info/warning/error boxes */
    div[data-testid="stSuccess"] {{
        border-color: {('#166534' if is_dark else '#86efac')} !important;
        background: {('#052e16' if is_dark else '#f0fdf4')} !important;
        color: {theme['text']} !important;
    }}
    div[data-testid="stError"] {{
        border-color: {('#991b1b' if is_dark else '#fca5a5')} !important;
        background: {('#450a0a' if is_dark else '#fef2f2')} !important;
        color: {theme['text']} !important;
    }}
    div[data-testid="stInfo"] {{
        color: {theme['text']} !important;
    }}

    /* Legacy checkpoint classes (kept for compatibility) */
    .cp-row {{ padding: 4px 8px; border-radius: 6px; margin-bottom: 2px; font-size: 0.84rem; border: 1px solid transparent; }}
    .cp-current {{ background: {theme['sidebar']}; border: 1px solid {theme['accent']}; font-weight: 700; }}
    .cp-passed {{ color: #16a34a; }}
    .cp-failed {{ color: #dc2626; }}
    .cp-skipped {{ color: #d97706; }}
    .cp-pending {{ color: #94a3b8; }}

    /* Scrollbar — thinner */
    ::-webkit-scrollbar {{ width: 4px; height: 4px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{
        background: {('rgba(255,255,255,0.15)' if is_dark else 'rgba(0,0,0,0.08)')};
        border-radius: 999px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: {('rgba(255,255,255,0.25)' if is_dark else 'rgba(0,0,0,0.15)')};
    }}

    /* Header — minimal */
    .stApp > header {{
        background: {('rgba(15,23,42,0.8)' if is_dark else 'rgba(255,255,255,0.8)')} !important;
        backdrop-filter: blur(8px);
        box-shadow: none !important;
        border-bottom: 1px solid {theme['sidebar_border']} !important;
    }}

    /* Markdown headings in main area */
    .main .stMarkdown h2 {{
        color: {theme['text']};
        border-bottom: none;
        padding-bottom: 0;
        margin-top: 1.2rem;
        font-weight: 600;
        font-size: 1.15rem;
    }}
    .main .stMarkdown h3 {{
        color: {theme['accent']};
        margin-top: 0.8rem;
        font-size: 0.95rem;
        font-weight: 600;
    }}
    .main .stMarkdown p {{
        color: {theme['text']} !important;
        line-height: 1.65;
    }}

    /* Hide Streamlit branding & footer */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}

    /* Desk Pet — interactive companion */
    .sp-pet {{
        position: fixed !important;
        right: 20px;
        bottom: 20px;
        z-index: 99999;
        user-select: none;
        touch-action: none;
        transition: transform 0.2s ease;
    }}
    .sp-pet:hover .sp-pet-body {{
        transform: scale(1.08);
        filter: drop-shadow(0 4px 12px rgba(0,0,0,0.18));
    }}
    .sp-pet.sp-dragging {{
        cursor: grabbing !important;
        transition: none !important;
    }}
    .sp-pet.sp-dragging .sp-pet-body {{
        animation: none !important;
        transform: scale(1.1);
        filter: drop-shadow(0 6px 16px rgba(0,0,0,0.25));
    }}
    .sp-pet-body {{
        width: 80px;
        height: 80px;
        cursor: grab;
        animation: spPetFloat 3s ease-in-out infinite;
        transition: transform 0.2s ease, filter 0.2s ease;
    }}
    .sp-pet-body:active {{
        cursor: grabbing;
    }}
    .sp-pet.sp-happy .sp-pet-body {{
        animation: spPetJump 0.45s ease-in-out 3;
    }}
    .sp-pet.sp-angry .sp-pet-body {{
        animation: spPetShake 0.12s ease-in-out 8;
    }}
    .sp-pet.sp-sleepy .sp-pet-body {{
        animation: spPetDrowse 2.5s ease-in-out infinite;
    }}
    .sp-pet.sp-sleepy .sp-pet-eye-pupil {{
        animation: spPetSleep 2.5s ease-in-out infinite !important;
    }}
    .sp-pet-cheek {{
        position: absolute;
        width: 18px;
        height: 10px;
        background: #fca5a5;
        border-radius: 50%;
        opacity: 0;
        pointer-events: none;
        filter: blur(2px);
        transition: opacity 0.3s ease;
    }}
    .sp-pet-cheek-l {{ left: 6px; top: 24px; }}
    .sp-pet-cheek-r {{ right: 6px; top: 24px; }}
    .sp-pet.sp-happy .sp-pet-cheek,
    .sp-pet.sp-angry .sp-pet-cheek {{
        opacity: 1;
    }}
    .sp-pet-zzz {{
        position: absolute;
        top: 0px;
        right: 8px;
        pointer-events: none;
        font-size: 14px;
        font-weight: bold;
        color: #94a3b8;
        opacity: 0;
        transition: opacity 0.5s ease;
    }}
    .sp-pet.sp-sleepy .sp-pet-zzz {{
        opacity: 1;
        animation: spPetZzz 2s ease-in-out infinite;
    }}
    @keyframes spPetFloat {{
        0%, 100% {{ transform: translateY(0px); }}
        50% {{ transform: translateY(-8px); }}
    }}
    .sp-pet-eye-pupil {{
        transition: transform 0.12s ease-out;
        animation: spPetBlink 4s ease-in-out infinite;
        transform-origin: center;
    }}
    @keyframes spPetBlink {{
        0%, 46%, 54%, 100% {{ transform: scaleY(1); }}
        50% {{ transform: scaleY(0.08); }}
    }}
    @keyframes spPetJump {{
        0%, 100% {{ transform: translateY(0) scale(1); }}
        30% {{ transform: translateY(-18px) scale(1.08); }}
        60% {{ transform: translateY(0) scale(0.95); }}
    }}
    @keyframes spPetShake {{
        0%, 100% {{ transform: translateX(0) rotate(0); }}
        25% {{ transform: translateX(-5px) rotate(-3deg); }}
        75% {{ transform: translateX(5px) rotate(3deg); }}
    }}
    @keyframes spPetDrowse {{
        0%, 100% {{ transform: translateY(0) rotate(0deg); }}
        50% {{ transform: translateY(3px) rotate(4deg); }}
    }}
    @keyframes spPetSleep {{
        0%, 100% {{ transform: scaleY(0.05); }}
    }}
    @keyframes spPetZzz {{
        0% {{ opacity: 0; transform: translateY(0) scale(0.8); }}
        50% {{ opacity: 1; transform: translateY(-10px) scale(1); }}
        100% {{ opacity: 0; transform: translateY(-20px) scale(1.3); }}
    }}
    .sp-pet-hitarea {{
        cursor: pointer;
    }}
    .sp-pet-hitarea-head {{
        cursor: pointer;
    }}
    .sp-pet-hitarea-tail {{
        cursor: pointer;
    }}
    .sp-pet-bubble {{
        position: absolute;
        right: 90px;
        bottom: 58px;
        background: {theme['sidebar']};
        border: 1px solid {theme['sidebar_border']};
        border-radius: 14px;
        padding: 10px 16px;
        font-size: 0.8rem;
        color: {theme['text']};
        white-space: nowrap;
        box-shadow: 0 6px 20px rgba(0,0,0,{0.25 if is_dark else 0.12});
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.3s ease, transform 0.3s ease;
        transform: translateY(6px) scale(0.95);
        max-width: 280px;
        white-space: normal;
        line-height: 1.5;
    }}
    .sp-pet-bubble::after {{
        content: '';
        position: absolute;
        right: -7px;
        bottom: 18px;
        width: 0;
        height: 0;
        border-left: 7px solid {theme['sidebar_border']};
        border-top: 6px solid transparent;
        border-bottom: 6px solid transparent;
    }}
    .sp-pet-bubble::before {{
        content: '';
        position: absolute;
        right: -5px;
        bottom: 18px;
        width: 0;
        height: 0;
        border-left: 7px solid {theme['sidebar']};
        border-top: 6px solid transparent;
        border-bottom: 6px solid transparent;
        z-index: 1;
    }}
    .sp-pet-bubble.sp-show {{
        opacity: 1;
        transform: translateY(0) scale(1);
    }}
    /* Quick questions panel */
    .sp-pet-quick-panel {{
        position: absolute;
        right: 90px;
        bottom: 40px;
        background: {theme['sidebar']};
        border: 1px solid {theme['sidebar_border']};
        border-radius: 14px;
        padding: 12px 14px;
        box-shadow: 0 8px 28px rgba(0,0,0,{0.3 if is_dark else 0.15});
        opacity: 0;
        pointer-events: none;
        transform: translateY(10px) scale(0.95);
        transition: opacity 0.25s ease, transform 0.25s ease;
        z-index: 9999;
        min-width: 220px;
        max-width: 280px;
    }}
    .sp-pet-quick-panel.sp-show {{
        opacity: 1;
        pointer-events: auto;
        transform: translateY(0) scale(1);
    }}
    .sp-pet-quick-panel-title {{
        font-size: 0.78rem;
        font-weight: 600;
        color: {theme['text']};
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .sp-pet-quick-panel-close {{
        margin-left: auto;
        cursor: pointer;
        opacity: 0.6;
        font-size: 0.9rem;
        padding: 0 4px;
    }}
    .sp-pet-quick-panel-close:hover {{
        opacity: 1;
    }}
    .sp-pet-quick-item {{
        display: block;
        padding: 7px 10px;
        margin: 4px 0;
        background: {theme['app']};
        border: 1px solid {theme['sidebar_border']};
        border-radius: 8px;
        font-size: 0.8rem;
        color: {theme['text']};
        cursor: pointer;
        transition: all 0.15s ease;
        text-decoration: none;
        line-height: 1.4;
    }}
    .sp-pet-quick-item:hover {{
        background: {theme['accent']};
        color: #fff;
        border-color: {theme['accent']};
        transform: translateX(2px);
    }}
    .sp-pet-quick-panel::after {{
        content: '';
        position: absolute;
        right: -7px;
        bottom: 20px;
        width: 0;
        height: 0;
        border-left: 7px solid {theme['sidebar_border']};
        border-top: 6px solid transparent;
        border-bottom: 6px solid transparent;
    }}
    .sp-pet-quick-panel::before {{
        content: '';
        position: absolute;
        right: -5px;
        bottom: 20px;
        width: 0;
        height: 0;
        border-left: 7px solid {theme['sidebar']};
        border-top: 6px solid transparent;
        border-bottom: 6px solid transparent;
        z-index: 1;
    }}
    .sp-pet.sp-wag .sp-pet-tail-group {{
        animation: spPetWag 0.25s ease-in-out 5;
    }}
    @keyframes spPetWag {{
        0%, 100% {{ transform: rotate(0deg); }}
        25% {{ transform: rotate(25deg); }}
        75% {{ transform: rotate(-25deg); }}
    }}
    /* Per-pet happy animations */
    .sp-pet[data-pet="penguin"].sp-happy .sp-pet-tail-group {{
        animation: spPenguinWing 0.3s ease-in-out 4;
    }}
    @keyframes spPenguinWing {{
        0%, 100% {{ transform: rotate(0deg); }}
        50% {{ transform: rotate(25deg) translateY(3px); }}
    }}
    .sp-pet[data-pet="dog"].sp-happy .sp-pet-tail-group {{
        animation: spDogTail 0.2s ease-in-out 6;
    }}
    @keyframes spDogTail {{
        0%, 100% {{ transform: rotate(0deg); }}
        50% {{ transform: rotate(35deg); }}
    }}
    .sp-pet[data-pet="robot"].sp-happy .sp-pet-tail-group {{
        animation: spRobotAntenna 0.3s ease-in-out 5;
    }}
    @keyframes spRobotAntenna {{
        0%, 100% {{ transform: rotate(0deg); }}
        25% {{ transform: rotate(-15deg); }}
        75% {{ transform: rotate(15deg); }}
    }}
    /* Robot screen glow on happy */
    .sp-pet[data-pet="robot"].sp-happy .sp-pet-eye-pupil {{
        animation: spRobotGlow 0.4s ease-in-out 4 !important;
    }}
    @keyframes spRobotGlow {{
        0%, 100% {{ opacity: 0.95; }}
        50% {{ opacity: 1; filter: brightness(1.8) drop-shadow(0 0 6px #22d3ee); }}
    }}
    /* Per-pet idle tail wag */
    .sp-pet[data-pet="dog"]:not(.sp-dragging):not(.sp-sleepy):hover .sp-pet-tail-group {{
        animation: spDogTail 0.3s ease-in-out infinite;
    }}
    /* Blush positions per pet (cat is set in cat-specific section below) */
    .sp-pet[data-pet="penguin"] .sp-pet-cheek-l {{ left: 12px; top: 28px; }}
    .sp-pet[data-pet="penguin"] .sp-pet-cheek-r {{ right: 12px; top: 28px; }}
    .sp-pet[data-pet="dog"] .sp-pet-cheek-l {{ left: 10px; top: 30px; width:16px; height:9px; }}
    .sp-pet[data-pet="dog"] .sp-pet-cheek-r {{ right: 10px; top: 30px; width:16px; height:9px; }}
    .sp-pet[data-pet="robot"] .sp-pet-cheek {{ display: none; }}
    /* Robot happy: extra button flash */
    .sp-pet[data-pet="robot"].sp-happy rect[fill="#fbbf24"] {{
        animation: spRobotLight 0.3s ease-in-out 5;
    }}
    @keyframes spRobotLight {{
        0%, 100% {{ fill: #fbbf24; }}
        50% {{ fill: #fef08a; filter: drop-shadow(0 0 4px #fbbf24); }}
    }}
    /* ===== Cat-specific animations ===== */
    /* Ear wiggle */
    .sp-cat-ear-l, .sp-cat-ear-r {{
        transform-origin: center bottom;
        transition: transform 0.15s ease;
    }}
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-ear-l {{
        animation: spCatEarL 0.3s ease-in-out 5;
    }}
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-ear-r {{
        animation: spCatEarR 0.3s ease-in-out 5;
    }}
    @keyframes spCatEarL {{
        0%, 100% {{ transform: rotate(0deg); }}
        50% {{ transform: rotate(-12deg) translateY(-1px); }}
    }}
    @keyframes spCatEarR {{
        0%, 100% {{ transform: rotate(0deg); }}
        50% {{ transform: rotate(12deg) translateY(-1px); }}
    }}
    /* Whisker twitch */
    .sp-cat-whiskers-l, .sp-cat-whiskers-r {{
        transition: transform 0.1s ease;
    }}
    .sp-pet[data-pet="cat"]:hover .sp-cat-whiskers-l {{
        animation: spCatWhiskL 2s ease-in-out infinite;
    }}
    .sp-pet[data-pet="cat"]:hover .sp-cat-whiskers-r {{
        animation: spCatWhiskR 2s ease-in-out infinite;
    }}
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-whiskers-l {{
        animation: spCatWhiskL 0.25s ease-in-out 6;
    }}
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-whiskers-r {{
        animation: spCatWhiskR 0.25s ease-in-out 6;
    }}
    @keyframes spCatWhiskL {{
        0%, 100% {{ transform: translateX(0); }}
        50% {{ transform: translateX(-1.5px); }}
    }}
    @keyframes spCatWhiskR {{
        0%, 100% {{ transform: translateX(0); }}
        50% {{ transform: translateX(1.5px); }}
    }}
    /* Eye close (^_^ happy face) */
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-pupil-l,
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-pupil-r {{
        opacity: 0;
        transform: scaleY(0.08);
    }}
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-eye-closed-l,
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-eye-closed-r {{
        opacity: 1 !important;
    }}
    /* Sleepy eyes for cat */
    .sp-pet[data-pet="cat"].sp-sleepy .sp-cat-pupil-l,
    .sp-pet[data-pet="cat"].sp-sleepy .sp-cat-pupil-r {{
        animation: spCatSleepyEye 3s ease-in-out infinite !important;
    }}
    @keyframes spCatSleepyEye {{
        0%, 40%, 60%, 100% {{ transform: scaleY(1); opacity:1; }}
        50% {{ transform: scaleY(0.1); opacity:0.5; }}
    }}
    /* Happy: open mouth (meow!) */
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-mouth {{
        opacity: 0;
    }}
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-mouth-open {{
        opacity: 1 !important;
        animation: spCatMeow 0.4s ease-in-out 3;
    }}
    @keyframes spCatMeow {{
        0%, 100% {{ transform: scaleY(1); }}
        50% {{ transform: scaleY(1.4); }}
    }}
    /* Purr vibration */
    .sp-pet[data-pet="cat"].sp-purr .sp-pet-body {{
        animation: spCatPurr 0.12s ease-in-out infinite;
    }}
    @keyframes spCatPurr {{
        0%, 100% {{ transform: translateX(0); }}
        25% {{ transform: translateX(-0.8px); }}
        75% {{ transform: translateX(0.8px); }}
    }}
    /* Heart float */
    .sp-pet[data-pet="cat"] .sp-cat-hearts {{
        pointer-events: none;
        transition: opacity 0.3s;
    }}
    .sp-pet[data-pet="cat"].sp-hearts .sp-cat-hearts {{
        opacity: 1 !important;
    }}
    .sp-cat-heart {{
        opacity: 0;
    }}
    .sp-pet[data-pet="cat"].sp-hearts .sp-cat-heart {{
        animation: spCatHeartFloat 1.2s ease-out forwards;
    }}
    .sp-pet[data-pet="cat"].sp-hearts .sp-cat-h1 {{ animation-delay: 0s; }}
    .sp-pet[data-pet="cat"].sp-hearts .sp-cat-h2 {{ animation-delay: 0.15s; }}
    .sp-pet[data-pet="cat"].sp-hearts .sp-cat-h3 {{ animation-delay: 0.3s; }}
    @keyframes spCatHeartFloat {{
        0% {{ opacity: 0; transform: translateY(0) scale(0.3); }}
        20% {{ opacity: 1; transform: translateY(-5px) scale(1.1); }}
        100% {{ opacity: 0; transform: translateY(-35px) scale(0.6); }}
    }}
    /* Cat tail: slower S-curve sway on idle */
    .sp-pet[data-pet="cat"]:not(.sp-dragging):not(.sp-happy):not(.sp-angry):not(.sp-wag):hover .sp-pet-tail-group {{
        animation: spCatTailSway 1.8s ease-in-out infinite;
    }}
    @keyframes spCatTailSway {{
        0%, 100% {{ transform: rotate(-5deg); }}
        50% {{ transform: rotate(15deg); }}
    }}
    /* Happy tail: curl */
    .sp-pet[data-pet="cat"].sp-happy .sp-pet-tail-group {{
        animation: spCatTailHappy 0.4s ease-in-out 5;
    }}
    @keyframes spCatTailHappy {{
        0%, 100% {{ transform: rotate(0deg); }}
        50% {{ transform: rotate(-25deg) translateY(-3px); }}
    }}
    /* Angry tail: thrash */
    .sp-pet[data-pet="cat"].sp-angry .sp-pet-tail-group {{
        animation: spCatTailThrash 0.1s ease-in-out 10;
    }}
    @keyframes spCatTailThrash {{
        0%, 100% {{ transform: rotate(0deg); }}
        25% {{ transform: rotate(18deg); }}
        75% {{ transform: rotate(-18deg); }}
    }}
    /* Paw wave on body click */
    .sp-pet[data-pet="cat"].sp-wave .sp-cat-paw-l {{
        animation: spCatPawWave 0.3s ease-in-out 3;
        transform-origin: 22px 56px;
    }}
    @keyframes spCatPawWave {{
        0%, 100% {{ transform: rotate(0deg) translateY(0); }}
        50% {{ transform: rotate(-25deg) translateY(-4px); }}
    }}
    /* Cat cheek/blush adjusted for new face */
    .sp-pet[data-pet="cat"] .sp-pet-cheek-l {{ left: 10px; top: 34px; }}
    .sp-pet[data-pet="cat"] .sp-pet-cheek-r {{ right: 10px; top: 34px; }}
    /* Forehead stripe subtle shimmer */
    .sp-pet[data-pet="cat"].sp-happy .sp-cat-forehead {{
        animation: spCatStripeShimmer 0.5s ease-in-out 3;
    }}
    @keyframes spCatStripeShimmer {{
        0%, 100% {{ stroke: #cbd5e1; }}
        50% {{ stroke: #fda4af; }}
    }}
    .sp-pet-drag-hint {{
        position: absolute;
        bottom: -4px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 0.6rem;
        color: #cbd5e1;
        opacity: 0;
        transition: opacity 0.3s;
        white-space: nowrap;
        pointer-events: none;
    }}
    .sp-pet:hover .sp-pet-drag-hint {{
        opacity: 1;
    }}
    .sp-pet-hint-btn {{
        position: absolute;
        top: -12px;
        left: -16px;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: {theme['accent']};
        color: #fff;
        font-size: 20px;
        font-weight: bold;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        z-index: 25;
        animation: sp-hint-bounce 1.2s ease-in-out infinite;
        transition: transform 0.2s;
    }}
    .sp-pet-hint-btn::after {{
        content: '';
        position: absolute;
        bottom: -4px;
        right: 4px;
        width: 12px;
        height: 12px;
        background: {theme['accent']};
        transform: rotate(45deg);
        border-radius: 2px;
    }}
    .sp-pet-hint-btn:hover {{
        transform: scale(1.3) rotate(-5deg);
    }}
    @keyframes sp-hint-bounce {{
        0%, 100% {{ transform: translateY(0) scale(1); }}
        50% {{ transform: translateY(-6px) scale(1.1); }}
    }}
    .sp-pet.sp-happy .sp-pet-body {{
        animation: spPetHappyJump 0.5s ease;
    }}
    @keyframes spPetHappyJump {{
        0%, 100% {{ transform: translateY(0) scale(1); }}
        30% {{ transform: translateY(-15px) scale(1.08); }}
        60% {{ transform: translateY(-5px) scale(1.03); }}
    }}
    .sp-pet.sp-wag .sp-pet-body {{
        animation: spPetWiggle 0.35s ease-in-out 3;
    }}
    @keyframes spPetWiggle {{
        0%, 100% {{ transform: rotate(0deg); }}
        25% {{ transform: rotate(-6deg) translateX(-4px); }}
        75% {{ transform: rotate(6deg) translateX(4px); }}
    }}
    </style>
    """



def _workspace_theme_css(theme: dict, is_dark: bool) -> str:
    """生成工作区主题覆盖 CSS，统一 _WORKSPACE_CSS 的 CSS 变量与全局主题。

    映射关系：
    - --sp-primary → 主题 accent
    - --sp-success → 保持绿色系（质检通过等语义色）
    - --sp-bg-page / --sp-bg-card / --sp-text-* → 适配暗色模式
    """
    if is_dark:
        return f"""<style>
:root {{
    --sp-primary: {theme['accent']};
    --sp-primary-light: {theme['accent']}1a;
    --sp-success: #10b981;
    --sp-success-light: #10b98114;
    --sp-warning: #f59e0b;
    --sp-warning-light: #f59e0b14;
    --sp-danger: #ef4444;
    --sp-danger-light: #ef444414;
    --sp-text-primary: {theme['text']};
    --sp-text-secondary: {theme['sidebar_text']};
    --sp-text-tertiary: #94a3b8;
    --sp-border: {theme['sidebar_border']};
    --sp-bg-page: {theme['sidebar']};
    --sp-bg-card: {theme['app']};
}}
</style>"""
    else:
        # 浅色主题：仅映射 primary 到 accent，其余保持 _WORKSPACE_CSS 默认值
        return f"""<style>
:root {{
    --sp-primary: {theme['accent']};
    --sp-primary-light: {theme['accent']}0d;
}}
</style>"""



_WORKSPACE_CSS = """
<style>
/* ===== StructPilot Visual Token System ===== */
:root {
    --sp-primary: #2563EB;
    --sp-primary-light: #EFF6FF;
    --sp-success: #16A34A;
    --sp-success-light: #F0FDF4;
    --sp-warning: #D97706;
    --sp-warning-light: #FFFBEB;
    --sp-danger: #DC2626;
    --sp-danger-light: #FEF2F2;
    --sp-text-primary: #0F172A;
    --sp-text-secondary: #334155;
    --sp-text-tertiary: #475569;
    --sp-border: #E2E8F0;
    --sp-bg-page: #F8FAFC;
    --sp-bg-card: #FFFFFF;
    --sp-space-1: 4px;
    --sp-space-2: 8px;
    --sp-space-3: 12px;
    --sp-space-4: 16px;
    --sp-space-6: 24px;
    --sp-space-8: 32px;
    --sp-radius-sm: 4px;
    --sp-radius: 8px;
    --sp-radius-lg: 10px;
    --sp-radius-full: 999px;
}

/* ===== 全局字体：14px 基准 ===== */
.main .block-container { font-size: 14px !important; }
p, div, span, li { font-size: 14px !important; }
h1 { font-size: 26px !important; }
h2 { font-size: 22px !important; }
h3 { font-size: 18px !important; }
h4 { font-size: 16px !important; }

/* ===== Step 状态行（紧凑单行） ===== */
.sp-step-bar {
    display: flex;
    align-items: center;
    gap: var(--sp-space-2);
    padding: 6px 0;
    font-size: 14px;
}
.sp-step-label {
    font-weight: 600;
    color: var(--sp-text-primary);
}
.sp-step-progress {
    font-size: 12px;
    color: var(--sp-text-tertiary);
    background: var(--sp-bg-page);
    padding: 2px 8px;
    border-radius: var(--sp-radius-full);
}
.sp-step-badge {
    font-size: 12px;
    padding: 2px 8px;
    border-radius: var(--sp-radius-sm);
    font-weight: 500;
}
.sp-step-badge.sw {
    background: #d1fae5;
    color: #0f766e;
}
.sp-step-badge.ph {
    background: var(--sp-bg-page);
    color: var(--sp-text-secondary);
}

/* ===== 工作区头部（居中步骤名 + 两侧导航） ===== */
.sp-ws-title {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--sp-space-2);
    padding: var(--sp-space-2) 0;
    text-align: center;
}
.sp-ws-step-name {
    font-size: 18px;
    font-weight: 700;
    color: var(--sp-text-primary);
    line-height: 1.2;
}
.sp-ws-status { font-size: 1.25rem; }
.sp-ws-gate {
    font-size: 12px;
    color: var(--sp-warning);
    font-weight: 600;
    background: var(--sp-warning-light);
    padding: 2px 8px;
    border-radius: var(--sp-radius-full);
}

.sp-ws-depth-label {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: var(--sp-text-secondary) !important;
    line-height: 32px !important;
    padding-left: 2px;
}

/* ===== 回答深度选项卡（Segmented Control）视觉强化 ===== */
[data-testid="stSegmentedControl"] {
    background: rgba(255, 255, 255, 0.65) !important;
    border-radius: 10px !important;
    padding: 2px !important;
}
[data-testid="stSegmentedControl"] button {
    font-size: 1.05rem !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    color: var(--sp-text-secondary) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSegmentedControl"] button:hover {
    background: rgba(22, 163, 74, 0.08) !important;
    color: var(--sp-success) !important;
}
[data-testid="stSegmentedControl"] button[aria-selected="true"] {
    background: var(--sp-success) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    box-shadow: 0 0 14px rgba(22, 163, 74, 0.35) !important;
}

button[kind="primary"] {
    background: var(--sp-success) !important;
    border-color: var(--sp-success) !important;
    font-weight: 600 !important;
    min-height: 36px !important;
}
button[kind="primary"]:hover {
    background: #15803d !important;
    border-color: #15803d !important;
}
button[kind="secondary"] {
    background: #ffffff !important;
    border: 1px solid var(--sp-border) !important;
    color: var(--sp-text-primary) !important;
    font-weight: 600 !important;
    min-height: 36px !important;
}
button[kind="secondary"]:hover {
    border-color: #93c5fd !important;
    color: var(--sp-primary) !important;
    background: var(--sp-primary-light) !important;
}

/* ===== 工作区导航按钮额外强调 ===== */
/* 注：Streamlit 未提供按钮文案选择器，导航按钮的额外强调改由 use_container_width
   + type 参数在 Python 层控制，此处不再使用非法的 :has-text() 伪类。 */

/* ===== 超宽屏适配 ===== */
@media (min-width: 1920px) {
    .main .block-container {
        max-width: 1680px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
}

/* ===== 响应式：平板 ===== */
@media (max-width: 1024px) {
    .sp-ws-title {
        padding: var(--sp-space-1) 0;
    }
    .sp-ws-step-name {
        font-size: 16px;
    }
}

/* ===== 响应式：手机 ===== */
@media (max-width: 768px) {
    .main .block-container {
        padding-left: 8px !important;
        padding-right: 8px !important;
    }
    button {
        min-height: 44px !important;
    }
    .sp-step-bar {
        flex-wrap: wrap;
        gap: 4px;
    }
    .sp-step-badge {
        font-size: 11px;
    }
    /* Streamlit columns 在窄屏下垂直堆叠 */
    div[data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
    }
    div[data-testid="stHorizontalBlock"] > div {
        width: 100% !important;
    }
}
</style>
"""
