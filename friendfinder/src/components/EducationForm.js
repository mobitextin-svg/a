// Stepwise "add an education record" wizard.
// Step 1 Location · Step 2 Type · Step 3 Institution Search ·
// Step 4 Details · Step 5 Status · Step 6 Visibility.
// Every dropdown (course/degree, district, city, institution) offers an
// "Other / type manually" fallback.
import React, { useMemo, useState } from 'react';
import { View, Text, StyleSheet, Pressable, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Button, Field, Select, Toggle } from './ui';
import LocationPicker from './LocationPicker';
import { colors, radius } from '../theme';
import {
  EDUCATION_TYPES, EDU_FIELDS, COURSE_OPTIONS, STATUSES, VISIBILITIES,
} from '../data';
import { searchInstitutions, popularInCity } from '../institutions';
import { useApp } from '../store';

const TOTAL = 6;
const TITLES = {
  1: 'Location', 2: 'Education Type', 3: 'Institution Search',
  4: 'Institution Details', 5: 'Status', 6: 'Visibility',
};

// Single-select option row used for Type / Status / Visibility.
function RadioRow({ label, selected, onPress }) {
  return (
    <Pressable onPress={onPress} style={[styles.radioRow, selected && styles.radioRowOn]}>
      <Ionicons
        name={selected ? 'radio-button-on' : 'radio-button-off'}
        size={20}
        color={selected ? colors.primary : colors.muted}
      />
      <Text style={[styles.radioText, selected && { color: colors.primary, fontWeight: '800' }]}>{label}</Text>
    </Pressable>
  );
}

export default function EducationForm({ onAdd, addLabel = 'Add this education' }) {
  const { state: appState, addRecentInstitution } = useApp();

  const [step, setStep] = useState(1);
  const [place, setPlace] = useState({ state: '', district: '', city: '' });
  const [type, setType] = useState('');
  const [query, setQuery] = useState('');
  const [manual, setManual] = useState(false);
  const [details, setDetails] = useState({});
  const [status, setStatus] = useState('');
  const [visibility, setVisibility] = useState('Public');
  const [searchMatching, setSearchMatching] = useState(true);

  const fields = type ? EDU_FIELDS[type] || [] : [];
  const setD = (k, v) => setDetails((d) => ({ ...d, [k]: v }));

  const reset = () => {
    setStep(1); setPlace({ state: '', district: '', city: '' }); setType('');
    setQuery(''); setManual(false); setDetails({}); setStatus('');
    setVisibility('Public'); setSearchMatching(true);
  };

  // Resolve a field value, honouring the "Other" -> custom text override.
  const resolved = (fl) => {
    let v = String(details[fl.key] || '').trim();
    const custom = String(details[fl.key + 'Custom'] || '').trim();
    if (v === 'Other' && custom) v = custom;
    return v;
  };

  const canNext = useMemo(() => {
    if (step === 1) return !!(place.state && place.district && place.city);
    if (step === 2) return !!type;
    if (step === 3) return !!String(details.name || '').trim();
    if (step === 4) return fields.filter((fl) => fl.required).every((fl) => resolved(fl));
    if (step === 5) return !!status;
    if (step === 6) return !!visibility;
    return true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, place, type, details, fields, status, visibility]);

  const pickType = (t) => { setType(t); setDetails({}); };
  const pickInstitution = (name) => { setD('name', name); setManual(false); };

  const finish = () => {
    const entry = {
      type, level: type,
      state: place.state, district: place.district, city: place.city,
      status, visibility, searchMatching,
    };
    fields.forEach((fl) => { const v = resolved(fl); if (v) entry[fl.key] = v; });
    if (entry.name) addRecentInstitution(entry.name);
    onAdd(entry);
    reset();
  };

  // --- Step bodies ----------------------------------------------------------
  const renderStep3 = () => {
    const suggestions = searchInstitutions(query, place.city);
    const popular = popularInCity(place.city);
    const recent = appState.recentInstitutions || [];
    return (
      <View>
        <Field
          label="Search Institution"
          icon="search-outline"
          placeholder="Search by institution name"
          value={query}
          onChangeText={setQuery}
          autoCorrect={false}
        />

        {!!details.name && (
          <View style={styles.selectedBox}>
            <Ionicons name="checkmark-circle" size={18} color={colors.success} />
            <Text style={styles.selectedText} numberOfLines={1}>Selected: {details.name}</Text>
          </View>
        )}

        {/* Manual add */}
        <Pressable style={styles.checkRow} onPress={() => setManual((m) => !m)}>
          <Ionicons name={manual ? 'checkbox' : 'square-outline'} size={20} color={manual ? colors.primary : colors.muted} />
          <Text style={styles.checkText}>Add Institution Manually</Text>
        </Pressable>
        {manual && (
          <Field
            placeholder="Enter institution name"
            value={details.name || ''}
            onChangeText={(t) => setD('name', t)}
            autoFocus
          />
        )}

        {!manual && (
          <>
            {query.length > 0 && (
              <>
                <Text style={styles.listLabel}>Suggestions</Text>
                {suggestions.length ? suggestions.map((i) => (
                  <Pressable key={i.name} style={styles.instRow} onPress={() => pickInstitution(i.name)}>
                    <Ionicons name="business-outline" size={18} color={colors.primary} />
                    <View style={{ flex: 1, marginLeft: 10 }}>
                      <Text style={styles.instName}>{i.name}</Text>
                      <Text style={styles.instCity}>{i.city}</Text>
                    </View>
                    {details.name === i.name && <Ionicons name="checkmark" size={18} color={colors.success} />}
                  </Pressable>
                )) : <Text style={styles.note}>No matches. Tick “Add Institution Manually” above.</Text>}
              </>
            )}

            {recent.length > 0 && (
              <>
                <Text style={styles.listLabel}>Recent Searches</Text>
                <View style={styles.chipWrap}>
                  {recent.map((r) => (
                    <Pressable key={r} style={styles.chip} onPress={() => pickInstitution(r)}>
                      <Ionicons name="time-outline" size={13} color={colors.body} />
                      <Text style={styles.chipText}>{r}</Text>
                    </Pressable>
                  ))}
                </View>
              </>
            )}

            <Text style={styles.listLabel}>Popular in {place.city || 'your city'}</Text>
            {popular.length ? popular.map((i) => (
              <Pressable key={i.name} style={styles.instRow} onPress={() => pickInstitution(i.name)}>
                <Ionicons name="star-outline" size={18} color={colors.gold} />
                <View style={{ flex: 1, marginLeft: 10 }}>
                  <Text style={styles.instName}>{i.name}</Text>
                  <Text style={styles.instCity}>{i.city}</Text>
                </View>
                {details.name === i.name && <Ionicons name="checkmark" size={18} color={colors.success} />}
              </Pressable>
            )) : <Text style={styles.note}>No popular institutions listed for this city — search above or add manually.</Text>}
          </>
        )}
      </View>
    );
  };

  const renderStep4 = () => (
    <View>
      {fields.map((fl) => {
        if (fl.kind === 'course') {
          const opts = COURSE_OPTIONS[type] || [];
          if (!opts.length) {
            return (
              <Field
                key={fl.key}
                label={fl.label + (fl.required ? ' *' : '')}
                value={details[fl.key] || ''}
                onChangeText={(t) => setD(fl.key, t)}
              />
            );
          }
          return (
            <View key={fl.key}>
              <Select
                label={fl.label}
                required={fl.required}
                placeholder={`Select ${fl.label}`}
                value={details[fl.key] || ''}
                options={opts}
                onChange={(t) => setD(fl.key, t)}
              />
              {details[fl.key] === 'Other' && (
                <Field
                  placeholder={`Enter ${fl.label.toLowerCase()}`}
                  value={details[fl.key + 'Custom'] || ''}
                  onChangeText={(t) => setD(fl.key + 'Custom', t)}
                />
              )}
            </View>
          );
        }
        return (
          <Field
            key={fl.key}
            label={fl.label + (fl.required ? ' *' : '')}
            keyboardType={fl.kind === 'number' ? 'number-pad' : 'default'}
            value={details[fl.key] || ''}
            onChangeText={(t) => setD(fl.key, t)}
          />
        );
      })}
    </View>
  );

  const renderBody = () => {
    switch (step) {
      case 1:
        return (
          <LocationPicker
            required
            cityLabel="City / Town / Village"
            value={place}
            onChange={(patch) => setPlace((p) => ({ ...p, ...patch }))}
          />
        );
      case 2:
        return EDUCATION_TYPES.map((t) => (
          <RadioRow key={t} label={t} selected={type === t} onPress={() => pickType(t)} />
        ));
      case 3:
        return renderStep3();
      case 4:
        return renderStep4();
      case 5:
        return STATUSES.map((s) => (
          <RadioRow key={s} label={s} selected={status === s} onPress={() => setStatus(s)} />
        ));
      case 6:
        return (
          <View>
            {VISIBILITIES.map((v) => (
              <RadioRow key={v} label={v} selected={visibility === v} onPress={() => setVisibility(v)} />
            ))}
            <View style={{ marginTop: 8 }}>
              <Toggle
                label="Use for Search Matching"
                hint="Let this record help batchmates find you."
                icon="search-outline"
                value={searchMatching}
                onValueChange={setSearchMatching}
              />
            </View>
          </View>
        );
      default:
        return null;
    }
  };

  return (
    <View style={styles.card}>
      {/* Progress */}
      <Text style={styles.stepLabel}>STEP {step} OF {TOTAL}</Text>
      <Text style={styles.stepTitle}>{TITLES[step]}</Text>
      <View style={styles.dots}>
        {Array.from({ length: TOTAL }).map((_, i) => (
          <View key={i} style={[styles.dot, i < step && styles.dotOn]} />
        ))}
      </View>

      <View style={{ marginTop: 4 }}>{renderBody()}</View>

      {/* Nav */}
      <View style={styles.nav}>
        {step > 1 ? (
          <View style={{ flex: 1, marginRight: 8 }}>
            <Button title="Back" variant="ghost" icon="chevron-back" onPress={() => setStep((s) => s - 1)} />
          </View>
        ) : null}
        <View style={{ flex: 1, marginLeft: step > 1 ? 8 : 0 }}>
          {step < TOTAL ? (
            <Button title="Next" icon="chevron-forward" onPress={() => setStep((s) => s + 1)} disabled={!canNext} />
          ) : (
            <Button title={addLabel} icon="add-circle-outline" onPress={finish} disabled={!canNext} />
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: 16 },
  stepLabel: { color: colors.primary, fontWeight: '800', fontSize: 11.5, letterSpacing: 1 },
  stepTitle: { fontSize: 20, fontWeight: '900', color: colors.ink, marginTop: 2 },
  dots: { flexDirection: 'row', marginTop: 10, marginBottom: 14 },
  dot: { flex: 1, height: 4, borderRadius: 2, backgroundColor: colors.border, marginRight: 4 },
  dotOn: { backgroundColor: colors.primary },
  radioRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 13, paddingHorizontal: 14, borderRadius: radius.sm, borderWidth: 1.5, borderColor: colors.border, marginBottom: 8 },
  radioRowOn: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  radioText: { marginLeft: 12, fontSize: 15, fontWeight: '600', color: colors.ink },
  checkRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, marginBottom: 8 },
  checkText: { marginLeft: 10, fontWeight: '700', color: colors.ink, fontSize: 14.5 },
  selectedBox: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.successSoft, borderRadius: radius.sm, padding: 10, marginBottom: 12 },
  selectedText: { marginLeft: 8, color: colors.ink, fontWeight: '700', flex: 1 },
  listLabel: { fontWeight: '800', color: colors.ink, fontSize: 13, marginTop: 14, marginBottom: 8 },
  instRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 11, paddingHorizontal: 12, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border, marginBottom: 8 },
  instName: { fontWeight: '700', color: colors.ink, fontSize: 14.5 },
  instCity: { color: colors.muted, fontSize: 12.5, marginTop: 1 },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap' },
  chip: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.bg, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border, paddingVertical: 7, paddingHorizontal: 12, marginRight: 8, marginBottom: 8 },
  chipText: { marginLeft: 5, color: colors.body, fontWeight: '700', fontSize: 12.5 },
  note: { color: colors.muted, fontSize: 13, marginBottom: 6 },
  nav: { flexDirection: 'row', marginTop: 18 },
});
