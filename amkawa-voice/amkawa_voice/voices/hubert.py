"""Minimal HuBERT/ContentVec encoder (inference only), compatible with the
`lengyue233/content-vec-best` checkpoint used by RVC. Avoids shipping fairseq/transformers."""
import math

import torch
from torch import nn
from torch.nn import functional as F

CONTENTVEC_URL = "https://huggingface.co/lengyue233/content-vec-best/resolve/main/pytorch_model.bin"
CONTENTVEC_SIZE = 378342945


class _FeatureExtractor(nn.Module):
    def __init__(self):
        super().__init__()
        kernels = [10, 3, 3, 3, 3, 2, 2]
        strides = [5, 2, 2, 2, 2, 2, 2]
        layers = []
        for i, (k, s) in enumerate(zip(kernels, strides)):
            layer = nn.Module()
            layer.conv = nn.Conv1d(1 if i == 0 else 512, 512, k, stride=s, bias=False)
            if i == 0:
                layer.layer_norm = nn.GroupNorm(512, 512, affine=True)
            layers.append(layer)
        self.conv_layers = nn.ModuleList(layers)

    def forward(self, x):
        x = x[:, None]
        for i, layer in enumerate(self.conv_layers):
            x = layer.conv(x)
            if i == 0:
                x = layer.layer_norm(x)
            x = F.gelu(x)
        return x


class _FeatureProjection(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer_norm = nn.LayerNorm(512, eps=1e-5)
        self.projection = nn.Linear(512, 768)

    def forward(self, x):
        return self.projection(self.layer_norm(x))


class _Attention(nn.Module):
    def __init__(self, dim=768, heads=12):
        super().__init__()
        self.heads = heads
        self.head_dim = dim // heads
        self.q_proj = nn.Linear(dim, dim)
        self.k_proj = nn.Linear(dim, dim)
        self.v_proj = nn.Linear(dim, dim)
        self.out_proj = nn.Linear(dim, dim)

    def forward(self, x):
        b, t, d = x.shape

        def split(y):
            return y.view(b, t, self.heads, self.head_dim).transpose(1, 2)

        q = split(self.q_proj(x)) * (self.head_dim ** -0.5)
        k = split(self.k_proj(x))
        v = split(self.v_proj(x))
        attn = torch.softmax(q @ k.transpose(-1, -2), dim=-1)
        out = (attn @ v).transpose(1, 2).reshape(b, t, d)
        return self.out_proj(out)


class _FeedForward(nn.Module):
    def __init__(self):
        super().__init__()
        self.intermediate_dense = nn.Linear(768, 3072)
        self.output_dense = nn.Linear(3072, 768)

    def forward(self, x):
        return self.output_dense(F.gelu(self.intermediate_dense(x)))


class _Layer(nn.Module):
    def __init__(self):
        super().__init__()
        self.attention = _Attention()
        self.layer_norm = nn.LayerNorm(768, eps=1e-5)
        self.feed_forward = _FeedForward()
        self.final_layer_norm = nn.LayerNorm(768, eps=1e-5)

    def forward(self, x):
        x = self.layer_norm(x + self.attention(x))
        return self.final_layer_norm(x + self.feed_forward(x))


class _PosConv(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv1d(768, 768, 128, padding=64, groups=16)

    def forward(self, x):
        y = self.conv(x.transpose(1, 2))[:, :, :-1]
        return F.gelu(y).transpose(1, 2)


class _Encoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.pos_conv_embed = _PosConv()
        self.layer_norm = nn.LayerNorm(768, eps=1e-5)
        self.layers = nn.ModuleList([_Layer() for _ in range(12)])


class ContentVec(nn.Module):
    def __init__(self):
        super().__init__()
        self.feature_extractor = _FeatureExtractor()
        self.feature_projection = _FeatureProjection()
        self.encoder = _Encoder()
        self.final_proj = nn.Linear(768, 256)

    @classmethod
    def load(cls, path):
        state = torch.load(str(path), map_location="cpu", weights_only=True)
        prefix = "encoder.pos_conv_embed.conv."
        g = state.pop(prefix + "weight_g", None)
        v = state.pop(prefix + "weight_v", None)
        if g is None:  # newer transformers parametrisation names
            g = state.pop(prefix + "parametrizations.weight.original0")
            v = state.pop(prefix + "parametrizations.weight.original1")
        norm = v.pow(2).sum(dim=(0, 1), keepdim=True).sqrt()
        state[prefix + "weight"] = g * v / norm
        state.pop("masked_spec_embed", None)
        model = cls()
        model.load_state_dict(state, strict=True)
        model.eval()
        return model

    @torch.no_grad()
    def forward(self, wav16k, version="v2"):
        """wav16k: (1, samples) float tensor -> (1, frames, 768 or 256) at 50 frames/s."""
        x = self.feature_extractor(wav16k).transpose(1, 2)
        x = self.feature_projection(x)
        x = x + self.encoder.pos_conv_embed(x)
        x = self.encoder.layer_norm(x)
        n_layers = 12 if version == "v2" else 9
        for layer in self.encoder.layers[:n_layers]:
            x = layer(x)
        if version != "v2":
            x = self.final_proj(x)
        return x


def frames_for(samples: int) -> int:
    """Number of ContentVec frames for a 16 kHz input of `samples` length."""
    n = samples
    for k, s in zip([10, 3, 3, 3, 3, 2, 2], [5, 2, 2, 2, 2, 2, 2]):
        n = math.floor((n - k) / s) + 1
    return n
