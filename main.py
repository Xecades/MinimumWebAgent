import json
import sys
import uuid

from agent.client import MODEL, make_client
from agent.loop import run
from agent.tools import browser


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main.py '<query>'", file=sys.stderr)
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    # Each process gets a unique browser session so concurrent runs are isolated.
    session_id = f"agent_{uuid.uuid4().hex[:8]}"
    browser.set_session(session_id)

    client = make_client()
    result = run(client, MODEL, query)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
