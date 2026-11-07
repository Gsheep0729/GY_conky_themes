"""Read-only Plasma Wayland connector validation for a fixed Xinerama index."""
import json
import math
import os
from conky_tree import run


def logical_rectangles(config):
    result={}
    for output in config.get('outputs',[]):
        if not output.get('connected') or not output.get('enabled',True):continue
        name=output['name'];scale=float(output.get('scale',1))
        if not math.isfinite(scale) or scale<=0:raise RuntimeError('Invalid KScreen scale')
        mode=next((m for m in output.get('modes',[]) if str(m.get('id'))==str(output.get('currentModeId'))),None)
        if not mode:raise RuntimeError('KScreen current mode missing for '+name)
        w=float(mode['size']['width'])/scale;h=float(mode['size']['height'])/scale
        if int(output.get('rotation',1)) in [2,8,32,128]:w,h=h,w
        pos=output['pos'];result[name]=(int(pos['x']),int(pos['y']),int(math.floor(w+.5)),int(math.floor(h+.5)))
        if min(result[name][2:])<=0:raise RuntimeError('Invalid KScreen mode size')
    if not result:raise RuntimeError('No enabled KScreen output')
    x=min(v[0] for v in result.values());y=min(v[1] for v in result.values())
    return {name:(r[0]-x,r[1]-y,r[2],r[3]) for name,r in result.items()}


def connector_rectangle(config,connector,heads):
    rects=logical_rectangles(config)
    if connector not in rects:raise RuntimeError('Internal connector '+connector+' is disabled or absent')
    if len(rects)!=len(heads):raise RuntimeError('KScreen/Xinerama output count differs; refusing ambiguous placement')
    native=rects[connector];observed=[(h['x'],h['y'],h['width'],h['height']) for h in heads]
    if len(set(observed))!=len(observed) or len(set(rects.values()))!=len(rects):
        raise RuntimeError('Mirrored output geometry is ambiguous')
    matches=[]
    for head in observed:
        factor=head[2]/native[2]
        if not .25<=factor<=4 or abs(head[3]-native[3]*factor)>1:continue
        scaled={name:tuple(int(math.floor(v*factor+.5)) for v in rect) for name,rect in rects.items()}
        # Validate the entire layout before accepting a global XWayland scale;
        # never infer an internal screen merely from one matching resolution.
        remaining=list(observed)
        good=True
        for rect in scaled.values():
            candidates=[i for i,v in enumerate(remaining) if all(abs(a-b)<=1 for a,b in zip(rect,v))]
            if len(candidates)!=1:good=False;break
            remaining.pop(candidates[0])
        if good and not remaining:matches.append(scaled[connector])
    unique=set(matches)
    if len(unique)!=1:raise RuntimeError('Cannot uniquely map KScreen internal connector to XWayland coordinates')
    return next(iter(unique))


def is_plasma_wayland():
    return os.environ.get('XDG_SESSION_TYPE')=='wayland' and ('KDE' in os.environ.get('XDG_CURRENT_DESKTOP','').split(':') or os.environ.get('KDE_FULL_SESSION')=='true')


def validate_fixed(cfg,heads):
    text=run(['kscreen-doctor','-j'],timeout=3)
    if not text:raise RuntimeError('Cannot read live KDE output information; fixed-screen validation stopped')
    try:expected=connector_rectangle(json.loads(text),cfg['expected_connector'],heads)
    except (ValueError,KeyError,TypeError,StopIteration) as error:raise RuntimeError('Invalid KScreen JSON: '+type(error).__name__) from error
    index=cfg['monitor_index']
    if index>=len(heads):raise RuntimeError('Fixed Xinerama index is absent')
    head=heads[index];actual=(head['x'],head['y'],head['width'],head['height'])
    if not all(abs(a-b)<=1 for a,b in zip(actual,expected)):
        raise RuntimeError('固定0号屏不对应 eDP-1 内屏，已停止；没有改编号或切到外屏。请用 --doctor 检查。')
    return head
