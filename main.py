import json
import subprocess
import sys
import uuid

from dotenv import load_dotenv

from agent.client import MODELS, make_client
from agent.logger import make_logger
from agent.loop import run
from agent.tools import browser


def main() -> None:
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python main.py '<query>'", file=sys.stderr)
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    # Each process gets a unique session ID — used for browser isolation and log naming.
    session_id = f"agent_{uuid.uuid4().hex[:8]}"
    browser.set_session(session_id)

    logger = make_logger(session_id)
    client = make_client()

    try:
        result = run(client, MODELS, query, logger)
    finally:
        # Always clean up the browser session to avoid leaked processes.
        subprocess.run(
            ["agent-browser", "--session", session_id, "close"],
            capture_output=True,
        )
        logger.debug("Browser session %s closed.", session_id)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
