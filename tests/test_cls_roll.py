"""财联社 Roll API 客户端测试。"""

import hashlib
from urllib.parse import urlencode

import pytest

from src.api.cls_roll import CLSRollClient, generate_sign


class TestGenerateSign:
    """签名算法测试。"""

    def test_generate_sign_basic(self):
        """测试基本签名生成。"""
        params = {
            "app": "CailianpressWeb",
            "category": "red",
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
            "category": "red",
            "last_time": "1774332705",
            "os": "web",
            "refresh_type": "1",
            "rn": "20",
            "sv": "8.4.6",
        }

        sign = generate_sign(params)

        # 预期签名值（通过验证）
        expected = "cbb737601896bed10d48aedf2f0e08d5"
        assert sign == expected

    def test_generate_sign_algorithm_steps(self):
        """测试签名算法的各个步骤。"""
        params = {
            "app": "CailianpressWeb",
            "category": "red",
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


class TestCLSRollClient:
    """CLSRollClient 类测试。"""

    def test_client_initialization(self):
        """测试客户端初始化。"""
        client = CLSRollClient(timeout=15.0)

        assert client.timeout == 15.0
        assert client._cache == {}
        assert client._cache_time is None

    def test_build_params(self):
        """测试参数构建。"""
        client = CLSRollClient()
        params = client._build_params(last_time=1234567890, rn=10)

        # 检查必要参数
        assert params["app"] == "CailianpressWeb"
        assert params["category"] == "red"
        assert params["last_time"] == "1234567890"
        assert params["os"] == "web"
        assert params["rn"] == "10"
        assert params["sv"] == "8.4.6"
        assert "sign" in params
        assert len(params["sign"]) == 32

    def test_parse_telegraph(self):
        """测试电报数据解析。"""
        client = CLSRollClient()

        item = {
            "title": "测试标题",
            "content": "测试内容",
            "ctime": 1700000000,
            "level": 3,
        }

        result = client.parse_telegraph(item)

        assert result["title"] == "测试标题"
        assert result["content"] == "测试内容"
        assert result["level"] == 3
        assert result["ctime"] == 1700000000
        assert result["publish_time"] is not None

    def test_parse_telegraph_missing_fields(self):
        """测试缺失字段的处理。"""
        client = CLSRollClient()

        item = {}

        result = client.parse_telegraph(item)

        assert result["title"] == ""
        assert result["content"] == ""
        assert result["level"] == 0
        assert result["ctime"] == 0
        assert result["publish_time"] is None


class TestCLSRollClientIntegration:
    """CLSRollClient 集成测试（需要网络）。"""

    @pytest.mark.skip(reason="需要网络连接，在 CI 中跳过")
    def test_fetch_latest(self):
        """测试获取最新电报。"""
        client = CLSRollClient()
        items = client.fetch_latest(limit=5)

        assert isinstance(items, list)
        assert len(items) <= 5

        if items:
            # 检查数据结构
            item = items[0]
            assert "title" in item or "content" in item

    @pytest.mark.skip(reason="需要网络连接，在 CI 中跳过")
    def test_fetch_by_time_range(self):
        """测试按时间范围获取电报。"""
        import time

        client = CLSRollClient()

        # 获取最近 1 小时的数据
        end_time = int(time.time())
        start_time = end_time - 3600

        items = client.fetch_by_time_range(start_time, end_time)

        assert isinstance(items, list)

        # 检查时间范围
        for item in items:
            ctime = item.get("ctime", 0)
            assert start_time <= ctime <= end_time
