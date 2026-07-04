"""
model_ucf101.py — VideoMAE fine-tuned for UCF-101

Why VideoMAE-Kinetics for UCF-101:
    - Pretrained on Kinetics-400 (400 action classes, 400k videos)
    - UCF-101 is a subset of human actions — very similar domain
    - Fine-tuning from Kinetics gets 99%+ because the model already
      knows most of the actions before it even sees UCF-101

Architecture:
    VideoMAE (Kinetics pretrained)
        ↓
    Mean pool over patch tokens
        ↓
    Residual classifier head (101 classes)
"""

import torch
import torch.nn as nn
from transformers import VideoMAEForVideoClassification, VideoMAEConfig


class UCF101VideoMAE(nn.Module):

    def __init__(self, num_classes=101, num_frames=16):
        super().__init__()

        print("Loading VideoMAE pretrained on Kinetics-400...")
        print("(Downloads ~330MB on first run)")

        # ── VideoMAE fine-tuned on Kinetics-400 ───────────────
        # This is the KEY difference from before:
        # "videomae-base"                  → raw pretraining only
        # "videomae-base-finetuned-kinetics" → already knows actions
        # UCF-101 actions ≈ Kinetics actions → huge transfer
        self.model = VideoMAEForVideoClassification.from_pretrained(
            "MCG-NJU/videomae-base-finetuned-kinetics",
            num_labels=num_classes,
            ignore_mismatched_sizes=True,  # replace Kinetics head with UCF head
            num_frames=num_frames,
        )

        # Feature dim = 768 for VideoMAE base
        hidden_size = self.model.config.hidden_size

        # Replace the classifier head with our residual one
        self.model.classifier = ResidualHead(hidden_size, num_classes)

        # ── Freeze strategy ───────────────────────────────────
        # Freeze everything first
        # train.py unfreezes progressively
        for param in self.model.videomae.parameters():
            param.requires_grad = False

        print(f"Model loaded. Feature dim: {hidden_size}")
        print(f"Num classes: {num_classes}")

    def unfreeze_encoder_block(self, block_idx):
        """Unfreeze one transformer encoder block."""
        count = 0
        for name, param in self.model.videomae.named_parameters():
            if f"encoder.layer.{block_idx}." in name:
                param.requires_grad = True
                count += 1
        print(f"  → Unfrozen encoder block {block_idx} ({count} tensors)")

    def unfreeze_last_n_blocks(self, n):
        """Unfreeze last n encoder blocks (blocks 11, 10, 9 ...)"""
        total_blocks = self.model.config.num_hidden_layers  # 12 for base
        for i in range(total_blocks - n, total_blocks):
            self.unfreeze_encoder_block(i)

    def forward(self, x):
        # x: (B, T, C, H, W) — note: T before C for VideoMAE
        # Our dataset outputs (T, C, H, W) per sample
        # DataLoader stacks to (B, T, C, H, W) ✓

        outputs = self.model(pixel_values=x)
        return outputs.logits  # (B, num_classes)


class ResidualHead(nn.Module):
    """Residual GELU classifier head — same proven design."""

    def __init__(self, dim, num_classes, dropout=0.4):
        super().__init__()
        self.norm  = nn.LayerNorm(dim)
        self.fc1   = nn.Linear(dim, dim)
        self.act   = nn.GELU()
        self.drop1 = nn.Dropout(dropout)
        self.fc2   = nn.Linear(dim, dim)
        self.drop2 = nn.Dropout(dropout)
        self.head  = nn.Linear(dim, num_classes)

    def forward(self, x):
        x   = self.norm(x)
        res = x
        x   = self.drop1(self.act(self.fc1(x)))
        x   = self.drop2(self.fc2(x))
        return self.head(x + res)
