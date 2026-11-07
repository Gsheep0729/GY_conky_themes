"""Apply only the target Plasma validation/backend additions to the base launcher."""
from pathlib import Path


def adapted_launcher(source):
    needle="        if not match:raise RuntimeError('Configured internal connector is inactive; refusing external-screen fallback')"
    replacement="""        if not match:
            from plasma_compat import is_plasma_wayland, validate_fixed
            if is_plasma_wayland():return validate_fixed(cfg,heads)
            raise RuntimeError('Configured internal connector is inactive; refusing external-screen fallback')"""
    if source.count(needle)!=1:raise RuntimeError('Base launcher changed; review the Plasma patch')
    source=source.replace(needle,replacement)
    needle='    return make_classic_config(cfg, head, base, state)'
    replacement="    text=make_classic_config(cfg, head, base, state)\n    return text.replace('conky.config = {','conky.config = {\\n    out_to_x = true,\\n    out_to_wayland = false,',1)"
    if source.count(needle)!=1:raise RuntimeError('Base generator changed; review the backend patch')
    return source.replace(needle,replacement)
