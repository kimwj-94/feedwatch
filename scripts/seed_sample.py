from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.models import Item, Source, item_hash, new_id
from shared.repository import get_repository


def main() -> None:
    repository = get_repository()
    groups = repository.list_groups()
    common = groups[0]
    source = repository.save_source(
        Source(
            id="",
            name="FeedWatch 샘플 공지",
            url="https://example.com/notice",
            group_ids=[common.id],
            selector="a",
            active=False,
        )
    )
    samples = [
        ("샘플 공지: 첫 번째 항목", "https://example.com/notice/1"),
        ("샘플 공지: 두 번째 항목", "https://example.com/notice/2"),
    ]
    items = [
        Item(
            id=new_id("item"),
            source_id=source.id,
            source_name=source.name,
            group_ids=list(source.group_ids),
            title=title,
            url=url,
            hash=item_hash(source.id, title, url),
        )
        for title, url in samples
    ]
    new_items = repository.add_items_dedup(items)
    print(f"Seeded {len(new_items)} sample items.")


if __name__ == "__main__":
    main()
