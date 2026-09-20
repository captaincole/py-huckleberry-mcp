"""Tests for feeding tracking tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo
from huckleberry_mcp.tools import feeding


@pytest.fixture
def mock_api():
    """Create a mock API instance."""
    api = AsyncMock()
    api.get_children = MagicMock(return_value=[{"uid": "child1", "name": "Alice"}])
    api.start_feeding = MagicMock()  # Synchronous, not async
    api.pause_feeding = MagicMock()  # Synchronous, not async
    api.resume_feeding = MagicMock()  # Synchronous, not async
    api.switch_feeding_side = MagicMock()  # Synchronous, not async
    api.complete_feeding = MagicMock()  # Synchronous, not async
    api.cancel_feeding = MagicMock()  # Synchronous, not async
    api._timezone = ZoneInfo("America/New_York")  # EST/EDT timezone
    api._get_timezone_offset_minutes = MagicMock(return_value=-300.0)  # EST offset

    # Mock Firestore client for log_breastfeeding
    mock_firestore = MagicMock()
    mock_collection = MagicMock()
    mock_document = MagicMock()
    mock_intervals_collection = MagicMock()
    mock_interval_doc = MagicMock()

    # Setup chain: client.collection("feed").document(child_uid)
    mock_firestore.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_document

    # Setup chain: feed_ref.collection("intervals").document(interval_id)
    mock_document.collection.return_value = mock_intervals_collection
    mock_intervals_collection.document.return_value = mock_interval_doc

    api._get_firestore_client = MagicMock(return_value=mock_firestore)

    return api


@pytest.mark.asyncio
async def test_start_breastfeeding_success(mock_api):
    """Test starting a breastfeeding session."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        result = await feeding.start_breastfeeding("child1", "left")

        assert result["success"] is True
        assert result["side"] == "left"
        mock_api.start_feeding.assert_called_once_with("child1", side="left")


@pytest.mark.asyncio
async def test_start_breastfeeding_invalid_side(mock_api):
    """Test starting breastfeeding with invalid side."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        with pytest.raises(ValueError, match="Invalid side"):
            await feeding.start_breastfeeding("child1", "middle")


@pytest.mark.asyncio
async def test_switch_feeding_side_success(mock_api):
    """Test switching feeding sides."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        result = await feeding.switch_feeding_side("child1")

        assert result["success"] is True
        assert "message" in result
        mock_api.switch_feeding_side.assert_called_once_with("child1")


@pytest.mark.asyncio
async def test_log_breastfeeding_with_durations(mock_api):
    """Test logging breastfeeding with left and right durations."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        result = await feeding.log_breastfeeding(
            "child1",
            start_time="2024-01-01T14:00:00Z",
            left_duration_minutes=10,
            right_duration_minutes=15
        )

        assert result["success"] is True
        assert result["left_duration_minutes"] == 10
        assert result["right_duration_minutes"] == 15
        assert result["total_duration_minutes"] == 25
        assert result["last_side"] == "right"  # Right has more duration
        assert "interval_id" in result


@pytest.mark.asyncio
async def test_log_breastfeeding_with_end_time(mock_api):
    """Test logging breastfeeding with end_time."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        result = await feeding.log_breastfeeding(
            "child1",
            start_time="2024-01-01T14:00:00Z",
            end_time="2024-01-01T14:30:00Z",
            last_side="left"
        )

        assert result["success"] is True
        assert result["left_duration_minutes"] == 30
        assert result["right_duration_minutes"] == 0
        assert result["total_duration_minutes"] == 30
        assert result["last_side"] == "left"


@pytest.mark.asyncio
async def test_log_breastfeeding_left_only(mock_api):
    """Test logging breastfeeding with only left duration."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        result = await feeding.log_breastfeeding(
            "child1",
            start_time="2024-01-01T14:00:00Z",
            left_duration_minutes=20
        )

        assert result["success"] is True
        assert result["left_duration_minutes"] == 20
        assert result["right_duration_minutes"] == 0
        assert result["last_side"] == "left"


@pytest.mark.asyncio
async def test_log_breastfeeding_no_duration_or_end_time(mock_api):
    """Test logging breastfeeding without duration or end_time raises error."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        with pytest.raises(ValueError, match="Must provide either end_time OR"):
            await feeding.log_breastfeeding("child1", start_time="2024-01-01T14:00:00Z")


@pytest.mark.asyncio
async def test_log_breastfeeding_both_end_time_and_durations(mock_api):
    """Test logging breastfeeding with both end_time and durations raises error."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        with pytest.raises(ValueError, match="When using end_time, do not specify"):
            await feeding.log_breastfeeding(
                "child1",
                start_time="2024-01-01T14:00:00Z",
                end_time="2024-01-01T14:30:00Z",
                left_duration_minutes=10
            )


@pytest.mark.asyncio
async def test_log_breastfeeding_end_time_without_last_side(mock_api):
    """Test logging breastfeeding with end_time but no last_side raises error."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        with pytest.raises(ValueError, match="When using end_time, last_side is required"):
            await feeding.log_breastfeeding(
                "child1",
                start_time="2024-01-01T14:00:00Z",
                end_time="2024-01-01T14:30:00Z"
            )


@pytest.mark.asyncio
async def test_log_breastfeeding_invalid_last_side(mock_api):
    """Test logging breastfeeding with invalid last_side raises error."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        with pytest.raises(ValueError, match="Invalid last_side"):
            await feeding.log_breastfeeding(
                "child1",
                start_time="2024-01-01T14:00:00Z",
                left_duration_minutes=10,
                last_side="middle"
            )


# ============== Bottle Feeding Tests ==============

@pytest.mark.asyncio
async def test_log_bottle_feeding_success(mock_api):
    """Test logging bottle feeding with default values."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        result = await feeding.log_bottle_feeding("child1", amount=4.0)

        assert result["success"] is True
        assert result["amount"] == 4.0
        assert result["units"] == "oz"
        assert result["bottle_type"] == "Formula"
        assert "interval_id" in result
        assert "timestamp" in result


@pytest.mark.asyncio
async def test_log_bottle_feeding_breast_milk(mock_api):
    """Test logging bottle feeding with breast milk."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        result = await feeding.log_bottle_feeding(
            "child1",
            amount=120,
            bottle_type="Breast Milk",
            units="ml"
        )

        assert result["success"] is True
        assert result["amount"] == 120
        assert result["units"] == "ml"
        assert result["bottle_type"] == "Breast Milk"


@pytest.mark.asyncio
async def test_log_bottle_feeding_mixed(mock_api):
    """Test logging bottle feeding with mixed content."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        result = await feeding.log_bottle_feeding(
            "child1",
            amount=5.5,
            bottle_type="Mixed",
            units="oz"
        )

        assert result["success"] is True
        assert result["amount"] == 5.5
        assert result["bottle_type"] == "Mixed"


@pytest.mark.asyncio
async def test_log_bottle_feeding_with_timestamp(mock_api):
    """Test logging bottle feeding with retroactive timestamp."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        result = await feeding.log_bottle_feeding(
            "child1",
            amount=4.0,
            timestamp="2024-01-01T14:30:00Z"
        )

        assert result["success"] is True
        assert result["amount"] == 4.0
        # Timestamp should be converted to local timezone
        assert "2024-01-01" in result["timestamp"]


@pytest.mark.asyncio
async def test_log_bottle_feeding_invalid_type(mock_api):
    """Test logging bottle feeding with invalid bottle_type raises error."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        with pytest.raises(ValueError, match="Invalid bottle_type"):
            await feeding.log_bottle_feeding("child1", amount=4.0, bottle_type="water")


@pytest.mark.asyncio
async def test_log_bottle_feeding_invalid_units(mock_api):
    """Test logging bottle feeding with invalid units raises error."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        with pytest.raises(ValueError, match="Invalid units"):
            await feeding.log_bottle_feeding("child1", amount=4.0, units="cups")


@pytest.mark.asyncio
async def test_log_bottle_feeding_zero_amount(mock_api):
    """Test logging bottle feeding with zero amount raises error."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        with pytest.raises(ValueError, match="Amount must be a positive number"):
            await feeding.log_bottle_feeding("child1", amount=0)


@pytest.mark.asyncio
async def test_log_bottle_feeding_negative_amount(mock_api):
    """Test logging bottle feeding with negative amount raises error."""
    with patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api), \
         patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api):

        with pytest.raises(ValueError, match="Amount must be a positive number"):
            await feeding.log_bottle_feeding("child1", amount=-2.5)


# ============== Feeding History Tests ==============

def _patched(mock_api, intervals):
    """Patch auth and the raw Firestore fetch so tests can feed intervals directly."""
    return (
        patch("huckleberry_mcp.tools.feeding.get_authenticated_api", return_value=mock_api),
        patch("huckleberry_mcp.tools.children.get_authenticated_api", return_value=mock_api),
        patch("huckleberry_mcp.tools.feeding._fetch_feed_intervals", return_value=intervals),
    )


@pytest.mark.asyncio
async def test_get_feeding_history_breast(mock_api):
    """Breast entries expose durations converted from seconds to minutes."""
    intervals = [{
        "mode": "breast",
        "start": 1704103200,
        "leftDuration": 600,   # 10 minutes
        "rightDuration": 900,  # 15 minutes
        "is_multi_entry": False,
    }]
    a, b, c = _patched(mock_api, intervals)
    with a, b, c:
        result = await feeding.get_feeding_history("child1", "2024-01-01", "2024-01-02")

    assert len(result) == 1
    assert result[0]["mode"] == "breast"
    assert result[0]["left_duration_minutes"] == 10
    assert result[0]["right_duration_minutes"] == 15
    assert result[0]["total_duration_minutes"] == 25
    assert "amount" not in result[0]


@pytest.mark.asyncio
async def test_get_feeding_history_bottle(mock_api):
    """Bottle entries expose amount, units, and bottle_type."""
    intervals = [{
        "mode": "bottle",
        "start": 1704103200,
        "amount": 4.5,
        "units": "oz",
        "bottleType": "Formula",
        "is_multi_entry": False,
    }]
    a, b, c = _patched(mock_api, intervals)
    with a, b, c:
        result = await feeding.get_feeding_history("child1", "2024-01-01", "2024-01-02")

    assert len(result) == 1
    assert result[0]["mode"] == "bottle"
    assert result[0]["amount"] == 4.5
    assert result[0]["units"] == "oz"
    assert result[0]["bottle_type"] == "Formula"
    assert "left_duration_minutes" not in result[0]


@pytest.mark.asyncio
async def test_get_feeding_history_bottle_without_amount(mock_api):
    """Bottle rows saved without a volume return amount=None rather than failing."""
    intervals = [{
        "mode": "bottle",
        "start": 1704103200,
        "units": "ml",
        "bottleType": "Breast Milk",
        "is_multi_entry": False,
    }]
    a, b, c = _patched(mock_api, intervals)
    with a, b, c:
        result = await feeding.get_feeding_history("child1", "2024-01-01", "2024-01-02")

    assert result[0]["amount"] is None
    assert result[0]["units"] == "ml"
    assert result[0]["bottle_type"] == "Breast Milk"


@pytest.mark.asyncio
async def test_get_feeding_history_multi_entry(mock_api):
    """Multi-entry rows keep their flag and mode-specific fields."""
    intervals = [
        {"mode": "breast", "start": 1704103200, "leftDuration": 600, "rightDuration": 900, "is_multi_entry": True},
        {"mode": "bottle", "start": 1704106800, "amount": 120, "units": "ml", "bottleType": "Mixed", "is_multi_entry": True},
    ]
    a, b, c = _patched(mock_api, intervals)
    with a, b, c:
        result = await feeding.get_feeding_history("child1", "2024-01-01", "2024-01-02")

    assert [r["is_multi_entry"] for r in result] == [True, True]
    assert result[0]["left_duration_minutes"] == 10
    assert result[1]["amount"] == 120


@pytest.mark.asyncio
async def test_get_feeding_history_legacy_row_without_mode(mock_api):
    """Rows with durations but no mode field are treated as breast."""
    intervals = [{"start": 1704103200, "leftDuration": 300, "rightDuration": 0, "is_multi_entry": False}]
    a, b, c = _patched(mock_api, intervals)
    with a, b, c:
        result = await feeding.get_feeding_history("child1", "2024-01-01", "2024-01-02")

    assert result[0]["mode"] == "breast"
    assert result[0]["left_duration_minutes"] == 5


def _doc(data):
    d = MagicMock()
    d.to_dict.return_value = data
    return d


def test_fetch_feed_intervals_reads_regular_and_multi_docs(mock_api):
    """The raw fetch preserves all fields, skips multi docs in the range query,
    filters nested multi entries by date, and sorts by start."""
    intervals_ref = mock_api._get_firestore_client().collection().document().collection()

    # Range query: one bottle row, one breast row, one multi container (must be skipped here)
    intervals_ref.where.return_value.where.return_value.order_by.return_value.stream.return_value = [
        _doc({"mode": "bottle", "start": 200, "amount": 3.0, "units": "oz", "bottleType": "Formula"}),
        _doc({"mode": "breast", "start": 100, "leftDuration": 60, "rightDuration": 0}),
        _doc({"multi": True, "data": {}}),
    ]
    # Multi query: one entry in range, one out of range, one malformed
    intervals_ref.where.return_value.stream.return_value = [
        _doc({"multi": True, "data": {
            "a": {"mode": "bottle", "start": 150, "amount": 2.0, "units": "oz", "bottleType": "Mixed"},
            "b": {"mode": "bottle", "start": 999, "amount": 9.0, "units": "oz", "bottleType": "Formula"},
            "c": "not-a-dict",
        }}),
    ]

    result = feeding._fetch_feed_intervals(mock_api, "child1", 0, 500)

    assert [r["start"] for r in result] == [100, 150, 200]
    assert [r["is_multi_entry"] for r in result] == [False, True, False]
    assert result[1]["amount"] == 2.0 and result[1]["bottleType"] == "Mixed"
    assert result[2]["bottleType"] == "Formula"
