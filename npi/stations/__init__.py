"""各站模組。每站提供 prepare(ctx)、check(ctx, facts, judgement)、render(ctx, facts, judgement)、read_back(ctx, facts, judgement)。"""

STATION_ORDER = ["dfm", "release", "cost", "po", "supply"]

# 站名 → 模組；各站做好時登記進來
REGISTRY = {}

from . import cost, dfm, po_check, release, supply  # noqa: E402

REGISTRY.update(dfm=dfm, release=release, cost=cost, po=po_check, supply=supply)
