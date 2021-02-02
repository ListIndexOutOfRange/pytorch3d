# Copyright (c) Facebook, Inc. and its affiliates. All rights reserved.
import torch


def sample_pdf(
    bins: torch.Tensor,
    weights: torch.Tensor,
    N_samples: int,
    det: bool = False,
    eps: float = 1e-5,
):
    """
    Samples a probability density functions defined by bin edges `bins` and
    the non-negative per-bin probabilities `weights`.

    Note: This is a direct conversion of the TensorFlow function from the original
    release [1] to PyTorch.

    Args:
        bins: Tensor of shape `(..., n_bins+1)` denoting the edges of the sampling bins.
        weights: Tensor of shape `(..., n_bins)` containing non-negative numbers
            representing the probability of sampling the corresponding bin.
        N_samples: The number of samples to draw from each set of bins.
        det: If `False`, the sampling is random. `True` yields deterministic
            uniformly-spaced sampling from the inverse cumulative density function.
        eps: A constant preventing division by zero in case empty bins are present.

    Returns:
        samples: Tensor of shape `(..., N_samples)` containing `N_samples` samples
            drawn from each set probability distribution.

    Refs:
        [1] https://github.com/bmild/nerf/blob/55d8b00244d7b5178f4d003526ab6667683c9da9/run_nerf_helpers.py#L183  # noqa E501
    """

    # Get pdf
    weights = weights + eps  # prevent nans
    pdf = weights / weights.sum(dim=-1, keepdim=True)
    cdf = torch.cumsum(pdf, -1)
    cdf = torch.cat([torch.zeros_like(cdf[..., :1]), cdf], -1)

    # Take uniform samples
    if det:
        u = torch.linspace(0.0, 1.0, N_samples, device=cdf.device, dtype=cdf.dtype)
        u = u.expand(list(cdf.shape[:-1]) + [N_samples]).contiguous()
    else:
        u = torch.rand(
            list(cdf.shape[:-1]) + [N_samples], device=cdf.device, dtype=cdf.dtype
        )

    # Invert CDF
    inds = torch.searchsorted(cdf, u, right=True)
    below = (inds - 1).clamp(0)
    above = inds.clamp(max=cdf.shape[-1] - 1)
    inds_g = torch.stack([below, above], -1).view(
        *below.shape[:-1], below.shape[-1] * 2
    )

    cdf_g = torch.gather(cdf, -1, inds_g).view(*below.shape, 2)
    bins_g = torch.gather(bins, -1, inds_g).view(*below.shape, 2)

    denom = cdf_g[..., 1] - cdf_g[..., 0]
    denom = torch.where(denom < eps, torch.ones_like(denom), denom)
    t = (u - cdf_g[..., 0]) / denom
    samples = bins_g[..., 0] + t * (bins_g[..., 1] - bins_g[..., 0])

    return samples