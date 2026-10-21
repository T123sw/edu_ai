"""Connect teaching-scene visibility to HyperFrames' native motion assertions."""
import json
import re


def write_visibility_assertions(directory, targets, timeline):
    if not isinstance(targets, dict):
        raise ValueError('Return visible_targets: {segment_id: ["#visible-title-or-diagram-container"]}')
    assertions = []
    for segment in timeline['segments']:
        selectors = targets.get(segment['id'])
        if not isinstance(selectors, list) or not selectors:
            raise ValueError('Missing visible teaching targets for segment ' + segment['id'])
        for selector in selectors:
            if not isinstance(selector, str) or not re.fullmatch(r'#[A-Za-z_][A-Za-z0-9_-]*', selector):
                raise ValueError('Visible targets must use unique CSS #ids on text or diagram containers')
            assertions.append({'kind': 'appearsBy', 'selector': selector, 'bySec': segment['end']})
    # Preserve authored native assertions, following upstream sidecar selection.
    sidecars = sorted(directory.glob('*.motion.json'))
    matching = [p for p in sidecars if p.with_name(p.name[:-len('.motion.json')] + '.html').is_file()]
    if len(matching) > 1:
        raise ValueError('Multiple composition motion sidecars: use one native project spec')
    path = (matching or sidecars or [directory / 'index.motion.json'])[0]
    spec = json.loads(path.read_text()) if path.is_file() else {'version': 1, 'assertions': []}
    if not isinstance(spec, dict) or not isinstance(spec.get('assertions'), list):
        raise ValueError('Invalid native motion spec')
    spec['assertions'].extend(a for a in assertions if a not in spec['assertions'])
    path.write_text(json.dumps(spec, ensure_ascii=False))
    return spec
