"""板块 API 单元测试 - 同花顺数据源。"""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.api.sector import THSSectorClient, SectorClient, SectorData, SectorAPIError


class TestSectorData:
    """SectorData 数据模型测试。"""

    def test_sector_data_creation(self):
        """测试创建板块数据对象。"""
        sector = SectorData(
            code="",  # 同花顺无板块代码
            name="电力",
            price=None,
            change_pct=3.73,
            change=0,
            volume=193237000,  # 万手
            amount=137236000000,  # 亿元
        )

        assert sector.code == ""
        assert sector.name == "电力"
        assert sector.change_pct == 3.73

    def test_sector_data_repr(self):
        """测试板块数据对象的字符串表示。"""
        sector = SectorData(code="", name="电力", change_pct=3.73)
        assert "电力" in repr(sector)


class TestTHSSectorClient:
    """THSSectorClient 类测试。"""

    def test_client_initialization(self):
        """测试客户端初始化。"""
        client = THSSectorClient(timeout=15.0)

        assert client.timeout == 15.0
        assert client._cache == {}
        assert client._cache_time == {}

    def test_alias_compatibility(self):
        """测试别名兼容性。"""
        # SectorClient 应该是 THSSectorClient 的别名
        assert SectorClient == THSSectorClient


class TestFetchWithCurl:
    """curl 请求函数测试。"""

    def test_fetch_with_curl_success(self):
        """测试 curl 请求成功。"""
        client = THSSectorClient()

        # 模拟成功的 HTML 响应
        mock_html = """
        <html>
        <table class="bdbox">
            <tr><td>序号</td><td>板块</td><td>涨跌幅(%)</td><td>总成交量</td><td>总成交额</td></tr>
            <tr><td>1</td><td><a href="#">电力</a></td><td>3.73</td><td>19323.70</td><td>1372.36</td></tr>
        </table>
        </html>
        """.encode("gbk")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_html
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result):
            html = client._fetch_with_curl(client.INDUSTRY_URL)

        assert html is not None
        assert "电力" in html

    def test_fetch_with_curl_failure(self):
        """测试 curl 请求失败。"""
        client = THSSectorClient()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = b"error"

        with patch("subprocess.run", return_value=mock_result):
            html = client._fetch_with_curl(client.INDUSTRY_URL)

        assert html is None

    def test_fetch_with_curl_timeout(self):
        """测试 curl 请求超时。"""
        client = THSSectorClient()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("curl", 10)):
            html = client._fetch_with_curl(client.INDUSTRY_URL)

        assert html is None

    def test_fetch_with_curl_not_found(self):
        """测试 curl 命令不可用. """
        client = THSSectorClient()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            html = client._fetch_with_curl(client.INDUSTRY_URL)

        assert html is None

    def test_fetch_with_curl_network_disabled(self):
        """测试网络请求被禁用。 """
        # 设置环境变量禁用网络
        os.environ["WCHAT_DISABLE_NETWORK"] = "1"
        client = THSSectorClient()

        html = client._fetch_with_curl(client.INDUSTRY_URL)

        assert html is None

        # 清理环境变量
        del os.environ["WCHAT_DISABLE_NETWORK"]


class TestParseIndustryTable:
    """HTML 表格解析测试."""

    def test_parse_valid_html(self):
        """测试解析有效的 HTML 表格. """
        client = THSSectorClient()

        html = """
        <table class="bdbox">
            <tr><td>序号</td><td>板块</td><td>涨跌幅(%)</td><td>总成交量（万手）</td><td>总成交额（亿元）</td></tr>
            <tr><td>1</td><td><a href="#">电力</a></td><td>3.73</td><td>19323.70</td><td>1372.36</td></tr>
            <tr><td>2</td><td><a href="#">通信服务</a></td><td>3.51</td><td>2256.23</td><td>423.25</td></tr>
        </table>
        """

        sectors = client._parse_industry_table(html)

        assert len(sectors) == 2
        assert sectors[0].name == "电力"
        assert sectors[0].change_pct == 3.73
        assert sectors[1].name == "通信服务"
        assert sectors[1].change_pct == 3.51

    def test_parse_empty_html(self):
        """测试解析空 HTML. """
        client = THSSectorClient()

        sectors = client._parse_industry_table("")

        assert len(sectors) == 0

    def test_parse_no_table(self):
        """测试解析无表格的 HTML. """
        client = THSSectorClient()

        html = "<html><body><p>No table here</p></body></html>"
        sectors = client._parse_industry_table(html)

        assert len(sectors) == 0


class TestGetIndustrySectors:
    """获取行业板块测试. """

    def test_get_industry_sectors_success(self):
        """测试成功获取行业板块. """
        client = THSSectorClient()

        mock_html = """
        <table class="bdbox">
            <tr><td>序号</td><td>板块</td><td>涨跌幅(%)</td><td>总成交量</td><td>总成交额</td></tr>
            <tr><td>1</td><td><a href="#">电力</a></td><td>3.73</td><td>19323.70</td><td>1372.36</td></tr>
            <tr><td>2</td><td><a href="#">通信设备</a></td><td>3.75</td><td>2184.76</td><td>1421.51</td></tr>
        </table>
        """.encode("gbk")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_html
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result):
            sectors = client.get_industry_sectors()

        assert len(sectors) == 2
        # 錟涨幅排序（应该是降序）
        assert sectors[0].name == "通信设备"
        assert sectors[0].change_pct == 3.75

    def test_get_industry_sectors_with_limit(self):
        """测试获取行业板块时应用 limit. """
        client = THSSectorClient()

        mock_html = """
        <table class="bdbox">
            <tr><td>序号</td><td>板块</td><td>涨跌幅(%)</td><td>总成交量</td><td>总成交额</td></tr>
            <tr><td>1</td><td><a href="#">电力</a></td><td>3.73</td><td>100</td><td>100</td></tr>
            <tr><td>2</td><td><a href="#">通信</a></td><td>2.50</td><td>100</td><td>100</td></tr>
            <tr><td>3</td><td><a href="#">计算机</a></td><td>1.80</td><td>100</td><td>100</td></tr>
        </table>
        """.encode("gbk")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_html
        mock_result.stderr = b""

        with patch("subprocess.run", return_value=mock_result):
            sectors = client.get_industry_sectors(limit=2)

        assert len(sectors) == 2

    def test_get_industry_sectors_failure(self):
        """测试获取行业板块失败. """
        client = THSSectorClient()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = b"error"

        with patch("subprocess.run", return_value=mock_result):
            sectors = client.get_industry_sectors()

        assert len(sectors) == 0


class TestGetConceptSectors:
    """获取概念板块测试. """

    def test_get_concept_sectors_returns_empty(self):
        """测试概念板块返回空列表（暂不支持）. """
        client = THSSectorClient()

        # 概念板块暂不支持
        sectors = client.get_concept_sectors()

        assert len(sectors) == 0


class TestCaching:
    """缓存测试. """

    def test_cache_validity(self):
        """测试缓存有效性检查. """
        import time

        client = THSSectorClient()

        # 初始状态，缓存无效
        assert not client._is_cache_valid("test_key")

        # 设置缓存时间
        client._cache_time["test_key"] = time.time()
        assert client._is_cache_valid("test_key")

        # 设置过期缓存（6 分钟前）
        client._cache_time["test_key"] = time.time() - 360
        assert not client._is_cache_valid("test_key")

    def test_cache_clear(self):
        """测试清除缓存. """
        client = THSSectorClient()
        client._cache = {"test": "data"}
        client._cache_time = {"test": 12345.0}

        client.clear_cache()

        assert client._cache == {}
        assert client._cache_time == {}
