"""Pure-stdlib text distance metrics (no third-party dependencies).

Used to quantify how much a PM edited a generated artifact between generation
and approval. ``char_edit_distance`` is a standard Levenshtein distance;
``normalized_edit_distance`` scales it to 0..1 by the longer input length so
short and long artifacts are comparable.
"""


def char_edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance (insertions/deletions/substitutions) between two strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # Two-row dynamic programming — O(len(a) * len(b)) time, O(len(b)) space.
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def normalized_edit_distance(a: str, b: str) -> float:
    """Edit distance scaled to 0..1 by the longer string length (0.0 == identical)."""
    if not a and not b:
        return 0.0
    longest = max(len(a), len(b))
    if longest == 0:
        return 0.0
    return char_edit_distance(a, b) / longest
