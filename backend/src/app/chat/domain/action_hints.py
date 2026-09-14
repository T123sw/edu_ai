from typing import Literal


GenerationActionHint = Literal[
    "generate.report",
    "generate.lesson_plan",
    "generate.blog",
    "generate.quiz",
    "generate.flashcard",
    "generate.graph",
    "generate.game",
    "generate.classroom",
]

ActionHint = Literal[
    "chat.reply",
    "chat.rewrite",
    "research.lookup",
    "generate.report",
    "generate.lesson_plan",
    "generate.blog",
    "generate.quiz",
    "generate.flashcard",
    "generate.graph",
    "generate.game",
    "generate.classroom",
]

GENERATION_ACTION_HINTS = frozenset(
    {
        "generate.report",
        "generate.lesson_plan",
        "generate.blog",
        "generate.quiz",
        "generate.flashcard",
        "generate.graph",
        "generate.game",
        "generate.classroom",
    }
)

ALLOWED_ACTION_HINTS = frozenset(
    {"chat.reply", "chat.rewrite", "research.lookup", *GENERATION_ACTION_HINTS}
)
