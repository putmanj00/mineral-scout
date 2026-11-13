"""fetch_text must not cache upstream error bodies (HTTP-200 WFS exceptions)."""
import pytest
import respx
from httpx import Response

from app.sources import mrds
from app.upstream import UpstreamError


@pytest.mark.anyio
@respx.mock
async def test_wfs_exception_not_negatively_cached():
    route = respx.get(mrds.WFS_URL)
    route.side_effect = [
        Response(200, text="<ServiceExceptionReport>boom</ServiceExceptionReport>"),
        Response(200, text=open("tests/__init__.py").read() or "x"),  # placeholder, replaced below
    ]
    with pytest.raises(UpstreamError):
        await mrds.query_bbox((-113.0, 33.0, -112.0, 34.0))
    # second call must hit upstream again (not the cache) — serve valid GML now
    from tests.test_mrds import GML_SAMPLE
    route.side_effect = [Response(200, text=GML_SAMPLE)]
    sites, truncated = await mrds.query_bbox((-113.0, 33.0, -112.0, 34.0))
    assert len(sites) == 2
    assert truncated is False
