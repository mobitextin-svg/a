// A nicely-styled card for a single education record.
// Used by the Profile tab, Edit Profile and onboarding for a consistent look.
import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius } from '../theme';
import { eduSummary, eduLocation, eduYearRange, typeMeta } from '../data';

const STATUS_COLOR = {
  Completed: colors.success,
  'Currently Studying': colors.accent,
  Discontinued: colors.danger,
};

export default function EducationCard({ entry, onRemove, onEdit }) {
  const e = entry;
  const meta = typeMeta(e.type || e.level);
  const summary = eduSummary(e);
  const years = eduYearRange(e);
  const place = eduLocation(e);

  return (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={[styles.badge, { backgroundColor: meta.color + '18' }]}>
          <Ionicons name={meta.icon} size={20} color={meta.color} />
        </View>
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={styles.title} numberOfLines={1}>{e.name || e.course || e.type}</Text>
          {!!summary && <Text style={styles.sub} numberOfLines={1}>{summary}</Text>}
        </View>
        {onEdit ? (
          <Pressable onPress={onEdit} hitSlop={8} style={styles.trash}>
            <Ionicons name="create-outline" size={18} color={colors.primary} />
          </Pressable>
        ) : null}
        {onRemove ? (
          <Pressable onPress={onRemove} hitSlop={8} style={styles.trash}>
            <Ionicons name="trash-outline" size={18} color={colors.danger} />
          </Pressable>
        ) : null}
      </View>

      {(years || place) && (
        <View style={styles.metaRow}>
          {!!years && (
            <View style={styles.metaItem}>
              <Ionicons name="calendar-outline" size={13} color={colors.muted} />
              <Text style={styles.metaText}>{years}</Text>
            </View>
          )}
          {!!place && (
            <View style={[styles.metaItem, { flex: 1 }]}>
              <Ionicons name="location-outline" size={13} color={colors.muted} />
              <Text style={styles.metaText} numberOfLines={1}>{place}</Text>
            </View>
          )}
        </View>
      )}

      <View style={styles.tagRow}>
        <View style={[styles.tag, { backgroundColor: meta.color + '14', borderColor: meta.color + '33' }]}>
          <Text style={[styles.tagText, { color: meta.color }]}>{e.type || e.level}</Text>
        </View>
        {!!e.status && (
          <View style={[styles.tag, { backgroundColor: (STATUS_COLOR[e.status] || colors.muted) + '14', borderColor: (STATUS_COLOR[e.status] || colors.muted) + '33' }]}>
            <Text style={[styles.tagText, { color: STATUS_COLOR[e.status] || colors.muted }]}>{e.status}</Text>
          </View>
        )}
        {!!e.visibility && e.visibility !== 'Public' && (
          <View style={styles.lockTag}>
            <Ionicons name="lock-closed" size={11} color={colors.muted} />
            <Text style={styles.lockText}>{e.visibility}</Text>
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: 14, marginBottom: 10 },
  topRow: { flexDirection: 'row', alignItems: 'center' },
  badge: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  title: { fontWeight: '800', color: colors.ink, fontSize: 15.5 },
  sub: { color: colors.body, fontSize: 13, marginTop: 2 },
  trash: { padding: 4, marginLeft: 6 },
  metaRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12, marginLeft: 2 },
  metaItem: { flexDirection: 'row', alignItems: 'center', marginRight: 16 },
  metaText: { color: colors.muted, fontSize: 12.5, marginLeft: 5, fontWeight: '600' },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', marginTop: 12 },
  tag: { borderWidth: 1, borderRadius: radius.pill, paddingVertical: 4, paddingHorizontal: 10, marginRight: 6, marginTop: 4 },
  tagText: { fontWeight: '700', fontSize: 12 },
  lockTag: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.bg, borderRadius: radius.pill, paddingVertical: 4, paddingHorizontal: 9, marginTop: 4 },
  lockText: { color: colors.muted, fontSize: 11, fontWeight: '700', marginLeft: 4 },
});
