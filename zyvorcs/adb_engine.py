"""
ZyvoRCS Sender - ADB Engine v12
================================
RCS-ONLY: SMS is NEVER sent regardless of SIM mode.
  - send_rcs_message : detects channel before clipboard → skips if not RCS
  - send_via_newchat : detects channel after conversation open → skips if not RCS
  Contacts without RCS enabled are logged as ⏭️ Skipped.

v12 changes:
Zyvo Tools | adb_engine.py

Fixed in v11:
  - Clipboard is now set ONLY after RCS is confirmed.
    Before: clipboard was always set upfront (even for SMS-only contacts that get skipped).
    After:  open conversation → tap compose → detect channel →
            if RCS: set clipboard + paste + send
            if SMS: back out immediately (no clipboard touched)
    Result: cleaner log (no 'Clipboard: OK' before SMS-skip), faster skip path.

Fixed in v9/v10 (Vivo Funtouch OS / Android 13):
  - Replaced KEYCODE_TAB with direct compose field tap (88% screen height)
    TAB focus is unreliable on Vivo; direct tap always hits the field.
  - Replaced broken _set_clipboard (all 3 methods blocked on Android 13)
    Now uses adb push to write text file on device + Clipper broadcast.
    Falls back to input text if Clipper not installed.
  - Corner tap fallback raised from 96.3% to 91% to clear Vivo nav bar.

Fixed in v8:
  - dump_ok no longer trusts uiautomator returncode — vivo devices
    throw EACCES on /sys/board_info causing non-zero exit even when
    the dump succeeds. Now checks 'adb shell ls /sdcard/ui.xml' instead.
  - Added 'Compose:Draft:Send' to _find_send_button known resource IDs
    (confirmed from device UI dump — Google Messages Compose/RCS UI)
  - KEYCODE_BACK removed from _force_foreground loop — it was firing
    unconditionally and navigating back to conversation list even when
    the chat was already open, causing TAB+paste to land on home screen.

Fixed in v6/v7:
  - _force_foreground() — multi-method shade kill loop (up to 4 tries)
  - send_rcs_message uses -W -S flags for reliable launch
  - _find_send_button uses node-level attribute scanning (order-safe)
  - UTF-8 encoding on subprocess to fix Windows cp1252 Tamil decode crash
"""

import time
import random
import subprocess
import os
import re
import threading
from datetime import datetime

import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from bold_utils import _process_bold_markers

# ── SIM Mode Constants ────────────────────────────────────────────
SIM_MODE_SIM1   = 'sim1'
SIM_MODE_SIM2   = 'sim2'
SIM_MODE_ROTATE = 'rotate'
SIM_MODE_RANDOM = 'random'
SIM_MODE_AUTO   = 'auto'


# ═══════════════════════════════════════════════════════════════════
# DEVICE INFO
# ═══════════════════════════════════════════════════════════════════

def get_device_info(device):
    """Return brand, model, Android version for display in the UI"""
    df = ['-s', device] if device else []
    def prop(key):
        try:
            r = _adb(df + ['shell', 'getprop', key])
            return r.stdout.strip() if r.returncode == 0 else ''
        except Exception:
            return ''

    brand   = prop('ro.product.brand')
    model   = prop('ro.product.model')
    android = prop('ro.build.version.release')
    name    = f'{brand} {model}'.strip() if (brand or model) else 'Unknown Device'
    return {'name': name, 'brand': brand, 'model': model, 'android': android}


# ═══════════════════════════════════════════════════════════════════
# SIM DETECTION
# ═══════════════════════════════════════════════════════════════════

def get_sims(device):
    """
    Detect SIM slots and their REAL subscription IDs from the device.

    sub_id fix (v35):
      Previously hardcoded sub_ids = [1, 2].
      Now reads actual sub_ids from the device via:
        1. telephony.siminfo database (most reliable — returns real sub_ids)
        2. dumpsys telephony.registry (fallback — parses mSubId per slot)
        3. Default [1, 2] only as last resort

    The real sub_id is what Android uses to route via a specific SIM when
    passed as --ei subscription_id to the SENDTO intent.  Using the wrong
    sub_id silently falls back to the default SIM, making SIM 2 / rotation
    appear to always use SIM 1.
    """
    df = ['-s', device] if device else []
    sims = []

    # ── Step 1: SIM states ────────────────────────────────────────
    try:
        r = _adb(df + ['shell', 'getprop', 'gsm.sim.state'])
        states = [s.strip() for s in r.stdout.strip().split(',')]
    except Exception:
        states = ['UNKNOWN', 'UNKNOWN']

    # ── Step 2: Real sub_ids via content query (telephony DB) ─────
    # content://telephony/siminfo has icc_id, sim_slot_index, _id (= sub_id)
    real_sub_ids = {}   # slot_index → sub_id
    real_numbers = {}   # slot_index → MSISDN (may be blank on many ROMs)
    try:
        q = _adb(df + ['shell', 'content', 'query', '--uri',
                        'content://telephony/siminfo',
                        '--projection', 'sim_slot_index:_id:number'])
        # Output lines like:  Row: 0 sim_slot_index=0, _id=1, number=+9199...
        for line in (q.stdout or '').splitlines():
            slot_m = re.search(r'sim_slot_index=(\d+)', line)
            subid_m = re.search(r'_id=(\d+)', line)
            num_m = re.search(r'number=([^,]*)', line)
            if slot_m and subid_m:
                slot = int(slot_m.group(1))
                real_sub_ids[slot] = int(subid_m.group(1))
                if num_m:
                    real_numbers[slot] = (num_m.group(1) or '').strip()
    except Exception:
        pass

    # ── Step 3: Fallback — parse dumpsys telephony.registry ───────
    if not real_sub_ids:
        try:
            tr = _adb(df + ['shell', 'dumpsys', 'telephony.registry'])
            # Look for "mSubId=X" paired near "phoneId=Y"
            for m in re.finditer(r'phoneId=(\d+).*?mSubId=(\d+)', tr.stdout or '', re.DOTALL):
                slot, sub = int(m.group(1)), int(m.group(2))
                if sub > 0:   # sub_id=0 or negative = invalid
                    real_sub_ids.setdefault(slot, sub)
        except Exception:
            pass

    # ── Build result list ─────────────────────────────────────────
    try:
        for i, state in enumerate(states):
            active = state in ('READY', 'LOADED', 'APPLIST')
            # Use detected sub_id, fall back to slot+1 (historical default)
            sub_id = real_sub_ids.get(i, i + 1)
            sims.append({
                'slot':   i,
                'label':  f'SIM {i + 1}',
                'state':  state or 'UNKNOWN',
                'active': active,
                'sub_id': sub_id,
                'number': real_numbers.get(i, ''),
            })
    except Exception:
        sims = [
            {'slot': 0, 'label': 'SIM 1', 'state': 'UNKNOWN', 'active': True,  'sub_id': real_sub_ids.get(0, 1)},
            {'slot': 1, 'label': 'SIM 2', 'state': 'UNKNOWN', 'active': False, 'sub_id': real_sub_ids.get(1, 2)},
        ]

    return sims or [{'slot': 0, 'label': 'SIM 1', 'state': 'READY', 'active': True, 'sub_id': 1}]


# ═══════════════════════════════════════════════════════════════════
# FORCE FOREGROUND  (Funtouch OS shade killer)
# ═══════════════════════════════════════════════════════════════════

def _force_foreground(df, intent_cmd, dbg, max_tries=4):
    """
    Launch Google Messages hidden behind the home screen.

    Strategy:
      1. Go home so Messages starts behind it (never visible to user)
      2. Fire intent (no -S, no-animation)
      3. Immediately send HOME again to keep it buried
      4. Collapse statusbar as a safety measure
      5. Verify Messages is running (not necessarily focused — that's fine)
    """
    # Ensure home is showing before we launch
    _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_HOME'])
    time.sleep(0.3)

    # Fire the intent — app opens in background behind home screen
    _adb(intent_cmd)
    time.sleep(2.0)

    # Push home again immediately in case it surfaced
    _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_HOME'])
    time.sleep(0.3)
    _adb(df + ['shell', 'cmd', 'statusbar', 'collapse'])
    time.sleep(0.2)

    # Check Messages is running (focused on any window is fine — we don't
    # need it in the foreground, just alive so keyevents reach it)
    fg = _adb(df + ['shell', 'dumpsys', 'window', '|', 'grep', 'mCurrentFocus'])
    focus = fg.stdout.lower()
    dbg(f'Focus after hidden launch: {fg.stdout.strip()[:100]}')

    # Messages may or may not be the focused window — both are OK since
    # we send keyevents to the app directly via `am broadcast` or rely
    # on it being the most-recent task. Return True either way.
    return True


# ═══════════════════════════════════════════════════════════════════
# DIAGNOSTIC TEST  (called from /test_send endpoint)
# ═══════════════════════════════════════════════════════════════════

def run_diagnostic(device, mobile, message, device_pin=''):
    """
    Runs one test send with step-by-step results.
    Returns list of {step, result, ok} dicts.
    v6: includes raw XML snippet in send button step for debugging.
    """
    df    = ['-s', device] if device else []
    steps = []

    def step(name, fn):
        try:
            res = fn()
            ok  = res.returncode == 0 if hasattr(res, 'returncode') else True
            out = (res.stdout + res.stderr).strip() if hasattr(res, 'stdout') else str(res)
            steps.append({'step': name, 'result': out[:300] or 'OK', 'ok': ok})
            return ok
        except Exception as e:
            steps.append({'step': name, 'result': str(e), 'ok': False})
            return False

    def dbg_step(name, msg, ok=True):
        steps.append({'step': name, 'result': msg, 'ok': ok})

    # 1. ADB connection check
    step('ADB ping device',
         lambda: _adb(df + ['shell', 'echo', 'connected']))

    # 2. Wake + unlock
    step('Wake screen',
         lambda: _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_WAKEUP']))
    time.sleep(0.4)
    step('Collapse shade (pre-unlock)',
         lambda: _adb(df + ['shell', 'cmd', 'statusbar', 'collapse']))
    time.sleep(0.2)
    step('Dismiss keyguard',
         lambda: _adb(df + ['shell', 'wm', 'dismiss-keyguard']))
    time.sleep(0.6)

    # If device has a PIN/password, wm dismiss-keyguard won't work alone.
    # Swipe up to reveal the PIN field, then type the PIN + Enter.
    if device_pin:
        step('Swipe up to reveal PIN field',
             lambda: _adb(df + ['shell', 'input', 'swipe', '540', '1600', '540', '800', '200']))
        time.sleep(0.6)
        step(f'Enter PIN ({len(device_pin)} digits)',
             lambda: _adb(df + ['shell', 'input', 'text', device_pin]))
        time.sleep(0.3)
        step('Confirm PIN (Enter)',
             lambda: _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_ENTER']))
        time.sleep(0.8)

    # 3. Screen state
    step('Screen on check',
         lambda: _adb(df + ['shell', 'dumpsys', 'power', '|', 'grep', 'mHoldingDisplaySuspendBlocker']))

    # 4. Clipboard
    step('Set clipboard',
         lambda: _set_clipboard(df, message))
    time.sleep(0.3)

    # 5. Launch Messages in foreground (direct — same as bulk send)
    step('Launch Google Messages',
         lambda: _adb(df + [
             'shell', 'am', 'start', '-W',
             '--activity-no-animation',
             '-a', 'android.intent.action.SENDTO',
             '-d', f'smsto:{mobile}',
             '-p', 'com.google.android.apps.messaging',
             '--activity-clear-top',
         ]))
    time.sleep(2.0)

    # 6. Confirm Messages is in foreground
    fg_r = _adb(df + ['shell', 'dumpsys', 'window', '|', 'grep', 'mCurrentFocus'])
    fg_txt = fg_r.stdout.strip()
    in_fg = 'messaging' in fg_txt.lower() or 'messages' in fg_txt.lower()
    dbg_step('Foreground result',
             f'{"✅ Google Messages is in foreground" if in_fg else "⚠️ Messages may not be focused"}: {fg_txt[:120]}',
             True)

    # 7. Tap compose field (reliable on Vivo — TAB is not)
    _size_r = _adb(df + ['shell', 'wm', 'size'])
    _sw, _sh = 1080, 2400
    try:
        _sm = re.search(r'(\d+)x(\d+)', _size_r.stdout)
        if _sm:
            _sw, _sh = int(_sm.group(1)), int(_sm.group(2))
    except Exception:
        pass
    _cx, _cy = _sw // 2, int(_sh * 0.88)
    step(f'Tap compose field ({_cx},{_cy})',
         lambda: _adb(df + ['shell', 'input', 'tap', str(_cx), str(_cy)]))
    time.sleep(0.5)

    # 8. Paste
    step('Paste from clipboard',
         lambda: _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_PASTE']))
    time.sleep(0.5)

    # 9. Dump UI
    # NOTE: uiautomator dump exits non-zero on some devices (vivo EACCES on /sys/board_info)
    # even when the dump succeeds. Don't trust returncode — check file existence instead.
    step('uiautomator dump',
         lambda: _adb(df + ['shell', 'uiautomator', 'dump', '/sdcard/ui.xml']))
    time.sleep(1.0)
    xml_exists_r = _adb(df + ['shell', 'ls', '/sdcard/ui.xml'])
    dump_ok = xml_exists_r.returncode == 0 and 'ui.xml' in xml_exists_r.stdout

    # 10. Read XML + find button
    if dump_ok:
        try:
            dump_r = _adb(df + ['shell', 'cat', '/sdcard/ui.xml'])
            xml    = dump_r.stdout or ''   # null-safe: encoding errors return None on Windows

            if not xml.strip():
                dbg_step('UI XML is empty', 'Likely a Windows cp1252 decode issue — fixed in v7 via UTF-8 encoding', False)
            else:
                # Sanity check: warn if XML is from launcher not Messages
                if 'com.google.android.apps.messaging' not in xml and 'com.android.launcher' in xml:
                    dbg_step('⚠️ XML is from launcher, not Messages',
                             'Messages did not come to foreground — check intent/timing', False)
                # Show clickable nodes for debugging
                clickable_nodes = re.findall(r'<node[^>]*clickable="true"[^>]*/>', xml)
                snippet = '\n'.join(clickable_nodes[:15]) if clickable_nodes else xml[:400]
                dbg_step('Clickable nodes in XML (first 15)', snippet or '(empty)', bool(clickable_nodes))

                btn_bounds = _find_send_button(xml)
                if btn_bounds:
                    x, y = btn_bounds
                    steps.append({'step': f'Send button found at ({x},{y})', 'result': 'OK', 'ok': True})
                    step(f'Tap send button ({x},{y})',
                         lambda: _adb(df + ['shell', 'input', 'tap', str(x), str(y)]))
                else:
                    # Send button often cut off at screen edge in XML dump.
                    # Derive its position from the compose field: send button
                    # is always to the right of the text input at same vertical center.
                    compose_xy = _find_compose_field_send_pos(xml)
                    if compose_xy:
                        cx, cy = compose_xy
                        steps.append({'step': f'Send button derived from compose field at ({cx},{cy})',
                                      'result': 'OK', 'ok': True})
                        step(f'Tap send button ({cx},{cy})',
                             lambda: _adb(df + ['shell', 'input', 'tap', str(cx), str(cy)]))
                    else:
                        dbg_step('Send button NOT found in XML — KEYCODE_ENTER fallback',
                                 'Tip: check the Clickable nodes step above to find the right button', False)
                        step('Fallback: KEYCODE_ENTER',
                             lambda: _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_ENTER']))
        except Exception as e:
            steps.append({'step': 'Parse UI dump', 'result': str(e), 'ok': False})

    time.sleep(0.5)
    step('Go home', lambda: _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_HOME']))

    return steps


def get_ui_dump(device):
    """Return last saved UI dump XML from device (for browser inspection)"""
    df = ['-s', device] if device else []
    try:
        _adb(df + ['shell', 'uiautomator', 'dump', '/sdcard/ui_inspect.xml'])
        time.sleep(1.0)
        r = _adb(df + ['shell', 'cat', '/sdcard/ui_inspect.xml'])
        return r.stdout
    except Exception as e:
        return f'Error: {e}'


# ═══════════════════════════════════════════════════════════════════
# MAIN SEND LOOP
# ═══════════════════════════════════════════════════════════════════

def run_bulk_send(contacts, template, delay, device, status, lock, report_dir,
                  sim_mode=SIM_MODE_AUTO, sim1_sub_id=1, sim2_sub_id=2, device_pin='',
                  daily_limit=150, min_delay=45, max_delay=90,
                  batch_size=0, batch_pause=30, sim1_number='', sim2_number=''):

    if min_delay > max_delay:          # guard against swapped values
        min_delay, max_delay = max_delay, min_delay

    results    = []
    rotate_idx = 0
    watchdog   = WatchdogThread(device, status, lock)
    watchdog.start()

    # ── v36 SIM ENFORCEMENT ───────────────────────────────────────────
    # The SIM-mode selection only sticks if (a) we use the REAL sub_ids the
    # device assigns (not the UI's 1/2 guess) and (b) we set the OS default
    # SMS subscription before each send. The on-screen send button obeys the
    # OS default; the intent's --ei subscription_id alone does NOT.
    #
    # NOTE: this forces the SMS path onto the chosen SIM. RCS ("encrypted")
    # always rides the SIM provisioned for chat features in Google Messages
    # settings — that is a device-side toggle, not controllable from here.
    _df = ['-s', device] if device else []
    try:
        _sims = get_sims(device)
        _detected = {s['slot']: s['sub_id'] for s in _sims}
        _det_num = {s['slot']: s.get('number', '') for s in _sims}
        _r1 = _detected.get(0, sim1_sub_id)
        _r2 = _detected.get(1, sim2_sub_id)
        if (_r1, _r2) != (sim1_sub_id, sim2_sub_id):
            _log(status, lock,
                 f'🔧 Real sub_ids: SIM1={_r1}, SIM2={_r2} '
                 f'(UI sent {sim1_sub_id}/{sim2_sub_id}) — using real values')
        sim1_sub_id, sim2_sub_id = _r1, _r2
        # SIM phone numbers: prefer UI-provided, else device-detected (may be blank).
        sim1_number = (sim1_number or _det_num.get(0, '') or '').strip()
        sim2_number = (sim2_number or _det_num.get(1, '') or '').strip()
    except Exception as _e:
        _log(status, lock, f'⚠️  sub_id auto-detect failed: {_e} — using UI values')

    # Map sim_key (1/2/0) → that SIM's own phone number for the report.
    _sim_numbers = {1: sim1_number, 2: sim2_number, 0: ''}

    _forced_sub = {'v': None}
    def _force_sim(sub_id):
        """Set the device default SMS subscription so the send button uses it."""
        if sub_id is None or sub_id == _forced_sub['v']:
            return
        try:
            _adb(_df + ['shell', 'settings', 'put', 'global',
                        'multi_sim_sms', str(sub_id)])
            time.sleep(0.4)
            _forced_sub['v'] = sub_id
            _log(status, lock, f'🔧 Default SMS SIM → sub_id {sub_id}')
        except Exception as _e:
            _log(status, lock, f'⚠️  could not set default SMS SIM: {_e}')

    sim_label = {
        SIM_MODE_SIM1:   f'SIM 1 only (sub_id={sim1_sub_id})',
        SIM_MODE_SIM2:   f'SIM 2 only (sub_id={sim2_sub_id})',
        SIM_MODE_ROTATE: f'Rotation SIM1↔SIM2',
        SIM_MODE_RANDOM: f'Random SIM per contact',
        SIM_MODE_AUTO:   'Auto (device default)',
    }.get(sim_mode, sim_mode)
    _log(status, lock, f'📡 SIM Mode: {sim_label}')
    _log(status, lock, f'📊 Daily limit: {daily_limit}/SIM | Delay: {min_delay}–{max_delay}s (randomized)')
    if batch_size > 0:
        _log(status, lock, f'📦 Batch mode: pause {batch_pause}s after every {batch_size} sent messages')

    # Per-SIM daily send counters
    sim_sent = {1: 0, 2: 0, 0: 0}

    # Batch counter — counts only actual sends (not skips/fails)
    batch_count = 0

    try:
        for i, contact in enumerate(contacts):

            with lock:
                if status['stop_flag']:
                    _log(status, lock, '🛑 Stopped by user')
                    break

            while True:
                with lock:
                    paused = status['paused']
                if not paused:
                    break
                time.sleep(0.8)

            if sim_mode == SIM_MODE_SIM1:
                active_sub, sim_tag, sim_key = sim1_sub_id, '📶¹', 1
            elif sim_mode == SIM_MODE_SIM2:
                active_sub, sim_tag, sim_key = sim2_sub_id, '📶²', 2
            elif sim_mode == SIM_MODE_ROTATE:
                if rotate_idx % 2 == 0:
                    active_sub, sim_tag, sim_key = sim1_sub_id, '📶¹', 1
                else:
                    active_sub, sim_tag, sim_key = sim2_sub_id, '📶²', 2
                rotate_idx += 1
            elif sim_mode == SIM_MODE_RANDOM:
                # Random per contact: coin-flip SIM 1 or SIM 2 for each number.
                if random.random() < 0.5:
                    active_sub, sim_tag, sim_key = sim1_sub_id, '📶¹', 1
                else:
                    active_sub, sim_tag, sim_key = sim2_sub_id, '📶²', 2
            else:
                active_sub, sim_tag, sim_key = None, '📶', 0

            # Enforce the chosen SIM as the OS default SMS subscription.
            # Skipped in AUTO mode (active_sub is None → device default).
            _force_sim(active_sub)

            message = template
            for key, value in contact.items():
                message = message.replace('{' + key + '}', str(value))

            # Convert {bold}...{/bold} tags to Unicode bold glyphs
            message = _process_bold_markers(message)

            # Warn if any {placeholder} was not substituted
            import re as _re
            unfilled = _re.findall(r'\{[^}]+\}', message)
            if unfilled:
                _log(status, lock, f'⚠️  Unfilled placeholders: {unfilled} — check CSV column names match template')

            mobile = contact.get('mobile', '').strip()
            name   = contact.get('name', mobile) or mobile

            with lock:
                status['current'] = f'{sim_tag} {name} ({mobile})'

            _log(status, lock, f'{sim_tag} [{i+1}/{len(contacts)}] → {name} ({mobile})')

            # Daily limit check per SIM
            if sim_sent[sim_key] >= daily_limit:
                _log(status, lock, f'⚠️  SIM {sim_key} daily limit ({daily_limit}) reached — skipping {name}')
                with lock:
                    status['failed'] += 1
                continue

            if sim_key in (1, 2):
                # Explicit SIM mode (SIM1 / SIM2 / Rotation): use the New chat
                # screen picker so the chosen SIM is actually honored.
                send_state, err_msg = send_via_newchat(device, mobile, message,
                                                       want_sim=sim_key,
                                                       status=status, lock=lock,
                                                       device_pin=device_pin)
            else:
                # Auto mode: device default, original fast path.
                send_state, err_msg = send_rcs_message(device, mobile, message,
                                                       sub_id=active_sub,
                                                       status=status, lock=lock,
                                                       device_pin=device_pin)
            if send_state == 'sent':
                with lock:
                    status['sent'] += 1
                sim_sent[sim_key] += 1
                batch_count += 1
                _log(status, lock, f'✅ Sent {sim_tag} → {name} (SIM{sim_key}: {sim_sent[sim_key]}/{daily_limit})')
                # Batch pause: sleep after every N sent messages
                if batch_size > 0 and batch_count % batch_size == 0 and i < len(contacts) - 1:
                    _log(status, lock, f'📦 Batch of {batch_size} sent — pausing {batch_pause}s...')
                    for _ in range(batch_pause * 2):
                        with lock:
                            if status['stop_flag']:
                                break
                        time.sleep(0.5)
                    _log(status, lock, f'▶️  Batch pause done — resuming...')
            elif send_state == 'skipped':
                with lock:
                    status['skipped'] = status.get('skipped', 0) + 1
                _log(status, lock, f'⏭️  Skipped → {name} | {err_msg}')
            else:
                with lock:
                    status['failed'] += 1
                _log(status, lock, f'❌ Failed → {name} | {err_msg}')

            sim_used = (f'SIM{sim_key}' if sim_key else 'Auto')
            ok = (send_state == 'sent')
            result_status = {'sent': 'Sent', 'skipped': 'Skipped'}.get(send_state, 'Failed')
            results.append({
                'name': name, 'mobile': mobile, 'sim': sim_used,
                'sim_number': _sim_numbers.get(sim_key, ''),
                'status': result_status,
                'message': message,
                'time': datetime.now().strftime('%H:%M:%S'),
                'error': '' if ok else err_msg,
            })

            if i < len(contacts) - 1:
                with lock:
                    if status['stop_flag']:
                        break

                # Randomized delay to avoid carrier pattern detection
                rand_delay = random.randint(min_delay, max_delay)
                _log(status, lock, f'⏱️  Waiting {rand_delay}s before next message...')

                # Night-time warning (10PM–8AM)
                hour = datetime.now().hour
                if hour >= 22 or hour < 8:
                    _log(status, lock, '🌙 Warning: sending during night hours (10PM–8AM) — carrier may flag')

                for _ in range(rand_delay * 2):
                    with lock:
                        if status['stop_flag']:
                            break
                    time.sleep(0.5)

    except Exception as e:
        with lock:
            status['error'] = str(e)
        _log(status, lock, f'💥 Engine error: {e}')

    finally:
        watchdog.stop()
        _generate_report(results, report_dir)
        with lock:
            status['running'] = False
            status['current'] = ''
            s, f = status['sent'], status['failed']
        _log(status, lock, f'📊 Complete — Sent: {s} | Failed: {f}')


# ═══════════════════════════════════════════════════════════════════
# SIM-AWARE SEND  (v36) — New chat screen picker
# Opens Google Messages' "New chat" screen, explicitly selects SIM 1 or
# SIM 2 via the on-screen "With:" chip (the only place SIM choice is honored),
# enters the number, opens the conversation, then reuses the existing
# compose / clipboard / send-button helpers to deliver the message.
# Validated against live Funtouch/Vivo dumps.
# ═══════════════════════════════════════════════════════════════════

_MSGS_PKG = 'com.google.android.apps.messaging'


def _nc_nodes(xml):
    return re.findall(r'<node[^>]*>', xml or '')


def _nc_attr(node, name):
    m = re.search(rf'{name}="([^"]*)"', node)
    return m.group(1) if m else ''


def _nc_dump(df):
    """Dump UI and return XML text (handles Vivo EACCES noise)."""
    _adb(df + ['shell', 'uiautomator', 'dump', '/sdcard/_nc.xml'])
    time.sleep(0.5)
    return (_adb(df + ['shell', 'cat', '/sdcard/_nc.xml']).stdout) or ''


def _nc_tap(df, xy):
    _adb(df + ['shell', 'input', 'tap', str(xy[0]), str(xy[1])])
    time.sleep(1.2)


def _nc_find_sim_chip(xml):
    """Clickable 'With: SIM x' chip near the top of the New chat screen."""
    for n in _nc_nodes(xml):
        if _nc_attr(n, 'clickable') == 'true':
            c = _bounds_center(_nc_attr(n, 'bounds'))
            if c and 400 <= c[1] <= 545 and 150 <= c[0] <= 470:
                return c
    for n in _nc_nodes(xml):
        if 'SimSelectorConversation' in _nc_attr(n, 'resource-id'):
            return _bounds_center(_nc_attr(n, 'bounds'))
    return None


def _nc_chip_shows(xml):
    for n in _nc_nodes(xml):
        t = _nc_attr(n, 'text').strip()
        c = _bounds_center(_nc_attr(n, 'bounds'))
        if c and re.match(r'SIM \d', t) and 400 <= c[1] <= 545:
            return t
    return ''


def _nc_find_sim_option(xml, want):
    """Dropdown row for 'SIM {want}'. Lowest match on screen = the open option."""
    target = f'SIM {want}'
    hits = []
    for n in _nc_nodes(xml):
        if _nc_attr(n, 'text').strip() == target:
            c = _bounds_center(_nc_attr(n, 'bounds'))
            if c:
                hits.append(c)
    if not hits:
        return None
    hits.sort(key=lambda c: c[1])
    return hits[-1]


def _nc_find_to_field(xml):
    for n in _nc_nodes(xml):
        if 'ContactSearchField' in _nc_attr(n, 'resource-id'):
            return _bounds_center(_nc_attr(n, 'bounds'))
    return None


def _nc_find_send_to_row(xml):
    """The 'Send to <number>' suggestion row; return its clickable centre."""
    text_pt = None
    for n in _nc_nodes(xml):
        if _nc_attr(n, 'text').strip().lower().startswith('send to'):
            text_pt = _bounds_center(_nc_attr(n, 'bounds'))
            break
    if not text_pt:
        return None
    best, best_area = None, 1 << 60
    for n in _nc_nodes(xml):
        if _nc_attr(n, 'clickable') != 'true':
            continue
        b = _nc_attr(n, 'bounds')
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if not m:
            continue
        x1, y1, x2, y2 = map(int, m.groups())
        if x1 <= text_pt[0] <= x2 and y1 <= text_pt[1] <= y2:
            a = (x2 - x1) * (y2 - y1)
            if a < best_area:
                best, best_area = (_bounds_center(b)), a
    return best or text_pt


def _nc_find_next(xml):
    """The 'Next' FAB that commits the recipient and opens the conversation."""
    for n in _nc_nodes(xml):
        if 'MIRROR_EXTENDED_FAB_UI' in _nc_attr(n, 'resource-id') and _nc_attr(n, 'clickable') == 'true':
            c = _bounds_center(_nc_attr(n, 'bounds'))
            if c:
                return c
    for n in _nc_nodes(xml):
        if _nc_attr(n, 'text').strip().lower() == 'next':
            return _bounds_center(_nc_attr(n, 'bounds'))
    return None


def send_via_newchat(device, mobile, message, want_sim, status=None, lock=None,
                     device_pin=''):
    """
    Send `message` to `mobile` forcing SIM `want_sim` (1 or 2) via the
    New chat screen SIM picker.  RCS-ONLY — if the conversation resolves to
    SMS/MMS the contact is skipped immediately; no message is ever sent via SMS.
    Returns (status_str, msg) with status_str in {'sent','skipped','failed'}.
    """
    df = ['-s', device] if device else []

    def dbg(m):
        if status and lock:
            _log(status, lock, f'   ↳ {m}')

    ime_available, original_ime = False, ''
    try:
        # 1) Wake + unlock
        _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'])
        time.sleep(0.4)
        _adb(df + ['shell', 'cmd', 'statusbar', 'collapse'])
        _adb(df + ['shell', 'wm', 'dismiss-keyguard'])
        time.sleep(0.5)
        if device_pin:
            _adb(df + ['shell', 'input', 'swipe', '540', '1600', '540', '800', '200'])
            time.sleep(0.6)
            _adb(df + ['shell', 'input', 'text', device_pin])
            _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_ENTER'])
            time.sleep(0.8)

        # 2) Open the New chat (recipient-entry) screen
        _adb(df + ['shell', 'am', 'start', '-a', 'android.intent.action.SENDTO',
                   '-d', 'sms:'])
        time.sleep(2.5)
        xml = _nc_dump(df)
        if 'ContactSearchField' not in xml:
            return 'failed', 'New chat screen did not open'

        # 3) Open the SIM dropdown and pick the wanted SIM
        chip = _nc_find_sim_chip(xml)
        if not chip:
            return 'failed', 'SIM chip not found on New chat screen'
        _nc_tap(df, chip)
        xml = _nc_dump(df)
        opt = _nc_find_sim_option(xml, want_sim)
        if not opt:
            return 'failed', f'SIM {want_sim} option not found in dropdown'
        _nc_tap(df, opt)
        xml = _nc_dump(df)
        shown = _nc_chip_shows(xml)
        if shown != f'SIM {want_sim}':
            dbg(f'warning: chip shows "{shown}" after selecting SIM {want_sim}')
        else:
            dbg(f'SIM {want_sim} selected ✓')

        # 4) Enter the number
        to_field = _nc_find_to_field(xml)
        if to_field:
            _nc_tap(df, to_field)
        _adb(df + ['shell', 'input', 'text', re.sub(r'\D', '', mobile)])
        time.sleep(1.0)
        xml = _nc_dump(df)

        # 5) Commit recipient + open conversation
        row = _nc_find_send_to_row(xml)
        if not row:
            return 'failed', '"Send to" suggestion not found'
        _nc_tap(df, row)
        time.sleep(0.8)
        xml = _nc_dump(df)
        nxt = _nc_find_next(xml)
        if not nxt:
            return 'failed', 'Next button not found'
        _nc_tap(df, nxt)
        time.sleep(1.6)

        # 6) Focus compose box (bottom of screen) and inject the message
        xml = _nc_dump(df)
        compose_xy = _find_compose_field_box(xml)
        if compose_xy:
            _nc_tap(df, compose_xy)
        else:
            _adb(df + ['shell', 'input', 'tap', '540', '1900'])  # fallback
            time.sleep(0.8)

        # ── RCS-ONLY GATE ────────────────────────────────────────────
        # Detect the channel BEFORE touching the clipboard.
        # If the conversation is SMS/MMS skip it immediately — this app
        # is RCS-only and will never fall back to SMS.
        rcs_state = 'unknown'
        for _attempt in range(4):
            xml = _nc_dump(df)
            rcs_state = _detect_rcs_state(xml)
            dbg(f'RCS check {_attempt+1}: {rcs_state}')
            if rcs_state in ('rcs', 'sms'):
                break
            time.sleep(1.2)
        if rcs_state != 'rcs':
            dbg(f'⏭️  Not RCS (channel={rcs_state}) — skipping, SMS will NOT be sent')
            _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_BACK'])
            time.sleep(0.3)
            return 'skipped', f'RCS not enabled (channel={rcs_state})'
        dbg('✅ RCS confirmed — proceeding to send')
        # ── END RCS GATE ─────────────────────────────────────────────

        injected = False
        # Prefer clipboard paste (Unicode-safe when Clipper is present)
        if _set_clipboard(df, message):
            _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_PASTE'])
            time.sleep(0.8)
            injected = _compose_has_text(_nc_dump(df))
        if not injected:
            ime_available, original_ime = _ensure_adb_keyboard(df)
            if ime_available:
                if compose_xy:
                    _nc_tap(df, compose_xy)
                _type_via_adbkeyboard(df, message)
                time.sleep(0.9)
                injected = _compose_has_text(_nc_dump(df))
        if not injected:
            # ASCII last resort
            _adb(df + ['shell', 'input', 'text', _escape_for_adb(message)])
            time.sleep(0.7)
            injected = _compose_has_text(_nc_dump(df))
        if not injected:
            return 'failed', 'message never entered the compose box'

        # 7) Send
        xml = _nc_dump(df)
        send_btn = _find_send_button(xml)
        if not send_btn:
            return 'failed', 'send button not found'
        _nc_tap(df, send_btn)
        time.sleep(1.8)

        return 'sent', ''

    except Exception as e:
        return 'failed', f'newchat send error: {e}'
    finally:
        _restore_ime(df, original_ime)
        _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_HOME'])


# ═══════════════════════════════════════════════════════════════════
# CORE SEND  v6 — aggressive shade kill
# ═══════════════════════════════════════════════════════════════════

def send_rcs_message(device, mobile, message, sub_id=None, status=None, lock=None,
                     device_pin='', require_rcs=True):
    """
    v11 send flow (RCS detect FIRST, clipboard only when needed):
    1. Wake + unlock
    2. Open the conversation via SENDTO intent (carries subscription_id → SIM)
    3. Tap compose field (no paste yet) + UIAutomator dump → DETECT channel
         - SMS only   → back out immediately, NO clipboard used  → ('skipped', 'no RCS')
         - RCS active → set clipboard + paste + tap send button  → ('sent', '')
       (When require_rcs is False, clipboard is set before open — legacy behaviour.)
    4. Go home

    Returns (status_str, msg) where status_str ∈ {'sent','skipped','failed'}.
    Clipboard is only touched when RCS is confirmed, eliminating wasted
    clipboard operations on SMS-only contacts.
    """
    df = ['-s', device] if device else []

    def dbg(msg):
        if status and lock:
            _log(status, lock, f'   ↳ {msg}')

    try:
        # ── Step 1: Wake + unlock ────────────────────────────────
        _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'])
        time.sleep(0.4)
        _adb(df + ['shell', 'cmd', 'statusbar', 'collapse'])
        time.sleep(0.2)
        _adb(df + ['shell', 'wm', 'dismiss-keyguard'])
        time.sleep(0.5)
        if device_pin:
            # PIN/pattern lock — swipe up to reveal input, type PIN, confirm
            _adb(df + ['shell', 'input', 'swipe', '540', '1600', '540', '800', '200'])
            time.sleep(0.6)
            _adb(df + ['shell', 'input', 'text', device_pin])
            time.sleep(0.3)
            _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_ENTER'])
            time.sleep(0.8)

        # ── Step 2: Build intent ──────────────────────────────────
        # Encode the full message into the smsto: URI as a percent-encoded
        # `body=` parameter.  This is the only method that survives newlines,
        # emoji (including multi-codepoint flags like 🇮🇳), Tamil, and any
        # other Unicode through `am start` without corruption or truncation.
        #
        # Why not --es sms_body?  Android's `am` tool splits the extra value
        # at the first newline, so only the first line reaches the compose box.
        # URI encoding avoids that entirely — %0A is preserved verbatim and
        # Google Messages decodes the full body on receipt.
        from urllib.parse import quote as _url_quote
        _body_enc = _url_quote(message, safe='')
        _smsto_uri = f'smsto:{mobile}?body={_body_enc}'
        intent_cmd = df + [
            'shell', 'am', 'start', '-W',
            '--activity-no-animation',
            '-a', 'android.intent.action.SENDTO',
            '-d', _smsto_uri,             # ← full Unicode body in URI (newlines, emoji OK)
            '-p', 'com.google.android.apps.messaging',
            '--activity-clear-top',
        ]
        if sub_id is not None:
            intent_cmd += ['--ei', 'subscription_id', str(sub_id)]

        # Screen size — only used as a LAST-RESORT fallback tap if the real
        # compose box can't be located in the dump.
        _size_r = _adb(df + ['shell', 'wm', 'size'])
        _sw, _sh = 1080, 2208
        try:
            _sm = re.search(r'(\d+)x(\d+)', _size_r.stdout)
            if _sm:
                _sw, _sh = int(_sm.group(1)), int(_sm.group(2))
        except Exception:
            pass
        _fallback_x = _sw // 2
        _fallback_y = int(_sh * 0.88)

        # ── Steps 3–4: open conversation, focus the REAL box, detect channel ──
        # IMPORTANT: we tap the compose box at its ACTUAL bounds read from the
        # dump (not a blind 88%-height tap). The old blind tap landed below the
        # box on the mic/voice area, opening the voice recorder and leaving the
        # box unfocused — so paste went nowhere and the bottom-right "button"
        # was the microphone, not Send. Tapping the real box fixes all of that.
        # Retry up to 3× in case Google Messages lands on the inbox list.
        state, xml = 'unknown', ''
        compose_xy = None
        for open_attempt in range(3):
            _adb(intent_cmd)
            time.sleep(2.0)

            # Tap the fallback compose-bar position immediately on open so the
            # field is focused before we dump. Without this, sms_body intent
            # can leave the compose bar unfocused and resource-id may be absent.
            _adb(df + ['shell', 'input', 'tap', str(_fallback_x), str(_fallback_y)])
            time.sleep(0.4)

            # Now dump — compose field should be focused and visible.
            xml = _dump_ui(df)
            compose_xy = _find_compose_field_box(xml)
            tap_x, tap_y = compose_xy if compose_xy else (_fallback_x, _fallback_y)
            if compose_xy:
                # Re-tap at the REAL position if we found it
                _adb(df + ['shell', 'input', 'tap', str(tap_x), str(tap_y)])
                time.sleep(0.3)
            dbg(f'Open attempt {open_attempt+1}: focused compose box ({tap_x},{tap_y})'
                f'{"" if compose_xy else " [fallback blind tap]"}')

            # Detect channel; re-dump a few times while RCS resolves async
            state, xml = 'unknown', ''
            for attempt in range(4):
                xml = _dump_ui(df)
                state = _detect_rcs_state(xml)
                dbg(f'channel detect {attempt+1}: {state}')
                if compose_xy is None:
                    compose_xy = _find_compose_field_box(xml)
                if state in ('rcs', 'sms'):
                    break
                time.sleep(1.2)

            if state in ('rcs', 'sms'):
                break
            if not _on_conversation_list(xml):
                break   # inside a chat but channel unreadable — don't reopen
            dbg('Landed on inbox list — conversation did not open, re-opening')

        # Save the last dump for debugging / resource-id tuning
        try:
            import os as _os, datetime as _dt
            _debug_path = _os.path.join(
                _os.path.dirname(_os.path.abspath(__file__)), 'reports',
                f'ui_dump_{_dt.datetime.now().strftime("%H%M%S")}.xml'
            )
            with open(_debug_path, 'w', encoding='utf-8') as _f:
                _f.write(xml)
        except Exception:
            pass

        # ── Step 5a: SKIP if RCS is not active ───────────────────
        if require_rcs and state != 'rcs':
            dbg(f'RCS not active (channel={state}) — SKIPPING, not sending SMS')
            _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_BACK'])
            time.sleep(0.3)
            _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_HOME'])
            time.sleep(0.3)
            return 'skipped', f'RCS not enabled (channel={state})'

        # ── Step 5b: RCS active → verify text in box, then send ────────────
        # PRIMARY: SENDTO intent was launched with --es sms_body so Google
        # Messages pre-fills the compose box on launch. Works for full Unicode
        # (Tamil, emoji, newlines) with no clipboard or ADBKeyboard needed.
        #
        # FALLBACK (if sms_body was ignored by the ROM):
        #   1. ADBKeyboard broadcast (Unicode, requires app install)
        #   2. Clipper broadcast with literal text arg (requires Clipper app)
        #   3. adb shell input text (ASCII only, last resort)

        use_ime, orig_ime = _ensure_adb_keyboard(df)
        clip_ok = False

        # If the voice recorder somehow opened, back out of it first.
        if _voice_panel_open(xml):
            dbg('Voice recorder panel detected — closing it before typing')
            _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_BACK'])
            time.sleep(0.5)
            xml = _dump_ui(df)
            compose_xy = _find_compose_field_box(xml) or compose_xy

        # Check if sms_body intent already pre-filled the compose box.
        xml = _dump_ui(df)
        prefilled = _compose_has_text(xml)
        if prefilled:
            dbg('smsto URI body= pre-filled compose box (Unicode/newlines/emoji OK) ✓')

        # If not pre-filled, prepare the fallback entry method.
        if not prefilled:
            if use_ime:
                dbg('sms_body not pre-filled — will inject via ADBKeyboard')
            else:
                clip_ok = _set_clipboard(df, message)
                if clip_ok:
                    dbg('sms_body not pre-filled — using Clipper clipboard paste')
                else:
                    dbg('sms_body not pre-filled — falling back to input text (ASCII only)')
            time.sleep(0.2)

        # Enter text + VERIFY it actually landed in the box. We NEVER tap Send
        # on an empty box — on an empty box the bottom-right control is the MIC.
        pasted = prefilled  # already good if intent pre-filled
        for paste_try in range(3):
            if pasted:
                break
            # (Re)focus the real compose box at its current bounds
            cxy = _find_compose_field_box(xml) or compose_xy
            if cxy:
                _adb(df + ['shell', 'input', 'tap', str(cxy[0]), str(cxy[1])])
                time.sleep(0.4)
            # Enter the message via whichever fallback method is available
            if use_ime:
                _adb(df + ['shell', 'am', 'broadcast', '-a', 'ADB_CLEAR_TEXT'])
                time.sleep(0.2)
                _type_via_adbkeyboard(df, message)
            elif clip_ok:
                _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_PASTE'])
            else:
                _adb(df + ['shell', 'input', 'text', _escape_for_adb(message)])
            time.sleep(0.8)
            # Verify
            xml = _dump_ui(df)
            if _compose_has_text(xml):
                pasted = True
                dbg(f'Text verified in the compose box (try {paste_try+1})')
                break
            dbg(f'Text-entry try {paste_try+1}: box still empty, retrying focus+type')

        if not pasted:
            _restore_ime(df, orig_ime)
            dbg('Message never entered the compose box — NOT sending (would hit mic)')
            _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_HOME'])
            if use_ime:
                hint = ''
            elif clip_ok:
                hint = ' — clipboard paste failed; check Clipper app'
            else:
                hint = ' — smsto URI body= ignored by ROM; install ADBKeyboard for Unicode'
            return 'failed', f'message not entered into composer{hint}'

        # Now the box has text → the bottom-right control is the real Send button.
        btn = _find_send_button(xml) or _find_compose_field_send_pos(xml)
        if not btn:
            _restore_ime(df, orig_ime)
            dbg('Send button not located in dump after paste')
            _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_HOME'])
            return 'failed', 'send button not found'
        x, y = btn
        _adb(df + ['shell', 'input', 'tap', str(x), str(y)])
        dbg(f'Tapped RCS send button at ({x},{y})')

        # ── Wait for Google Messages to process the send ──────────
        # Vivo V2117 RCS needs ~2s for the message to animate into
        # the chat and the compose box to clear.  Pressing HOME too
        # early (< 1s) interrupts the send and saves a draft instead.
        time.sleep(2.5)

        # Verify the compose box is now empty (message was sent, not drafted)
        xml_post = _dump_ui(df)
        if _compose_has_text(xml_post):
            dbg('⚠️  Compose box still has text after send tap — retrying send button once')
            btn2 = _find_send_button(xml_post) or _find_compose_field_send_pos(xml_post)
            if btn2:
                _adb(df + ['shell', 'input', 'tap', str(btn2[0]), str(btn2[1])])
                dbg(f'Retry send tapped at ({btn2[0]},{btn2[1]})')
                time.sleep(2.5)
            else:
                dbg('Retry send button not found — message may be in draft')

        # ── Step 6: Go home AFTER send ────────────────────────────
        _adb(df + ['shell', 'input', 'keyevent', 'KEYCODE_HOME'])
        time.sleep(0.3)

        # Restore the user's original keyboard AFTER home (avoids Vivo IME race)
        _restore_ime(df, orig_ime)

        return 'sent', ''

    except subprocess.TimeoutExpired:
        return 'failed', 'ADB timeout'
    except Exception as e:
        return 'failed', str(e)


# ═══════════════════════════════════════════════════════════════════
# CLIPBOARD HELPER
# ═══════════════════════════════════════════════════════════════════

def _set_clipboard(df, text):
    """
    Android 13 / Funtouch OS compatible clipboard setter.
    All broadcast/service-call methods are blocked on Android 10+.

    Strategy (in order):
      1. Clipper app broadcast with literal text (free app, Android 13 OK).
         NOTE: text is passed as a subprocess list arg — no shell substitution.
      2. Push file to /sdcard then use a shell one-liner via 'adb shell' with
         input redirection to invoke am broadcast reading from the file.
         This avoids quoting issues for multi-line / special-char messages.
      3. Return False → caller falls back to 'input text' (ASCII only).
    """
    import tempfile as _tf, os as _os

    device_path = '/sdcard/zyvo_clip.txt'

    # ── Method 1: Clipper broadcast with literal text arg ──────────
    # Pass text directly as a list element — subprocess.run does NOT invoke
    # a shell, so no quoting/substitution issues. Works for any Unicode.
    try:
        r = _adb(df + [
            'shell', 'am', 'broadcast', '-a', 'clipper.set',
            '--es', 'text', text          # ← literal text, not $(cat ...)
        ], timeout=8)
        if r.returncode == 0 and 'error' not in (r.stdout or '').lower():
            return True
    except Exception:
        pass

    # ── Method 2: Push file then read-and-broadcast via shell ──────
    # Useful when Clipper is installed but the text contains chars that
    # am broadcast mishandles even as a list arg (very rare edge case).
    try:
        with _tf.NamedTemporaryFile(mode='w', suffix='.txt',
                                     delete=False, encoding='utf-8') as _tmp:
            _tmp.write(text)
            _tmp_path = _tmp.name
        import subprocess as _sp
        _push_cmd = ['adb'] + (df[1:] if df and df[0] == '-s' else df or []) + \
                    ['-s', df[1]] + ['push', _tmp_path, device_path] \
                    if df and df[0] == '-s' else \
                    ['adb'] + (df or []) + ['push', _tmp_path, device_path]
        _sp.run(_push_cmd, capture_output=True, timeout=8)
        _os.unlink(_tmp_path)
        # Read the file on-device and pass to Clipper via shell
        shell_cmd = f'am broadcast -a clipper.set --es text "$(cat {device_path})"'
        r2 = _adb(df + ['shell', shell_cmd], timeout=8)
        if r2.returncode == 0 and 'error' not in (r2.stdout or '').lower():
            return True
    except Exception:
        pass

    # ── All clipboard methods failed ────────────────────────────────
    # Caller will use 'adb shell input text' (ASCII-safe only).
    return False

def _detect_rcs_state(xml_text):
    """
    Inspect the Google Messages conversation to decide the channel.
    Returns 'rcs', 'sms', or 'unknown' (still resolving / not in a chat).

    Signals confirmed from real Vivo/Funtouch dumps, most reliable first:
      1. Compose bar hint (id=compose_message_text):
             "SIM 1 • RCS message"  → rcs
             "SIM 1 • Text message" → sms
      2. Send button content-desc ("Send RCS message" / "Send SMS")
      3. Conversation body:
             "Texting with NNN (SMS/MMS)" → sms
             "End-to-end encrypted message" → rcs
    """
    if not xml_text:
        return 'unknown'

    # 0) If we're on the inbox/home list there is no channel to read — the
    #    list shows OTHER conversations' "(SMS/MMS)" labels which would
    #    otherwise produce a false 'sms'. Force 'unknown' so the caller reopens.
    _has_compose = any(cid in xml_text for cid in _COMPOSE_IDS)
    if (not _has_compose and
            ('start_chat_fab' in xml_text or 'id/home_fragment' in xml_text)):
        return 'unknown'

    # 1) Compose bar hint — the definitive signal for the active draft
    for node in re.findall(r'<node\s[^>]*?/>', xml_text, re.DOTALL):
        if not any(cid in node for cid in _COMPOSE_IDS):
            continue
        t_m  = re.search(r'\stext="([^"]*)"', node)
        cd_m = re.search(r'content-desc="([^"]*)"', node)
        hint = ((t_m.group(1) if t_m else '') + ' ' +
                (cd_m.group(1) if cd_m else '')).lower()
        if 'rcs' in hint or 'chat message' in hint:
            return 'rcs'
        if 'text message' in hint or 'sms' in hint:
            return 'sms'
        # compose field present but hint empty → keep checking other signals

    low = xml_text.lower()

    # 2) Send button content-desc
    for m in re.finditer(r'content-desc="([^"]*send[^"]*)"', low):
        d = m.group(1)
        if 'rcs' in d or 'chat' in d:
            return 'rcs'
        if 'sms' in d or 'text' in d:
            return 'sms'

    # 3) Conversation-body signals
    if 'sms/mms' in low:                 # "Texting with NNN (SMS/MMS)"
        return 'sms'
    if 'end-to-end encrypted' in low:
        return 'rcs'
    if 'rcs message' in low:
        return 'rcs'
    if 'text message' in low:
        return 'sms'
    return 'unknown'


def _on_conversation_list(xml_text):
    """
    True when Messages is showing the inbox/home list rather than an open
    conversation — i.e. the SENDTO intent failed to open the chat. Detected
    by the 'Start chat' FAB / home_fragment being present with no compose bar.
    """
    if not xml_text:
        return False
    has_inbox   = 'start_chat_fab' in xml_text or 'id/home_fragment' in xml_text
    has_compose = any(cid in xml_text for cid in _COMPOSE_IDS)
    return has_inbox and not has_compose


# ── ADBKeyboard (Unicode input IME) ───────────────────────────────
# Free, open-source IME (com.android.adbkeyboard) that lets ADB inject
# arbitrary Unicode — Tamil, emoji, newlines — into the focused field via
# a broadcast. This is the only reliable way to type non-ASCII text over
# pure ADB on Android 13, since the clipboard cannot be set without root.
_ADB_IME_ID = 'com.android.adbkeyboard/.AdbIME'


def _ensure_adb_keyboard(df):
    """
    If ADBKeyboard is installed, enable it and make it the active IME so we can
    inject Unicode into the focused field. Returns (available, original_ime).
    """
    try:
        listed = (_adb(df + ['shell', 'ime', 'list', '-s', '-a']).stdout) or ''
    except Exception:
        listed = ''
    if 'com.android.adbkeyboard' not in listed:
        return False, ''
    orig = ''
    try:
        orig = (_adb(df + ['shell', 'settings', 'get', 'secure',
                           'default_input_method']).stdout or '').strip()
    except Exception:
        pass
    try:
        _adb(df + ['shell', 'ime', 'enable', _ADB_IME_ID])
        _adb(df + ['shell', 'ime', 'set', _ADB_IME_ID])
        time.sleep(0.6)
    except Exception:
        return False, orig
    return True, orig


def _restore_ime(df, original):
    """Switch back to the user's keyboard after we're done injecting text."""
    if original and 'adbkeyboard' not in original.lower():
        try:
            _adb(df + ['shell', 'ime', 'set', original])
        except Exception:
            pass


def _type_via_adbkeyboard(df, text):
    """Inject Unicode text into the focused field using ADBKeyboard's b64 API."""
    import base64
    b64 = base64.b64encode(text.encode('utf-8')).decode('ascii')
    _adb(df + ['shell', 'am', 'broadcast', '-a', 'ADB_INPUT_B64', '--es', 'msg', b64])


def _dump_ui(df):
    """uiautomator dump → return XML text ('' on failure). Caller adds delays."""
    try:
        _adb(df + ['shell', 'uiautomator', 'dump', '/sdcard/ui_dump.xml'])
        time.sleep(0.6)
        return (_adb(df + ['shell', 'cat', '/sdcard/ui_dump.xml']).stdout) or ''
    except Exception:
        return ''


# Compose-bar HINT patterns (placeholder shown when the box is empty), e.g.
# "SIM 1 • RCS message", "SIM 1 • Text message", "RCS message", "Text message".
_HINT_RE = re.compile(r'^(sim\s*\d?\s*[•·\-\.\s]*)?(rcs|text|chat)\s+message$', re.I)


# Resource-id fragments that identify the compose EditText in Google Messages.
# Vivo/Funtouch OS may use different IDs depending on ROM version / focus state.
_COMPOSE_IDS = (
    'compose_message_text',   # standard Google Messages
    'compose_message',        # some ROM variants
    'message_edit_text',      # seen on some OEM builds
    'enter_message',          # fallback ID
)

def _find_compose_field_box(xml_text):
    """
    Center (x,y) of the compose EditText itself — the box you tap to focus and
    paste into. Tries multiple known resource-id fragments so Vivo ROM variants
    that use a different ID are still found. Returns (x,y) or None.
    """
    if not xml_text:
        return None
    for node in re.findall(r'<node\s[^>]*?/>', xml_text, re.DOTALL):
        if not any(cid in node for cid in _COMPOSE_IDS):
            continue
        m = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
        if m:
            x1, y1, x2, y2 = (int(g) for g in m.groups())
            return ((x1 + x2) // 2, (y1 + y2) // 2)
    return None


def _compose_has_text(xml_text):
    """
    True if the compose box currently holds USER text (paste succeeded), False
    if it's empty / still showing the hint placeholder. Used to guarantee we
    never tap Send on an empty box (which is the mic button).
    """
    if not xml_text:
        return False
    for node in re.findall(r'<node\s[^>]*?/>', xml_text, re.DOTALL):
        if not any(cid in node for cid in _COMPOSE_IDS):
            continue
        m = re.search(r'\stext="([^"]*)"', node)
        t = (m.group(1) if m else '').strip()
        if not t:
            return False                 # empty box
        if _HINT_RE.match(t):
            return False                 # only the hint placeholder is showing
        return True                      # real text present
    return False


def _voice_panel_open(xml_text):
    """True if the voice-message recorder panel is open (box hidden)."""
    if not xml_text:
        return False
    low = xml_text.lower()
    _has_compose = any(cid in xml_text for cid in _COMPOSE_IDS)
    return ('tap to record your voice' in low
            or 'record a voice message' in low and not _has_compose)


def _find_compose_field_send_pos(xml_text):
    """
    Derive send button position from the compose text field bounds.
    The send button in Google Messages is always to the RIGHT of the
    compose field (EditText with resource-id ending in compose_message_text),
    at the same vertical center, near the right edge of the screen.

    Returns (x, y) or None.
    """
    if not xml_text:
        return None

    nodes = re.findall(r'<node\s[^>]*/>', xml_text, re.DOTALL)
    for node in nodes:
        def attr(name, n=node):
            m = re.search(rf'{name}="([^"]*)"', n)
            return m.group(1) if m else ''

        rid = attr('resource-id')
        if 'compose_message_text' not in rid:
            continue

        bounds = attr('bounds')
        if not bounds:
            continue

        # Parse bounds: [x1,y1][x2,y2]
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if not m:
            continue

        x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        cy = (y1 + y2) // 2         # vertical center of compose row
        # Send button is right of compose field; assume ~154px wide button at right edge
        # Use x2 + 154 + 77 as center (154px gap + half of ~154px button)
        # But simpler: screen width is typically x2 + (x2 - x1) * 0.5 or just x2 + 130
        send_x = x2 + 130           # approx center of send button right of field
        send_y = cy
        return (send_x, send_y)

    return None


def _find_send_button(xml_text):
    """
    Parse uiautomator dump XML to find Google Messages send button.
    v6: uses node-level scanning so attribute ORDER doesn't matter.
    Returns (x, y) center coordinates or None.
    """
    if not xml_text:
        return None

    # Known send button resource ID suffixes
    send_ids = [
        'Compose:Draft:Send',       # Google Messages (Compose UI / RCS)
        'send_message_button',
        'send_button',
        'action_send',
        'compose_send_button',
        'send_sms_button',
        'send_rcs_button',
        'send_rcs_message',
        'send',
        'Send',
    ]

    # Search raw XML for Compose:Draft:Send resource-id (Compose UI nodes span multiple lines)
    # Use a broader regex that captures multi-line node blocks too
    all_nodes = re.findall(r'<node\s(?:[^>]|>(?!<))*?/>', xml_text, re.DOTALL)
    # Also try single-line nodes
    single_nodes = re.findall(r'<node\s[^>]*/>', xml_text, re.DOTALL)
    nodes = single_nodes  # single-line is sufficient for attribute scanning

    # Direct search for Compose:Draft:Send anywhere in XML (most reliable)
    m_direct = re.search(r'resource-id="Compose:Draft:Send"[^>]*bounds="(\[[^\]]+\]\[[^\]]+\])"', xml_text)
    if not m_direct:
        # Try reversed attribute order
        m_direct = re.search(r'bounds="(\[[^\]]+\]\[[^\]]+\])"[^>]*resource-id="Compose:Draft:Send"', xml_text)
    if m_direct:
        return _bounds_center(m_direct.group(1))

    for node in nodes:
        def attr(name, _n=node):
            m = re.search(rf'{name}="([^"]*)"', _n)
            return m.group(1) if m else ''

        rid      = attr('resource-id')
        cdesc    = attr('content-desc').lower()
        cls      = attr('class')
        clickable = attr('clickable')
        bounds   = attr('bounds')

        if not bounds:
            continue

        # Match by resource ID suffix (don't require clickable=true for Compose UI)
        if any(sid in rid for sid in send_ids):
            return _bounds_center(bounds)

        if clickable != 'true':
            continue

        # Match by content-desc — RCS send button often just says "Send"
        if 'send' in cdesc:
            return _bounds_center(bounds)

    # Last resort: last clickable ImageButton (usually bottom-right send button)
    image_buttons = []
    for node in nodes:
        def attr(name, n=node):
            m = re.search(rf'{name}="([^"]*)"', n)
            return m.group(1) if m else ''
        if 'ImageButton' in attr('class') and attr('clickable') == 'true' and attr('bounds'):
            image_buttons.append(attr('bounds'))

    if image_buttons:
        return _bounds_center(image_buttons[-1])

    return None


def _bounds_center(bounds_str):
    """Parse '[x1,y1][x2,y2]' and return center (x,y)"""
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if m:
        return (int(m.group(1)) + int(m.group(3))) // 2, \
               (int(m.group(2)) + int(m.group(4))) // 2
    return None


def _escape_for_adb(text):
    replacements = [
        ('\\', '\\\\'), ("'", "\\'"), ('"', '\\"'), ('`', '\\`'),
        ('(', '\\('),   (')', '\\)'), ('&', '\\&'), ('|', '\\|'),
        (';', '\\;'),   ('<', '\\<'), ('>', '\\>'), (' ', '%s'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _adb(args, timeout=20):
    return subprocess.run(
        ['adb'] + args,
        capture_output=True, text=True, timeout=timeout,
        encoding='utf-8', errors='replace'  # Windows fix: cp1252 can't decode Tamil/Unicode in XML
    )


# ═══════════════════════════════════════════════════════════════════
# WATCHDOG THREAD
# ═══════════════════════════════════════════════════════════════════

class WatchdogThread(threading.Thread):
    def __init__(self, device, status, lock):
        super().__init__(daemon=True)
        self.device = device
        self.status = status
        self.lock   = lock
        self._stop  = threading.Event()

    def run(self):
        while not self._stop.is_set():
            time.sleep(15)
            if self._stop.is_set(): break
            with self.lock:
                if not self.status['running']: break
            self._ping()

    def stop(self): self._stop.set()

    def _ping(self):
        try:
            df = ['-s', self.device] if self.device else []
            r  = _adb(df + ['shell', 'echo', 'ping'], timeout=5)
            if r.returncode != 0:
                _log(self.status, self.lock, '⚠️ Device dropped. Reconnecting...')
                self._reconnect()
        except Exception:
            self._reconnect()

    def _reconnect(self):
        try:
            if ':' in self.device:
                _adb(['connect', self.device], timeout=8)
                _log(self.status, self.lock, '🔄 Reconnected')
        except Exception as e:
            _log(self.status, self.lock, f'❌ Reconnect failed: {e}')


# ═══════════════════════════════════════════════════════════════════
# REPORT GENERATOR
# ═══════════════════════════════════════════════════════════════════

def _generate_report(results, report_dir):
    if not results: return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Send Results'

    HDR_FILL = PatternFill('solid', fgColor='1F4E78')
    HDR_FONT = Font(color='FFFFFF', bold=True, name='Calibri', size=11)
    ALT_FILL = PatternFill('solid', fgColor='EBF3FB')
    OK_FONT  = Font(color='006400', bold=True)
    ERR_FONT = Font(color='CC0000', bold=True)

    headers = ['Name', 'Receiver Number', 'Sender (SIM)', 'Sender SIM Number', 'Status', 'Time', 'Message Sent', 'Error']
    widths  = [22, 18, 14, 18, 10, 10, 70, 35]

    for col, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = HDR_FILL; cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = w
    ws.row_dimensions[1].height = 22

    for ri, r in enumerate(results, 2):
        alt = ALT_FILL if ri % 2 == 0 else None
        for ci, val in enumerate([r['name'], r['mobile'], r.get('sim','Auto'),
                                   r.get('sim_number',''),
                                   r['status'], r['time'], r['message'], r['error']], 1):
            cell = ws.cell(row=ri, column=ci, value=val)
            if alt: cell.fill = alt
            if ci == 5: cell.font = OK_FONT if val == 'Sent' else ERR_FONT

    ws2     = wb.create_sheet('Summary')
    total   = len(results)
    sent    = sum(1 for r in results if r['status'] == 'Sent')
    skipped = sum(1 for r in results if r['status'] == 'Skipped')
    failed  = total - sent - skipped
    s1s     = sum(1 for r in results if r.get('sim') == 'SIM1' and r['status'] == 'Sent')
    s2s     = sum(1 for r in results if r.get('sim') == 'SIM2' and r['status'] == 'Sent')

    summary = [
        ('Total Contacts',     total),
        ('Messages Sent (RCS)', sent),
        ('Skipped (no RCS)',   skipped),
        ('Messages Failed',    failed),
        ('Success Rate',       f'{(sent/total*100):.1f}%' if total else '0%'),
        ('Sent via SIM 1',   s1s),
        ('Sent via SIM 2',   s2s),
        ('Report Time',      datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ('Tool',             'ZyvoRCS Sender v7 — Zyvo Tools'),
    ]
    ws2.column_dimensions['A'].width = 22
    ws2.column_dimensions['B'].width = 30
    HDR2 = Font(bold=True, color='1F4E78')
    for ri, (k, v) in enumerate(summary, 1):
        ws2.cell(row=ri, column=1, value=k).font = HDR2
        ws2.cell(row=ri, column=2, value=v)

    os.makedirs(report_dir, exist_ok=True)
    wb.save(os.path.join(report_dir, 'report.xlsx'))


# ═══════════════════════════════════════════════════════════════════
# LOG HELPER
# ═══════════════════════════════════════════════════════════════════

def _log(status, lock, message):
    with lock:
        status['log'].append({'time': datetime.now().strftime('%H:%M:%S'), 'message': message})
        if len(status['log']) > 300:
            status['log'] = status['log'][-300:]
