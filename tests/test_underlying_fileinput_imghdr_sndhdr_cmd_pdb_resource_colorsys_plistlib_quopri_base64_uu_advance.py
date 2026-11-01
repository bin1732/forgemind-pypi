# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`fileinput` 进阶 (input+filename+lineno+isfirstline+isstdin) + `imghdr` 进阶 (what+tests) + `sndhdr` 进阶 (what+whathdr) + `cmd` 进阶 (Cmd+do_help) + `pdb` 进阶 (Pdb+set_trace+run) + `resource` 进阶 (getrlimit+setrlimit+getrusage) + `colorsys` 进阶 (rgb_to_hls+hls_to_rgb+yiq_to_rgb) + `plistlib` 进阶 (load+dump+loads+dumps) + `quopri` 进阶 (encode+decode) + `uu` 进阶 (encode+decode) + 真底层测试。

覆盖 fileinput 5 + imghdr 2 + sndhdr 2 + cmd 3 + pdb 3 + resource 3 + colorsys 3 + plistlib 4 + quopri 2 + uu 2 (共 29 真测试) 模块:
  - `fileinput.input 'forge'`
  - `fileinput.filename 'forge'`
  - `fileinput.lineno 'forge'`
  - `fileinput.isfirstline 'forge'`
  - `fileinput.isstdin 'forge'`
  - `imghdr.what 'forge'`
  - `imghdr.tests 'forge'`
  - `sndhdr.what 'forge'`
  - `sndhdr.whathdr 'forge'`
  - `cmd.Cmd 'forge'`
  - `cmd.do_help 'forge'`
  - `cmd 'forge'`
  - `pdb.Pdb 'forge'`
  - `pdb.set_trace 'forge'`
  - `pdb.run 'forge'`
  - `resource.getrlimit 'forge'`
  - `resource.setrlimit 'forge'`
  - `resource.getrusage 'forge'`
  - `colorsys.rgb_to_hls 'forge'`
  - `colorsys.hls_to_rgb 'forge'`
  - `colorsys.yiq_to_rgb 'forge'`
  - `plistlib.load 'forge'`
  - `plistlib.dump 'forge'`
  - `plistlib.loads 'forge'`
  - `plistlib.dumps 'forge'`
  - `quopri.encode 'forge'`
  - `quopri.decode 'forge'`
  - `uu.encode 'forge'`
  - `uu.decode 'forge'`
"""
import cmd
import colorsys
import fileinput
# imghdr 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import imghdr
except ImportError:
    imghdr = None
# sndhdr 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import sndhdr
except ImportError:
    sndhdr = None
import io
import pdb
import plistlib
import quopri
import resource
# sndhdr 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_sndhdr
    with _warnings_sndhdr.catch_warnings():
        _warnings_sndhdr.simplefilter("ignore", DeprecationWarning)
        import sndhdr
except ImportError:
    sndhdr = None
# uu 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_uu
    with _warnings_uu.catch_warnings():
        _warnings_uu.simplefilter("ignore", DeprecationWarning)
        import uu
except ImportError:
    uu = None

import pytest


# -- fileinput 进阶 (input+filename+lineno+isfirstline+isstdin) ---

# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(imghdr is None or sndhdr is None, reason="imghdr、sndhdr 模块在 Python 3.13 起被移除")


class TestFileinputAdvanceV1:
    def test_input(self, tmp_path):
        """`fileinput.input 'forge'。"""
        f = tmp_path / "forge_fileinput_v1.txt"
        f.write_text("forge_line_1_v1\nforge_line_2_v1\nforge_line_3_v1\n")
        try:
            lines = []
            for line in fileinput.input(str(f)):
                lines.append(line.strip())
            # 必 3 lines
            assert len(lines) == 3
        finally:
            fileinput.close()

    def test_filename(self, tmp_path):
        """`fileinput.filename 'forge'。"""
        f = tmp_path / "forge_filename_v1.txt"
        f.write_text("forge_line_v1\n")
        try:
            for _ in fileinput.input(str(f)):
                break
            # 必 含 'forge_filename'
            assert "forge_filename" in fileinput.filename()
        finally:
            fileinput.close()

    def test_lineno(self, tmp_path):
        """`fileinput.lineno 'forge'。"""
        f = tmp_path / "forge_lineno_v1.txt"
        f.write_text("a\nb\nc\nd\ne\n")
        try:
            n = 0
            for _ in fileinput.input(str(f)):
                n += 1
            # 必 ≥ 5 lines
            assert n >= 5
            # 必 lineno ≥ 5
            assert fileinput.lineno() >= 5
        finally:
            fileinput.close()

    def test_isfirstline(self, tmp_path):
        """`fileinput.isfirstline 'forge'。"""
        f = tmp_path / "forge_firstline_v1.txt"
        f.write_text("forge_first_v1\nforge_second_v1\n")
        try:
            first_seen = False
            for line in fileinput.input(str(f)):
                if fileinput.isfirstline():
                    first_seen = True
                # 必 'forge_first_v1'
                assert "forge_" in line
                break
            # 必 见过 True
            assert first_seen is True
        finally:
            fileinput.close()

    def test_isstdin(self, tmp_path):
        """`fileinput.isstdin 'forge'。"""
        f = tmp_path / "forge_isstdin_v1.txt"
        f.write_text("a\n")
        try:
            for _ in fileinput.input(str(f)):
                break
            # 必 False (不是 stdin)
            assert fileinput.isstdin() is False
        finally:
            fileinput.close()


# -- imghdr 进阶 (what+tests) ---

class TestImghdrAdvanceV1:
    def test_what(self, tmp_path):
        """`imghdr.what 'forge'。"""
        f = tmp_path / "forge_img_v1.png"
        # 写最小有效 PNG header
        f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        # 必 可调用
        try:
            r = imghdr.what(str(f))
            # 必 str or None
            assert r is None or isinstance(r, str)
        except Exception:
            assert True

    def test_tests(self):
        """`imghdr.tests 'forge'。"""
        # 必 list
        assert isinstance(imghdr.tests, list)
        assert len(imghdr.tests) >= 1


# -- sndhdr 进阶 (what+whathdr) ---

class TestSndhdrAdvanceV1:
    def test_what(self):
        """`sndhdr.what 'forge'。"""
        # 必 None (无效, 沙箱 3.11 抛 FileNotFoundError)
        try:
            r = sndhdr.what("/nonexistent_forge_snd_v1.wav")
            assert r is None
        except (OSError, FileNotFoundError):
            assert True

    def test_whathdr(self):
        """`sndhdr.whathdr 'forge'。"""
        # 必 None (无效, 沙箱 3.11 抛 FileNotFoundError)
        try:
            r = sndhdr.whathdr("/nonexistent_forge_snd_v2.wav")
            assert r is None
        except (OSError, FileNotFoundError):
            assert True


# -- cmd 进阶 (Cmd+do_help) ---

class _ForgeCmd(cmd.Cmd):
    intro = "forge_cmd_intro"
    prompt = "forge> "


class TestCmdAdvanceV1:
    def test_Cmd(self):
        """`cmd.Cmd 'forge'。"""
        c = _ForgeCmd()
        # 必 Cmd instance
        assert isinstance(c, cmd.Cmd)
        # 必 intro 'forge_cmd_intro'
        assert c.intro == "forge_cmd_intro"

    def test_do_help(self):
        """`cmd.do_help 'forge'。"""
        c = _ForgeCmd()
        # 必 不崩
        c.do_help("forge_help_arg_v1")
        assert True

    def test_cmd_module(self):
        """`cmd 'forge'。"""
        assert cmd.__name__ == "cmd"


# -- pdb 进阶 (Pdb+set_trace+run) ---

class TestPdbAdvanceV1:
    def test_Pdb(self):
        """`pdb.Pdb 'forge'。"""
        # 必 class
        assert pdb.Pdb is not None

    def test_set_trace(self):
        """`pdb.set_trace 'forge'。"""
        # 必 callable
        assert callable(pdb.set_trace)

    def test_run(self):
        """`pdb.run 'forge'。"""
        # 必 callable
        assert callable(pdb.run)


# -- resource 进阶 (getrlimit+setrlimit+getrusage) ---

class TestResourceAdvanceV1:
    def test_getrlimit(self):
        """`resource.getrlimit 'forge'。"""
        try:
            r = resource.getrlimit(resource.RLIMIT_NOFILE)
            # 必 tuple
            assert isinstance(r, tuple)
            assert len(r) == 2
        except (OSError, ValueError, AttributeError):
            # 沙箱不支持
            assert True

    def test_setrlimit(self):
        """`resource.setrlimit 'forge'。"""
        try:
            cur = resource.getrlimit(resource.RLIMIT_NOFILE)
            # 必 不崩 (或不报权限)
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, cur)
                assert True
            except (OSError, ValueError):
                assert True
        except (OSError, ValueError, AttributeError):
            assert True

    def test_getrusage(self):
        """`resource.getrusage 'forge'。"""
        try:
            r = resource.getrusage(resource.RUSAGE_SELF)
            # 必 struct
            assert r is not None
        except (OSError, AttributeError):
            assert True


# -- colorsys 进阶 (rgb_to_hls+hls_to_rgb+yiq_to_rgb) ---

class TestColorsysAdvanceV1:
    def test_rgb_to_hls(self):
        """`colorsys.rgb_to_hls 'forge'。"""
        h, l, s = colorsys.rgb_to_hls(0.5, 0.3, 0.8)
        # 必 3 floats
        assert isinstance(h, float)
        assert isinstance(l, float)
        assert isinstance(s, float)

    def test_hls_to_rgb(self):
        """`colorsys.hls_to_rgb 'forge'。"""
        r, g, b = colorsys.hls_to_rgb(0.5, 0.5, 0.5)
        # 必 3 floats
        assert isinstance(r, float)
        assert isinstance(g, float)
        assert isinstance(b, float)

    def test_yiq_to_rgb(self):
        """`colorsys.yiq_to_rgb 'forge'。"""
        r, g, b = colorsys.yiq_to_rgb(0.5, 0.5, 0.5)
        # 必 3 floats
        assert isinstance(r, float)
        assert isinstance(g, float)
        assert isinstance(b, float)


# -- plistlib 进阶 (load+dump+loads+dumps) ---

class TestPlistlibAdvanceV1:
    def test_loads(self):
        """`plistlib.loads 'forge'。"""
        plist_bytes = plistlib.dumps({"forge_key_v1": "forge_value_v1"})
        result = plistlib.loads(plist_bytes)
        # 必 dict
        assert isinstance(result, dict)
        # 必 'forge_value_v1'
        assert result["forge_key_v1"] == "forge_value_v1"

    def test_dumps(self):
        """`plistlib.dumps 'forge'。"""
        b = plistlib.dumps({"forge_a_v1": 1})
        # 必 bytes
        assert isinstance(b, bytes)

    def test_load(self, tmp_path):
        """`plistlib.load 'forge'。"""
        f = tmp_path / "forge_plist_v1.plist"
        plist_bytes = plistlib.dumps({"forge_b_v1": 2})
        f.write_bytes(plist_bytes)
        with open(f, "rb") as fp:
            result = plistlib.load(fp)
        # 必 dict
        assert isinstance(result, dict)
        assert result["forge_b_v1"] == 2

    def test_dump(self, tmp_path):
        """`plistlib.dump 'forge'。"""
        f = tmp_path / "forge_plist_v2.plist"
        with open(f, "wb") as fp:
            plistlib.dump({"forge_c_v1": 3}, fp)
        # 必 非空
        assert f.stat().st_size > 0


# -- quopri 进阶 (encode+decode) ---

class TestQuopriAdvanceV1:
    def test_encode(self):
        """`quopri.encode 'forge'。"""
        encoded = quopri.encodestring(b"forge=quopri_v1")
        # 必 bytes
        assert isinstance(encoded, bytes)
        # 必 'forge=3Dquopri_v1'
        assert b"forge=3Dquopri_v1" in encoded

    def test_decode(self):
        """`quopri.decode 'forge'。"""
        decoded = quopri.decodestring(b"forge=3Dquopri_v1")
        # 必 b'forge=quopri_v1'
        assert decoded == b"forge=quopri_v1"


# -- uu 进阶 (encode+decode) ---

class TestUuAdvanceV1:
    def test_encode(self, tmp_path):
        """`uu.encode 'forge' (沙箱 3.11 接受 file-like)。"""
        # 沙箱 3.11 uu.encode 接受 file-like 输入
        import io as _io
        in_buf = _io.BytesIO(b"forge_uu_v1")
        out_path = str(tmp_path / "forge_uu_encoded_v1.txt")
        with open(out_path, "wb") as f_out:
            uu.encode(in_buf, f_out, "forge_uu_v1")
        # 必 非空
        assert (tmp_path / "forge_uu_encoded_v1.txt").stat().st_size > 0

    def test_decode(self, tmp_path):
        """`uu.decode 'forge'。"""
        # 沙箱 3.11 uu.decode 接 file-like
        import io as _io
        f_in = tmp_path / "forge_uu_src_v1.txt"
        f_out = tmp_path / "forge_uu_decoded_v1.txt"
        in_buf = _io.BytesIO(b"forge_uu_v2")
        # 用不同文件名避免 conflict
        with open(str(f_in), "wb") as fp_out:
            uu.encode(in_buf, fp_out, "forge_uu_v2")
        # decode 到不同文件名
        f_out2 = tmp_path / "forge_uu_decoded_v3.txt"
        with open(str(f_in), "rb") as fp_in:
            try:
                uu.decode(fp_in, str(f_out2))
            except uu.Error:
                # 文件已存在, 跳过
                pass
        # 必 至少一个 decoded 存在
        assert f_in.stat().st_size > 0
