TOOLS = [
    {
        "name": "today",
        "title": "Today's date",
        "description": "Return today's date with a specified format argument that adheres to the Python strftime() format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "description": "provide a format that adheres to Python strftime() format"}
            },
            "required": ["format"],
        },
    },
    {
        "name": "weekday",
        "title": "Weekday of a given date",
        "description": "Return the weekday for a date provided in the date argument.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "provide the date"}
            },
            "required": ["date"],
        },
    },
    {
        "name": "timer",
        "title": "Egg timer",
        "description": "A simple “egg timer” that sends an update every ten seconds and an alarm. The argument alarm specifies the number of seconds until the alarm.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "alarm": {"type": "integer", "description": "the number of seconds until the alarm."}
            },
            "required": ["alarm"],
        },
    },
    {
        "name": "calculator",
        "title": "Calculator tool",
        "description": "Interpret expression element and return answer, using the bc calculator tool.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "provide expression to be computed"}
            },
            "required": ["expression"],
        },
    },
]

def today(args):
    form = args.get("format")
    if not form or not isinstance(form, str) or not form.strip():
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Require 'format' argument with type string"}],
            "isError": True,
        }
    try:
        res = datetime.date.today().strftime(form.strip())
    except ValueError as e:
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": f"The format string is not a valid format"}],
            "isError": True,
        }
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": res}],
        "isError": False,
    }


def weekday(args):
    date = args.get("date")
    if not date or not isinstance(date, str) or not date.strip():
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Require 'date' argument with type string"}],
            "isError": True,
        }
    try:
        res = datetime.date.fromisoformat(date.strip())
    except ValueError:
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": f"Could not parse '{date}' argument. Please use ISO 8601 format"}],
            "isError": True,
        }
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": res.strftime("%A")}],
        "isError": False,
    }


def calculator(args):
    expr = args.get("expression")
    if not expr or not isinstance(expr, str) or not expr.strip() :
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Require 'expression' argument with type string"}],
            "isError": True,
        }

    try:
        proc = subprocess.run(["bc", "-l"], input=expr.strip(), capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Calculation timed out after 5 seconds."}],
            "isError": True,
        }

    if proc.stderr.strip():
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": f"bc error: {proc.stderr.strip()}"}],
            "isError": True,
        }

    if not proc.stdout.strip():
        return {
            "resultType": "complete",
            "content": [{"type": "text", "text": f"bc failed to provide an output to the expression"}],
            "isError": True,
        }

    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": proc.stdout.strip()}],
        "isError": False,
    }