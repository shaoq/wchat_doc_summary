"""html_to_markdown 转换函数单元测试。"""

from src.utils.html_converter import html_to_markdown


class TestHtmlToMarkdown:
    """HTML → Markdown 核心转换测试。"""

    def test_paragraph(self) -> None:
        html = "<p>第一段</p><p>第二段</p>"
        md = html_to_markdown(html)
        assert "第一段" in md
        assert "第二段" in md
        assert "<p>" not in md

    def test_headings(self) -> None:
        html = "<h1>大标题</h1><h2>二级</h2><h3>三级</h3>"
        md = html_to_markdown(html)
        assert "# 大标题" in md
        assert "## 二级" in md
        assert "### 三级" in md

    def test_inline_format(self) -> None:
        html = "<strong>加粗</strong><em>斜体</em><code>代码</code>"
        md = html_to_markdown(html)
        assert "**加粗**" in md
        assert "*斜体*" in md
        assert "`代码`" in md

    def test_image(self) -> None:
        html = '<img src="https://example.com/a.jpg" alt="图片">'
        md = html_to_markdown(html)
        assert "![图片](https://example.com/a.jpg)" in md

    def test_link(self) -> None:
        html = '<a href="https://example.com">链接文字</a>'
        md = html_to_markdown(html)
        assert "[链接文字](https://example.com)" in md

    def test_unordered_list(self) -> None:
        html = "<ul><li>项目一</li><li>项目二</li></ul>"
        md = html_to_markdown(html)
        assert "- 项目一" in md
        assert "- 项目二" in md

    def test_ordered_list(self) -> None:
        html = "<ol><li>步骤一</li><li>步骤二</li></ol>"
        md = html_to_markdown(html)
        assert "1." in md
        assert "步骤一" in md
        assert "步骤二" in md

    def test_blockquote(self) -> None:
        html = "<blockquote>引用内容</blockquote>"
        md = html_to_markdown(html)
        assert ">" in md
        assert "引用内容" in md

    def test_empty_input(self) -> None:
        assert html_to_markdown("") == ""
        assert html_to_markdown("   ") == ""
        assert html_to_markdown(None) == ""  # type: ignore[arg-type]

    def test_strip_section_tags(self) -> None:
        html = "<section><section>嵌套内容</section></section>"
        md = html_to_markdown(html)
        assert "<section>" not in md
        assert "嵌套内容" in md

    def test_strip_span_tags(self) -> None:
        html = "<span>文本</span>"
        md = html_to_markdown(html)
        assert "<span>" not in md
        assert "文本" in md

    def test_br_to_newline(self) -> None:
        html = "第一行<br>第二行"
        md = html_to_markdown(html)
        assert "第一行" in md
        assert "第二行" in md

    def test_compress_blank_lines(self) -> None:
        html = "<p>A</p><p></p><p></p><p></p><p>B</p>"
        md = html_to_markdown(html)
        assert "\n\n\n" not in md  # 不应出现连续 3 个换行

    def test_wechat_style_article(self) -> None:
        """模拟微信公众号文章典型结构。"""
        html = """
        <section style="padding: 10px;">
            <h2>文章标题</h2>
            <section>
                <p>这是<strong>加粗</strong>的文字</p>
                <p><img src="https://mmbiz.qpic.cn/test.jpg" alt="图片"></p>
                <ul><li>列表项</li></ul>
            </section>
        </section>
        """
        md = html_to_markdown(html)
        assert "## 文章标题" in md
        assert "**加粗**" in md
        assert "![图片](https://mmbiz.qpic.cn/test.jpg)" in md
        assert "- 列表项" in md
        assert "<section>" not in md
        assert "style=" not in md


class TestBuildArticleMarkdown:
    """build_article_markdown 集成测试。"""

    def test_export_no_html_tags(self) -> None:
        """导出的 markdown 不应包含 HTML 标签。"""
        from src.cli.article import build_article_markdown
        from src.models.schema import Article

        article = Article(
            id=1,
            title="测试文章",
            content="<p>这是<strong>重要</strong>内容</p><ul><li>项目</li></ul>",
        )
        md = build_article_markdown(article)
        assert "<p>" not in md
        assert "<strong>" not in md
        assert "<ul>" not in md
        assert "重要" in md
        assert "- 项目" in md

    def test_export_empty_content(self) -> None:
        """空内容不应报错。"""
        from src.cli.article import build_article_markdown
        from src.models.schema import Article

        article = Article(id=1, title="空文章", content=None)
        md = build_article_markdown(article)
        assert "# 空文章" in md
        assert md.strip().endswith("空文章")
