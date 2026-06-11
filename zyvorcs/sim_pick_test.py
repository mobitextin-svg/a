#!/usr/bin/env python3
# sim_pick_test.py — verify SIM selection on the Google Messages "New chat" screen.
#
# It opens the New chat (recipient-entry) screen, taps the "With:" SIM chip,
# selects the SIM you ask for, then types the number. It STOPS before sending,
# so nothing is actually sent — this is only to confirm SIM selection works.
#
# Usage (phone connected, screen unlocked):
#     python sim_pick_test.py 7200275452 2
#     python sim_pick_test.py 7200275452 1
#     python sim_pick_test.py 7200275452 2 --serial <device-serial>
#
# Watch the console output. Dumps are saved as step_*.xml in this folder.

import re
import sys
import time
import subprocess

PKG = 'com.google.android.apps.messaging'


def adb(args, serial=None, timeout=25):
    base = ['adb'] + (['-s', serial] if serial else [])
    return subprocess.run(base + args, capture_output=True, text=True,
                          timeout=timeout, encoding='utf-8', errors='replace')


def log(msg):
    print(f'  {msg}', flush=True)


def dump(serial, tag):
    """Dump UI to a local file and return its XML text. Tolerates Vivo EACCES noise."""
    adb(['shell', 'uiautomator', 'dump', '/sdcard/_pick.xml'], serial)
    local = f'step_{tag}.xml'
    adb(['pull', '/sdcard/_pick.xml', local], serial)
    try:
        return open(local, encoding='utf-8', errors='replace').read()
    except Exception as e:
        log(f'could not read dump {local}: {e}')
        return ''


def nodes(xml):
    return re.findall(r'<node[^>]*>', xml)


def attr(node, name):
    m = re.search(rf'{name}="([^"]*)"', node)
    return m.group(1) if m else ''


def center(bounds):
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def tap(serial, xy, what):
    log(f'tap {what} at {xy}')
    adb(['shell', 'input', 'tap', str(xy[0]), str(xy[1])], serial)
    time.sleep(1.2)


def find_sim_chip(xml):
    """The 'With: SIM x' chip: clickable node inside the SimSelectorConversation container."""
    sel = None
    for n in nodes(xml):
        if 'SimSelectorConversation' in attr(n, 'resource-id'):
            sel = center(attr(n, 'bounds'))
    # Prefer the clickable child whose bounds sit inside the selector container.
    for n in nodes(xml):
        if attr(n, 'clickable') == 'true':
            c = center(attr(n, 'bounds'))
            if c and 400 <= c[1] <= 545 and 150 <= c[0] <= 460:
                return c
    return sel  # fallback to container center


def find_sim_option(xml, want):
    """Find the dropdown row for 'SIM {want}'. Picks the lowest match on screen
    (dropdown opens below the chip, so the option is lower than the chip label)."""
    target = f'SIM {want}'
    matches = []
    for n in nodes(xml):
        if attr(n, 'text').strip() == target:
            c = center(attr(n, 'bounds'))
            if c:
                matches.append(c)
    if not matches:
        return None
    matches.sort(key=lambda c: c[1])      # by y, top -> bottom
    return matches[-1]                    # lowest = the dropdown item


def chip_shows(xml):
    """Read what SIM the chip currently displays."""
    inside = []
    for n in nodes(xml):
        t = attr(n, 'text').strip()
        c = center(attr(n, 'bounds'))
        if c and re.match(r'SIM \d', t) and 400 <= c[1] <= 545:
            inside.append(t)
    return inside[0] if inside else '(unknown)'


def main():
    if len(sys.argv) < 3:
        print('usage: python sim_pick_test.py <number> <1|2> [--serial S]')
        sys.exit(1)
    number = sys.argv[1]
    want = sys.argv[2]
    serial = None
    if '--serial' in sys.argv:
        serial = sys.argv[sys.argv.index('--serial') + 1]

    print(f'\n=== SIM-pick test: number={number}  target=SIM {want} ===\n')

    log('1) opening New chat (recipient-entry) screen')
    # Empty smsto: lands on the new-message recipient screen with the With: chip.
    adb(['shell', 'am', 'start', '-a', 'android.intent.action.SENDTO',
         '-d', 'sms:', '-n',
         f'{PKG}/.ui.conversation.LaunchConversationActivity'], serial)
    time.sleep(2.5)
    xml = dump(serial, '1_open')
    if 'SimSelectorConversation' not in xml and 'ContactSearchField' not in xml:
        log('   that intent did not land on the recipient screen — trying plain SENDTO')
        adb(['shell', 'am', 'start', '-a', 'android.intent.action.SENDTO',
             '-d', 'sms:'], serial)
        time.sleep(2.5)
        xml = dump(serial, '1b_open')
    log(f'   chip currently shows: {chip_shows(xml)}')

    chip = find_sim_chip(xml)
    if not chip:
        log('   !! could not locate the SIM chip. Check step_1_open.xml')
        sys.exit(2)

    log('2) opening SIM dropdown')
    tap(serial, chip, 'With: chip')
    xml = dump(serial, '2_dropdown')

    opt = find_sim_option(xml, want)
    if not opt:
        log(f'   !! SIM {want} option not found in dropdown. Check step_2_dropdown.xml')
        sys.exit(3)

    log(f'3) selecting SIM {want}')
    tap(serial, opt, f'SIM {want} option')
    xml = dump(serial, '3_selected')
    log(f'   chip now shows: {chip_shows(xml)}')

    log('4) entering the number')
    # tap the To: field then type digits (ASCII — no special keyboard needed)
    for n in nodes(xml):
        if 'ContactSearchField' in attr(n, 'resource-id'):
            c = center(attr(n, 'bounds'))
            if c:
                tap(serial, c, 'To: field')
                break
    adb(['shell', 'input', 'text', number], serial)
    time.sleep(1.0)
    dump(serial, '4_number')

    print('\n=== DONE — nothing was sent. ===')
    print('Check on the phone: does the chip read "SIM', want, '" and the number is filled?')
    print('Dumps saved: step_1_open.xml, step_2_dropdown.xml, step_3_selected.xml, step_4_number.xml')
    print('If the chip shows the wrong SIM, send me step_2_dropdown.xml.\n')


if __name__ == '__main__':
    main()
