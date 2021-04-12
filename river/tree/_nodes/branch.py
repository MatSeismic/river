import abc
import dataclasses
import math
import typing

from river.base.typing import FeatureName
from river.stats import Var

from ..base import Branch


class HTBranch(Branch):
    def __init__(self, stats, *children, **attributes):
        super().__init__(*children)
        self.stats = stats
        self.__dict__.update(attributes)

    @property
    def total_weight(self):
        return sum(child.total_weight for child in filter(None, self.children))

    @property
    @abc.abstractmethod
    def max_branches(self):
        pass

    @abc.abstractmethod
    def most_common_path(self):
        pass


@dataclasses.dataclass(eq=False)
class BranchFactory:
    """Helper class used to assemble branches designed by the splitters."""

    feature: FeatureName
    split_info: typing.Union[typing.Hashable, typing.List[typing.Hashable]]
    children_stats: typing.List
    numerical_feature: bool
    multiway_split: bool

    def assemble(
        self,
        branch: typing.Type[HTBranch],
        stats: typing.Union[typing.Dict, Var],
        depth: int,
        *children,
        **kwargs
    ):
        return branch(stats, self.feature, self.split_info, depth, *children, **kwargs)


class NumericBinaryBranch(HTBranch):
    def __init__(self, stats, feature, threshold, depth, left, right, **attributes):
        super().__init__(stats, left, right, **attributes)
        self.feature = feature
        self.threshold = threshold
        self.depth = depth

    def next(self, x):
        left, right = self.children

        if x[self.feature] <= self.threshold:
            return left
        return right

    @property
    def max_branches(self):
        return 2

    def most_common_path(self):
        left, right = self.children

        if left.total_weight < right.total_weight:
            return right
        return left


class NominalBinaryBranch(HTBranch):
    def __init__(self, stats, feature, value, depth, left, right, **attributes):
        super().__init__(stats, left, right, **attributes)
        self.feature = feature
        self.value = value
        self.depth = depth

    def next(self, x):
        left, right = self.children

        if x[self.feature] == self.value:
            return left
        return right

    @property
    def max_branches(self):
        return 2

    def most_common_path(self):
        left, right = self.children

        if left.total_weight < right.total_weight:
            return right
        return left


class NumericMultiwayBranch(HTBranch):
    def __init__(
        self, stats, feature, radius, depth, slot_ids, *children, **attributes
    ):
        super().__init__(stats, *children, **attributes)
        # The number of branches can increase in runtime
        self.children = list(self.children)

        self.feature = feature
        self.radius = radius
        self.depth = depth

        # Controls the branch mapping
        self._mapping = {s: i for i, s in enumerate(slot_ids)}
        self._r_mapping = {i: s for s, i in self._mapping.items()}

    def next(self, x):
        slot = math.floor(x[self.feature] / self.radius)
        pos = self._mapping[slot]

        return self.children[pos]

    @property
    def max_branches(self):
        return -1

    def most_common_path(self):
        # Get the most traversed path
        pos = max(
            range(len(self.children)), key=lambda i: self.children[i].total_weight
        )

        return self.children[pos]

    def add_child(self, feature_val, child):
        slot = math.floor(feature_val / self.radius)

        self._mapping[slot] = len(self.children)
        self._r_mapping[len(self.children)] = slot
        self.children.append(child)


class NominalMultiwayBranch(HTBranch):
    def __init__(self, stats, feature, feature_values, depth, *children, **attributes):
        super().__init__(stats, *children, **attributes)
        # The number of branches can increase in runtime
        self.children = list(self.children)

        self.feature = feature
        self.depth = depth

        # Controls the branch mapping
        self._mapping = {feat_v: i for i, feat_v in enumerate(feature_values)}
        self._r_mapping = {i: feat_v for feat_v, i in self._mapping.items()}

    def next(self, x):
        pos = self._mapping[x[self.feature]]

        return self.children[pos]

    @property
    def max_branches(self):
        return -1

    def most_common_path(self):
        # Get the most traversed path
        pos = max(
            range(len(self.children)), key=lambda i: self.children[i].total_weight
        )

        return self.children[pos]

    def add_child(self, feature_val, child):
        self._mapping[feature_val] = len(self.children)
        self._r_mapping[len(self.children)] = feature_val
        self.children.append(child)