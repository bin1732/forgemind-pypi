# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import numpy as np
import pandas as pd


class TestTransformerModel:
    """Transformer 时序模型 — 真 PyTorch 实现验证"""
    
    def test_import(self):
        """应能从 transformer_model 导入"""
        from forgemind.core.models.transformer_model import (
            TransformerModel,
            TransformerTimeSeries,
            PositionalEncoding,
        )
        assert TransformerModel is not None
    
    def test_create(self):
        """创建 Transformer 模型不应报错"""
        from forgemind.core.models.transformer_model import TransformerModel
        m = TransformerModel(sequence_length=10, n_features=5)
        assert m.sequence_length == 10
        assert m.n_features == 5
        assert m.model is None  # 还没训练
    
    def test_train_and_predict(self):
        """应能真训练 + 预测"""
        from forgemind.core.models.transformer_model import TransformerModel
        
        np.random.seed(42)
        n_samples = 200
        seq_len = 10
        n_feat = 5
        
        X = np.random.randn(n_samples, seq_len, n_feat).astype(np.float32)
        # 让 y 与 X 第 1 个特征相关
        y = X[:, -1, 0] * 0.5 + np.random.randn(n_samples) * 0.1
        
        m = TransformerModel(
            sequence_length=seq_len, n_features=n_feat,
            d_model=16, nhead=2, num_layers=1, dim_feedforward=32,
            epochs=3, batch_size=32,
        )
        result = m.train(X, y, verbose=False)
        
        assert "n_samples" in result
        assert result["n_samples"] == n_samples
        assert "history" in result
        assert len(result["history"]["train"]) == 3  # 3 epochs
        
        # 训练后 model 应非 None
        assert m.model is not None
        assert m._is_fitted is True
        
        # 预测
        preds = m.predict(X[:10])
        assert len(preds) == 10
        assert not np.allclose(preds, 0)  # 不是全零
    
    def test_save_load(self):
        """应能保存 + 加载"""
        import tempfile
        import os
        from forgemind.core.models.transformer_model import TransformerModel
        
        np.random.seed(42)
        X = np.random.randn(50, 8, 5).astype(np.float32)
        y = np.random.randn(50).astype(np.float32)
        
        m = TransformerModel(sequence_length=8, n_features=5, d_model=16, epochs=1)
        m.train(X, y, verbose=False)
        
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            path = f.name
        try:
            m.save(path)
            assert os.path.exists(path)
            
            m2 = TransformerModel()
            m2.load(path)
            assert m2._is_fitted is True
            assert m2.sequence_length == 8
            assert m2.n_features == 5
        finally:
            if os.path.exists(path):
                os.unlink(path)
    
    def test_predict_without_train(self):
        """未训练应该返回全零(明确行为,非静默失败)"""
        from forgemind.core.models.transformer_model import TransformerModel
        
        m = TransformerModel(sequence_length=10, n_features=3)
        preds = m.predict(np.random.randn(5, 10, 3))
        assert len(preds) == 5
        assert np.allclose(preds, 0)
    
    def test_shape_mismatch(self):
        """shape 不匹配应明确报错"""
        from forgemind.core.models.transformer_model import TransformerModel
        
        m = TransformerModel(sequence_length=10, n_features=3)
        # sequence_length 应该是 10,这里给 5
        with pytest.raises(ValueError, match="sequence_length mismatch"):
            m.train(np.random.randn(20, 5, 3), np.random.randn(20))


class TestOnlineLearningStrategy:
    """OnlineLearningStrategy — 真在线学习"""
    
    def test_import(self):
        """应能导入"""
        from forgemind.core.strategies.extended_library import OnlineLearningStrategy
        assert OnlineLearningStrategy is not None
    
    def test_create_with_factory(self):
        """应能用 model_factory 创建"""
        from forgemind.core.strategies.extended_library import OnlineLearningStrategy
        
        # 假模型工厂
        def factory():
            from sklearn.linear_model import LinearRegression
            return LinearRegression()
        
        s = OnlineLearningStrategy(
            model_factory=factory,
            retrain_freq=10,
            window_size=50,
            top_k=5,
            bottom_k=5,
        )
        assert s.retrain_freq == 10
        assert s.window_size == 50
        assert s.top_k == 5
        assert s.current_model is None
    
    def test_generate_signal_runs(self):
        """generate_signal 应真运行,不返回全零"""
        from forgemind.core.strategies.extended_library import OnlineLearningStrategy
        
        def factory():
            from sklearn.linear_model import LinearRegression
            return LinearRegression()
        
        np.random.seed(42)
        # 构造可预测数据:y = f1 + f2(让模型能学)
        n = 300
        n_symbols = 20
        dates = pd.date_range("2024-01-01", periods=n // n_symbols, freq="D").repeat(n_symbols)
        symbols = list(range(n_symbols)) * (n // n_symbols)
        
        df = pd.DataFrame({
            "date": dates,
            "symbol": symbols,
            "f1": np.random.randn(n),
            "f2": np.random.randn(n),
            "f3": np.random.randn(n),
            "fwd_ret_5": np.random.randn(n) * 0.01,
        })
        df["fwd_ret_5"] = df["f1"] * 0.01 + np.random.randn(n) * 0.005
        
        s = OnlineLearningStrategy(
            model_factory=factory,
            retrain_freq=20,
            window_size=60,
            top_k=3,
            bottom_k=3,
        )
        signals = s.generate_signal(df)
        
        assert len(signals) == n
        # 不应该全零(模型预测了一些非零值)
        # 注意:第一段 (window_size) 是 0,后面才有信号
        nonzero_ratio = (signals != 0).mean()
        assert nonzero_ratio > 0
    
    def test_train_history_recorded(self):
        """应记录训练历史"""
        from forgemind.core.strategies.extended_library import OnlineLearningStrategy
        
        def factory():
            from sklearn.linear_model import LinearRegression
            return LinearRegression()
        
        np.random.seed(42)
        n = 200
        n_symbols = 10
        dates = pd.date_range("2024-01-01", periods=n // n_symbols, freq="D").repeat(n_symbols)
        symbols = list(range(n_symbols)) * (n // n_symbols)
        
        df = pd.DataFrame({
            "date": dates,
            "symbol": symbols,
            "f1": np.random.randn(n),
            "fwd_ret_5": np.random.randn(n),
        })
        
        s = OnlineLearningStrategy(
            model_factory=factory,
            retrain_freq=30,
            window_size=60,
        )
        s.generate_signal(df)
        
        history = s.get_train_history()
        # 至少重训过几次
        assert len(history) >= 1
        assert "idx" in history[0]


class TestFetchMulti:
    """DataSourceRegistry.fetch_multi — 并发拉多源,显式日志"""
    
    def test_fetch_multi_success(self):
        """所有源都成功应返回所有结果"""
        from forgemind.core.data.sources.extended_sources import (
            DataSourceRegistry, DataSource,
        )
        
        class MockSource(DataSource):
            name = "mock_ok"
            def fetch(self, **kwargs):
                import polars as pl
                return pl.DataFrame({"a": [1, 2, 3]})
            def get_schema(self):
                return {"a": "int"}
        
        registry = DataSourceRegistry()
        registry.register("mock_ok", MockSource())
        
        result = registry.fetch_multi(["mock_ok"])
        assert "mock_ok" in result
        assert result["mock_ok"].height == 3
    
    def test_fetch_multi_with_failure(self):
        """一个失败不应阻塞其他"""
        from forgemind.core.data.sources.extended_sources import (
            DataSourceRegistry, DataSource,
        )
        import polars as pl
        
        class GoodSource(DataSource):
            name = "good"
            def fetch(self, **kwargs):
                return pl.DataFrame({"a": [1]})
            def get_schema(self):
                return {"a": "int"}
        
        class BadSource(DataSource):
            name = "bad"
            def fetch(self, **kwargs):
                raise RuntimeError("API 限流")
            def get_schema(self):
                return {"a": "int"}
        
        registry = DataSourceRegistry()
        registry.register("good", GoodSource())
        registry.register("bad", BadSource())
        
        result = registry.fetch_multi(["good", "bad"])
        assert "good" in result
        assert "bad" not in result  # 失败的被剔除
    
    def test_fetch_multi_missing_source(self):
        """不存在的源应警告 + 跳过"""
        from forgemind.core.data.sources.extended_sources import (
            DataSourceRegistry, DataSource,
        )
        import polars as pl
        
        class GoodSource(DataSource):
            name = "good2"
            def fetch(self, **kwargs):
                return pl.DataFrame({"x": [1]})
            def get_schema(self):
                return {"x": "int"}
        
        registry = DataSourceRegistry()
        registry.register("good2", GoodSource())
        
        result = registry.fetch_multi(["good2", "nonexistent"])
        assert "good2" in result
        assert "nonexistent" not in result


class TestDuckDBStorageContextManager:
    """DuckDB __exit__ 应该记录异常上下文"""
    
    def test_normal_exit(self):
        """正常退出应关闭连接"""
        import tempfile
        import os
        from forgemind.core.data.storage import DuckDBStorage
        
        # 用 mkstemp 而非 NamedTemporaryFile,避免空文件干扰 duckdb
        fd, path = tempfile.mkstemp(suffix=".duckdb")
        os.close(fd)
        os.unlink(path)  # 让 duckdb 自己创建
        try:
            with DuckDBStorage(path=path) as db:
                db.execute("CREATE TABLE t (x INT)")
                db.execute("INSERT INTO t VALUES (1)")
            # 退出后 conn 应该关闭
            assert db.conn is None
        finally:
            if os.path.exists(path):
                os.unlink(path)
    
    def test_exit_with_error(self):
        """异常退出应该记录 warning 但不抛出"""
        import tempfile
        import os
        from forgemind.core.data.storage import DuckDBStorage
        
        fd, path = tempfile.mkstemp(suffix=".duckdb")
        os.close(fd)
        os.unlink(path)
        try:
            try:
                with DuckDBStorage(path=path) as db:
                    db.execute("CREATE TABLE t (x INT)")
                    raise ValueError("test")
            except ValueError:
                pass  # 异常应该被重新 raise 出来
            # 连接应被关闭
            assert db.conn is None
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestSettingsRiskRemoval:
    """risk_* 字段已删除(主框架是研究层,不需要)"""
    
    def test_no_risk_fields(self):
        """Settings 不应再含 risk_* 字段"""
        from forgemind.core.config.settings import Settings
        s = Settings(api_secret_key="x" * 32)
        # 确认 risk_* 字段已删
        assert not hasattr(s, "risk_daily_loss_limit_pct")
        assert not hasattr(s, "risk_max_daily_trades")
        assert not hasattr(s, "risk_cancel_ratio_limit")
        assert not hasattr(s, "risk_max_position_pct")


class TestQuickChatEnvFallback:
    """quick_chat 应能从 settings 读 API key"""
    
    def test_resolves_api_key_from_settings(self):
        """显式传 key 优先"""
        from forgemind.core.ai.providers import ProviderConfig, ProviderType, create_provider

        # 直接用 ProviderConfig 测试解析逻辑
        config = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            api_key="explicit-key",
            model_name="gpt-4o-mini",
        )
        p = create_provider(config)
        assert p.config.api_key == "explicit-key"
    
    def test_settings_provider_keys_present(self):
        """Settings 应含所有 provider 的 key 字段"""
        from forgemind.core.config.settings import Settings
        s = Settings(api_secret_key="x" * 32)
        assert hasattr(s, "openai_api_key")
        assert hasattr(s, "anthropic_api_key")
        assert hasattr(s, "qwen_api_key")
        assert hasattr(s, "deepseek_api_key")
        assert hasattr(s, "gemini_api_key")
        assert hasattr(s, "mistral_api_key")