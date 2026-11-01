# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""gettext 方向的底层真实行为测试:MO 目录解析、复数形式、上下文、install 与 find。

覆盖模块:gettext(标准库,GNU gettext 消息目录的 Python 封装)。

真实测试项(共 18 个):
  1. NullTranslations.gettext 原样返回消息
  2. NullTranslations.ngettext 按 n 选择单数或复数形式
  3. NullTranslations.info 为空字典,charset() 为 None
  4. GNUTranslations 从真实 .mo 文件读出目录条目
  5. GNUTranslations 对目录里没有的消息原样返回
  6. GNUTranslations.ngettext 依据 Plural-Forms 表达式选形
  7. GNUTranslations.info 报出目录头部的元数据
  8. GNUTranslations.charset 来自 Content-Type 头
  9. GNUTranslations.pgettext 只在上下文匹配时命中
 10. GNUTranslations.npgettext 组合上下文与复数形式
 11. GNUTranslations.add_fallback 把缺失消息交给后备目录
 12. GNUTranslations 对魔数错误的 .mo 文件抛 OSError
 13. translation 按 localedir 目录布局加载真实目录文件
 14. translation 找不到目录文件时抛 FileNotFoundError,fallback=True 时给空实现
 15. find 返回命中语言对应的 .mo 路径,未命中返回 None
 16. find(all=True) 列出全部命中的 .mo 路径,未命中返回空列表
 17. install 把真实翻译注册进 builtins
 18. textdomain 与 bindtextdomain 把查找路由到绑定的目录

用例里的 .mo 文件都由 _build_mo_bytes 按 GNU MO 二进制格式真实写出,
全部由真实二进制文件与真实查找路径产生;find 与 install 读的都是磁盘上的目录文件。
"""

import builtins
import gettext
import os
import struct

import pytest

# 测试用域名,系统里不存在同名目录文件,避免命中宿主环境的其它目录。
DOMAIN = "forgemind-unittest"

# GNU MO 文件的小端魔数与版本号。
MO_MAGIC_LE = 0x950412DE
MO_REVISION = 0

# 目录头部元数据:Content-Type 决定解码用的字符集,Plural-Forms 决定复数选择。
CATALOG_METADATA = (
    "Content-Type: text/plain; charset=UTF-8\n"
    "Plural-Forms: nplurals=2; plural=(n != 1);\n"
    "Project-Id-Version: forgemind 2026.9.3\n"
)

# 目录条目:msgid -> msgstr。带 \x04 的 msgid 表示带上下文的条目,
# 复数条目的 msgid/msgstr 用 \x00 分隔单数与复数两种形式。
CATALOG_ENTRIES = {
    "Hello": "你好",
    "Price": "价格",
    "Open": "打开",
    "menu\x04Open": "菜单打开",
    "file\x00files": "单个文件\x00多个文件",
    "menu\x04file\x00files": "菜单单个\x00菜单多个",
}


def _build_mo_bytes(entries: dict, metadata: str, charset: str = "UTF-8") -> bytes:
    """把消息条目与元数据写成真正的 GNU MO 二进制文件内容。

    MO 布局:7 个 32 位头字段,随后是原始串表与翻译串表(每项为长度加偏移),
    最后是两个串表的数据区,每个串以 NUL 结尾。
    """
    pairs = [(b"", metadata.encode(charset))]
    for msgid in sorted(entries):
        pairs.append((msgid.encode(charset), entries[msgid].encode(charset)))

    count = len(pairs)
    header_size = 7 * 4
    originals_table_offset = header_size
    translations_table_offset = originals_table_offset + 8 * count
    data_offset = translations_table_offset + 8 * count

    originals_data = b""
    originals_entries = []
    for msgid, _ in pairs:
        originals_entries.append((len(msgid), data_offset + len(originals_data)))
        originals_data += msgid + b"\x00"

    translations_data = b""
    translations_entries = []
    for _, msgstr in pairs:
        offset = data_offset + len(originals_data) + len(translations_data)
        translations_entries.append((len(msgstr), offset))
        translations_data += msgstr + b"\x00"

    blob = bytearray()
    blob += struct.pack(
        "<7I",
        MO_MAGIC_LE,
        MO_REVISION,
        count,
        originals_table_offset,
        translations_table_offset,
        0,
        data_offset,
    )
    for length, offset in originals_entries:
        blob += struct.pack("<2I", length, offset)
    for length, offset in translations_entries:
        blob += struct.pack("<2I", length, offset)
    blob += originals_data + translations_data
    return bytes(blob)


@pytest.fixture
def mo_bytes() -> bytes:
    """测试用 .mo 文件的真实二进制内容。"""
    return _build_mo_bytes(CATALOG_ENTRIES, CATALOG_METADATA)


@pytest.fixture
def localedir(tmp_path, mo_bytes):
    """按 GNU 目录布局摆出 en_US 与 en 两个语言目录,返回根路径。"""
    root = tmp_path / "locale"
    for language in ("en_US", "en"):
        target = root / language / "LC_MESSAGES"
        target.mkdir(parents=True)
        (target / f"{DOMAIN}.mo").write_bytes(mo_bytes)
    return root


@pytest.fixture
def language_env():
    """把 LANGUAGE 指向 en_US,让 gettext.find 走真实的环境变量解析路径。"""
    previous = os.environ.get("LANGUAGE")
    os.environ["LANGUAGE"] = "en_US"
    yield
    if previous is None:
        os.environ.pop("LANGUAGE", None)
    else:
        os.environ["LANGUAGE"] = previous


@pytest.fixture(autouse=True)
def _restore_gettext_globals():
    """把 builtins 里的翻译函数、textdomain 与目录绑定恢复到用例前的状态。"""
    builtin_names = ("_", "gettext", "ngettext", "npgettext", "pgettext")
    saved_builtins = {
        name: builtins.__dict__[name] for name in builtin_names if name in builtins.__dict__
    }
    saved_domain = gettext.textdomain()
    saved_localedirs = dict(gettext._localedirs)
    yield
    for name in builtin_names:
        builtins.__dict__.pop(name, None)
    builtins.__dict__.update(saved_builtins)
    gettext.textdomain(saved_domain)
    gettext._localedirs.clear()
    gettext._localedirs.update(saved_localedirs)


class TestNullTranslations:
    """空实现的行为。"""

    def test_null_translations_gettext_returns_msgid_unchanged(self):
        """NullTranslations.gettext 原样返回消息,不做任何替换。"""
        translations = gettext.NullTranslations()
        assert translations.gettext("Hello") == "Hello"
        assert translations.gettext("") == ""
        assert translations.gettext("Price") == "Price"

    def test_null_translations_ngettext_selects_singular_or_plural(self):
        """NullTranslations.ngettext 在 n 等于 1 时给单数形式,其余给复数形式。"""
        translations = gettext.NullTranslations()
        assert translations.ngettext("file", "files", 1) == "file"
        assert translations.ngettext("file", "files", 2) == "files"
        assert translations.ngettext("file", "files", 0) == "files"

    def test_null_translations_info_is_empty_and_charset_is_none(self):
        """NullTranslations.info 返回空字典,charset() 返回 None。"""
        translations = gettext.NullTranslations()
        assert translations.info() == {}
        assert translations.charset() is None


class TestGNUTranslations:
    """真实 .mo 文件的读取与查表。"""

    def test_gnu_translations_reads_catalog_entries_from_mo_file(self, tmp_path, mo_bytes):
        """GNUTranslations 从真实 .mo 文件读出目录条目并完成翻译。"""
        mofile = tmp_path / "catalog.mo"
        mofile.write_bytes(mo_bytes)
        with open(mofile, "rb") as handle:
            translations = gettext.GNUTranslations(handle)
        assert isinstance(translations, gettext.GNUTranslations)
        assert translations.gettext("Hello") == "你好"
        assert translations.gettext("Price") == "价格"

    def test_gnu_translations_missing_msgid_returns_original_text(self, tmp_path, mo_bytes):
        """目录里没有的消息原样返回,不做空串填充。"""
        mofile = tmp_path / "catalog.mo"
        mofile.write_bytes(mo_bytes)
        with open(mofile, "rb") as handle:
            translations = gettext.GNUTranslations(handle)
        assert translations.gettext("NotInCatalog") == "NotInCatalog"

    def test_gnu_translations_ngettext_uses_plural_forms_expression(self, tmp_path, mo_bytes):
        """ngettext 依据 Plural-Forms 的 (n != 1) 表达式在两种形式间切换。"""
        mofile = tmp_path / "catalog.mo"
        mofile.write_bytes(mo_bytes)
        with open(mofile, "rb") as handle:
            translations = gettext.GNUTranslations(handle)
        assert translations.ngettext("file", "files", 1) == "单个文件"
        assert translations.ngettext("file", "files", 2) == "多个文件"
        assert translations.ngettext("file", "files", 5) == "多个文件"
        assert translations.plural(1) == 0
        assert translations.plural(2) == 1

    def test_gnu_translations_info_reports_catalog_metadata(self, tmp_path, mo_bytes):
        """info 报出目录头部解析出的元数据键值。"""
        mofile = tmp_path / "catalog.mo"
        mofile.write_bytes(mo_bytes)
        with open(mofile, "rb") as handle:
            translations = gettext.GNUTranslations(handle)
        info = translations.info()
        assert info["content-type"] == "text/plain; charset=UTF-8"
        assert info["plural-forms"] == "nplurals=2; plural=(n != 1);"
        assert info["project-id-version"] == "forgemind 2026.9.3"

    def test_gnu_translations_charset_comes_from_content_type(self, tmp_path, mo_bytes):
        """charset() 取自 Content-Type 头里的 charset 参数。"""
        mofile = tmp_path / "catalog.mo"
        mofile.write_bytes(mo_bytes)
        with open(mofile, "rb") as handle:
            translations = gettext.GNUTranslations(handle)
        assert translations.charset() == "UTF-8"

    def test_gnu_translations_pgettext_requires_matching_context(self, tmp_path, mo_bytes):
        """pgettext 只有上下文一致才命中,上下文不同则返回原文。"""
        mofile = tmp_path / "catalog.mo"
        mofile.write_bytes(mo_bytes)
        with open(mofile, "rb") as handle:
            translations = gettext.GNUTranslations(handle)
        assert translations.pgettext("menu", "Open") == "菜单打开"
        assert translations.pgettext("other", "Open") == "Open"

    def test_gnu_translations_npgettext_combines_context_and_plural(self, tmp_path, mo_bytes):
        """npgettext 把上下文与复数形式组合起来查表。"""
        mofile = tmp_path / "catalog.mo"
        mofile.write_bytes(mo_bytes)
        with open(mofile, "rb") as handle:
            translations = gettext.GNUTranslations(handle)
        assert translations.npgettext("menu", "file", "files", 1) == "菜单单个"
        assert translations.npgettext("menu", "file", "files", 3) == "菜单多个"
        assert translations.npgettext("other", "file", "files", 3) == "files"

    def test_gnu_translations_add_fallback_resolves_missing_msgid(self, tmp_path, mo_bytes):
        """add_fallback 之后,主目录缺的消息由后备目录给出。"""
        primary_file = tmp_path / "primary.mo"
        primary_file.write_bytes(_build_mo_bytes({"Hello": "你好"}, CATALOG_METADATA))
        fallback_file = tmp_path / "fallback.mo"
        fallback_file.write_bytes(_build_mo_bytes({"Bonus": "奖金"}, CATALOG_METADATA))
        with open(primary_file, "rb") as handle:
            primary = gettext.GNUTranslations(handle)
        with open(fallback_file, "rb") as handle:
            fallback = gettext.GNUTranslations(handle)
        primary.add_fallback(fallback)
        assert primary.gettext("Hello") == "你好"
        assert primary.gettext("Bonus") == "奖金"
        assert primary.gettext("MissingEverywhere") == "MissingEverywhere"

    def test_gnu_translations_rejects_mo_file_with_bad_magic_number(self, tmp_path):
        """魔数不是 MO_MAGIC 的文件让 GNUTranslations 抛 OSError。"""
        broken = tmp_path / "broken.mo"
        broken.write_bytes(b"THIS IS NOT A MO FILE")
        with open(broken, "rb") as handle:
            with pytest.raises(OSError, match="Bad magic number"):
                gettext.GNUTranslations(handle)


class TestGettextLookup:
    """translation / find 的真实查找路径。"""

    def test_translation_loads_catalog_from_localedir_layout(self, localedir):
        """translation 按 localedir/<语言>/LC_MESSAGES/<域名>.mo 的布局加载目录。"""
        translations = gettext.translation(
            DOMAIN,
            localedir=str(localedir),
            languages=["en_US"],
        )
        assert isinstance(translations, gettext.GNUTranslations)
        assert translations.gettext("Hello") == "你好"

    def test_translation_missing_catalog_raises_or_falls_back(self, tmp_path):
        """找不到目录文件时抛 FileNotFoundError,fallback=True 时给空实现。"""
        with pytest.raises(FileNotFoundError, match="No translation file found for domain"):
            gettext.translation(
                DOMAIN,
                localedir=str(tmp_path),
                languages=["en_US"],
            )
        fallback = gettext.translation(
            DOMAIN,
            localedir=str(tmp_path),
            languages=["en_US"],
            fallback=True,
        )
        assert isinstance(fallback, gettext.NullTranslations)
        assert fallback.gettext("Hello") == "Hello"

    def test_find_returns_mo_path_for_matching_language(self, localedir):
        """find 返回命中语言对应的 .mo 路径,语言没有目录文件时返回 None。"""
        found = gettext.find(DOMAIN, localedir=str(localedir), languages=["en_US"])
        assert found == os.path.join(str(localedir), "en_US", "LC_MESSAGES", f"{DOMAIN}.mo")
        assert gettext.find(DOMAIN, localedir=str(localedir), languages=["de_DE"]) is None

    def test_find_all_lists_every_matching_catalog(self, localedir):
        """find(all=True) 列出全部命中的 .mo 路径,没有命中时给空列表。"""
        found_all = gettext.find(DOMAIN, localedir=str(localedir), languages=["en_US", "en"], all=True)
        assert found_all == [
            os.path.join(str(localedir), "en_US", "LC_MESSAGES", f"{DOMAIN}.mo"),
            os.path.join(str(localedir), "en", "LC_MESSAGES", f"{DOMAIN}.mo"),
        ]
        assert gettext.find(DOMAIN, localedir=str(localedir), languages=["de_DE"], all=True) == []


class TestGettextInstall:
    """install 与域名绑定。"""

    def test_install_registers_translation_in_builtins(self, localedir, language_env):
        """install 把真实翻译注册进 builtins,取用时命中目录里的译文。"""
        gettext.install(DOMAIN, localedir=str(localedir))
        translate = builtins.__dict__["_"]
        assert translate("Hello") == "你好"
        assert translate("NotInCatalog") == "NotInCatalog"

    def test_textdomain_and_bindtextdomain_route_lookups(self, localedir, language_env):
        """textdomain 决定当前域名,bindtextdomain 决定该域名的目录位置。"""
        gettext.bindtextdomain(DOMAIN, str(localedir))
        assert gettext.bindtextdomain(DOMAIN) == str(localedir)
        gettext.textdomain(DOMAIN)
        assert gettext.textdomain() == DOMAIN
        assert gettext.gettext("Hello") == "你好"
        assert gettext.dgettext(DOMAIN, "Price") == "价格"
        assert gettext.ngettext("file", "files", 2) == "多个文件"
        assert gettext.dngettext(DOMAIN, "file", "files", 1) == "单个文件"
