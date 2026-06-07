import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar, Card, Button, Tag } from '../../src/components/ui';
import { colors, radius } from '../../src/theme';
import { useApp } from '../../src/store';
import { REUNIONS, getUser } from '../../src/data';

export default function Reunion() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const { state, toggleRsvp } = useApp();
  const r = REUNIONS.find((x) => x.id === id);

  if (!r) return <SafeAreaView style={styles.center}><Text>Event not found</Text></SafeAreaView>;

  const going = state.rsvps.includes(r.id);
  const host = getUser(r.host);
  const attendees = [...new Set([...r.going, ...(going ? ['me'] : [])])];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} style={styles.iconCircle}><Ionicons name="chevron-back" size={22} color={colors.ink} /></Pressable>
      </View>

      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 30 }}>
        <View style={styles.banner}>
          <Ionicons name="sparkles" size={28} color="#fff" />
          <Text style={styles.bannerText}>Reunion Event</Text>
        </View>

        <Text style={styles.title}>{r.title}</Text>

        <Card style={{ marginTop: 14 }}>
          <Row icon="calendar" label="Date" value={r.date} />
          <Row icon="location" label="Venue" value={r.venue} />
          <Row icon="cash" label="Contribution" value={`₹${r.fee} per person`} />
          <Row icon="person" label="Hosted by" value={host?.name} last />
        </Card>

        <Text style={styles.section}>About</Text>
        <Text style={styles.desc}>{r.desc}</Text>

        <Text style={styles.section}>Attendees ({attendees.length})</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
          {attendees.map((aid) => {
            const u = aid === 'me' ? state.me : getUser(aid);
            return (
              <View key={aid} style={{ alignItems: 'center', width: 72, marginBottom: 12 }}>
                <Avatar name={u?.name} size={52} />
                <Text style={styles.attName} numberOfLines={1}>{aid === 'me' ? 'You' : u?.name?.split(' ')[0]}</Text>
              </View>
            );
          })}
        </View>
      </ScrollView>

      {/* Sticky RSVP bar */}
      <View style={styles.rsvpBar}>
        <View>
          <Text style={styles.feeLabel}>Contribution</Text>
          <Text style={styles.fee}>₹{r.fee}</Text>
        </View>
        <Button
          title={going ? 'Going ✓ — Cancel' : 'RSVP & Pay'}
          icon={going ? 'checkmark-circle' : 'card'}
          variant={going ? 'success' : 'primary'}
          onPress={() => toggleRsvp(r.id)}
          style={{ flex: 1, marginLeft: 16 }}
        />
      </View>
    </SafeAreaView>
  );
}

function Row({ icon, label, value, last }) {
  return (
    <View style={[styles.infoRow, !last && { borderBottomWidth: 1, borderBottomColor: colors.border }]}>
      <View style={styles.infoIcon}><Ionicons name={icon} size={18} color={colors.primary} /></View>
      <View style={{ marginLeft: 12 }}>
        <Text style={styles.infoLabel}>{label}</Text>
        <Text style={styles.infoValue}>{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  topBar: { paddingHorizontal: 16, paddingTop: 6 },
  iconCircle: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border },
  banner: { height: 120, borderRadius: radius.lg, backgroundColor: colors.purple, alignItems: 'center', justifyContent: 'center' },
  bannerText: { color: '#fff', fontWeight: '800', marginTop: 6, fontSize: 16 },
  title: { fontSize: 24, fontWeight: '900', color: colors.ink, marginTop: 16 },
  infoRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12 },
  infoIcon: { width: 38, height: 38, borderRadius: 11, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  infoLabel: { color: colors.muted, fontSize: 12.5 },
  infoValue: { color: colors.ink, fontWeight: '800', fontSize: 15, marginTop: 1 },
  section: { fontSize: 18, fontWeight: '800', color: colors.ink, marginTop: 22, marginBottom: 10 },
  desc: { color: colors.body, lineHeight: 22, fontSize: 15 },
  attName: { color: colors.body, fontSize: 12, marginTop: 6, fontWeight: '600' },
  rsvpBar: { flexDirection: 'row', alignItems: 'center', padding: 16, backgroundColor: colors.card, borderTopWidth: 1, borderTopColor: colors.border },
  feeLabel: { color: colors.muted, fontSize: 12 },
  fee: { color: colors.ink, fontWeight: '900', fontSize: 22 },
});
