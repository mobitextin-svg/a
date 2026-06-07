import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar, Card, Tag, Button, SectionTitle } from '../../src/components/ui';
import { colors, radius } from '../../src/theme';
import { useApp } from '../../src/store';
import { JOBS, MENTORS, BUSINESSES, getUser } from '../../src/data';

const TABS = ['Jobs', 'Mentorship', 'Business', 'Reunions', 'Groups'];

export default function Alumni() {
  const router = useRouter();
  const { reunions, groups, joined, joinGroup, state, startDM } = useApp();
  const [tab, setTab] = useState('Jobs');

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.head}>
        <Text style={styles.title}>Alumni Network</Text>
        <Text style={styles.sub}>Jobs, mentorship, business & reunions</Text>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabsWrap} contentContainerStyle={{ paddingHorizontal: 20 }}>
        {TABS.map((t) => (
          <Pressable key={t} onPress={() => setTab(t)} style={[styles.tab, tab === t && styles.tabActive]}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>{t}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 8, paddingBottom: 28 }} showsVerticalScrollIndicator={false}>
        {tab === 'Jobs' && JOBS.map((j) => {
          const by = getUser(j.by);
          return (
            <Card key={j.id} style={{ marginBottom: 12 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <View style={styles.jobIcon}><Ionicons name="briefcase" size={20} color={colors.primary} /></View>
                <Tag label={j.type} color={colors.accent} />
              </View>
              <Text style={styles.cardTitle}>{j.title}</Text>
              <Text style={styles.meta}>{j.company} • {j.location}</Text>
              <View style={styles.byRow}>
                <Avatar name={by?.name} size={24} />
                <Text style={styles.byText}>Posted by {by?.name}</Text>
              </View>
              <Button small title="Apply / Refer" variant="soft" icon="paper-plane" style={{ marginTop: 12, alignSelf: 'flex-start' }} onPress={() => router.push(`/user/${j.by}`)} />
            </Card>
          );
        })}

        {tab === 'Mentorship' && MENTORS.map((id) => {
          const m = getUser(id);
          return (
            <Card key={id} style={{ marginBottom: 12, flexDirection: 'row', alignItems: 'center' }}>
              <Avatar name={m.name} size={50} />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.cardTitle}>{m.name}</Text>
                <Text style={styles.meta}>{m.headline}</Text>
                <Tag label="Open to mentor" color={colors.success} icon="ribbon" />
              </View>
              <Button small title="Connect" onPress={() => { const c = startDM(id); router.push(`/chat/${c}`); }} />
            </Card>
          );
        })}

        {tab === 'Business' && BUSINESSES.map((b) => {
          const owner = getUser(b.by);
          return (
            <Card key={b.id} style={{ marginBottom: 12 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <View style={[styles.jobIcon, { backgroundColor: '#fef3c7' }]}><Ionicons name="storefront" size={20} color={colors.gold} /></View>
                <View style={{ marginLeft: 12, flex: 1 }}>
                  <Text style={styles.cardTitle}>{b.name}</Text>
                  <Text style={styles.meta}>{b.category} • {b.city}</Text>
                </View>
              </View>
              <Text style={styles.byText}>Owned by {owner?.name}</Text>
              {!state.premium && <Tag label="Business directory • Premium" color={colors.gold} icon="star" />}
            </Card>
          );
        })}

        {tab === 'Reunions' && reunions.map((r) => (
          <Card key={r.id} style={{ marginBottom: 12 }} onPress={() => router.push(`/reunion/${r.id}`)}>
            <View style={styles.reunionTop}>
              <Ionicons name="calendar" size={18} color={colors.primary} />
              <Text style={styles.reunionDate}>{r.date}</Text>
            </View>
            <Text style={styles.cardTitle}>{r.title}</Text>
            <Text style={styles.meta}><Ionicons name="location" size={13} color={colors.muted} /> {r.venue}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 }}>
              <Tag label={`₹${r.fee} • ${r.going.length} going`} color={colors.accent} />
              <Text style={styles.viewLink}>View & RSVP →</Text>
            </View>
          </Card>
        ))}

        {tab === 'Groups' && groups.map((g) => {
          const isJoined = joined.some((x) => x.id === g.id);
          return (
            <Card key={g.id} style={{ marginBottom: 12, flexDirection: 'row', alignItems: 'center' }}>
              <View style={[styles.groupIcon, { backgroundColor: g.color }]}><Ionicons name="people" size={22} color="#fff" /></View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.cardTitle}>{g.name}</Text>
                <Text style={styles.meta}>{g.institution} • {g.members.length} members</Text>
              </View>
              {isJoined ? (
                <Button small title="Open" variant="soft" onPress={() => router.push(`/group/${g.id}`)} />
              ) : (
                <Button small title="Join" onPress={() => joinGroup(g.id)} />
              )}
            </Card>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  head: { paddingHorizontal: 20, paddingTop: 8 },
  title: { fontSize: 24, fontWeight: '900', color: colors.ink },
  sub: { color: colors.muted, marginTop: 2 },
  tabsWrap: { marginTop: 14, maxHeight: 46, flexGrow: 0 },
  tab: { paddingVertical: 9, paddingHorizontal: 16, borderRadius: radius.pill, backgroundColor: colors.card, borderWidth: 1.5, borderColor: colors.border, marginRight: 8, height: 40 },
  tabActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  tabText: { fontWeight: '700', color: colors.body },
  tabTextActive: { color: '#fff' },
  jobIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontWeight: '800', color: colors.ink, fontSize: 16, marginTop: 8 },
  meta: { color: colors.muted, fontSize: 13.5, marginTop: 3 },
  byRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12 },
  byText: { color: colors.body, fontSize: 13, marginLeft: 8, marginTop: 6 },
  reunionTop: { flexDirection: 'row', alignItems: 'center' },
  reunionDate: { color: colors.primary, fontWeight: '800', marginLeft: 7 },
  viewLink: { color: colors.primary, fontWeight: '800', fontSize: 13.5 },
  groupIcon: { width: 46, height: 46, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
});
