# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import math
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import numpy as np

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


class PositionalEncoding(nn.Module):
    """标准 Transformer 位置编码"""
    
    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer('pe', pe)
    
    def forward(self, x):
        # x: (batch, seq_len, d_model)
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class TransformerTimeSeries(nn.Module):
    """时序 Transformer encoder"""
    
    def __init__(
        self,
        n_features: int,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 128,
        dropout: float = 0.1,
        output_dim: int = 1,
    ):
        super().__init__()
        self.input_proj = nn.Linear(n_features, d_model)
        self.pos_encoder = PositionalEncoding(d_model, dropout=dropout)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
            dropout=dropout, batch_first=True, activation='gelu',
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.head = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, output_dim),
        )
    
    def forward(self, x):
        # x: (batch, seq_len, n_features)
        x = self.input_proj(x)  # (batch, seq_len, d_model)
        x = self.pos_encoder(x)
        # 因果 mask: 防止看到未来
        seq_len = x.size(1)
        mask = torch.triu(torch.ones(seq_len, seq_len, device=x.device), diagonal=1).bool()
        x = self.transformer(x, mask=mask)
        # 取最后一时间步
        x = x[:, -1, :]  # (batch, d_model)
        return self.head(x)


class TransformerModel:
    """Transformer 时序预测模型 — A 股日频 K 线专用
    
    用法:
        model = TransformerModel(sequence_length=60, n_features=20)
        model.train(X_train, y_train)  # X: (n, 60, 20), y: (n,)
        preds = model.predict(X_test)  # (n_test,)
    """
    
    def __init__(
        self,
        sequence_length: int = 60,
        n_features: Optional[int] = None,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 128,
        dropout: float = 0.1,
        epochs: int = 20,
        batch_size: int = 64,
        lr: float = 1e-3,
        device: str = "cpu",
        random_state: int = 42,
    ):
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.d_model = d_model
        self.nhead = nhead
        self.num_layers = num_layers
        self.dim_feedforward = dim_feedforward
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.device = device
        self.random_state = random_state
        
        self.model: Optional[TransformerTimeSeries] = None
        self.train_losses: List[float] = []
        self.val_losses: List[float] = []
        self._is_fitted = False
    
    def _to_tensor(self, X, y=None) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        X_t = torch.as_tensor(np.asarray(X), dtype=torch.float32)
        if y is not None:
            y_t = torch.as_tensor(np.asarray(y), dtype=torch.float32)
            if y_t.ndim == 1:
                y_t = y_t.unsqueeze(1)
            return X_t, y_t
        return X_t, None
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        verbose: bool = False,
    ) -> Dict:
        """
        训练 Transformer
        
        Args:
            X: (n_samples, sequence_length, n_features)
            y: (n_samples,) 或 (n_samples, 1)
            X_val: 验证集(可选)
            y_val: 验证集(可选)
            verbose: 是否打印训练日志
        
        Returns:
            dict: 训练历史
        """
        torch.manual_seed(self.random_state)
        np.random.seed(self.random_state)
        
        n_samples, seq_len, n_feat = X.shape
        if seq_len != self.sequence_length:
            raise ValueError(
                f"sequence_length mismatch: X has {seq_len}, model expects {self.sequence_length}"
            )
        if self.n_features is None:
            self.n_features = n_feat
        elif self.n_features != n_feat:
            raise ValueError(
                f"n_features mismatch: X has {n_feat}, model expects {self.n_features}"
            )
        
        # 建模型
        self.model = TransformerTimeSeries(
            n_features=n_feat,
            d_model=self.d_model,
            nhead=self.nhead,
            num_layers=self.num_layers,
            dim_feedforward=self.dim_feedforward,
            dropout=self.dropout,
        ).to(self.device)
        
        # 数据
        X_t, y_t = self._to_tensor(X, y)
        dataset = TensorDataset(X_t, y_t)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True, drop_last=False)
        
        # 验证集
        val_loader = None
        if X_val is not None and y_val is not None:
            X_v_t, y_v_t = self._to_tensor(X_val, y_val)
            val_dataset = TensorDataset(X_v_t, y_v_t)
            val_loader = DataLoader(val_dataset, batch_size=self.batch_size, shuffle=False)
        
        # 优化器
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=self.lr, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=self.epochs)
        criterion = nn.MSELoss()
        
        # 训练
        self.train_losses = []
        self.val_losses = []
        self.model.train()
        
        for epoch in range(self.epochs):
            epoch_loss = 0.0
            n_batches = 0
            for X_b, y_b in loader:
                X_b = X_b.to(self.device)
                y_b = y_b.to(self.device)
                
                optimizer.zero_grad()
                pred = self.model(X_b)
                loss = criterion(pred, y_b)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()
                
                epoch_loss += loss.item()
                n_batches += 1
            
            scheduler.step()
            avg_train = epoch_loss / max(1, n_batches)
            self.train_losses.append(avg_train)
            
            # 验证
            if val_loader is not None:
                self.model.eval()
                val_loss = 0.0
                n_v = 0
                with torch.no_grad():
                    for X_b, y_b in val_loader:
                        X_b = X_b.to(self.device)
                        y_b = y_b.to(self.device)
                        pred = self.model(X_b)
                        val_loss += criterion(pred, y_b).item()
                        n_v += 1
                avg_val = val_loss / max(1, n_v)
                self.val_losses.append(avg_val)
                self.model.train()
                
                if verbose and (epoch + 1) % 5 == 0:
                    print(f"Epoch {epoch+1}/{self.epochs} - "
                          f"train_loss={avg_train:.4f} - val_loss={avg_val:.4f}")
            elif verbose and (epoch + 1) % 5 == 0:
                print(f"Epoch {epoch+1}/{self.epochs} - train_loss={avg_train:.4f}")
        
        self._is_fitted = True
        
        return {
            "n_samples": n_samples,
            "n_epochs": self.epochs,
            "train_loss": self.train_losses[-1],
            "val_loss": self.val_losses[-1] if self.val_losses else None,
            "history": {
                "train": self.train_losses,
                "val": self.val_losses,
            },
        }
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        预测
        
        Args:
            X: (n_samples, sequence_length, n_features)
        
        Returns:
            (n_samples,) 预测值
        """
        if self.model is None or not self._is_fitted:
            return np.zeros(len(X))
        
        self.model.eval()
        X_t, _ = self._to_tensor(X)
        preds = []
        with torch.no_grad():
            # 分批推理
            for i in range(0, len(X_t), self.batch_size):
                batch = X_t[i:i + self.batch_size].to(self.device)
                pred = self.model(batch)
                preds.append(pred.cpu().numpy())
        
        result = np.concatenate(preds, axis=0)
        return result.flatten() if result.ndim > 1 else result
    
    def save(self, path: str):
        """保存模型到磁盘"""
        if self.model is None:
            raise RuntimeError("Model not trained, cannot save")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "state_dict": self.model.state_dict(),
            "config": {
                "sequence_length": self.sequence_length,
                "n_features": self.n_features,
                "d_model": self.d_model,
                "nhead": self.nhead,
                "num_layers": self.num_layers,
                "dim_feedforward": self.dim_feedforward,
                "dropout": self.dropout,
            },
        }, path)
    
    def load(self, path: str):
        """从磁盘加载模型"""
        ckpt = torch.load(path, map_location=self.device)
        cfg = ckpt["config"]
        self.sequence_length = cfg["sequence_length"]
        self.n_features = cfg["n_features"]
        self.d_model = cfg["d_model"]
        self.nhead = cfg["nhead"]
        self.num_layers = cfg["num_layers"]
        self.dim_feedforward = cfg["dim_feedforward"]
        self.dropout = cfg["dropout"]
        
        self.model = TransformerTimeSeries(
            n_features=self.n_features,
            d_model=self.d_model,
            nhead=self.nhead,
            num_layers=self.num_layers,
            dim_feedforward=self.dim_feedforward,
            dropout=self.dropout,
        ).to(self.device)
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()
        self._is_fitted = True
    
    def get_attention_weights(self, X: np.ndarray) -> np.ndarray:
        """
        提取自注意力权重(可解释性)
        
        Returns:
            (n_samples, n_layers, n_heads, seq_len, seq_len)
        """
        if self.model is None:
            raise RuntimeError("Model not trained")
        
        self.model.eval()
        X_t, _ = self._to_tensor(X[:1])  # 只取第一个样本
        weights = []
        
        # 用 PyTorch 内部 API 拿 weights
        with torch.no_grad():
            x = self.model.input_proj(X_t)
            x = self.model.pos_encoder(x)
            for layer in self.model.transformer.layers:
                # self_attn 返回 (attn_output, attn_weights)
                _, attn_w = layer.self_attn(x, x, x, need_weights=True, average_attn_weights=False)
                weights.append(attn_w.cpu().numpy())
                x = layer(x)[0] if isinstance(layer(x), tuple) else layer(x)
        
        return np.stack(weights, axis=0).squeeze(1)  # (n_layers, n_heads, seq_len, seq_len)