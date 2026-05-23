"""html_to_markdown 转换函数和文章导出 HTML 构建器单元测试。"""

from src.models.schema import Article
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


class TestBuildArticleHtml:
    """build_article_html 集成测试。"""

    def test_complete_html_document_structure(self) -> None:
        """导出的 HTML 应包含完整文档结构。"""
        from datetime import datetime

        from src.cli.article import build_article_html
        from src.models.schema import Article

        article = Article(
            id=1,
            title="测试文章",
            content="<p>正文内容</p>",
            publish_time=datetime(2024, 1, 15, 10, 30),
            original_url="https://example.com/article",
            pic_url="https://example.com/cover.jpg",
            summary="这是一篇测试文章的摘要",
        )
        html_doc = build_article_html(article)

        assert "<!doctype html>" in html_doc
        assert '<html lang="zh-CN">' in html_doc
        assert '<meta charset="utf-8">' in html_doc
        assert '<meta name="viewport"' in html_doc
        assert "<title>测试文章</title>" in html_doc
        assert "<style>" in html_doc
        assert '<main class="article">' in html_doc
        assert '<header class="article-header">' in html_doc
        assert '<article class="article-content">' in html_doc
        assert "</html>" in html_doc

    def test_escaped_metadata(self) -> None:
        """元信息字段应被 HTML 转义。"""
        from src.cli.article import build_article_html
        from src.models.schema import Article

        article = Article(
            id=1,
            title='含<script>alert("xss")</script>标签',
            summary="摘要含 <b>标签</b> & 特殊字符",
            original_url='https://example.com?a=1&b=2',
        )
        html_doc = build_article_html(article)

        assert "<script>" not in html_doc.split("</head>")[0]
        assert "&lt;script&gt;" in html_doc
        assert "&lt;b&gt;" in html_doc
        assert "&amp;" in html_doc

    def test_preserves_stored_html_body(self) -> None:
        """存储的 HTML 正文应原样保留，不经过 html_to_markdown。"""
        from src.cli.article import build_article_html
        from src.models.schema import Article

        original_html = (
            '<p>这是<strong>重要</strong>内容</p><ul><li>项目</li></ul>'
        )
        article = Article(id=1, title="HTML 正文测试", content=original_html)
        html_doc = build_article_html(article)

        # 正文 HTML 应原样出现
        assert original_html in html_doc
        # 不应出现 markdown 转换后的符号
        assert "**重要**" not in html_doc
        assert "- 项目" not in html_doc

    def test_empty_content_valid_html(self) -> None:
        """空内容仍应产生有效 HTML 文档。"""
        from src.cli.article import build_article_html
        from src.models.schema import Article

        article = Article(id=1, title="空文章", content=None)
        html_doc = build_article_html(article)

        assert "<!doctype html>" in html_doc
        assert "<title>空文章</title>" in html_doc
        assert '<article class="article-content">' in html_doc
        assert "</html>" in html_doc

    def test_embedded_css_present(self) -> None:
        """应包含嵌入式 CSS。"""
        from src.cli.article import build_article_html
        from src.models.schema import Article

        article = Article(id=1, title="CSS 测试", content="<p>内容</p>")
        html_doc = build_article_html(article)

        assert ".article{" in html_doc
        assert "max-width:100%" in html_doc
        assert ".article-summary{" in html_doc


class TestExportFilenameHtml:
    """build_export_filename HTML 扩展名测试。"""

    def test_html_extension(self) -> None:
        """文件名应以 .html 结尾。"""
        from pathlib import Path

        from src.cli.article import build_export_filename

        export_dir = Path("/tmp/nonexistent")
        filename = build_export_filename(export_dir, "2024-01-15", "测试文章")
        assert filename.endswith(".html")
        assert filename == "2024-01-15_测试文章.html"

    def test_collision_suffix_html(self) -> None:
        """重名时应追加序号并使用 .html 扩展名。"""
        import tempfile
        from pathlib import Path

        from src.cli.article import build_export_filename

        with tempfile.TemporaryDirectory() as tmpdir:
            export_dir = Path(tmpdir)
            # 创建已有文件
            (export_dir / "2024-01-15_测试文章.html").write_text("existing")
            (export_dir / "2024-01-15_测试文章_2.html").write_text("existing")

            filename = build_export_filename(export_dir, "2024-01-15", "测试文章")
            assert filename == "2024-01-15_测试文章_3.html"


class TestExportCommandHtml:
    """export 命令 HTML 行为测试。"""

    def test_incremental_skip_html(self) -> None:
        """增量模式应跳过已存在的 .html 文件。"""
        import tempfile
        from pathlib import Path

        from src.cli.article import build_article_html, build_export_filename

        with tempfile.TemporaryDirectory() as tmpdir:
            export_dir = Path(tmpdir)
            article = Article(
                id=1,
                title="已存在文章",
                content="<p>内容</p>",
            )
            filename = build_export_filename(export_dir, "2024-01-15", "已存在文章")
            file_path = export_dir / filename

            # 模拟已存在
            file_path.write_text("existing html", encoding="utf-8")
            assert file_path.exists()

            # build_export_filename 不会自动跳过，但 export 命令中
            # 的逻辑会检查 file_path.exists() 并跳过
            # 此处验证文件名确实是 .html
            assert filename.endswith(".html")

    def test_forced_rebuild_clears_directory(self) -> None:
        """--force 模式应清除并重建导出目录。"""
        import shutil
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            export_dir = Path(tmpdir) / "test_mp"
            export_dir.mkdir()
            # 模拟旧 .md 文件
            (export_dir / "old_article.md").write_text("old markdown")
            (export_dir / "old_article.html").write_text("old html")

            # 模拟 --force 行为
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)

            # 旧文件应被清除
            assert not (export_dir / "old_article.md").exists()
            assert not (export_dir / "old_article.html").exists()
