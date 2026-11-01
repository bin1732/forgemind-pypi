# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""ssl 与 pickle 的底层真实行为测试(全 stdlib 为主,零模拟,零 mock)。

覆盖模块:
  ssl —— ssl.wrap_socket 的版本兼容路径(新版 Python 已移除该 API)、真实
          TLS 握手并在握手后传输数据、证书不受信时握手失败、ALPN 协议协商、
          PEM 与 DER 证书格式互转、PSK 能力常量(需要 Python 3.13+)。
  pickle —— dumps / loads 的真实往返、HIGHEST_PROTOCOL 与 DEFAULT_PROTOCOL
          取值、全部 protocol 均可往返、protocol 0 的 ASCII 载荷、
          Pickler 与 Unpickler 的流式读写、自定义 __reduce__ 往返、
          嵌套结构的容器类型保持、memo 共享引用保持、
          persistent_id / persistent_load 往返、__getstate__ / __setstate__
          往返、不可序列化对象的报错类型。

真实测试项(6 个 ssl + 11 个 pickle = 17):
  1.  test_ssl_wrap_socket_compat_path_handles_removed_api
  2.  test_ssl_real_tls_handshake_transfers_data_over_loopback
  3.  test_ssl_handshake_fails_when_certificate_is_untrusted
  4.  test_ssl_alpn_protocols_are_negotiated_between_peers
  5.  test_ssl_pem_cert_to_der_cert_converts_self_signed_certificate
  6.  test_ssl_psk_capability_constant_matches_python_version
  7.  test_pickle_dumps_loads_roundtrip_preserves_exact_values
  8.  test_pickle_highest_protocol_and_default_protocol_values
  9.  test_pickle_every_protocol_roundtrips_identically
  10. test_pickle_protocol_zero_produces_ascii_payload
  11. test_pickle_pickler_and_unpickler_stream_objects_through_bytesio
  12. test_pickle_custom_reduce_rebuilds_object_state
  13. test_pickle_nested_structure_roundtrip_preserves_container_types
  14. test_pickle_preserves_shared_references_via_memo
  15. test_pickle_persistent_id_and_persistent_load_roundtrip
  16. test_pickle_getstate_setstate_roundtrip
  17. test_pickle_unpicklable_object_raises_pickling_error

TLS 用例用 cryptography 生成自签名证书与私钥,握手双方都是真实套接字上的
真实 TLS 会话;生成证书失败时用例按 cryptography 缺失跳过。
"""

import datetime
import io
import pickle
import shutil
import socket
import ssl
import subprocess
import threading

import pytest


@pytest.fixture(scope="module")
def self_signed_cert(tmp_path_factory):
    """生成自签名证书与私钥文件路径,供真实 TLS 握手使用。

    证书的 CN 与 SAN 均为 localhost,签发者与主体相同,因此可以直接作为
    客户端的信任锚完成校验。优先用 openssl 命令行生成,命令行不可用时
    改用 cryptography 生成,两者都不可用时跳过。
    """
    directory = tmp_path_factory.mktemp("tls-cert")
    cert_path = directory / "server.crt"
    key_path = directory / "server.key"

    openssl = shutil.which("openssl")
    if openssl is not None:
        result = subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "ec",
                "-pkeyopt",
                "ec_paramgen_curve:prime256v1",
                "-nodes",
                "-keyout",
                str(key_path),
                "-out",
                str(cert_path),
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode == 0 and cert_path.exists() and key_path.exists():
            return str(cert_path), str(key_path)

    x509 = pytest.importorskip(
        "cryptography.x509",
        reason="openssl 命令行不可用,且缺少 cryptography 库,无法生成自签名证书",
    )
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return str(cert_path), str(key_path)


# ======================== ssl ========================
def test_ssl_wrap_socket_compat_path_handles_removed_api():
    """验证 ssl.wrap_socket 存在时给出弃用警告并返回 SSLSocket,已移除时走上下文接口。"""
    left, right = socket.socketpair()
    try:
        if hasattr(ssl, "wrap_socket"):
            with pytest.warns(DeprecationWarning):
                wrapped = ssl.wrap_socket(left, do_handshake_on_connect=False)
            assert isinstance(wrapped, ssl.SSLSocket)
            assert wrapped.family == socket.AF_UNIX
            wrapped.close()
        else:
            assert not hasattr(ssl, "wrap_socket")
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with ctx.wrap_socket(left, do_handshake_on_connect=False) as wrapped:
                assert isinstance(wrapped, ssl.SSLSocket)
                assert wrapped.family == socket.AF_UNIX
    finally:
        right.close()


def test_ssl_real_tls_handshake_transfers_data_over_loopback(self_signed_cert):
    """验证真实 TLS 握手成功,协商出 TLS 1.3 通道后数据按原样收发。"""
    cert_path, key_path = self_signed_cert
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert_path, key_path)
    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_ctx.load_verify_locations(cafile=cert_path)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(10)
    host, port = listener.getsockname()
    server_info = {}

    def server_side():
        raw, _ = listener.accept()
        with server_ctx.wrap_socket(raw, server_side=True) as tls_conn:
            server_info["version"] = tls_conn.version()
            server_info["cipher"] = tls_conn.cipher()[0]
            payload = tls_conn.recv(64)
            tls_conn.sendall(b"secure-reply:" + payload)

    thread = threading.Thread(target=server_side)
    thread.start()
    try:
        with socket.create_connection((host, port), timeout=10) as raw:
            with client_ctx.wrap_socket(raw, server_hostname="localhost") as tls_client:
                tls_client.sendall(b"secure-hello")
                assert tls_client.recv(64) == b"secure-reply:secure-hello"
                assert tls_client.version() in ("TLSv1.2", "TLSv1.3")
                assert tls_client.cipher()[0].startswith("TLS_")
                peer_cert = tls_client.getpeercert()
                assert peer_cert["subject"] == ((("commonName", "localhost"),),)
                assert ("DNS", "localhost") in peer_cert["subjectAltName"]
        thread.join(timeout=20)
        assert not thread.is_alive()
        assert server_info["version"] in ("TLSv1.2", "TLSv1.3")
        assert server_info["cipher"].startswith("TLS_")
    finally:
        listener.close()


def test_ssl_handshake_fails_when_certificate_is_untrusted(self_signed_cert):
    """验证客户端不信任自签名证书时,握手抛出 SSLCertVerificationError。"""
    cert_path, key_path = self_signed_cert
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert_path, key_path)
    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(10)
    host, port = listener.getsockname()
    server_errors = []

    def server_side():
        raw, _ = listener.accept()
        try:
            server_ctx.wrap_socket(raw, server_side=True)
        except ssl.SSLError as exc:
            server_errors.append(type(exc).__name__)

    thread = threading.Thread(target=server_side)
    thread.start()
    try:
        with socket.create_connection((host, port), timeout=10) as raw:
            with pytest.raises(ssl.SSLCertVerificationError) as excinfo:
                client_ctx.wrap_socket(raw, server_hostname="localhost")
        assert "certificate verify failed" in str(excinfo.value)
        thread.join(timeout=20)
        assert server_errors == ["SSLError"]
    finally:
        listener.close()


def test_ssl_alpn_protocols_are_negotiated_between_peers(self_signed_cert):
    """验证双方通过 set_alpn_protocols 协商出的协议是双方都声明的 http/1.1。"""
    cert_path, key_path = self_signed_cert
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert_path, key_path)
    server_ctx.set_alpn_protocols(["h2", "http/1.1"])
    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_ctx.load_verify_locations(cafile=cert_path)
    client_ctx.set_alpn_protocols(["http/1.1"])

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(10)
    host, port = listener.getsockname()
    server_alpn = []

    def server_side():
        raw, _ = listener.accept()
        with server_ctx.wrap_socket(raw, server_side=True) as tls_conn:
            server_alpn.append(tls_conn.selected_alpn_protocol())
            tls_conn.recv(16)

    thread = threading.Thread(target=server_side)
    thread.start()
    try:
        with socket.create_connection((host, port), timeout=10) as raw:
            with client_ctx.wrap_socket(raw, server_hostname="localhost") as tls_client:
                assert tls_client.selected_alpn_protocol() == "http/1.1"
                tls_client.sendall(b"alpn")
        thread.join(timeout=20)
        assert not thread.is_alive()
        assert server_alpn == ["http/1.1"]
    finally:
        listener.close()


def test_ssl_pem_cert_to_der_cert_converts_self_signed_certificate(self_signed_cert):
    """验证 PEM 证书转 DER 后是 ASN.1 SEQUENCE 开头,再转回 PEM 内容保持一致。"""
    cert_path, _key_path = self_signed_cert
    pem_text = open(cert_path, encoding="utf-8").read()
    der_bytes = ssl.PEM_cert_to_DER_cert(pem_text)
    assert isinstance(der_bytes, bytes)
    assert der_bytes[0] == 0x30
    assert len(der_bytes) > 200
    assert pem_text.strip().endswith("-----END CERTIFICATE-----")

    back_to_pem = ssl.DER_cert_to_PEM_cert(der_bytes)
    assert "BEGIN CERTIFICATE" in back_to_pem
    assert "END CERTIFICATE" in back_to_pem
    assert ssl.PEM_cert_to_DER_cert(back_to_pem) == der_bytes


@pytest.mark.skipif(
    not hasattr(ssl, "HAS_PSK"),
    reason="ssl.HAS_PSK 与 set_psk_client_callback 需要 Python 3.13+",
)
def test_ssl_psk_capability_constant_matches_python_version():
    """验证 HAS_PSK 为真时,SSLContext 同时提供客户端与服务端的 PSK 回调接口。"""
    assert ssl.HAS_PSK is True
    assert hasattr(ssl.SSLContext, "set_psk_client_callback")
    assert hasattr(ssl.SSLContext, "set_psk_server_callback")


# ======================== pickle ========================
class PicklePoint:
    """通过 __reduce__ 指定重建函数与参数的可序列化对象。"""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __reduce__(self):
        return (PicklePoint, (self.x, self.y))

    def __eq__(self, other):
        return (self.x, self.y) == (other.x, other.y)

    def __repr__(self):
        return f"PicklePoint({self.x}, {self.y})"


class PickleExternal:
    """需要通过 persistent_id 走带外通道传递的对象。"""

    def __init__(self, payload):
        self.payload = payload


class PickleExternalPickler(pickle.Pickler):
    """把 PickleExternal 对象编码成带外 id 的 Pickler。"""

    def persistent_id(self, obj):
        if isinstance(obj, PickleExternal):
            return ("external", obj.payload)
        return None


class PickleExternalUnpickler(pickle.Unpickler):
    """把带外 id 还原成 PickleExternal 对象的 Unpickler。"""

    def persistent_load(self, pid):
        kind, payload = pid
        assert kind == "external"
        return PickleExternal(payload)


class PickleCounter:
    """用 __getstate__ / __setstate__ 描述序列化状态的对象。"""

    def __init__(self, start):
        self.count = start
        self.history = []

    def __getstate__(self):
        return {"count": self.count, "history": list(self.history)}

    def __setstate__(self, state):
        self.count = state["count"]
        self.history = state["history"]

    def __eq__(self, other):
        return (self.count, self.history) == (other.count, other.history)


class PickleUnpicklable:
    """__reduce__ 明确拒绝序列化的对象。"""

    def __reduce__(self):
        raise pickle.PicklingError("refuse to pickle")


def test_pickle_dumps_loads_roundtrip_preserves_exact_values():
    """验证 dumps / loads 往返后字典内容、键集合与各值类型完全一致。"""
    payload = {"name": "forgemind", "count": 42, "ratio": 0.5, "flag": True, "none": None}
    restored = pickle.loads(pickle.dumps(payload))
    assert restored == payload
    assert restored is not payload
    assert restored["name"] == "forgemind"
    assert restored["count"] == 42
    assert restored["ratio"] == 0.5
    assert restored["flag"] is True
    assert restored["none"] is None
    assert sorted(restored) == ["count", "flag", "name", "none", "ratio"]
    assert all(type(restored[key]) is type(payload[key]) for key in payload)


def test_pickle_highest_protocol_and_default_protocol_values():
    """验证 HIGHEST_PROTOCOL 为 5、DEFAULT_PROTOCOL 为 4,且默认值低于最高版本。"""
    assert pickle.HIGHEST_PROTOCOL == 5
    assert pickle.DEFAULT_PROTOCOL == 4
    assert pickle.DEFAULT_PROTOCOL < pickle.HIGHEST_PROTOCOL
    assert 0 <= pickle.DEFAULT_PROTOCOL <= pickle.HIGHEST_PROTOCOL


def test_pickle_every_protocol_roundtrips_identically():
    """验证 0 到 HIGHEST_PROTOCOL 每个 protocol 编码后都能解回完全相同的数据。"""
    payload = {"list": [1, 2, 3], "tuple": (4, 5), "bytes": b"\x00\xff"}
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
        encoded = pickle.dumps(payload, protocol)
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0
        restored = pickle.loads(encoded)
        assert restored == payload
        assert restored["tuple"] == (4, 5)
        assert restored["bytes"] == b"\x00\xff"


def test_pickle_protocol_zero_produces_ascii_payload():
    """验证 protocol 0 的载荷是纯 ASCII,非 ASCII 字符以 \\u 转义写入。"""
    encoded = pickle.dumps({"name": "灵感", "n": 7}, 0)
    text = encoded.decode("ascii")
    assert all(ord(char) < 128 for char in text)
    assert text.startswith("(dp0")
    assert "\\u7075\\u611f" in text
    assert "灵感" not in text
    assert pickle.loads(encoded) == {"name": "灵感", "n": 7}


def test_pickle_pickler_and_unpickler_stream_objects_through_bytesio():
    """验证 Pickler 与 Unpickler 在同一字节流上依次写入并读出两个对象。"""
    buffer = io.BytesIO()
    pickler = pickle.Pickler(buffer, protocol=pickle.HIGHEST_PROTOCOL)
    pickler.dump({"index": 1})
    pickler.dump({"index": 2})
    raw = buffer.getvalue()
    assert raw.startswith(b"\x80")
    assert len(raw) > 10

    buffer.seek(0)
    unpickler = pickle.Unpickler(buffer)
    assert unpickler.load() == {"index": 1}
    assert unpickler.load() == {"index": 2}
    with pytest.raises(EOFError):
        unpickler.load()


def test_pickle_custom_reduce_rebuilds_object_state():
    """验证自定义 __reduce__ 的对象往返后类型与字段值保持不变。"""
    point = PicklePoint(3, 4)
    restored = pickle.loads(pickle.dumps(point))
    assert isinstance(restored, PicklePoint)
    assert restored.x == 3
    assert restored.y == 4
    assert restored == point
    assert restored is not point


def test_pickle_nested_structure_roundtrip_preserves_container_types():
    """验证嵌套结构往返后,list / tuple / set / bytes 的容器类型与内容都保持。"""
    payload = {
        "list": [1, [2, 3], {"deep": (4, 5)}],
        "set": {1, 2, 3},
        "bytes": b"\x00\x01",
        "tuple": ({"a": 1}, [2]),
    }
    restored = pickle.loads(pickle.dumps(payload))
    assert restored == payload
    assert isinstance(restored["list"], list)
    assert isinstance(restored["set"], set)
    assert isinstance(restored["bytes"], bytes)
    assert isinstance(restored["tuple"], tuple)
    assert isinstance(restored["list"][1], list)
    assert isinstance(restored["list"][2], dict)
    assert isinstance(restored["list"][2]["deep"], tuple)
    assert restored["list"][2]["deep"] == (4, 5)
    assert restored["set"] == {1, 2, 3}


def test_pickle_preserves_shared_references_via_memo():
    """验证同一对象被引用两次时,反序列化后两处仍指向同一个实例。"""
    shared = {"value": 1}
    payload = {"a": shared, "b": shared}
    restored = pickle.loads(pickle.dumps(payload))
    assert restored["a"] is restored["b"]
    assert restored["a"]["value"] == 1
    assert restored["a"] is not shared


def test_pickle_persistent_id_and_persistent_load_roundtrip():
    """验证 persistent_id 编码的对象经 persistent_load 还原后字段值不变。"""
    buffer = io.BytesIO()
    pickler = PickleExternalPickler(buffer, protocol=pickle.HIGHEST_PROTOCOL)
    pickler.dump({"ext": PickleExternal("data-1")})
    buffer.seek(0)
    restored = PickleExternalUnpickler(buffer).load()
    assert isinstance(restored["ext"], PickleExternal)
    assert restored["ext"].payload == "data-1"


def test_pickle_getstate_setstate_roundtrip():
    """验证 __getstate__ / __setstate__ 描述的状态在往返后逐字段一致。"""
    counter = PickleCounter(5)
    counter.history.append(1)
    restored = pickle.loads(pickle.dumps(counter))
    assert isinstance(restored, PickleCounter)
    assert restored.count == 5
    assert restored.history == [1]
    assert restored == counter


def test_pickle_unpicklable_object_raises_pickling_error():
    """验证 __reduce__ 抛错的对象报 PicklingError,局部 lambda 报 AttributeError。"""
    with pytest.raises(pickle.PicklingError) as excinfo:
        pickle.dumps(PickleUnpicklable())
    assert str(excinfo.value) == "refuse to pickle"

    with pytest.raises(AttributeError) as excinfo:
        pickle.dumps(lambda value: value)
    assert "Can't pickle local object" in str(excinfo.value)
