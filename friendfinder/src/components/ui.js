// Reusable UI primitives for BatchMate.
import React, { useState } from 'react';
import { View, Text, Pressable, TextInput, StyleSheet, ActivityIndicator, ScrollView, Modal, Switch, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, shadow, colorFor, initials } from '../theme';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const pad2 = (n) => String(n).padStart(2, '0');

export function Avatar({ name = '', size = 48, photo }) {
  if (photo) {
    return (
      <Image
        source={{ uri: photo }}
        style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors.border }}
      />
    );
  }
  const bg = colorFor(name);
  return (
    <View style={[styles.avatar, { width: size, height: size, borderRadius: size / 2, backgroundColor: bg }]}>
      <Text style={{ color: '#fff', fontWeight: '800', fontSize: size * 0.38 }}>{initials(name)}</Text>
    </View>
  );
}

// Slim progress bar (0–100).
export function ProgressBar({ percent = 0, color = colors.primary }) {
  return (
    <View style={styles.progressTrack}>
      <View style={[styles.progressFill, { width: `${Math.max(0, Math.min(100, percent))}%`, backgroundColor: color }]} />
    </View>
  );
}

// Date-of-birth picker via Day / Month / Year dropdowns (stores ISO YYYY-MM-DD).
export function DateField({ label, value, onChange }) {
  const parse = (v) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v || '');
    return m ? { y: m[1], m: String(Number(m[2])), d: String(Number(m[3])) } : { y: '', m: '', d: '' };
  };
  const init = parse(value);
  const [d, setD] = useState(init.d);
  const [m, setM] = useState(init.m);
  const [y, setY] = useState(init.y);

  const year0 = new Date().getFullYear();
  const days = Array.from({ length: 31 }, (_, i) => String(i + 1));
  const years = Array.from({ length: 100 }, (_, i) => String(year0 - i));

  const compose = (nd, nm, ny) => { if (nd && nm && ny) onChange(`${ny}-${pad2(nm)}-${pad2(nd)}`); };

  return (
    <View style={{ marginBottom: 16 }}>
      {label ? <Text style={styles.fieldLabel}>{label}</Text> : null}
      <View style={{ flexDirection: 'row' }}>
        <View style={{ flex: 1, marginRight: 6 }}>
          <Select placeholder="Day" value={d} options={days} onChange={(v) => { setD(v); compose(v, m, y); }} />
        </View>
        <View style={{ flex: 1.4, marginHorizontal: 6 }}>
          <Select placeholder="Month" value={m ? MONTHS[Number(m) - 1] : ''} options={MONTHS}
            onChange={(name) => { const mm = String(MONTHS.indexOf(name) + 1); setM(mm); compose(d, mm, y); }} />
        </View>
        <View style={{ flex: 1.2, marginLeft: 6 }}>
          <Select placeholder="Year" value={y} options={years} onChange={(v) => { setY(v); compose(d, m, v); }} />
        </View>
      </View>
    </View>
  );
}

export function Button({ title, onPress, variant = 'primary', icon, style, disabled, small }) {
  const v = {
    primary: { bg: colors.primary, fg: '#fff', bd: colors.primary },
    ghost: { bg: colors.card, fg: colors.ink, bd: colors.border },
    soft: { bg: colors.primarySoft, fg: colors.primary, bd: colors.primarySoft },
    danger: { bg: '#fff', fg: colors.danger, bd: '#fee2e2' },
    success: { bg: colors.success, fg: '#fff', bd: colors.success },
  }[variant];
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      style={({ pressed }) => [
        styles.btn,
        small && { paddingVertical: 9, paddingHorizontal: 14 },
        { backgroundColor: v.bg, borderColor: v.bd, opacity: disabled ? 0.5 : pressed ? 0.85 : 1 },
        style,
      ]}
    >
      {icon ? <Ionicons name={icon} size={small ? 16 : 18} color={v.fg} style={{ marginRight: 7 }} /> : null}
      <Text style={[styles.btnText, small && { fontSize: 14 }, { color: v.fg }]}>{title}</Text>
    </Pressable>
  );
}

export function Card({ children, style, onPress }) {
  if (onPress) {
    return (
      <Pressable onPress={onPress} style={({ pressed }) => [styles.card, shadow.card, pressed && { opacity: 0.92 }, style]}>
        {children}
      </Pressable>
    );
  }
  return <View style={[styles.card, shadow.card, style]}>{children}</View>;
}

export function Tag({ label, color = colors.primary, soft = true, icon }) {
  return (
    <View style={[styles.tag, { backgroundColor: soft ? color + '18' : color, borderColor: soft ? color + '30' : color }]}>
      {icon ? <Ionicons name={icon} size={12} color={soft ? color : '#fff'} style={{ marginRight: 4 }} /> : null}
      <Text style={{ color: soft ? color : '#fff', fontWeight: '700', fontSize: 12 }}>{label}</Text>
    </View>
  );
}

export function Field({ label, icon, ...props }) {
  return (
    <View style={{ marginBottom: 16 }}>
      {label ? <Text style={styles.fieldLabel}>{label}</Text> : null}
      <View style={styles.fieldWrap}>
        {icon ? <Ionicons name={icon} size={18} color={colors.muted} style={{ marginRight: 8 }} /> : null}
        <TextInput placeholderTextColor={colors.muted} style={styles.input} {...props} />
      </View>
    </View>
  );
}

// Dropdown picker (cross-platform via Modal). Use for gender, medium, course…
export function Select({ label, icon, value, placeholder = 'Select…', options = [], onChange, required }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={{ marginBottom: 16 }}>
      {label ? (
        <Text style={styles.fieldLabel}>
          {label}{required ? <Text style={{ color: colors.danger }}> *</Text> : null}
        </Text>
      ) : null}
      <Pressable style={styles.fieldWrap} onPress={() => setOpen(true)}>
        {icon ? <Ionicons name={icon} size={18} color={colors.muted} style={{ marginRight: 8 }} /> : null}
        <Text style={[styles.input, { paddingVertical: 13 }, !value && { color: colors.muted }]} numberOfLines={1}>
          {value || placeholder}
        </Text>
        <Ionicons name="chevron-down" size={18} color={colors.muted} />
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.sheetBackdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={() => {}}>
            <View style={styles.sheetHandle} />
            {label ? <Text style={styles.sheetTitle}>{label}</Text> : null}
            <ScrollView style={{ maxHeight: 360 }}>
              {options.map((opt) => {
                const active = opt === value;
                return (
                  <Pressable
                    key={opt}
                    onPress={() => { onChange?.(opt); setOpen(false); }}
                    style={[styles.optionRow, active && { backgroundColor: colors.primarySoft }]}
                  >
                    <Text style={[styles.optionText, active && { color: colors.primary, fontWeight: '800' }]}>{opt}</Text>
                    {active ? <Ionicons name="checkmark" size={18} color={colors.primary} /> : null}
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

// Labelled on/off row — used for privacy toggles (hide mobile / email).
export function Toggle({ label, hint, value, onValueChange, icon }) {
  return (
    <View style={styles.toggleRow}>
      {icon ? <Ionicons name={icon} size={18} color={colors.muted} style={{ marginRight: 10 }} /> : null}
      <View style={{ flex: 1 }}>
        <Text style={styles.toggleLabel}>{label}</Text>
        {hint ? <Text style={styles.toggleHint}>{hint}</Text> : null}
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        trackColor={{ true: colors.primary, false: colors.border }}
        thumbColor="#fff"
      />
    </View>
  );
}

// Multi-select chips with optional custom entry — used for interests / skills.
export function ChipSelect({ label, options = [], values = [], onChange, allowCustom, placeholder = 'Add your own' }) {
  const [text, setText] = useState('');
  const toggle = (opt) => {
    if (values.includes(opt)) onChange(values.filter((v) => v !== opt));
    else onChange([...values, opt]);
  };
  const addCustom = () => {
    const t = text.trim();
    if (t && !values.includes(t)) onChange([...values, t]);
    setText('');
  };
  // Custom values not present in the predefined options.
  const extras = values.filter((v) => !options.includes(v));
  return (
    <View style={{ marginBottom: 16 }}>
      {label ? <Text style={styles.fieldLabel}>{label}</Text> : null}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
        {[...options, ...extras].map((opt) => {
          const on = values.includes(opt);
          return (
            <Pressable
              key={opt}
              onPress={() => toggle(opt)}
              style={[styles.chip, on && { backgroundColor: colors.primary, borderColor: colors.primary }]}
            >
              <Text style={[styles.chipText, on && { color: '#fff' }]}>{opt}</Text>
              {on ? <Ionicons name="checkmark" size={13} color="#fff" style={{ marginLeft: 4 }} /> : null}
            </Pressable>
          );
        })}
      </View>
      {allowCustom && (
        <View style={[styles.fieldWrap, { marginTop: 6 }]}>
          <Ionicons name="add" size={18} color={colors.muted} style={{ marginRight: 8 }} />
          <TextInput
            placeholder={placeholder}
            placeholderTextColor={colors.muted}
            style={styles.input}
            value={text}
            onChangeText={setText}
            onSubmitEditing={addCustom}
            returnKeyType="done"
          />
          {text.trim() ? (
            <Pressable onPress={addCustom}><Ionicons name="checkmark-circle" size={22} color={colors.primary} /></Pressable>
          ) : null}
        </View>
      )}
    </View>
  );
}

export function SectionTitle({ children, action, onAction }) {
  return (
    <View style={styles.sectionRow}>
      <Text style={styles.sectionTitle}>{children}</Text>
      {action ? (
        <Pressable onPress={onAction}>
          <Text style={styles.sectionAction}>{action}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function Empty({ icon = 'sparkles-outline', title, subtitle }) {
  return (
    <View style={styles.empty}>
      <View style={styles.emptyIcon}>
        <Ionicons name={icon} size={28} color={colors.primary} />
      </View>
      <Text style={styles.emptyTitle}>{title}</Text>
      {subtitle ? <Text style={styles.emptySub}>{subtitle}</Text> : null}
    </View>
  );
}

export function Loader() {
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
      <ActivityIndicator size="large" color={colors.primary} />
    </View>
  );
}

export function Chip({ label, active, onPress }) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.chip, active && { backgroundColor: colors.primary, borderColor: colors.primary }]}
    >
      <Text style={[styles.chipText, active && { color: '#fff' }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  avatar: { alignItems: 'center', justifyContent: 'center' },
  btn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingVertical: 14, paddingHorizontal: 18, borderRadius: radius.pill, borderWidth: 1.5,
  },
  btnText: { fontWeight: '800', fontSize: 15.5 },
  card: { backgroundColor: colors.card, borderRadius: radius.md, padding: 16, borderWidth: 1, borderColor: colors.border },
  tag: {
    flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start',
    paddingVertical: 4, paddingHorizontal: 10, borderRadius: radius.pill, borderWidth: 1, marginRight: 6, marginTop: 6,
  },
  fieldLabel: { fontWeight: '700', color: colors.ink, marginBottom: 7, fontSize: 13.5 },
  fieldWrap: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
    borderWidth: 1.5, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: 14,
  },
  input: { flex: 1, paddingVertical: 13, fontSize: 15.5, color: colors.ink },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, marginTop: 8 },
  sectionTitle: { fontSize: 18, fontWeight: '800', color: colors.ink },
  sectionAction: { color: colors.primary, fontWeight: '700', fontSize: 14 },
  empty: { alignItems: 'center', paddingVertical: 40, paddingHorizontal: 24 },
  emptyIcon: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  emptyTitle: { fontWeight: '800', fontSize: 16, color: colors.ink, textAlign: 'center' },
  emptySub: { color: colors.muted, textAlign: 'center', marginTop: 6, lineHeight: 20 },
  chip: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 8, paddingHorizontal: 14, borderRadius: radius.pill,
    borderWidth: 1.5, borderColor: colors.border, backgroundColor: colors.card, marginRight: 8, marginBottom: 8,
  },
  chipText: { color: colors.body, fontWeight: '700', fontSize: 13.5 },
  sheetBackdrop: { flex: 1, backgroundColor: 'rgba(15,23,42,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: colors.card, borderTopLeftRadius: 22, borderTopRightRadius: 22, paddingHorizontal: 16, paddingTop: 10, paddingBottom: 24 },
  sheetHandle: { alignSelf: 'center', width: 44, height: 5, borderRadius: 3, backgroundColor: colors.border, marginBottom: 10 },
  sheetTitle: { fontWeight: '800', fontSize: 16, color: colors.ink, marginBottom: 8, paddingHorizontal: 4 },
  optionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 14, paddingHorizontal: 12, borderRadius: radius.sm },
  optionText: { fontSize: 15.5, color: colors.ink, fontWeight: '600' },
  toggleRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderWidth: 1.5, borderColor: colors.border, borderRadius: radius.sm, padding: 14, marginBottom: 16 },
  toggleLabel: { fontWeight: '700', color: colors.ink, fontSize: 14.5 },
  toggleHint: { color: colors.muted, fontSize: 12.5, marginTop: 2 },
  progressTrack: { height: 8, borderRadius: 4, backgroundColor: colors.border, overflow: 'hidden' },
  progressFill: { height: 8, borderRadius: 4 },
});
