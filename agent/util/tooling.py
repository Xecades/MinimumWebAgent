import json


def fmt_tool_args(args: object) -> str:
    if not isinstance(args, dict):
        return repr(args)
    parts = []
    for key, value in args.items():
        value_repr = repr(value) if not isinstance(value, str) else f"{value!r}"
        parts.append(f"{key}={value_repr}")
    return ", ".join(parts)


def tool_signature(name: str, args: object) -> str:
    return f"{name}:{json.dumps(args, ensure_ascii=False, sort_keys=True)}"
