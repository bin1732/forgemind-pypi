# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`email.message` 模块的真实行为验证。

覆盖模块:email.message / email.utils(标准库)

说明:`email.message.Message` 的头遍历接口是 `keys()` / `items()` / `raw_items()`,
CPython 的 `email.message` 里并不存在 `iter_headers` 这个方法,本文件按真实接口断言。

真实测试项(共 18 个):
   1. `set_content` 把正文设为 text/plain 并带上 utf-8 字符集
   2. `add_header` 追加同名的第二个头
   3. `get_all` 返回同名头的全部取值
   4. `get` 返回第一个取值,头不存在时返回 None
   5. `keys` / `items` 按写入顺序列出全部头
   6. `replace_header` 覆盖同名头的取值
   7. `del msg[...]` 把头从消息里删掉
   8. `as_string` 输出真实的头与正文文本
   9. `as_bytes` 输出与 `as_string` 同内容的 bytes
  10. `as_string` 与 `as_bytes` 对非 ASCII 正文选用不同的传输编码
  11. `To` 头里带多个收件人时取值原样保留
  12. `email.utils.getaddresses` 把多收件人头拆成地址对
  13. `add_attachment` 把消息变成 multipart/mixed
  14. 附件的 `get_payload(decode=True)` 还原出原始字节
  15. `iter_attachments` 列出附件文件名
  16. `walk` 依次走到根节点与各个子部分
  17. `add_alternative` 把消息变成 multipart/alternative
  18. `email.utils.getaddresses(strict=True)` 拒绝畸形地址(3.13+)

所有断言都针对真实构造出的邮件对象,不替换任何标准库对象。
"""

import email.utils
from email.message import EmailMessage

import pytest

_STRICT_PARSING = getattr(email.utils, "supports_strict_parsing", False)


class TestEmailMessageHeaders:
    """`EmailMessage` 的头读写。"""

    def test_set_content_sets_text_plain_type_and_body(self):
        """`set_content` 让正文类型为 text/plain,字符集为 utf-8,正文带结尾换行。"""
        message = EmailMessage()
        message.set_content("body text")
        assert message.get_content_type() == "text/plain"
        assert message.get_content_charset() == "utf-8"
        assert message["Content-Transfer-Encoding"] == "7bit"
        assert message.get_content() == "body text\n"

    def test_add_header_appends_second_value(self):
        """`add_header` 追加同名头,原来的取值仍留在第一个位置。"""
        message = EmailMessage()
        message.add_header("X-Multi", "one")
        message.add_header("X-Multi", "two")
        assert message.get_all("X-Multi") == ["one", "two"]
        assert message.get("X-Multi") == "one"

    def test_get_all_returns_every_duplicate_value(self):
        """`get_all` 返回同名头的全部取值,头不存在时返回 None。"""
        message = EmailMessage()
        message["X-Trace"] = "t-1"
        message.add_header("X-Trace", "t-2")
        assert message.get_all("X-Trace") == ["t-1", "t-2"]
        assert message.get_all("X-Absent") is None

    def test_get_returns_value_and_none_for_absent_header(self):
        """`get` 给出首个取值,不存在的头给出 None。"""
        message = EmailMessage()
        message["Subject"] = "hello"
        assert message.get("Subject") == "hello"
        assert message.get("X-Absent") is None

    def test_keys_and_items_preserve_header_order(self):
        """`keys` / `items` 按写入顺序列出全部头,同名头各占一项。"""
        message = EmailMessage()
        message["To"] = "a@example.com"
        message["Subject"] = "hello"
        message.add_header("X-Multi", "one")
        message.add_header("X-Multi", "two")
        assert message.keys() == ["To", "Subject", "X-Multi", "X-Multi"]
        assert message.items()[:4] == [
            ("To", "a@example.com"),
            ("Subject", "hello"),
            ("X-Multi", "one"),
            ("X-Multi", "two"),
        ]

    def test_replace_header_overwrites_existing_value(self):
        """`replace_header` 覆盖同名头的取值,头数量不变。"""
        message = EmailMessage()
        message["Subject"] = "old"
        message.replace_header("Subject", "new")
        assert message.get("Subject") == "new"
        assert message.keys().count("Subject") == 1

    def test_del_header_removes_the_header(self):
        """`del msg["X-Name"]` 把头从消息里删掉,再取值为 None。"""
        message = EmailMessage()
        message["Subject"] = "hello"
        message["X-Trace"] = "t-1"
        del message["X-Trace"]
        assert message.get("X-Trace") is None
        assert "X-Trace" not in message.keys()
        assert message.get("Subject") == "hello"


class TestEmailMessageSerialization:
    """`EmailMessage` 的序列化输出。"""

    def test_as_string_contains_headers_and_body(self):
        """`as_string` 输出真实的头、空行分隔与正文。"""
        message = EmailMessage()
        message["To"] = "a@example.com"
        message["Subject"] = "hello"
        message.set_content("body text")
        rendered = message.as_string()
        assert rendered == (
            "To: a@example.com\n"
            "Subject: hello\n"
            'Content-Type: text/plain; charset="utf-8"\n'
            "Content-Transfer-Encoding: 7bit\n"
            "MIME-Version: 1.0\n"
            "\n"
            "body text\n"
        )

    def test_as_bytes_returns_bytes_with_same_headers(self):
        """`as_bytes` 给出 bytes,头的内容与 `as_string` 一致。"""
        message = EmailMessage()
        message["To"] = "a@example.com"
        message.set_content("body text")
        rendered_bytes = message.as_bytes()
        assert isinstance(rendered_bytes, bytes)
        assert rendered_bytes.startswith(b"To: a@example.com\n")
        assert rendered_bytes.endswith(b"body text\n")
        assert b"Content-Type: text/plain; charset=\"utf-8\"" in rendered_bytes

    def test_as_string_and_as_bytes_use_different_transfer_encoding(self):
        """同一封非 ASCII 邮件,`as_string` 走 base64,`as_bytes` 走 8bit。"""
        message = EmailMessage()
        message.set_content("正文内容")
        assert "Content-Transfer-Encoding: base64\n" in message.as_string()
        assert b"Content-Transfer-Encoding: 8bit\n" in message.as_bytes()
        assert message.as_bytes().endswith("正文内容\n".encode())


class TestEmailMessageRecipients:
    """多收件人头的写法与解析。"""

    def test_to_header_carries_multiple_recipients(self):
        """`To` 头里写多个地址时,取值原样保留,不被拆开。"""
        message = EmailMessage()
        message["To"] = "a@example.com, b@example.com"
        message["Cc"] = "c@example.com"
        assert message["To"] == "a@example.com, b@example.com"
        assert message["Cc"] == "c@example.com"
        assert message.get_all("To") == ["a@example.com, b@example.com"]

    def test_getaddresses_parses_multiple_recipients(self):
        """`getaddresses` 把多收件人头拆成一组 (显示名, 地址) 二元组。"""
        message = EmailMessage()
        message["To"] = "a@example.com, b@example.com"
        message["Cc"] = "运维 <c@example.com>"
        assert email.utils.getaddresses([message["To"]]) == [
            ("", "a@example.com"),
            ("", "b@example.com"),
        ]
        assert email.utils.getaddresses([message["Cc"]]) == [("运维", "c@example.com")]


class TestEmailMessageAttachments:
    """附件与多部分结构。"""

    def test_add_attachment_turns_message_into_multipart_mixed(self):
        """`add_attachment` 把消息变成 multipart/mixed,并多出一个子部分。"""
        message = EmailMessage()
        message.set_content("hi")
        assert message.get_content_type() == "text/plain"
        message.add_attachment(
            b"\x00\x01binary",
            maintype="application",
            subtype="octet-stream",
            filename="a.bin",
        )
        assert message.get_content_type() == "multipart/mixed"
        assert message.is_multipart() is True
        assert len(message.get_payload()) == 2
        assert message.get_payload(0).get_content_type() == "text/plain"

    def test_attachment_payload_decodes_to_original_bytes(self):
        """附件的 `get_payload(decode=True)` 还原出与原始内容一致的字节。"""
        message = EmailMessage()
        message.set_content("hi")
        message.add_attachment(
            b"\x00\x01binary",
            maintype="application",
            subtype="octet-stream",
            filename="a.bin",
        )
        attachment = message.get_payload(1)
        assert attachment["Content-Transfer-Encoding"] == "base64"
        assert attachment.get_payload(decode=True) == b"\x00\x01binary"
        assert attachment.get_content_disposition() == "attachment"

    def test_iter_attachments_reports_filenames(self):
        """`iter_attachments` 列出每个附件的文件名。"""
        message = EmailMessage()
        message.set_content("hi")
        message.add_attachment(
            b"\x00\x01",
            maintype="application",
            subtype="octet-stream",
            filename="a.bin",
        )
        message.add_attachment(
            b"\x02\x03",
            maintype="application",
            subtype="octet-stream",
            filename="b.bin",
        )
        assert [part.get_filename() for part in message.iter_attachments()] == ["a.bin", "b.bin"]

    def test_walk_visits_root_and_all_parts(self):
        """`walk` 依次给出根节点与每个子部分。"""
        message = EmailMessage()
        message.set_content("hi")
        message.add_attachment(
            b"\x00\x01binary",
            maintype="application",
            subtype="octet-stream",
            filename="a.bin",
        )
        assert [part.get_content_type() for part in message.walk()] == [
            "multipart/mixed",
            "text/plain",
            "application/octet-stream",
        ]

    def test_add_alternative_creates_multipart_alternative(self):
        """`add_alternative` 把消息变成 multipart/alternative,同时含纯文本与 HTML。"""
        message = EmailMessage()
        message.set_content("plain body")
        assert message.get_content_type() == "text/plain"
        message.add_alternative("<p>html body</p>", subtype="html")
        assert message.get_content_type() == "multipart/alternative"
        assert [part.get_content_type() for part in message.walk()] == [
            "multipart/alternative",
            "text/plain",
            "text/html",
        ]


@pytest.mark.skipif(
    not _STRICT_PARSING,
    reason="email.utils 的 strict 解析参数需要 Python 3.13+",
)
def test_getaddresses_strict_rejects_malformed_input():
    """`getaddresses(strict=True)` 对畸形地址给出 ('', ''),`strict=False` 保留旧解析结果。"""
    malformed = ["alice@example.com <bob@example.com>"]
    assert email.utils.getaddresses(malformed) == [("", "")]
    assert email.utils.getaddresses(malformed, strict=False) == [
        ("", "alice@example.com"),
        ("", "bob@example.com"),
    ]
    assert email.utils.parseaddr("alice@example.com <bob@example.com>") == ("", "")
    assert email.utils.parseaddr("Name <c@z.com>") == ("Name", "c@z.com")
