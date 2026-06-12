#!/usr/bin/env python3
# sim_send_test.py — full send via the Google Messages "New chat" screen,
# choosing SIM 1 or SIM 2 explicitly. This is the flow we will fold into the
# bulk sender once confirmed.
#
# By default it DRY-RUNS: it does everything up to the send button but does NOT
# tap it (so nothing is sent). Add --send to actually send.
#
# Usage (phone connected, screen unlocked, screen-timeout set long):
#     python sim_send_test.py 7200275452 2 "Hello from SIM 2 test"
#     python sim_send_test.py 7200275452 2 "Hello" --send
#     python sim_send_test.py 7200275452 1 "Hi via SIM 1" --send --serial <serial>
#
# Notes:
#  - Message is typed with `adb shell input text`, which is ASCII-only. For
#    Tamil / emoji / newlines you need ADBKeyboard (the bulk sender already
#    handles that). For testing, use a plain ASCII message.

import re
import sys
import time
import subprocess

PKG = 'com.google.android.apps.messaging'


def adb(args, serial=None, timeout=25):
    base = ['adb'] + (['-s', serial] if serial else [])
    return subprocess.run(base + args, capture_output=True, text=True,
                          timeout=timeout, encoding='utf-8', errors='replace')


def log(m): print(f'  {m}', flush=True)


def dump(serial, tag):
    adb(['shell', 'uiautomator', 'dump', '/sdcard/_snd.xml'], serial)
    local = f'snd_{tag}.xml'
    adb(['pull', '/sdcard/_snd.xml', local], serial)
    try:
        return open(local, encoding='utf-8', errors='replace').read()
    except Exception as e:
        log(f'could not read {local}: {e}')
        return ''


def nodes(x): return re.findall(r'<node[^>]*>', x)
def attr(n, a):
    m = re.search(rf'{a}="([^"]*)"', n); return m.group(1) if m else ''


def center(b):
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
    if not m: return None
    x1, y1, x2, y2 = map(int, m.groups()); return (x1 + x2) // 2, (y1 + y2) // 2


def area(b):
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
    if not m: return 1 << 60
    x1, y1, x2, y2 = map(int, m.groups()); return (x2 - x1) * (y2 - y1)


def contains(b, pt):
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
    if not m: return False
    x1, y1, x2, y2 = map(int, m.groups())
    return x1 <= pt[0] <= x2 and y1 <= pt[1] <= y2


def tap(serial, xy, what):
    log(f'tap {what} at {xy}'); adb(['shell', 'input', 'tap', str(xy[0]), str(xy[1])], serial)
    time.sleep(1.3)


def find_sim_chip(x):
    for n in nodes(x):
        if attr(n, 'clickable') == 'true':
            c = center(attr(n, 'bounds'))
            if c and 400 <= c[1] <= 545 and 150 <= c[0] <= 470:
                return c
    for n in nodes(x):
        if 'SimSelectorConversation' in attr(n, 'resource-id'):
            return center(attr(n, 'bounds'))
    return None


def chip_shows(x):
    for n in nodes(x):
        t = attr(n, 'text').strip(); c = center(attr(n, 'bounds'))
        if c and re.match(r'SIM \d', t) and 400 <= c[1] <= 545:
            return t
    return '(unknown)'


def find_sim_option(x, want):
    target = f'SIM {want}'; matches = []
    for n in nodes(x):
        if attr(n, 'text').strip() == target:
            c = center(attr(n, 'bounds'))
            if c: matches.append(c)
    if not matches: return None
    matches.sort(key=lambda c: c[1]); return matches[-1]


def find_send_to_row(x):
    """Locate the 'Send to <number>' suggestion row and return the clickable
    row's center. Prefer the RCS row."""
    text_pt = None
    for n in nodes(x):
        if attr(n, 'text').strip().lower().startswith('send to'):
            text_pt = center(attr(n, 'bounds')); break
    if not text_pt:
        return None
    best = None
    for n in nodes(x):
        if attr(n, 'clickable') == 'true' and contains(attr(n, 'bounds'), text_pt):
            if best is None or area(attr(n, 'bounds')) < area(attr(best, 'bounds')):
                best = n
    return center(attr(best, 'bounds')) if best else text_pt


def find_compose(x):
    # Only accept an edit box in the BOTTOM part of the screen — the real
    # message composer. Never the To: search field at the top.
    for n in nodes(x):
        rid = attr(n, 'resource-id').lower()
        if 'ContactSearchField' in attr(n, 'resource-id'):
            continue
        if ('compose' in rid or 'message' in rid) and 'EditText' in attr(n, 'class'):
            c = center(attr(n, 'bounds'))
            if c and c[1] > 1400: return c
    for n in nodes(x):
        if 'ContactSearchField' in attr(n, 'resource-id'):
            continue
        if 'EditText' in attr(n, 'class') and attr(n, 'clickable') == 'true':
            c = center(attr(n, 'bounds'))
            if c and c[1] > 1400: return c
    return None


def find_next_fab(x):
    """The 'Next' button (MIRROR_EXTENDED_FAB_UI) that commits the recipient
    and opens the conversation."""
    for n in nodes(x):
        if 'MIRROR_EXTENDED_FAB_UI' in attr(n, 'resource-id') and attr(n, 'clickable') == 'true':
            c = center(attr(n, 'bounds'))
            if c: return c
    for n in nodes(x):
        if attr(n, 'text').strip().lower() == 'next':
            c = center(attr(n, 'bounds'))
            if c: return c
    return None


def find_send_button(x):
    for n in nodes(x):
        d = attr(n, 'content-desc').lower(); rid = attr(n, 'resource-id')
        if ('send' in d or 'Compose:Draft:Send' in rid):
            c = center(attr(n, 'bounds'))
            if c: return c
    return None


def main():
    if len(sys.argv) < 4:
        print('usage: python sim_send_test.py <number> <1|2> "<message>" [--send] [--serial S]')
        sys.exit(1)
    number, want, message = sys.argv[1], sys.argv[2], sys.argv[3]
    do_send = '--send' in sys.argv
    serial = sys.argv[sys.argv.index('--serial') + 1] if '--serial' in sys.argv else None

    print(f'\n=== send test: number={number} SIM={want} send={do_send} ===\n')

    log('1) open New chat screen')
    adb(['shell', 'am', 'start', '-a', 'android.intent.action.SENDTO', '-d', 'sms:'], serial)
    time.sleep(2.8)
    x = dump(serial, '1_open')
    if 'ContactSearchField' not in x:
        log('   !! New chat screen not detected — check snd_1_open.xml'); sys.exit(2)
    log(f'   chip shows: {chip_shows(x)}')

    log('2) open SIM dropdown')
    chip = find_sim_chip(x)
    if not chip: log('   !! SIM chip not found'); sys.exit(3)
    tap(serial, chip, 'With: chip')
    x = dump(serial, '2_dropdown')

    log(f'3) select SIM {want}')
    opt = find_sim_option(x, want)
    if not opt: log(f'   !! SIM {want} option not found — check snd_2_dropdown.xml'); sys.exit(4)
    tap(serial, opt, f'SIM {want}')
    x = dump(serial, '3_selected')
    log(f'   chip now shows: {chip_shows(x)}')

    log('4) type number')
    for n in nodes(x):
        if 'ContactSearchField' in attr(n, 'resource-id'):
            c = center(attr(n, 'bounds'))
            if c: tap(serial, c, 'To: field'); break
    adb(['shell', 'input', 'text', number], serial)
    time.sleep(1.2)
    x = dump(serial, '4_number')

    log('5) add recipient (tap "Send to" row)')
    row = find_send_to_row(x)
    if not row: log('   !! "Send to" row not found — check snd_4_number.xml'); sys.exit(5)
    tap(serial, row, '"Send to" row')
    time.sleep(1.0)
    x = dump(serial, '5_recipient')

    log('6) tap Next to open the conversation')
    nxt = find_next_fab(x)
    if not nxt: log('   !! Next button not found — check snd_5_recipient.xml'); sys.exit(6)
    tap(serial, nxt, 'Next')
    time.sleep(1.8)
    x = dump(serial, '6_conversation')

    log('7) type message')
    comp = find_compose(x)
    if comp:
        tap(serial, comp, 'compose box')
    else:
        log('   (compose box not pinpointed — blind tap near bottom)')
        tap(serial, (540, 1900), 'compose area (fallback)')
    adb(['shell', 'input', 'text', message.replace(' ', '%s')], serial)
    time.sleep(1.0)
    x = dump(serial, '7_typed')

    btn = find_send_button(x)
    if not btn:
        log('   !! send button not found — check snd_7_typed.xml'); sys.exit(7)

    if do_send:
        log('8) SEND')
        tap(serial, btn, 'send button')
        time.sleep(2.0)
        dump(serial, '8_sent')
        print('\n=== SENT (SIM', want, ') ===\n')
    else:
        log(f'8) DRY RUN — send button located at {btn}, NOT tapping.')
        print('\n=== DRY RUN done. Nothing sent. ===')
        print('Check the phone: conversation open, message typed, correct SIM.')
        print('Add --send to actually send. Dumps: snd_1..7.xml\n')


if __name__ == '__main__':
    main()
