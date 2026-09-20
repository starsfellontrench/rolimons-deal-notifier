from __future__ import annotations

from dataclasses import dataclass

import aiohttp

ITEM_DETAILS_URL = "https://api.rolimons.com/items/v1/itemdetails"
DEAL_ACTIVITY_URL = "https://api.rolimons.com/market/v2/dealactivity"

_NAME_INDEX = 0
_RAP_INDEX = 2
_VALUE_INDEX = 3

_TS_INDEX = 0
_ASSET_ID_INDEX = 2
_PRICE_INDEX = 4


@dataclass
class Item:
    asset_id: int
    name: str
    rap: int | None
    value: int | None

    @property
    def reference_price(self) -> int | None:
        if self.value and self.value > 0:
            return self.value
        if self.rap and self.rap > 0:
            return self.rap
        return None


@dataclass
class Deal:
    item: Item
    price: int
    timestamp: int
    percent_off: float


class RolimonsClient:
    def __init__(self, session: aiohttp.ClientSession):
        self._session = session
        self._items: dict[int, Item] = {}
        self._last_seen_ts = 0

    @property
    def item_count(self) -> int:
        return len(self._items)

    def get_item(self, asset_id: int) -> Item | None:
        return self._items.get(asset_id)

    def find_by_name(self, query: str, limit: int = 25) -> list[Item]:
        query = query.lower().strip()
        if not query:
            return []
        matches = [item for item in self._items.values() if query in item.name.lower()]
        matches.sort(key=lambda i: (not i.name.lower().startswith(query), i.name))
        return matches[:limit]

    async def refresh_item_cache(self) -> None:
        async with self._session.get(ITEM_DETAILS_URL) as resp:
            resp.raise_for_status()
            data = await resp.json()

        items: dict[int, Item] = {}
        for key, fields in data.get("items", {}).items():
            asset_id = int(key)
            rap = fields[_RAP_INDEX]
            value = fields[_VALUE_INDEX]
            items[asset_id] = Item(
                asset_id=asset_id,
                name=fields[_NAME_INDEX],
                rap=rap if rap and rap > 0 else None,
                value=value if value and value > 0 else None,
            )
        self._items = items

    async def poll_new_deals(self) -> list[Deal]:
        async with self._session.get(DEAL_ACTIVITY_URL) as resp:
            resp.raise_for_status()
            data = await resp.json()

        rows = data.get("activities", [])
        if not rows:
            return []

        first_poll = self._last_seen_ts == 0
        new_max_ts = self._last_seen_ts
        deals: list[Deal] = []

        for row in rows:
            ts = row[_TS_INDEX]
            if ts <= self._last_seen_ts:
                continue
            new_max_ts = max(new_max_ts, ts)

            if first_poll:
                continue

            asset_id = row[_ASSET_ID_INDEX]
            price = row[_PRICE_INDEX]
            item = self._items.get(asset_id)
            if item is None or not item.reference_price:
                continue

            reference = item.reference_price
            if price >= reference:
                continue

            percent_off = (reference - price) / reference * 100
            deals.append(Deal(item=item, price=price, timestamp=ts, percent_off=percent_off))

        self._last_seen_ts = new_max_ts
        return deals
