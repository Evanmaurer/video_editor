from __future__ import annotations

# Configurable lexicons for rule-based Albion OCR classification.
# Future custom ML models can replace classifier.py without changing consumers.

DEFAULT_ABILITY_NAMES: frozenset[str] = frozenset(
    {
        "avalon blink",
        "brimstone falls",
        "crystal leech",
        "dark blessing",
        "enchanted strike",
        "energy beam",
        "frost nova",
        "galatine pair",
        "grovekeeper",
        "hand of nature",
        "heavy smash",
        "heroic strike",
        "holy smite",
        "ice shard",
        "judgment",
        "locus of power",
        "meteor",
        "mighty swing",
        "morgana's curse",
        "poison thorns",
        "purge",
        "redemption",
        "sandstorm",
        "shield slam",
        "smite",
        "spirit walk",
        "stone fist",
        "sword slash",
        "thunderstorm",
        "wind wall",
    },
)

DEFAULT_ZONE_NAMES: frozenset[str] = frozenset(
    {
        "avalon",
        "brecilien",
        "bridgewatch",
        "caerleon",
        "fort sterling",
        "lymhurst",
        "martlock",
        "merlyn's crossing",
        "outlands",
        "roads of avalon",
        "thetford",
        "black zone",
        "blue zone",
        "red zone",
        "yellow zone",
    },
)
