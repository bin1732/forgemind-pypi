# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""发布流程不能制造"索引与文件不一致"的窗口

真实故障(我自己在装的时候撞到):全新 venv 执行
    pip install --extra-index-url .../pypi/simple/ forgemind
报
    THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE
      Expected sha256 <旧>
      Got        <新>

原因是 ship.yml 的顺序:

    PUT  .../releases/builds/source/<name>     # ① 文件先覆盖 → 索引还挂旧 hash
    PUT  .../pypi/simple/forgemind/index.html  # ② 索引后更新

①和 ②之间的窗口里,文件已是新版而索引声明旧 hash,正好落进去的用户装不上。
已验证窗口只有一两秒(156KB 的 wheel),但足以让一次安装直接失败。

现在改成:先落到**带 build 标识的新路径**,再让索引指向它。
这样任何时刻"索引指向的 URL"和"该 URL 的内容"都是自洽的。
"""

import re
from pathlib import Path

import pytest
import pytest

yaml = pytest.importorskip("yaml", reason="需要 pyyaml 才能解析工作流文件")

SHIP = Path(__file__).resolve().parent.parent.parent / "pubgit" / ".github" / "workflows" / "ship.yml"


def _script() -> str:
    """取 ship.yml 里那段发布用的 python 源码"""
    text = SHIP.read_text(encoding="utf-8")
    # 找出含 compute_ic / release 上传的那段 run
    m = re.search(r"run: \|\n(.*?)\n\s*PYEOF", text, re.S)
    return m.group(1) if m else text


@pytest.fixture(scope="module", autouse=True)
def require_ship():
    if not SHIP.exists():
        pytest.skip("公开仓不在本地检出")


class TestPublishOrderIsRaceFree:
    def test_wheel_goes_to_a_build_stamped_path(self):
        src = _script()
        assert re.search(r"releases/builds/\{?build_id", src), (
            "wheel 仍写在固定路径 releases/builds/source/,"
            "索引更新前会与旧 hash 不一致")
        assert "GITHUB_RUN_ID" in src, "build 标识应取自 GITHUB_RUN_ID"

    def test_index_is_written_after_the_file_and_points_at_it(self):
        src = _script()
        i_file = src.find("contents/{rp}")
        i_index = src.find("pypi/simple/forgemind/index.html")
        assert i_file != -1 and i_index != -1
        assert i_file < i_index, "必须先有文件,再更新索引"

    def test_index_hash_comes_from_the_bytes_being_published(self):
        src = _script()
        assert "hashlib.sha256(blob).hexdigest()" in src, (
            "索引里的 hash 必须由实际发布的字节算出,不能另算")

    def test_manifest_advertises_a_working_install_url(self):
        """manifest 曾写着 .../simple/forgemind/ —— 照抄必得 404

        pip 会自己拼项目名,写成 .../simple/forgemind/ 时它实际请求
        .../simple/forgemind/forgemind/。
        """
        src = _script()
        m = re.search(r"'install':\s*'([^']+)'", src)
        assert m, "manifest 里没有 install 命令"
        cmd = m.group(1)
        u = re.search(r"https://\S+", cmd).group(0).rstrip("/")
        # URL 段本身必须止于 /pypi/simple:多带一层 /forgemind/ 时 pip 会
        # 再拼一次项目名,实际请求 .../simple/forgemind/forgemind/ → 404
        assert u.endswith("/pypi/simple"), u
        assert "--extra-index-url" in cmd
        # "--index-url" 是 "--extra-index-url" 的子串,单独排除会误伤,
        # 所以用词边界
        assert not re.search(r"(?<!-)\b--index-url\b", cmd), (
            "--index-url 会替换默认源,依赖就全找不到了")
        assert cmd.split()[-1] == "forgemind", cmd


class TestShipYamlStaysValid:
    def test_yaml_parses(self):
        yaml.safe_load(SHIP.read_text(encoding="utf-8"))
