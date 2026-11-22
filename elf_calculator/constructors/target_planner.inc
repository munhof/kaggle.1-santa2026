// Included inside Tony Li's Puzzle structure by the practice experiment.
int capacity = 0, emitted = 0, dag_steps = 0;
vector<Int> residents, chosen;
set<Int> finished;
void load_value(Int v, vector<Int> locked = {}) {
    auto it = find(residents.begin(), residents.end(), v);
    if (it == residents.end()) {
        auto [a,b] = args.at(v);
        load_value(a,locked);
        auto pins=locked;
        pins.push_back(a);
        load_value(b,pins);
        // Rebuilding b can recursively evict a. Restore the operands together.
        if (find(residents.begin(),residents.end(),a)==residents.end())
            throw runtime_error("operand evicted");
        if (int(residents.size()) == capacity) {
            auto victim = find_if(residents.begin(), residents.end(), [&](Int x) {
                return find(locked.begin(),locked.end(),x)==locked.end() && find(starts.begin(),starts.end(),x)==starts.end();
            });
            if (victim == residents.end()) throw runtime_error("virtual bank full");
            residents.erase(victim);
        }
        ++emitted;
    } else residents.erase(it);
    residents.push_back(v);
}
vector<Int> leaves() const {
    if (capacity) return residents;
    vector<Int> result;
    set<Int> seen;
    auto add=[&](Int v){ if(seen.insert(v).second) result.push_back(v); };
    for(Int v:palette) add(v);
    for(Int v:starts) add(v);
    for(auto i=finished.rbegin();i!=finished.rend() && result.size()<52;++i) add(*i);
    for(auto i=order.rbegin();i!=order.rend() && result.size()<72;++i) add(*i);
    return result;
}
int cost() const {return capacity ? emitted : int(order.size());}
void take(Dictionary &d, Int t) {
    if(!defs.count(t)) build_target(d,t);
    if(capacity) load_value(t);
    finished.insert(t);
    chosen.push_back(t);
}
static int objective(int immediate,int remaining){return 5*immediate+2*remaining;}
void plan(int policy) {
    setup();
    if(capacity){
        residents=starts;
        for(Int v:order) load_value(v);
    }
    Dictionary d(limit), future(limit);
    while(chosen.size()<targets.size()){
        // Targets already produced incidentally require no new arithmetic.
        for(Int t:targets) if(!finished.count(t) && defs.count(t)){
            finished.insert(t);
            chosen.push_back(t);
        }
        if(chosen.size()==targets.size()) break;
        d.build(leaves());
        vector<pair<int,Int>> ranking;
        for(Int t:targets) if(!finished.count(t)){
            Puzzle trial=*this;
            trial.take(d,t);
            ranking.emplace_back(trial.cost()-cost(),t);
            if(!policy) break;
        }
        sort(ranking.begin(),ranking.end());
        Int selected=ranking.front().second;
        if(policy==2 && ranking.size()>1){
            pair<int,Int> best={INT_MAX,0};
            for(size_t i=0;i<min(size_t(6),ranking.size());++i){
                auto [price,t]=ranking[i];
                Puzzle trial=*this;
                trial.take(d,t);
                future.build(trial.leaves());
                int remaining=0;
                for(Int u:targets) if(!trial.defs.count(u)){
                    Puzzle after=trial;
                    after.take(future,u);
                    remaining+=after.cost()-trial.cost();
                }
                best=min(best,make_pair(objective(price,remaining),t));
            }
            selected=best.second;
        }
        take(d,selected);
    }
}
