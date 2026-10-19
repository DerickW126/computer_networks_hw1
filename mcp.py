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
