// Education record forms.
//
// Two modes:
//   mode="first" (onboarding) — a quick 3-step wizard that captures only the
//     essentials: Education Type · Location & Institution · Batch Year.
//   mode="edit"  (Edit Profile) — a full form pre-filled from an existing
//     record, where the remaining details (course, department, start/completion
//     years, status, visibility, search matching) are filled in.
import React, { useMemo, useState } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Button, Field, Select, Toggle } from './ui';
import LocationPicker from './LocationPicker';
import { colors, radius } from '../theme';
import {
  EDUCATION_TYPES, COURSE_OPTIONS, STATUSES, VISIBILITIES,
} from '../data';
import { searchInstitutions, popularInCity } from '../institutions';
import { useApp } from '../store';

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

// Institution search / picker (used inside the Location step of the wizard).
function InstitutionSearch({ city, value, onPick }) {
  const { state: appState } = useApp();
  const [query, setQuery] = useState('');
  const [manual, setManual] = useState(false);

  const suggestions = searchInstitutions(query, city);
  const popular = popularInCity(city);
  const recent = appState.recentInstitutions || [];

  return (
    <View>
      <Field
        label="Search Institution *"
        icon="search-outline"
        placeholder="Search by institution name"
        value={query}
        onChangeText={setQuery}
        autoCorrect={false}
      />

      {!!value && (
        <View style={styles.selectedBox}>
          <Ionicons name="checkmark-circle" size={18} color={colors.success} />
          <Text style={styles.selectedText} numberOfLines={1}>Selected: {value}</Text>
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
          value={value || ''}
          onChangeText={onPick}
          autoFocus
        />
      )}

      {!manual && (
        <>
          {query.length > 0 && (
            <>
              <Text style={styles.listLabel}>Suggestions</Text>
              {suggestions.length ? suggestions.map((i) => (
                <Pressable key={i.name} style={styles.instRow} onPress={() => onPick(i.name)}>
                  <Ionicons name="business-outline" size={18} color={colors.primary} />
                  <View style={{ flex: 1, marginLeft: 10 }}>
                    <Text style={styles.instName}>{i.name}</Text>
                    <Text style={styles.instCity}>{i.city}</Text>
                  </View>
                  {value === i.name && <Ionicons name="checkmark" size={18} color={colors.success} />}
                </Pressable>
              )) : <Text style={styles.note}>No matches. Tick “Add Institution Manually” above.</Text>}
            </>
          )}

          {recent.length > 0 && (
            <>
              <Text style={styles.listLabel}>Recent Searches</Text>
              <View style={styles.chipWrap}>
                {recent.map((r) => (
                  <Pressable key={r} style={styles.chip} onPress={() => onPick(r)}>
                    <Ionicons name="time-outline" size={13} color={colors.body} />
                    <Text style={styles.chipText}>{r}</Text>
                  </Pressable>
                ))}
              </View>
            </>
          )}

          <Text style={styles.listLabel}>Popular in {city || 'your city'}</Text>
          {popular.length ? popular.map((i) => (
            <Pressable key={i.name} style={styles.instRow} onPress={() => onPick(i.name)}>
              <Ionicons name="star-outline" size={18} color={colors.gold} />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={styles.instName}>{i.name}</Text>
                <Text style={styles.instCity}>{i.city}</Text>
              </View>
              {value === i.name && <Ionicons name="checkmark" size={18} color={colors.success} />}
            </Pressable>
          )) : <Text style={styles.note}>No popular institutions listed for this city — search above or add manually.</Text>}
        </>
      )}
    </View>
  );
}

// --- First-time wizard (3 quick steps) -------------------------------------
const FIRST_TOTAL = 3;
const FIRST_TITLES = { 1: 'Education Type', 2: 'Location & Institution', 3: 'Batch Year' };

function EducationWizard({ onAdd, addLabel = 'Add this institution' }) {
  const { addRecentInstitution } = useApp();

  const [step, setStep] = useState(1);
  const [type, setType] = useState('');
  const [place, setPlace] = useState({ state: '', district: '', city: '' });
  const [name, setName] = useState('');
  const [batch, setBatch] = useState('');

  const reset = () => {
    setStep(1); setType(''); setPlace({ state: '', district: '', city: '' });
    setName(''); setBatch('');
  };

  const canNext = useMemo(() => {
    if (step === 1) return !!type;
    if (step === 2) return !!(place.state && place.district && place.city && String(name).trim());
    if (step === 3) return !!String(batch).trim();
    return true;
  }, [step, type, place, name, batch]);

  const finish = () => {
    const n = String(name).trim();
    const entry = {
      type, level: type,
      state: place.state, district: place.district, city: place.city,
      name: n, batch: String(batch).trim(),
      status: '', visibility: 'Public', searchMatching: true,
    };
    if (n) addRecentInstitution(n);
    onAdd(entry);
    reset();
  };

  const renderBody = () => {
    switch (step) {
      case 1:
        return EDUCATION_TYPES.map((t) => (
          <RadioRow key={t} label={t} selected={type === t} onPress={() => setType(t)} />
        ));
      case 2:
        return (
          <View>
            <LocationPicker
              required
              cityLabel="City / Town / Village"
              value={place}
              onChange={(patch) => setPlace((p) => ({ ...p, ...patch }))}
            />
            <View style={{ marginTop: 4 }}>
              <InstitutionSearch city={place.city} value={name} onPick={setName} />
            </View>
          </View>
        );
      case 3:
        return (
          <Field
            label="Batch Year *"
            icon="calendar-outline"
            keyboardType="number-pad"
            placeholder="e.g. 2015"
            value={batch}
            onChangeText={setBatch}
          />
        );
      default:
        return null;
    }
  };

  return (
    <View style={styles.card}>
      <Text style={styles.stepLabel}>STEP {step} OF {FIRST_TOTAL}</Text>
      <Text style={styles.stepTitle}>{FIRST_TITLES[step]}</Text>
      <View style={styles.dots}>
        {Array.from({ length: FIRST_TOTAL }).map((_, i) => (
          <View key={i} style={[styles.dot, i < step && styles.dotOn]} />
        ))}
      </View>

      <View style={{ marginTop: 4 }}>{renderBody()}</View>

      <View style={styles.nav}>
        {step > 1 ? (
          <View style={{ flex: 1, marginRight: 8 }}>
            <Button title="Back" variant="ghost" icon="chevron-back" onPress={() => setStep((s) => s - 1)} />
          </View>
        ) : null}
        <View style={{ flex: 1, marginLeft: step > 1 ? 8 : 0 }}>
          {step < FIRST_TOTAL ? (
            <Button title="Next" icon="chevron-forward" onPress={() => setStep((s) => s + 1)} disabled={!canNext} />
          ) : (
            <Button title={addLabel} icon="add-circle-outline" onPress={finish} disabled={!canNext} />
          )}
        </View>
      </View>
    </View>
  );
}

// --- Full edit form (all remaining details) --------------------------------
function EducationEditForm({ initial = {}, onSave, onCancel, saveLabel = 'Save Changes' }) {
  // Education Type is chosen during sign-up for existing records; when adding a
  // brand-new record from Edit Profile we let the user pick it here.
  const initialType = initial.type || initial.level || '';
  const isNew = !initialType;
  const [type, setType] = useState(initialType);

  const courseOpts = COURSE_OPTIONS[type] || [];
  const courseInOpts = courseOpts.includes(initial.course);

  const [name, setName] = useState(initial.name || '');
  const [course, setCourse] = useState(courseInOpts ? initial.course : (initial.course ? 'Other' : ''));
  const [courseCustom, setCourseCustom] = useState(courseInOpts ? '' : (initial.course || ''));
  const [department, setDepartment] = useState(initial.department || initial.specialization || '');
  const [batch, setBatch] = useState(initial.batch || '');
  const [startYear, setStartYear] = useState(initial.startYear || '');
  const [endYear, setEndYear] = useState(initial.endYear || '');
  const [status, setStatus] = useState(initial.status || '');
  const [visibility, setVisibility] = useState(initial.visibility || 'Public');
  const [searchMatching, setSearchMatching] = useState(initial.searchMatching ?? true);

  const resolvedCourse = () => (course === 'Other' ? courseCustom.trim() : String(course).trim());
  const canSave = !!(type && String(name).trim() && resolvedCourse() && String(batch).trim());

  const save = () => {
    onSave({
      ...initial,
      type, level: type,
      name: String(name).trim(),
      course: resolvedCourse(),
      department: department.trim(),
      batch: String(batch).trim(),
      startYear: String(startYear).trim(),
      endYear: String(endYear).trim(),
      status, visibility, searchMatching,
    });
  };

  return (
    <View style={styles.card}>
      <Text style={styles.stepTitle}>Institution Details</Text>
      <View style={{ height: 14 }} />

      {isNew ? (
        <Select
          label="Education Type"
          required
          icon="school-outline"
          placeholder="Select Education Type"
          value={type}
          options={EDUCATION_TYPES}
          onChange={setType}
        />
      ) : (
        <View style={styles.typeBadge}>
          <Ionicons name="school-outline" size={15} color={colors.primary} />
          <Text style={styles.typeBadgeText}>{type}</Text>
        </View>
      )}

      <Field label="Institute Name *" icon="business-outline" value={name} onChangeText={setName} />

      {courseOpts.length ? (
        <>
          <Select
            label="Course Name"
            required
            placeholder="Select Course Name"
            value={course}
            options={courseOpts}
            onChange={setCourse}
          />
          {course === 'Other' && (
            <Field placeholder="Enter course name" value={courseCustom} onChangeText={setCourseCustom} />
          )}
        </>
      ) : (
        <Field label="Course Name *" value={course} onChangeText={setCourse} />
      )}

      <Field label="Department / Specialization" value={department} onChangeText={setDepartment} />
      <Field label="Batch Year *" icon="calendar-outline" keyboardType="number-pad" value={batch} onChangeText={setBatch} />
      <Field label="Start Year" keyboardType="number-pad" value={startYear} onChangeText={setStartYear} />
      <Field label="Completion Year" keyboardType="number-pad" value={endYear} onChangeText={setEndYear} />

      <Text style={styles.groupLabel}>Status</Text>
      {STATUSES.map((s) => (
        <RadioRow key={s} label={s} selected={status === s} onPress={() => setStatus(s)} />
      ))}

      <Text style={styles.groupLabel}>Visibility</Text>
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

      <View style={styles.nav}>
        {onCancel ? (
          <View style={{ flex: 1, marginRight: 8 }}>
            <Button title="Cancel" variant="ghost" onPress={onCancel} />
          </View>
        ) : null}
        <View style={{ flex: 1, marginLeft: onCancel ? 8 : 0 }}>
          <Button title={saveLabel} icon="checkmark-circle" onPress={save} disabled={!canSave} />
        </View>
      </View>
    </View>
  );
}

export default function EducationForm({ mode = 'first', initial, onAdd, onSave, onCancel, addLabel, saveLabel }) {
  if (mode === 'edit') {
    return <EducationEditForm initial={initial} onSave={onSave} onCancel={onCancel} saveLabel={saveLabel} />;
  }
  return <EducationWizard onAdd={onAdd} addLabel={addLabel} />;
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: 16 },
  stepLabel: { color: colors.primary, fontWeight: '800', fontSize: 11.5, letterSpacing: 1 },
  stepTitle: { fontSize: 20, fontWeight: '900', color: colors.ink, marginTop: 2 },
  groupLabel: { fontWeight: '800', color: colors.ink, fontSize: 14.5, marginTop: 10, marginBottom: 10 },
  typeBadge: { flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', backgroundColor: colors.primarySoft, borderRadius: radius.pill, paddingVertical: 6, paddingHorizontal: 12, marginBottom: 16 },
  typeBadgeText: { color: colors.primary, fontWeight: '800', fontSize: 13, marginLeft: 6 },
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
