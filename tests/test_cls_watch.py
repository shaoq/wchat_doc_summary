"""财联社看盘数据 API 客户端测试。"""

import hashlib
from urllib.parse import urlencode

import pytest

from src.api.cls_watch import CLSWatchClient, generate_sign


class TestGenerateSign:
    """签名算法测试。"""

    def test_generate_sign_basic(self):
        """测试基本签名生成。"""
        params = {
            "app": "CailianpressWeb",
            "category": "watch",
            "last_time": "1774332705",
            "os": "web",
            "refresh_type": "1",
            "rn": "20",
            "sv": "8.4.6",
        }

        sign = generate_sign(params)

        # 验证签名格式（MD5 输出为 32 位十六进制）
        assert len(sign) == 32
        assert all(c in "0123456789abcdef" for c in sign)

    def test_generate_sign_known_value(self):
        """测试已知参数的签名值。"""
        params = {
            "app": "CailianpressWeb",
            "category": "watch",
            "last_time": "1774332705",
            "os": "web",
            "refresh_type": "1",
            "rn": "20",
            "sv": "8.4.6",
        }

        sign = generate_sign(params)

        # 手动计算预期签名
        sorted_params = sorted(params.items())
        query_string = urlencode(sorted_params)
        sha1_hash = hashlib.sha1(query_string.encode()).hexdigest()
        expected_sign = hashlib.md5(sha1_hash.encode()).hexdigest()

        assert sign == expected_sign

    def test_generate_sign_algorithm_steps(self):
        """测试签名算法的各个步骤。"""
        params = {
            "app": "CailianpressWeb",
            "category": "watch",
            "last_time": "1774332705",
            "os": "web",
            "refresh_type": "1",
            "rn": "20",
            "sv": "8.4.6",
        }

        # 手动计算
        sorted_params = sorted(params.items())
        query_string = urlencode(sorted_params)
        sha1_hash = hashlib.sha1(query_string.encode()).hexdigest()
        expected_sign = hashlib.md5(sha1_hash.encode()).hexdigest()

        # 与函数结果比较
        actual_sign = generate_sign(params)
        assert actual_sign == expected_sign

    def test_generate_sign_different_params(self):
        """测试不同参数生成不同签名。"""
        params1 = {"a": "1", "b": "2"}
        params2 = {"a": "1", "b": "3"}

        sign1 = generate_sign(params1)
        sign2 = generate_sign(params2)

        assert sign1 != sign2

    def test_generate_sign_order_independence(self):
        """测试参数顺序不影响签名结果。"""
        params1 = {"b": "2", "a": "1", "c": "3"}
        params2 = {"c": "3", "a": "1", "b": "2"}

        sign1 = generate_sign(params1)
        sign2 = generate_sign(params2)

        assert sign1 == sign2


class TestCLSWatchClient:
    """CLSWatchClient 类测试。"""

    def test_client_initialization(self):
        """测试客户端初始化。"""
        client = CLSWatchClient(timeout=15.0)

        assert client.timeout == 15.0
        assert client._cache == {}
        assert client._cache_time is None

    def test_build_params(self):
        """测试参数构建。"""
        client = CLSWatchClient()
        params = client._build_params(last_time=1234567890, category="watch", rn=10)

        # 检查必要参数
        assert params["app"] == "CailianpressWeb"
        assert params["category"] == "watch"
        assert params["last_time"] == "1234567890"
        assert params["os"] == "web"
        assert params["rn"] == "10"
        assert params["sv"] == "8.4.6"
        assert "sign" in params
        assert len(params["sign"]) == 32

    def test_parse_watch_item(self):
        """测试看盘数据解析。"""
        client = CLSWatchClient()

        item = {
            "id": "test123",
            "title": "测试标题",
            "content": "测试内容",
            "ctime": 1700000000,
            "stocks": ["股票A", "股票B"],
            "sectors": ["板块A"],
        }

        result = client.parse_watch_item(item)

        assert result["watch_id"] == "test123"
        assert result["title"] == "测试标题"
        assert result["content"] == "测试内容"
        assert result["ctime"] == 1700000000
        assert result["publish_time"] is not None
        assert result["data_type"] == "stock_comment"  # 有股票/板块信息
        assert result["stocks"] == ["股票A", "股票B"]
        assert result["sectors"] == ["板块A"]

    def test_parse_watch_item_hot_data(self):
        """测试热点数据（无股票/板块信息）解析。"""
        client = CLSWatchClient()

        item = {
            "id": "hot123",
            "title": "热点标题",
            "content": "热点内容",
            "ctime": 1700000000,
        }

        result = client.parse_watch_item(item)

        assert result["watch_id"] == "hot123"
        assert result["data_type"] == "hot"  # 默认热点类型
        assert result["stocks"] == []
        assert result["sectors"] == []

    def test_parse_watch_item_missing_fields(self):
        """测试缺失字段的处理。"""
        client = CLSWatchClient()

        item = {}

        result = client.parse_watch_item(item)

        assert result["watch_id"] == ""
        assert result["title"] == ""
        assert result["content"] == ""
        assert result["data_type"] == "hot"  # 默认热点类型
        assert result["ctime"] == 0
        assert result["publish_time"] is None
        assert result["stocks"] == []
        assert result["sectors"] == []


class TestCLSWatchClientIntegration:
    """CLSWatchClient 集成测试（需要网络）。"""

    @pytest.mark.skip(reason="需要网络连接，在 CI 中跳过")
    def test_fetch_hot_data(self):
        """测试获取热点数据。"""
        client = CLSWatchClient()
        items = client.fetch_hot_data(limit=5)

        assert isinstance(items, list)
        assert len(items) <= 5

        if items:
            # 检查数据结构
            item = items[0]
            assert "title" in item or "content" in item

    @pytest.mark.skip(reason="需要网络连接，在 CI 中跳过")
    def test_fetch_by_time_range(self):
        """测试按时间范围获取看盘数据。"""
        import time

        client = CLSWatchClient()

        # 获取最近 1 小时的数据
        end_time = int(time.time())
        start_time = end_time - 3600

        items = client.fetch_by_time_range(start_time, end_time)

        assert isinstance(items, list)

        # 检查时间范围
        for item in items:
            ctime = item.get("ctime", 0)
            assert start_time <= ctime <= end_time
