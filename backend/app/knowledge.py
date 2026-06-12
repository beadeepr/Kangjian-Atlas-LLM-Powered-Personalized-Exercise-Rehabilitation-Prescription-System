import json
from pathlib import Path
from typing import List
from .schema import ActionItem

BASE_DIR = Path(__file__).resolve().parents[2]


def load_action_library() -> List[ActionItem]:
    actions_file = BASE_DIR / 'knowledge' / 'actions.json'
    with open(actions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [ActionItem(
        name=item['name'],
        sets=item.get('sets', 1),
        reps=item.get('reps', 1),
        note=item.get('description')
    ) for item in data.get('actions', [])]
