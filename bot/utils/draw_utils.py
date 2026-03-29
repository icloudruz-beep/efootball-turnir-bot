"""
Turnir sxemasini (bracket) yaratish va yangilash uchun yordamchi funksiyalar.
"""
import random
import math
from typing import Optional
from bot.db.participants import get_tournament_participants
from bot.db.matches import get_tournament_matches, create_match
from bot.db.participants import set_participant_group
from bot.db.tournaments import get_tournament


async def run_playoff_draw(tournament_id: int) -> tuple[list, list]:
    """
    Tasodifiy Play-off qura o'tkazadi va matchlar yaratadi.
    Returns: (participants, matches_created)
    """
    participants = await get_tournament_participants(tournament_id, approved_only=True)
    participants = list(participants)
    random.shuffle(participants)

    n = len(participants)
    rounds_count = math.ceil(math.log2(n)) if n > 1 else 1
    slots = 2 ** rounds_count

    padded = participants + [None] * (slots - n)

    matches = []
    for i in range(0, slots, 2):
        p1 = padded[i]
        p2 = padded[i + 1] if i + 1 < len(padded) else None
        if p1 is not None:
            p1_id = p1["id"]
            p2_id = p2["id"] if p2 else None
            mid = await create_match(
                tournament_id=tournament_id,
                stage="playoff",
                round_=1,
                participant1_id=p1_id,
                participant2_id=p2_id,
                group_name="",
            )
            matches.append(mid)

    return participants, matches


async def run_group_draw(tournament_id: int, group_size: int = 4) -> dict:
    """
    Tasodifiy guruh qura o'tkazadi.
    Returns: {group_name: [participants]}
    """
    participants = await get_tournament_participants(tournament_id, approved_only=True)
    participants = list(participants)
    random.shuffle(participants)

    group_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    groups = {}
    for i, p in enumerate(participants):
        gname = group_letters[i // group_size]
        if gname not in groups:
            groups[gname] = []
        groups[gname].append(p)
        await set_participant_group(p["id"], gname, i % group_size)

    for gname, members in groups.items():
        for j, p1 in enumerate(members):
            for p2 in members[j + 1:]:
                await create_match(
                    tournament_id=tournament_id,
                    stage="group",
                    round_=1,
                    participant1_id=p1["id"],
                    participant2_id=p2["id"],
                    group_name=gname,
                )

    return groups


async def determine_winner(match_row) -> Optional[int]:
    score1 = match_row["score1"]
    score2 = match_row["score2"]
    if score1 is None or score2 is None:
        return None
    if score1 > score2:
        return match_row["participant1_id"]
    elif score2 > score1:
        return match_row["participant2_id"]
    return None
