from __future__ import annotations
import argparse, json, struct, time, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.race_state_receiver import RaceStateReceiver

MAGIC=b'ARERPL01'; RH=struct.Struct('<dI')
# Keep every packet that can carry discrete race/rule/damage/setup/participant events.
ALWAYS={1,3,4,5,8,10,14,15}
# High-frequency families are sampled but retain original timestamps/order.
SAMPLED={0:20,2:8,6:8,7:8,11:8,12:8,13:20,16:20}

def iter_records(path):
    with open(path,'rb') as f:
        if f.read(len(MAGIC))!=MAGIC: raise ValueError('bad replay magic')
        while True:
            raw=f.read(RH.size)
            if not raw: break
            off,size=RH.unpack(raw); data=f.read(size)
            if len(data)!=size: raise ValueError('truncated replay')
            yield off,data

def run(path):
    receiver=RaceStateReceiver(tts_enabled=False,wheel_telemetry=False)
    counts=Counter(); kept=Counter(); seq=Counter(); total=0; processed=0
    start=time.perf_counter(); base=time.monotonic()
    last_off=0.0; observed={k:set() for k in ('opponent_strategy','undercut','overcut','safety_car_pit','vsc_pit','mandatory_compound_status','pit_window','weather_transition','wing_pit_threshold')}
    contexts=set(); strategy_samples=0
    for off,data in iter_records(path):
        total+=1; pid=int(data[6]) if len(data)>6 else -1; counts[pid]+=1; seq[pid]+=1
        keep=pid in ALWAYS or (pid in SAMPLED and seq[pid] % SAMPLED[pid]==0)
        if not keep: continue
        receiver.process_packet(data,('127.0.0.1',20777),base+off)
        kept[pid]+=1; processed+=1; last_off=off
        ext_now=receiver.engine.state.extended or {}
        adv_now=ext_now.get('advanced_strategy')
        if isinstance(adv_now,dict):
            strategy_samples+=1
            for k in observed:
                v=adv_now.get(k)
                if v is not None: observed[k].add(str(v))
        arb_now=ext_now.get('race_message_arbitration')
        if isinstance(arb_now,dict) and isinstance(arb_now.get('context'),dict):
            lv=arb_now['context'].get('level')
            if lv: contexts.add(str(lv))
    st=receiver.engine.state; ext=st.extended or {}
    strategy=ext.get('advanced_strategy'); arb=ext.get('race_message_arbitration')
    player=getattr(st,'player',None); session=getattr(st,'session',None)
    out={
      'recording':str(path),'total_packets':total,'processed_strategy_relevant_packets':processed,
      'packet_counts':dict(counts),'kept_counts':dict(kept),'recording_duration_s':last_off,
      'validation_runtime_s':round(time.perf_counter()-start,3),
      'session_type':str(getattr(getattr(session,'session_type',None),'name',getattr(session,'session_type',None))),
      'track':str(getattr(getattr(session,'track',None),'name',getattr(session,'track',None))),
      'current_lap':getattr(getattr(player,'lap',None),'current_lap',None) if player else None,
      'advanced_strategy':strategy,'race_message_arbitration':arb,
      'strategy_error':ext.get('advanced_strategy_error'),
      'measured_lap_count':len(getattr(st,'measured_laps',()) or ()),
      'strategy_samples_observed':strategy_samples,
      'observed_strategy_values':{k:sorted(v) for k,v in observed.items()},
      'observed_context_levels':sorted(contexts),
    }
    return out

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('replay'); ap.add_argument('--output',required=True); a=ap.parse_args()
    out=run(a.replay); Path(a.output).write_text(json.dumps(out,indent=2,default=str),encoding='utf-8'); print(json.dumps(out,indent=2,default=str))
