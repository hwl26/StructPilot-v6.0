"""Legacy browser-session compatibility helpers.

Authentication state is intentionally not persisted in browser-accessible
storage.  The historical save/restore entry points remain as safe no-ops so
older callers do not fail, while logout can still remove legacy artifacts.
"""

from __future__ import annotations

import streamlit.components.v1 as components


def save_session_to_storage(username: str, role: str, display_name: str) -> None:
    """Deprecated: never write identity or session data to localStorage."""
    return None


def restore_session_from_storage() -> None:
    """Deprecated: browser storage is not trusted as an authentication source."""
    return None


def clear_session_from_storage() -> None:
    """Remove data left by versions that used localStorage for login state."""
    components.html(
        """
        <script>
        try { localStorage.removeItem('structpilot_session'); } catch (e) {}
        </script>
        """,
        height=0,
    )


def init_session_persistence() -> None:
    """Deprecated compatibility entry point; authentication stays server-side."""
    return None


def save_session_cookie(username: str, role: str, display_name: str) -> None:
    """Deprecated: JavaScript cookies are not used for authentication."""
    return None


def restore_session_cookie() -> None:
    """Deprecated: JavaScript cookies are not trusted for authentication."""
    return None


def clear_session_cookie() -> None:
    """Expire the non-HttpOnly cookie used by older versions, if it exists."""
    components.html(
        """
        <script>
        document.cookie = 'structpilot_session=; Max-Age=0; path=/; SameSite=Lax';
        </script>
        """,
        height=0,
    )
