"""
DOT —— 結構距離信心估計器(Tier 3:工程假設,目前不是神經網路)

DOT 不預測 divergence risk score 本身,只回答一個問題:
    「這個 genome 的結構,跟我們已經驗證過的形狀有多像?」

現階段已驗證樣本量(個位數到十位數)撐不起任何真正的學習器,所以這裡的
實作是「結構特徵的最近鄰距離」——概念上等同一個信心函數,但沒有訓練、
沒有梯度下降。等已驗證樣本累積到 24-36 筆以上、且橫跨多種 genome 形狀,
才有資格把這個最近鄰換成真正可訓練的神經元。在那之前,DOT 就是換了名字
的最近鄰查表,不要把它當神經網路用。

輸入特徵全部來自 genome 的結構,不碰語意內容:
    step_count            genome 的 step 數量
    duplicate_count        重複 step 名稱的次數
    constraint_types        rune 宣告的 constraint 類型集合(全域,非 per-step)
    constraint_count        constraint 總數
    has_mixed_constraints   是否同時宣告多種 constraint

輸出是 0~1 的信心值,不是風險分數:
    接近 1 —— 這個 genome 形狀跟已驗證案例非常相似,risk score 可信
    接近 0 —— 結構上是全新的形狀,risk score 本質是外推,別把它當真

2026-06-18 修正:extract_features() 原本假設 genome 是
{"steps": [{"name": ..., "constraints": [...]}, ...]} 這種「per-step
constraint」結構。對照 rune_loader.py / RFC-0001 / 現有 .rune 檔案後確認
這個假設不成立,且不是小出入:
  - genome 在真實格式裡只是一串 step 名稱字串(例如
    ["search", "analyze", "search", "summarize"]),重複的 step 直接
    出現在清單裡,不是巢狀的 dict 清單。
  - constraints 是 rune 層級的全域清單,套用到整個 genome,完全沒有
    「這個 constraint 只套用在某個 step」這種概念
    (build_system_prompt() 跟 divergence_linter.py 都是這樣處理)。
extract_features() 已改成直接吃 rune_loader.load_rune() 回傳的 Rune
dataclass instance,不再吃手刻的 dict;因為真實格式比原本假設的更簡單,
新版函式也變短了。__main__ 的 demo 也改成直接讀專案裡真實存在的
research.rune / coder.rune / multitool.rune / multitool_v2.rune,
不再用手刻的假資料。

已知限制 (b) 仍未處理:只有 2 個已驗證樣本時,_feature_scale() 的正規化
範圍極不穩定(任何一個樣本的數值都會直接定義整個刻度的上下界)。這個問題
本質上需要更多樣本才能緩解,不是這次修正的範圍——DOT 整合進
divergence_linter.py 仍照 roadmap 規劃,等 Stage 2(24-36 筆樣本、第三種
genome 形狀)完成後再做。
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rune_loader import Rune


@dataclass(frozen=True)
class GenomeFeatures:
    step_count: int
    duplicate_count: int
    constraint_types: frozenset
    constraint_count: int
    has_mixed_constraints: bool

    @property
    def has_duplicates(self) -> bool:
        return self.duplicate_count > 0


def extract_features(rune: "Rune") -> GenomeFeatures:
    """
    從一個已載入的 Rune 物件抽出 DOT 需要的結構特徵。

    rune 必須是 rune_loader.load_rune() 回傳的 Rune dataclass instance,
    不是原始 dict、也不是 yaml.safe_load() 的結果。

    per RFC-0001:
        rune.genome      —— 純字串清單,例如
                            ["search", "analyze", "search", "summarize"],
                            重複的 step 名稱直接出現在清單裡。
        rune.constraints —— 整個 rune 的全域清單,例如
                            ["cite_sources", "structured_output"]。
                            套用到全部 step,沒有「只套用某個 step」這種
                            概念。

    這個函式只依賴 rune.genome 跟 rune.constraints 這兩個屬性。如果
    RFC-0001 之後真的加入 per-step constraint,屆時只需要改這裡,不用動
    到 DOT 類別或下面的距離計算邏輯。
    """
    genome = rune.genome
    name_counts = Counter(genome)
    duplicate_count = sum(c - 1 for c in name_counts.values() if c > 1)

    constraints = rune.constraints or []
    constraint_types = frozenset(constraints)

    return GenomeFeatures(
        step_count=len(genome),
        duplicate_count=duplicate_count,
        constraint_types=constraint_types,
        constraint_count=len(constraints),
        has_mixed_constraints=len(constraint_types) > 1,
    )


def _jaccard_distance(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    inter = a & b
    return 1.0 - (len(inter) / len(union))


def _numeric_distance(a: GenomeFeatures, b: GenomeFeatures, scale: tuple[float, float, float]) -> float:
    # 用已驗證樣本裡各特徵的實際範圍做正規化,避免 step_count 這種
    # 量級天生比 duplicate_count 大的數字,在距離計算裡幫忙作弊。
    s_step, s_dup, s_con = scale
    d_step = abs(a.step_count - b.step_count) / s_step
    d_dup = abs(a.duplicate_count - b.duplicate_count) / s_dup
    d_con = abs(a.constraint_count - b.constraint_count) / s_con
    return math.sqrt(d_step**2 + d_dup**2 + d_con**2) / math.sqrt(3)


class DOT:
    """
    DOT 的最近鄰版本(Tier 3)。

    用法:
        dot = DOT()
        dot.add_validated(extract_features(load_rune("examples/research.rune")))
        dot.add_validated(extract_features(load_rune("examples/coder.rune")))
        result = dot.confidence(extract_features(load_rune("examples/multitool.rune")))
        # {'confidence': 0.41, 'nearest_distance': 0.52, 'n_validated_examples': 2}

    decay_scale / jaccard_weight 是還沒校準過的超參數,等真的累積到
    roadmap 定的 24-36 筆樣本,應該回頭用實際資料調整,不要假裝這兩個
    數字現在就是對的。
    """

    def __init__(self, decay_scale: float = 0.6, jaccard_weight: float = 0.5):
        self.examples: list[GenomeFeatures] = []
        self.decay_scale = decay_scale
        self.jaccard_weight = jaccard_weight

    def add_validated(self, features: GenomeFeatures) -> None:
        """記錄一個已驗證過的 genome 結構——不管它的 risk score 準不準,這筆都算數。"""
        self.examples.append(features)

    def _feature_scale(self) -> tuple[float, float, float]:
        steps = [e.step_count for e in self.examples]
        dups = [e.duplicate_count for e in self.examples]
        cons = [e.constraint_count for e in self.examples]
        return (
            (max(steps) - min(steps)) or 1,
            (max(dups) - min(dups)) or 1,
            (max(cons) - min(cons)) or 1,
        )

    def _distance(self, f: GenomeFeatures, ex: GenomeFeatures, scale) -> float:
        num_d = _numeric_distance(f, ex, scale)
        jac_d = _jaccard_distance(f.constraint_types, ex.constraint_types)
        return (1 - self.jaccard_weight) * num_d + self.jaccard_weight * jac_d

    def confidence(self, features: GenomeFeatures) -> dict:
        if not self.examples:
            return {
                "confidence": 0.0,
                "nearest_distance": None,
                "note": "尚無已驗證案例,DOT 無法判斷,等於完全外推",
            }
        scale = self._feature_scale()
        distances = [self._distance(features, ex, scale) for ex in self.examples]
        nearest = min(distances)
        raw_confidence = math.exp(-nearest / self.decay_scale)
        return {
            "confidence": round(max(0.0, min(1.0, raw_confidence)), 3),
            "nearest_distance": round(nearest, 3),
            "n_validated_examples": len(self.examples),
        }


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from rune_loader import load_rune

    examples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples")

    # 已驗證的基準:research.rune 跟 coder.rune 是 Stage 1 兩個成功案例
    # (correlation 0.967 等級),代表「DOT 應該給高信心」的形狀。
    research = load_rune(os.path.join(examples_dir, "research.rune"))
    coder = load_rune(os.path.join(examples_dir, "coder.rune"))

    # multitool.rune / multitool_v2.rune 是 Stage 1 暴露問題的形狀
    # (重複 search step + 混合 constraint),結構上明顯偏離前兩者。
    multitool = load_rune(os.path.join(examples_dir, "multitool.rune"))
    multitool_v2 = load_rune(os.path.join(examples_dir, "multitool_v2.rune"))

    dot = DOT()
    dot.add_validated(extract_features(research))
    dot.add_validated(extract_features(coder))

    print(f"已驗證案例數:{len(dot.examples)}")
    for label, rune in [
        ("research.rune(已驗證案例本身,信心應該很高)", research),
        ("multitool.rune(重複 search + 混合 constraint)", multitool),
        ("multitool_v2.rune(重複 search,只有 cite_sources)", multitool_v2),
    ]:
        result = dot.confidence(extract_features(rune))
        print(f"{label}: {result}")
