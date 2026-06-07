// Dynamic "add an education record" form.
// Renders a different set of inputs per education type (driven by EDU_FIELDS)
// and a predefined Course/Degree picker (COURSE_OPTIONS). Shared by the
// onboarding flow and the Edit Profile screen.
import React, { useMemo, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Button, Field, Select } from './ui';
import LocationPicker from './LocationPicker';
import { colors } from '../theme';
import { EDUCATION_TYPES, EDU_FIELDS, COURSE_OPTIONS, MEDIUMS } from '../data';

// Keys written by the cascading location picker.
const LOCATION_KEYS = ['state', 'district', 'city'];

const emptyValues = () => ({});

export default function EducationForm({ onAdd, addLabel = 'Add this education' }) {
  const [type, setType] = useState(EDUCATION_TYPES[2]); // default: College (UG)
  const [values, setValues] = useState(emptyValues());

  const fields = EDU_FIELDS[type] || [];
  const set = (key, val) => setValues((v) => ({ ...v, [key]: val }));

  // Required fields that are still empty block submission.
  const missing = useMemo(() => {
    const out = [];
    fields.forEach((fl) => {
      if (!fl.required) return;
      if (fl.kind === 'location') {
        // State, District & City are all required for a location field.
        LOCATION_KEYS.forEach((k) => {
          if (!String(values[k] || '').trim()) out.push(k[0].toUpperCase() + k.slice(1));
        });
      } else if (!String(values[fl.key] || '').trim()) {
        out.push(fl.label);
      }
    });
    return out;
  }, [fields, values]);

  const changeType = (t) => { setType(t); setValues(emptyValues()); };

  const add = () => {
    if (missing.length) return;
    // Keep `level` mirrored to `type` for back-compat with search/matching.
    const entry = { type, level: type };
    fields.forEach((fl) => {
      if (fl.kind === 'location') {
        LOCATION_KEYS.forEach((k) => {
          const v = String(values[k] || '').trim();
          if (v) entry[k] = v;
        });
        return;
      }
      let val = String(values[fl.key] || '').trim();
      // If "Other" was chosen and a custom value typed, use the custom text.
      const custom = String(values[fl.key + 'Custom'] || '').trim();
      if (val === 'Other' && custom) val = custom;
      if (val) entry[fl.key] = val;
    });
    onAdd(entry);
    setValues(emptyValues());
  };

  return (
    <View>
      <Select
        label="Education Type"
        icon="school-outline"
        value={type}
        options={EDUCATION_TYPES}
        onChange={changeType}
      />

      {fields.map((fl) => {
        if (fl.kind === 'course') {
          const opts = COURSE_OPTIONS[type] || [];
          // No predefined list → free text entry.
          if (!opts.length) {
            return (
              <Field
                key={fl.key}
                label={fl.label + (fl.required ? ' *' : '')}
                value={values[fl.key] || ''}
                onChangeText={(t) => set(fl.key, t)}
              />
            );
          }
          return (
            <View key={fl.key}>
              <Select
                label={fl.label}
                required={fl.required}
                placeholder={`Select ${fl.label}`}
                value={values[fl.key] || ''}
                options={opts}
                onChange={(t) => set(fl.key, t)}
              />
              {values[fl.key] === 'Other' && (
                <Field
                  placeholder={`Enter ${fl.label.toLowerCase()}`}
                  value={values[fl.key + 'Custom'] || ''}
                  onChangeText={(t) => set(fl.key + 'Custom', t)}
                />
              )}
            </View>
          );
        }
        if (fl.kind === 'medium') {
          return (
            <Select
              key={fl.key}
              label={fl.label + ' (Optional)'}
              placeholder="Select medium"
              value={values[fl.key] || ''}
              options={MEDIUMS}
              onChange={(t) => set(fl.key, t)}
            />
          );
        }
        if (fl.kind === 'location') {
          return (
            <LocationPicker
              key={fl.key}
              required={fl.required}
              value={{ state: values.state, district: values.district, city: values.city }}
              onChange={(patch) => setValues((v) => ({ ...v, ...patch }))}
            />
          );
        }
        return (
          <Field
            key={fl.key}
            label={fl.label + (fl.required ? ' *' : '')}
            keyboardType={fl.kind === 'number' ? 'number-pad' : 'default'}
            value={values[fl.key] || ''}
            onChangeText={(t) => set(fl.key, t)}
          />
        );
      })}

      {missing.length > 0 && (
        <Text style={styles.hint}>Required: {missing.join(', ')}</Text>
      )}

      <Button
        title={addLabel}
        variant="soft"
        icon="add-circle-outline"
        onPress={add}
        disabled={missing.length > 0}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  hint: { color: colors.danger, fontSize: 12.5, marginBottom: 10, fontWeight: '600' },
});
