#pragma once
#include <algorithm>
#include <limits>
#include <unordered_map>
#include <unordered_set>
#include <vector>

// Score each existing helper once per target it can reach, either directly
// or as target = helper * fixed_factor +/- fixed_offset.
template<class I>
std::vector<I> rank_pending(std::vector<I> recent, const std::vector<I>& fixed,
                            const std::vector<I>& pending) {
    std::unordered_map<I, int> score;
    for (I v : recent) score.emplace(v, 0);
    for (I t : pending) {
        std::unordered_set<I> hits;
        auto mark = [&](I v) { if (score.count(v)) hits.insert(v); };
        for (I a : fixed) {
            mark(t-a);
            mark(a-t);
            if (t <= std::numeric_limits<I>::max()-a) mark(t+a);
            if (t % a == 0) mark(t/a);
            if (a % t == 0) mark(a/t);
            if (t <= std::numeric_limits<I>::max()/a) mark(t*a);
            for (I residual : fixed) {
                if (t > residual && (t-residual)%a == 0) mark((t-residual)/a);
                if (t <= std::numeric_limits<I>::max()-residual && (t+residual)%a == 0)
                    mark((t+residual)/a);
            }
        }
        for (I v : hits) ++score.at(v);
    }
    std::stable_sort(recent.begin(), recent.end(), [&](I a, I b) {
        return score.at(a) > score.at(b);
    });
    return recent;
}
