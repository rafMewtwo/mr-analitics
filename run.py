"""Runner do Streamlit que evita o bug de WebSocket keepalive no Windows.

Streamlit 1.50+ usa Uvicorn por baixo. No Python 3.12 + Windows o loop padrão
(ProactorEventLoop) tem problemas com o ping/pong do WebSocket, o que faz a
página ficar eternamente em skeleton.

A solução é trocar o event loop pra SelectorEventLoop ANTES de qualquer import
do Streamlit/uvicorn.

Uso:
    python run.py
"""

from __future__ import annotations

import asyncio
import sys


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    from streamlit.web.cli import main as st_main

    sys.argv = [
        "streamlit",
        "run",
        "app.py",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    st_main()


if __name__ == "__main__":
    main()
