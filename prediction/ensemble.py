"""Ensemble methods for combining model predictions."""

from __future__ import annotations

import numpy as np


def equal_weight_probs(
    model_probs: list[dict[str, float]],
) -> dict[str, float]:
    """Average probability vectors from multiple models."""
    keys = model_probs[0].keys()
    return {k: np.mean([m[k] for m in model_probs]) for k in keys}


def ensemble_tournament_probs(
    model_tournament_probs: dict[str, dict[str, dict[str, float]]],
    method: str = "equal_weight",
) -> dict[str, dict[str, float]]:
    """Ensemble tournament-level probabilities across models.

    Parameters
    ----------
    model_tournament_probs : {model_name: {team: {stage: probability}}}

    Returns
    -------
    {team: {stage: ensembled_probability}}
    """
    model_names = list(model_tournament_probs.keys())
    teams = list(model_tournament_probs[model_names[0]].keys())
    stages = list(model_tournament_probs[model_names[0]][teams[0]].keys())

    result = {}
    for team in teams:
        result[team] = {}
        for stage in stages:
            probs = [model_tournament_probs[mn][team][stage] for mn in model_names]
            result[team][stage] = float(np.mean(probs))

    return result
