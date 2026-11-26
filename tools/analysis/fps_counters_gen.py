import csv
rows = {r['site']: r for r in csv.DictReader(open(r'work\fps_census\frame-locked.csv', encoding='ascii'))}
fs = sorted([r for r in rows.values() if r['kind'] == 'f32+reg' and r['mean60'] in ('0.03333', '0.01667')],
            key=lambda r: -int(r['visits60']))
# Sites that look like a frame adder but are not one; the census and the player's eyes found them (HANDOVER 61.5).
DROP = {
 '71000ed738': 'one half of a MIRRORED TIMER PAIR: [x19+800] accumulates while [x19+808] counts the other way, chosen by '
               'bit 1 of the state at [x19+8]; scaling only this half breaks the balance and the title twitches',
 '71000ed8dc': 'the store is fmax-clamped to a floor ([x19+804], constant 0x7100f658b0): fps_fs would turn the clamp into a '
               'half-speed approach instead of a snap',
}
f1 = sorted([r for r in rows.values() if r['kind'] == 'f32+reg' and r['mean60'] == '1' and r['site'] not in DROP],
            key=lambda r: -int(r['visits60']))
# batch 4: the per-entity float accumulators (50+ objects each). A phase or a state time advanced by a small amount a
# frame: scaling the increment by the step is fps_fs, and it cannot be a clamped counter or a progress test.
F4 = [
 '71007ff5b8',  # [x23+32]  3158 objects, +0.06667 a visit (2/30 s)
 # '7100922874',  # [x21+24] 901 objects, +0.006401 -- DROPPED: the census showed its |d| per visit going 0.006 -> 0.043
 #                # instead of halving; another writer touches the field, so it is not one accumulator (59.10)
 '710092bea8',  # [x8+72]    549 objects, +0.0001736
 '71009044f0',  # [x8+0]     160 objects, +0.04892
 '7100800b20',  # [x19+72]    64 objects, +0.003161
 '710080062c',  # [x19+104]   64 objects, +0.04004
 '7100800c98',  # [x19+24]    64 objects, +0.005594
 '7100800950',  # [x19+72]    64 objects, +0.003511
 '710086e960',  # [x19+16]    70 objects, +0.1
 '710086e9b4',  # [x19+16]    54 objects, +0.1
]
# batch 5: the per-entity integer counters of one a frame (an animation or state frame index per object).
F5 = ['710087a620', '710087a8c4', '710087a678']
# batch 6: the title screen's own frame counters (found by a census pair on the title, HANDOVER 61.6): the blink of the
# selection cursor is driven by one of these, at [x19+548] in two different UI objects.
F6 = [('710068cac4', 'int32+1', '[x19+548]'), ('7100644028', 'int32+1', '[x19+548]')]
def block(title, note, sites, extra=''):
    out = ['', '# ---- ' + title + ' (%d) -- %s' % (len(sites), note)]
    for s in sites:
        r = rows[s]
        out.append('%s   # %s %s, %s objects, mean %s a visit, func 0x%s%s'
                   % (s, r['kind'], r['field'], r['fields60'], r['mean60'], r['func'], extra))
    return out
CI_OK = ['71007572e0', '710033b254']
CI_BAD = {
 '7100005968': 'a REFERENCE COUNT: [x21+8] counts down, 0 calls the destructor at [x21]+8 (fired m_RefCount > 0 at boot)',
 '7100513554': 'the same reference-count template as 7100005968',
 '7100806f58': 'a countdown with expiry, but 0 through the sampled scenes (cannot be verified yet)',
 '71008b7668': 'the same (a countdown with expiry that only ticks inside some state)',
 '710081d3b8': 'a cooldown pair, also 0 in every sampled scene',
 '71007736b8': 'a linked-list loop counter: while (n--) node = node->next, one extra step dereferences null',
 '710078a258': 'the decremented value is a scaled index into a table ([x19+80] + value*[x21])',
 '710078a7fc': 'the same index pattern (12-byte records)',
 '710033cb1c': 'a stack index: the value picks [x22 + value*2 + 4112] and the pushed slot',
 '7100773e0c': 'a table index: [x22 + value + 0x16a8]',
 '71008b9408': 'an int64 loop counter of a division loop (umulh, modulo): arithmetic, not time',
 '7100772ec8': 'the pending-count of a lock-free queue (a bitmask CAS right above it)',
 '71006ed23c': 'a per-record counter of an array walk (x22 += 12 a step), a job budget',
 '71009404f0': 'a per-frame budget: how many items the loop processes this frame ([x9+325])',
 '7100922ae0': 'int16-1 of a register: the amount is not known at lift time (left for the manual pass)',
 '71009233e8': 'the same (+reg)',
 '710086f5f0': 'int32+reg, 9.55 a visit: a scaled value, not a frame count',
}
L = ['# Frame counters converted to the game time (HANDOVER 59): one "<store hex> [# what it counts]" per line.',
     '# The store addresses are the ones of build\\fps_sites.txt (the census list); the rule follows from the site kind:',
     '#   f32+1.0 / f32-1.0 -> fps_cf (a +-1.0 counter)      f32+reg -> fps_fs (the increment x the step)',
     '#   intN+k / intN-k   -> fps_ci (the frames due; a countdown never passes 0)      intN+reg -> skipped (unknown)',
     '# Every call returns the game own value at the native 30 Hz ([xc2] fps = 0), so this list is inert there.',
     '#',
     '# A frame-locked site is only a timer once its code says so: the batches below were read one by one (HANDOVER 59.3).',
     '# The census is the test (frame-locked -> scaled, mean per visit halved) and the boot is the other one.',
     '']
L += block('batch 1: float timers that add 1/30 s a frame', 'fps_fs', [r['site'] for r in fs])
L += block('batch 2: integer countdowns read and verified', 'fps_ci', CI_OK)
L += block('batch 3: float adders of +1.0 a frame', 'fps_fs', [r['site'] for r in f1])
L += block('batch 4: per-entity float accumulators (a phase or state time)', 'fps_fs', F4)
L += block('batch 5: per-entity integer frame counters', 'fps_ci', F5)
L.append('')
L.append('# ---- batch 6: the title screen counters of one a frame (%d) -- fps_ci' % len(F6))
for s, kind, field in F6:
    L.append('%s   # %s %s -- the title census pair found it frame-locked; the cursor blink runs twice as fast without it' % (s, kind, field))
L.append('')
L.append('# ---- not converted: a frame-locked value that is not a plain adder (read, and left alone)')
for s, why in DROP.items():
    r = rows.get(s)
    if r:
        L.append('# %s   # %s %s -- %s' % (s, r['kind'], r['field'], why))
L.append('')
L.append('# ---- not converted: frame-locked values that are not timers (read one by one, left alone)')
for s, why in CI_BAD.items():
    r = rows.get(s)
    if r:
        L.append('# %s   # %s %s -- %s' % (s, r['kind'], r['field'], why))
L.append('')
L.append('# ---- queue: the +1.0 float counter compared against exactly 1.0 (a progress value, not a timer)')
for r in sorted([r for r in rows.values() if r['kind'] in ('f32+1.0', 'f32-1.0')], key=lambda r: -int(r['visits60'])):
    L.append('# %s   # %s %s -- fcmp against 1.0 right after the store' % (r['site'], r['kind'], r['field']))
open(r'xc2\build\fps_counters.txt', 'w', encoding='ascii', newline='\n').write('\n'.join(L) + '\n')
n = len(fs) + len(CI_OK) + len(f1) + len(F4) + len(F5)
print('%d active: fs %d, ci %d, f1 %d, per-entity float %d, per-entity int %d' % (n, len(fs), len(CI_OK), len(f1), len(F4), len(F5)))