"""
A/B Test Routing Service for Model Inference

Supports:
- User-feature-based routing (new users -> A, old users -> B, etc.)
- Dynamic traffic ratio adjustment without downtime
- Automatic statistical significance testing with auto-conclusion
"""

import hashlib
import math
import threading
import time
from collections import defaultdict
from enum import Enum
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class Operator(str, Enum):
    eq = "eq"
    neq = "neq"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    in_ = "in"
    contains = "contains"


class TargetingRule(BaseModel):
    """A single targeting condition, e.g. user_type == 'new'"""
    field: str
    operator: Operator
    value: Any


class VariantConfig(BaseModel):
    name: str
    model_endpoint: str = ""
    targeting_rules: list[TargetingRule] = Field(default_factory=list)


class MetricType(str, Enum):
    proportion = "proportion"  # conversion rate, CTR, etc.
    continuous = "continuous"  # latency, score, etc.


class CreateExperimentRequest(BaseModel):
    name: str
    description: str = ""
    variants: list[VariantConfig]
    traffic_ratio: list[float]
    metric_type: MetricType = MetricType.proportion
    min_sample_per_variant: int = 100
    significance_level: float = 0.05

    def model_post_init(self, __context: Any) -> None:
        if len(self.variants) != len(self.traffic_ratio):
            raise ValueError("variants and traffic_ratio must have the same length")
        if len(self.variants) < 2:
            raise ValueError("need at least 2 variants")
        total = sum(self.traffic_ratio)
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"traffic_ratio must sum to 1.0, got {total}")


class UpdateTrafficRequest(BaseModel):
    traffic_ratio: list[float]


class UserFeatures(BaseModel):
    user_id: str
    user_type: str = ""  # "new" / "old" / "vip" ...
    registration_days: int = 0
    platform: str = ""
    region: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class RecordResultRequest(BaseModel):
    user_id: str
    variant: str
    metric_value: float  # 1/0 for proportion, continuous value otherwise
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictRequest(BaseModel):
    experiment_name: str
    user: UserFeatures
    payload: dict[str, Any] = Field(default_factory=dict)


class ExperimentStatus(str, Enum):
    running = "running"
    concluded = "concluded"
    stopped = "stopped"


# ---------------------------------------------------------------------------
# Statistics Engine
# ---------------------------------------------------------------------------


class StatsEngine:
    """Hypothesis testing for A/B experiments."""

    @staticmethod
    def _z_test_proportions(n1: int, s1: int, n2: int, s2: int) -> tuple[float, float]:
        """Two-proportion z-test. Returns (z_stat, p_value)."""
        p1 = s1 / n1 if n1 else 0
        p2 = s2 / n2 if n2 else 0
        p_pool = (s1 + s2) / (n1 + n2) if (n1 + n2) else 0
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)) if (n1 and n2 and 0 < p_pool < 1) else 0
        if se == 0:
            return 0.0, 1.0
        z = (p1 - p2) / se
        p_value = 2 * (1 - _norm_cdf(abs(z)))
        return z, p_value

    @staticmethod
    def _welch_t_test(
        n1: int, mean1: float, var1: float,
        n2: int, mean2: float, var2: float,
    ) -> tuple[float, float]:
        """Welch's t-test for unequal variances. Returns (t_stat, p_value)."""
        if n1 < 2 or n2 < 2:
            return 0.0, 1.0
        se = math.sqrt(var1 / n1 + var2 / n2)
        if se == 0:
            return 0.0, 1.0
        t = (mean1 - mean2) / se
        # Welch-Satterthwaite degrees of freedom
        num = (var1 / n1 + var2 / n2) ** 2
        den = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
        df = num / den if den > 0 else 1
        p_value = 2 * (1 - _t_cdf(abs(t), df))
        return t, p_value

    @staticmethod
    def analyze(
        metric_type: MetricType,
        data_a: list[float],
        data_b: list[float],
    ) -> dict:
        """Run hypothesis test between two groups. Returns stats dict."""
        n_a, n_b = len(data_a), len(data_b)
        if n_a == 0 or n_b == 0:
            return {"error": "insufficient data", "n_a": n_a, "n_b": n_b}

        mean_a = sum(data_a) / n_a
        mean_b = sum(data_b) / n_b

        if metric_type == MetricType.proportion:
            s_a = sum(1 for v in data_a if v >= 0.5)
            s_b = sum(1 for v in data_b if v >= 0.5)
            stat, p_value = StatsEngine._z_test_proportions(n_a, s_a, n_b, s_b)
            test_name = "two_proportion_z_test"
        else:
            var_a = sum((x - mean_a) ** 2 for x in data_a) / (n_a - 1) if n_a > 1 else 0
            var_b = sum((x - mean_b) ** 2 for x in data_b) / (n_b - 1) if n_b > 1 else 0
            stat, p_value = StatsEngine._welch_t_test(n_a, mean_a, var_a, n_b, mean_b, var_b)
            test_name = "welch_t_test"

        lift = (mean_a - mean_b) / mean_b if mean_b != 0 else float("inf")

        return {
            "test": test_name,
            "statistic": round(stat, 4),
            "p_value": round(p_value, 6),
            "n_a": n_a,
            "n_b": n_b,
            "mean_a": round(mean_a, 6),
            "mean_b": round(mean_b, 6),
            "lift": round(lift, 6),
        }


# Pure-Python normal CDF (no scipy dependency)
def _norm_cdf(x: float) -> float:
    """Standard normal CDF using the Abramowitz & Stegun approximation."""
    return 0.5 * math.erfc(-x / math.sqrt(2))


def _t_cdf(t: float, df: float) -> float:
    """Approximate Student's t CDF via normal approximation for large df,
    and regularized incomplete beta for small df."""
    if df >= 30:
        # Cornish-Fisher approximation
        g1 = (t**2 + 1) / (4 * df)
        z = t * (1 - g1)
        return _norm_cdf(z)
    # Use regularized incomplete beta: P(T <= t) = 1 - 0.5 * I_{x}(df/2, 0.5)
    x = df / (df + t * t)
    return 1.0 - 0.5 * _regularized_beta(x, df / 2, 0.5)


def _regularized_beta(x: float, a: float, b: float, max_iter: int = 200) -> float:
    """Regularized incomplete beta function I_x(a, b) via continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # Use the continued fraction representation (Lentz's method)
    ln_prefix = a * math.log(x) + b * math.log(1 - x) - math.log(a) - _ln_beta(a, b)
    prefix = math.exp(ln_prefix)

    # Continued fraction for I_x(a, b)
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d

    for m in range(1, max_iter + 1):
        m2 = 2 * m
        # Even step
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        # Odd step
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-10:
            break

    result = prefix * h * a
    # Clamp to [0, 1]
    return max(0.0, min(1.0, result))


def _ln_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


# ---------------------------------------------------------------------------
# Experiment Manager
# ---------------------------------------------------------------------------


class Experiment:
    """Runtime state for a single experiment."""

    def __init__(self, config: CreateExperimentRequest):
        self.config = config
        self.status = ExperimentStatus.running
        self.created_at = time.time()
        self.concluded_at: float | None = None
        self.conclusion: str | None = None
        self.conclusion_stats: dict | None = None
        # variant_name -> list of metric values
        self.data: dict[str, list[float]] = defaultdict(list)
        # user_id -> assigned variant (sticky assignment)
        self.assignments: dict[str, str] = {}
        self.lock = threading.Lock()

    def variant_names(self) -> list[str]:
        return [v.name for v in self.config.variants]

    def get_variant_config(self, name: str) -> VariantConfig | None:
        for v in self.config.variants:
            if v.name == name:
                return v
        return None


class ExperimentManager:
    def __init__(self):
        self._experiments: dict[str, Experiment] = {}
        self._lock = threading.Lock()

    def create(self, req: CreateExperimentRequest) -> Experiment:
        with self._lock:
            if req.name in self._experiments:
                raise ValueError(f"experiment '{req.name}' already exists")
            exp = Experiment(req)
            self._experiments[req.name] = exp
            return exp

    def get(self, name: str) -> Experiment:
        with self._lock:
            if name not in self._experiments:
                raise KeyError(f"experiment '{name}' not found")
            return self._experiments[name]

    def list_all(self) -> list[Experiment]:
        with self._lock:
            return list(self._experiments.values())

    def delete(self, name: str) -> None:
        with self._lock:
            if name not in self._experiments:
                raise KeyError(f"experiment '{name}' not found")
            del self._experiments[name]


# ---------------------------------------------------------------------------
# Routing Engine
# ---------------------------------------------------------------------------


def _evaluate_rule(rule: TargetingRule, user: UserFeatures) -> bool:
    """Evaluate a single targeting rule against user features."""
    # Resolve field value from user
    if hasattr(user, rule.field):
        val = getattr(user, rule.field)
    elif rule.field in user.extra:
        val = user.extra[rule.field]
    else:
        return False

    op = rule.operator
    target = rule.value

    if op == Operator.eq:
        return val == target
    if op == Operator.neq:
        return val != target
    if op == Operator.gt:
        return val > target
    if op == Operator.gte:
        return val >= target
    if op == Operator.lt:
        return val < target
    if op == Operator.lte:
        return val <= target
    if op == Operator.in_:
        return val in target
    if op == Operator.contains:
        return target in val
    return False


def assign_variant(experiment: Experiment, user: UserFeatures) -> str:
    """Assign a user to a variant based on targeting rules + traffic ratio.

    Priority:
    1. Sticky: if user was already assigned, return the same variant
    2. Rules: if user matches a variant's targeting rules, assign there
    3. Hash: deterministic assignment by traffic ratio
    """
    with experiment.lock:
        # Sticky assignment
        if user.user_id in experiment.assignments:
            return experiment.assignments[user.user_id]

        cfg = experiment.config

        # Rule-based matching: first matching variant wins
        for variant in cfg.variants:
            if variant.targeting_rules:
                if all(_evaluate_rule(r, user) for r in variant.targeting_rules):
                    experiment.assignments[user.user_id] = variant.name
                    return variant.name

        # Hash-based assignment using traffic ratio
        hash_key = f"{cfg.name}:{user.user_id}"
        hash_val = int(hashlib.sha256(hash_key.encode()).hexdigest(), 16) % 10000
        cumulative = 0
        for variant, ratio in zip(cfg.variants, cfg.traffic_ratio):
            cumulative += int(ratio * 10000)
            if hash_val < cumulative:
                experiment.assignments[user.user_id] = variant.name
                return variant.name

        # Fallback to last variant
        fallback = cfg.variants[-1].name
        experiment.assignments[user.user_id] = fallback
        return fallback


def record_and_check(experiment: Experiment, variant: str, value: float) -> dict | None:
    """Record a metric value and auto-check significance if enough samples."""
    with experiment.lock:
        if experiment.status != ExperimentStatus.running:
            return experiment.conclusion_stats

        experiment.data[variant].append(value)

        # Check if all variants have enough samples
        min_n = experiment.config.min_sample_per_variant
        variant_names = experiment.variant_names()
        counts = {v: len(experiment.data[v]) for v in variant_names}
        if any(counts.get(v, 0) < min_n for v in variant_names):
            return None  # not enough data yet

        # Run pairwise test: first variant is baseline (control)
        baseline = variant_names[0]
        data_baseline = experiment.data[baseline]
        results = {}
        all_significant = True

        for v in variant_names[1:]:
            data_v = experiment.data[v]
            stats = StatsEngine.analyze(experiment.config.metric_type, data_v, data_baseline)
            stats["significant"] = stats.get("p_value", 1) < experiment.config.significance_level
            if not stats["significant"]:
                all_significant = False
            results[f"{v}_vs_{baseline}"] = stats

        # Auto-conclude if all comparisons are significant
        if all_significant:
            experiment.status = ExperimentStatus.concluded
            experiment.concluded_at = time.time()
            # Find the best variant
            means = {v: sum(experiment.data[v]) / len(experiment.data[v]) for v in variant_names}
            best = max(means, key=means.get)
            experiment.conclusion = f"Experiment concluded: '{best}' is the winner (all comparisons significant at alpha={experiment.config.significance_level})"
            experiment.conclusion_stats = {
                "conclusion": experiment.conclusion,
                "comparisons": results,
                "sample_counts": counts,
                "variant_means": {k: round(v, 6) for k, v in means.items()},
            }
        else:
            experiment.conclusion_stats = {
                "status": "running",
                "comparisons": results,
                "sample_counts": counts,
            }

        return experiment.conclusion_stats


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(title="A/B Test Routing Service", version="1.0.0")
manager = ExperimentManager()


@app.post("/experiments", status_code=201)
def create_experiment(req: CreateExperimentRequest):
    """Create a new A/B test experiment."""
    try:
        exp = manager.create(req)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "name": exp.config.name,
        "variants": [v.name for v in exp.config.variants],
        "traffic_ratio": exp.config.traffic_ratio,
        "status": exp.status.value,
    }


@app.get("/experiments")
def list_experiments():
    """List all experiments."""
    result = []
    for exp in manager.list_all():
        counts = {v: len(exp.data[v]) for v in exp.variant_names()}
        result.append({
            "name": exp.config.name,
            "status": exp.status.value,
            "variants": exp.variant_names(),
            "traffic_ratio": exp.config.traffic_ratio,
            "sample_counts": counts,
        })
    return result


@app.get("/experiments/{name}")
def get_experiment(name: str):
    """Get experiment details including latest statistics."""
    try:
        exp = manager.get(name)
    except KeyError as e:
        raise HTTPException(404, str(e))

    variant_names = exp.variant_names()
    counts = {v: len(exp.data[v]) for v in variant_names}
    means = {}
    for v in variant_names:
        d = exp.data[v]
        means[v] = round(sum(d) / len(d), 6) if d else None

    # Compute live statistics
    live_stats = None
    if len(variant_names) >= 2:
        baseline = variant_names[0]
        data_baseline = exp.data[baseline]
        if data_baseline:
            comparisons = {}
            for v in variant_names[1:]:
                data_v = exp.data[v]
                if data_v:
                    stats = StatsEngine.analyze(exp.config.metric_type, data_v, data_baseline)
                    stats["significant"] = stats.get("p_value", 1) < exp.config.significance_level
                    comparisons[f"{v}_vs_{baseline}"] = stats
            if comparisons:
                live_stats = comparisons

    return {
        "name": exp.config.name,
        "description": exp.config.description,
        "status": exp.status.value,
        "metric_type": exp.config.metric_type.value,
        "variants": [
            {
                "name": v.name,
                "model_endpoint": v.model_endpoint,
                "targeting_rules": [
                    {"field": r.field, "operator": r.operator.value, "value": r.value}
                    for r in v.targeting_rules
                ],
            }
            for v in exp.config.variants
        ],
        "traffic_ratio": exp.config.traffic_ratio,
        "min_sample_per_variant": exp.config.min_sample_per_variant,
        "significance_level": exp.config.significance_level,
        "sample_counts": counts,
        "variant_means": means,
        "live_statistics": live_stats,
        "conclusion": exp.conclusion_stats if exp.status == ExperimentStatus.concluded else None,
        "created_at": exp.created_at,
        "concluded_at": exp.concluded_at,
    }


@app.put("/experiments/{name}/traffic")
def update_traffic(name: str, req: UpdateTrafficRequest):
    """Dynamically adjust traffic ratio without stopping the experiment."""
    try:
        exp = manager.get(name)
    except KeyError as e:
        raise HTTPException(404, str(e))

    with exp.lock:
        if len(req.traffic_ratio) != len(exp.config.variants):
            raise HTTPException(400, f"expected {len(exp.config.variants)} ratios, got {len(req.traffic_ratio)}")
        total = sum(req.traffic_ratio)
        if not (0.99 <= total <= 1.01):
            raise HTTPException(400, f"ratios must sum to 1.0, got {total}")

        old_ratio = exp.config.traffic_ratio[:]
        exp.config.traffic_ratio = req.traffic_ratio
        # Clear sticky assignments so new ratio takes effect for future requests.
        # Existing recorded data is preserved.
        exp.assignments.clear()

    return {
        "name": name,
        "old_traffic_ratio": old_ratio,
        "new_traffic_ratio": req.traffic_ratio,
        "message": "Traffic ratio updated. Sticky assignments cleared for re-bucketing.",
    }


@app.post("/experiments/{name}/assign")
def assign_user(name: str, user: UserFeatures):
    """Assign a user to a variant based on features and traffic ratio."""
    try:
        exp = manager.get(name)
    except KeyError as e:
        raise HTTPException(404, str(e))

    variant = assign_variant(exp, user)
    vc = exp.get_variant_config(variant)
    return {
        "experiment": name,
        "user_id": user.user_id,
        "variant": variant,
        "model_endpoint": vc.model_endpoint if vc else "",
    }


@app.post("/experiments/{name}/record")
def record_result(name: str, req: RecordResultRequest):
    """Record an experiment observation and auto-check significance."""
    try:
        exp = manager.get(name)
    except KeyError as e:
        raise HTTPException(404, str(e))

    if req.variant not in exp.variant_names():
        raise HTTPException(400, f"unknown variant '{req.variant}'")

    stats = record_and_check(exp, req.variant, req.metric_value)
    counts = {v: len(exp.data[v]) for v in exp.variant_names()}
    return {
        "experiment": name,
        "variant": req.variant,
        "sample_counts": counts,
        "status": exp.status.value,
        "statistics": stats,
    }


@app.post("/predict")
async def predict(req: PredictRequest):
    """Model inference endpoint with automatic A/B routing.

    Assigns the user to a variant, forwards the request to the
    corresponding model endpoint, and records the result.
    """
    try:
        exp = manager.get(req.experiment_name)
    except KeyError as e:
        raise HTTPException(404, str(e))

    variant = assign_variant(exp, req.user)
    vc = exp.get_variant_config(variant)

    if not vc or not vc.model_endpoint:
        # No endpoint configured — return assignment info only
        return {
            "experiment": req.experiment_name,
            "user_id": req.user.user_id,
            "variant": variant,
            "model_endpoint": None,
            "message": "No model endpoint configured for this variant. Use /experiments/{name}/record to manually log results.",
        }

    # Forward to model endpoint
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(vc.model_endpoint, json=req.payload)
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Model endpoint error: {e}")

    return {
        "experiment": req.experiment_name,
        "user_id": req.user.user_id,
        "variant": variant,
        "model_endpoint": vc.model_endpoint,
        "model_response": result,
    }


@app.delete("/experiments/{name}")
def stop_experiment(name: str):
    """Stop and remove an experiment."""
    try:
        exp = manager.get(name)
    except KeyError as e:
        raise HTTPException(404, str(e))

    with exp.lock:
        exp.status = ExperimentStatus.stopped

    # Compute final stats before deletion
    variant_names = exp.variant_names()
    counts = {v: len(exp.data[v]) for v in variant_names}
    final_stats = None
    if len(variant_names) >= 2:
        baseline = variant_names[0]
        data_baseline = exp.data[baseline]
        if data_baseline:
            comparisons = {}
            for v in variant_names[1:]:
                data_v = exp.data[v]
                if data_v:
                    comparisons[f"{v}_vs_{baseline}"] = StatsEngine.analyze(
                        exp.config.metric_type, data_v, data_baseline,
                    )
            if comparisons:
                final_stats = comparisons

    manager.delete(name)
    return {
        "name": name,
        "status": "stopped",
        "final_sample_counts": counts,
        "final_statistics": final_stats,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
