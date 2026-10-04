"""Console rendering for V0.4 engineer messages."""

from .models import EngineerMessage


def format_messages(messages: tuple[EngineerMessage, ...]) -> str:
    if not messages:
        return 'Engineer: --'
    lines = ['Engineer:']
    for message in messages:
        lines.append(f'  [{message.priority_name.upper():11s}] {message.text}')
    return '\n'.join(lines)
