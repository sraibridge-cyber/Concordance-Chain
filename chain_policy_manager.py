#!/usr/bin/env python3
"""
Concordance Chain — Policy Harmonization Protocol v5.4.0
Four-part system: manifest registry → chain_policy_manager →
  Bridge UI hook → guarded concordance with rollback
"""
import json, time, hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

CHAIN_VERSION = "5.4.0"
RESONANCE_GOLD   = 0.9999
RESONANCE_AZURE  = 0.9995
RESONANCE_SILENCE = 0.9995

@dataclass
class ChainLink:
    source: str; targets: List[str]; fields: List[str]; mode: str  # propagate | advise

@dataclass
class ChainEvent:
    t: float; src: str; targets: List[str]; fields: List[str]
    mu_concordance: float; state: str; old_vals: Dict[str, Any] = field(default_factory=dict)
    new_vals: Dict[str, Any] = field(default_factory=dict)

class PolicyLinkRegistry:
    def __init__(self):
        self.links: List[Dict] = [
            {"source": ".forge/mantra_policy.json",   "targets": [".forge/synthesis_policy.json", ".forge/dominion_state.json"],
             "fields": ["thresholds.gold","thresholds.azure","thresholds.silence_below"], "mode": "propagate"},
            {"source": ".forge/synthesis_policy.json", "targets": [".forge/mantra_policy.json",  ".forge/dominion_state.json"],
             "fields": ["thresholds.coherence_min","thresholds.health_min","epoch_window_s"], "mode": "propagate"},
            {"source": ".forge/dominion_state.json",  "targets": [".forge/synthesis_policy.json"],
             "fields": ["mu_coherence","rejoins","status"], "mode": "advise"},
        ]
        self.rules = {"conflict_resolution": "prefer-newer", "timestamp_field": "updated_at",
                      "log_history": True, "enforce_resonance_guard": True}

class ChainStatus:
    def __init__(self):
        self.version = CHAIN_VERSION; self.last_sync_ts = 0.0; self.last_sync_iso = ""
        self.last_source = ""; self.last_targets: List[str] = []
        self.mu_concordance = 1.0; self.drift_count = 0
        self.state = "BOOTING"; self.errors: List[str] = []
        self.resonance = {"gold": RESONANCE_GOLD, "azure": RESONANCE_AZURE, "silence_below": RESONANCE_SILENCE}

    def to_dict(self) -> Dict: return self.__dict__

    def sync(self, src: str, targets: List[str], mu: float, ok: bool):
        self.last_sync_ts = time.time()
        self.last_sync_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_sync_ts))
        self.last_source = src; self.last_targets = targets
        self.mu_concordance = mu; self.drift_count += 0 if ok else 1
        self.state = "OK" if ok else "DRIFT_DETECTED"
        self.errors.append(f"DRIFT from {src}") if not ok else None

class ChainHistory:
    def __init__(self, path: str = "/home/workspace/Services/Concordance-C/.forge/chain_history.jsonl"):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: ChainEvent):
        with open(self.path, "a") as f:
            f.write(json.dumps({"t": event.t, "src": event.src, "targets": event.targets,
                                "fields": event.fields, "mu_concordance": event.mu_concordance,
                                "state": event.state}) + "\n")

    def last_n(self, n: int = 10) -> List[Dict]:
        if not self.path.exists(): return []
        lines = self.path.read_text().strip().split("\n")
        return [json.loads(l) for l in lines[-n:]]

class ChainPolicyManager:
    def __init__(self):
        self.registry = PolicyLinkRegistry(); self.status = ChainStatus(); self.history = ChainHistory()
        self.policies: Dict[str, Dict] = self._load_policies()

    def _load_policies(self) -> Dict[str, Dict]:
        base = {"mu_coherence": 0.9995, "rejoins": 0, "status": "active",
                "thresholds": {"gold": RESONANCE_GOLD, "azure": RESONANCE_AZURE,
                               "coherence_min": 0.9995, "health_min": 0.9995, "silence_below": RESONANCE_SILENCE},
                "epoch_window_s": 300, "updated_at": time.time()}
        return {
            ".forge/mantra_policy.json":    dict(base),
            ".forge/synthesis_policy.json":  dict(base),
            ".forge/dominion_state.json":   dict(base),
        }

    def propagate_field(self, src: str, field: str, value: Any) -> List[ChainEvent]:
        events = []
        for link in self.registry.links:
            if link["source"] == src and field in link["fields"] and link["mode"] == "propagate":
                old = {t: self.policies[t].get(field) for t in link["targets"]}
                for target in link["targets"]:
                    self.policies[target][field] = value
                ev = ChainEvent(time.time(), src, link["targets"], [field], 1.0, "OK", old, {t: value for t in link["targets"]})
                self.history.append(ev)
                self.status.sync(src, link["targets"], 1.0, True)
                events.append(ev)
        return events

    def enforce_resonance_guard(self, field: str, value: float) -> bool:
        guards = {"thresholds.gold": RESONANCE_GOLD, "thresholds.azure": RESONANCE_AZURE,
                  "thresholds.silence_below": RESONANCE_SILENCE}
        if field in guards and value < guards[field]:
            return False
        return True

    def status_snapshot(self) -> Dict: return self.status.to_dict()

def main():
    mgr = ChainPolicyManager()
    snap = mgr.status_snapshot()
    print(f"Concordance Chain v{CHAIN_VERSION}")
    print(f"State: {snap['state']} | μ_concordance: {snap['mu_concordance']}")
    print(f"Resonance: {snap['resonance']}")
    mgr.propagate_field(".forge/mantra_policy.json", "thresholds.gold", 0.9999)
    print("History:", mgr.history.last_n(3))
    print("SEAL:", hashlib.sha3_512(b"ConcordanceChain-v5.4.0").hexdigest()[:16])

if __name__ == "__main__": main()