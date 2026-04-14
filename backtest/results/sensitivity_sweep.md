# Layer 1 Sensitivity Sweep

How much does the 83-tie hit rate move when we perturb each canonical
Poisson constant? If the model's edge lives on a knife-edge of some
parameter value, hit rate should wobble. If not, the 63.9% is robust.

## POISSON_AVG_GOALS

|   value |   hit_rate |   brier |   delta_hit_rate |
|--------:|-----------:|--------:|-----------------:|
|     2.3 |     0.6386 |  0.2207 |                0 |
|     2.5 |     0.6386 |  0.2207 |                0 |
|     2.7 |     0.6386 |  0.2207 |                0 |
|     2.9 |     0.6386 |  0.2207 |                0 |
|     3.1 |     0.6386 |  0.2207 |                0 |

**Spread across grid: 0.0pp**

## UCL_HOME_ADVANTAGE_ELO

|   value |   hit_rate |   brier |   delta_hit_rate |
|--------:|-----------:|--------:|-----------------:|
|      30 |     0.5904 |  0.2235 |          -0.0482 |
|      50 |     0.6386 |  0.2216 |           0      |
|      65 |     0.6386 |  0.2207 |           0      |
|      80 |     0.6145 |  0.2208 |          -0.0241 |
|     100 |     0.6386 |  0.2194 |           0      |

**Spread across grid: 4.8pp**

## KNOCKOUT_PENALTY_ADVANTAGE

|   value |   hit_rate |   brier |   delta_hit_rate |
|--------:|-----------:|--------:|-----------------:|
|   0.5   |     0.6386 |  0.2207 |                0 |
|   0.525 |     0.6386 |  0.2207 |                0 |
|   0.55  |     0.6386 |  0.2207 |                0 |
|   0.575 |     0.6386 |  0.2207 |                0 |
|   0.6   |     0.6386 |  0.2207 |                0 |

**Spread across grid: 0.0pp**
